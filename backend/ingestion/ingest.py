"""
One-off batch ingestion script. Run manually at setup time, NOT on the
live request path (avoids PDF-processing latency during interviews):

    python -m backend.ingestion.ingest

For each book referenced in ROLE_TOPICS:
  1. Load pages via PyMuPDF (loaders.py) -- text + best-guess section title.
  2. Chunk each page's text with RecursiveCharacterTextSplitter.
  3. Attach metadata: {source_book, page_number, section_title, role_tag}.
     A book can map to >1 role, so a chunk gets one row inserted per role
     that references that book (keeps retrieval filtering by role simple
     and exact, at the cost of some duplicated storage -- an acceptable
     tradeoff for a 48-hour build with a handful of PDFs).
  4. Embed + upsert into the persistent Chroma collection.
"""

import os
import sys
import uuid

from langchain_text_splitters import RecursiveCharacterTextSplitter

from backend.config import get_settings
from backend.core.vector_store import get_vector_store
from backend.ingestion.loaders import iter_pdf_pages
from backend.ingestion.role_topics import ROLE_TOPICS, all_book_filenames, role_for_book

SOURCE_BOOKS_DIR = os.path.join(os.path.dirname(__file__), "source_books")

CHUNK_SIZE = 900
CHUNK_OVERLAP = 175


def get_default_embedding_function():
    """
    Local sentence-transformers embeddings -- no API key required, so
    ingestion is unblocked regardless of which LLM provider is chosen
    later for question generation. Swap this out in config.py if you
    later decide to embed via an API provider instead.
    """
    from langchain_huggingface import HuggingFaceEmbeddings

    settings = get_settings()
    return HuggingFaceEmbeddings(model_name=settings.embedding_model_name)


def build_splitter() -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )


BATCH_SIZE = 100


def _flush(vector_store, texts: list, metadatas: list, ids: list) -> None:
    if texts:
        vector_store.add_texts(texts=texts, metadatas=metadatas, ids=ids)


def ingest_book(book_filename: str, splitter, vector_store) -> int:
    """
    Streams pages -> chunks -> Chroma writes, flushing every BATCH_SIZE
    chunk-role rows instead of accumulating the whole book's chunks in
    memory first. Peak memory is O(batch_size), not O(book size).
    """
    path = os.path.join(SOURCE_BOOKS_DIR, book_filename)
    if not os.path.exists(path):
        print(f"  [skip] {book_filename} not found in {SOURCE_BOOKS_DIR}")
        return 0

    roles_for_this_book = role_for_book(book_filename)

    texts, metadatas, ids = [], [], []
    total = 0

    for page in iter_pdf_pages(path):
        if not page.text.strip():
            continue
        for chunk in splitter.split_text(page.text):
            if not chunk.strip():
                continue
            for role in roles_for_this_book:
                texts.append(chunk)
                metadatas.append(
                    {
                        "source_book": book_filename,
                        "page_number": page.page_number,
                        "section_title": page.section_title or "unknown",
                        "role_tag": role,
                    }
                )
                ids.append(str(uuid.uuid4()))

                if len(texts) >= BATCH_SIZE:
                    _flush(vector_store, texts, metadatas, ids)
                    total += len(texts)
                    texts, metadatas, ids = [], [], []

    # flush any remainder smaller than BATCH_SIZE
    _flush(vector_store, texts, metadatas, ids)
    total += len(texts)

    return total


def main():
    settings = get_settings()
    print(f"Persisting to: {settings.chroma_persist_dir}")

    if not os.path.isdir(SOURCE_BOOKS_DIR):
        print(f"ERROR: expected source books at {SOURCE_BOOKS_DIR}")
        print(f"Expected filenames: {all_book_filenames()}")
        sys.exit(1)

    embedding_fn = get_default_embedding_function()
    vector_store = get_vector_store(embedding_fn)
    splitter = build_splitter()

    total_chunks = 0
    for book_filename in all_book_filenames():
        print(f"Ingesting {book_filename} ...")
        n = ingest_book(book_filename, splitter, vector_store)
        print(f"  -> {n} chunk-role rows added")
        total_chunks += n

    print(f"Done. Total chunk-role rows ingested: {total_chunks}")


if __name__ == "__main__":
    main()