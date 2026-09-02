"""
Resume processing: raw text extraction (PDF or plain text) + structured
data extraction (skills / technologies / domains).

Extraction strategy: keyword/taxonomy matching against a curated ML-role
vocabulary, chosen deliberately over an LLM call here so this works today
with zero dependency on the (still-undecided) LLM provider. This is a
clear extension point -- swap `extract_structured_data` for an LLM-based
version later without touching the route or the rest of the pipeline;
the function signature (raw_text -> dict) stays the same either way.
"""

import io
import re

import fitz  # PyMuPDF
from fastapi import UploadFile

# Curated vocabulary, scoped to the roles this system actually supports
# (ai_ml_engineer, data_scientist_applied_ml, advanced_ml_researcher) --
# matches the domains covered by the ingested textbooks, not a generic
# "all of software engineering" list.
SKILL_TAXONOMY: dict[str, list[str]] = {
    "languages": ["python", "r", "sql", "c++", "java", "scala"],
    "ml_frameworks": [
        "scikit-learn", "sklearn", "tensorflow", "pytorch", "keras",
        "xgboost", "lightgbm", "huggingface", "transformers",
    ],
    "data_tools": ["pandas", "numpy", "spark", "hadoop", "airflow"],
    "ml_concepts": [
        "supervised learning", "unsupervised learning", "reinforcement learning",
        "neural network", "deep learning", "decision tree", "random forest",
        "bayesian", "gradient descent", "feature engineering", "clustering",
        "dimensionality reduction", "nlp", "natural language processing",
        "computer vision", "recommendation system", "time series",
    ],
    "infra": ["docker", "kubernetes", "aws", "gcp", "azure", "mlflow", "fastapi", "flask"],
}

# Flat lookup: normalized keyword -> category, built once at import time.
_KEYWORD_TO_CATEGORY = {
    kw.lower(): category
    for category, keywords in SKILL_TAXONOMY.items()
    for kw in keywords
}


def extract_text(file_bytes: bytes, content_type: str, filename: str) -> str:
    """
    Extract raw text from an uploaded resume, PDF or plain text.

    PDFs go through PyMuPDF for consistency with the ingestion pipeline
    (same extraction quality/behavior). Plain text is decoded directly.
    """
    is_pdf = content_type == "application/pdf" or filename.lower().endswith(".pdf")

    if is_pdf:
        doc = fitz.open(stream=io.BytesIO(file_bytes), filetype="pdf")
        try:
            return "\n".join(page.get_text("text") for page in doc)
        finally:
            doc.close()

    # Plain text (.txt) -- try utf-8, fall back to latin-1 for safety.
    try:
        return file_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return file_bytes.decode("latin-1")


def extract_structured_data(raw_text: str) -> dict:
    """
    Returns: {"skills": [...], "technologies": [...], "domains": [...],
              "matched_categories": {category: [keywords]}}

    "skills"/"technologies"/"domains" are a simplified flattening for
    downstream consumers (question generation prompt, difficulty scoring);
    "matched_categories" preserves the full taxonomy breakdown for
    anything that needs finer granularity later.
    """
    text_lower = raw_text.lower()

    matched_categories: dict[str, list[str]] = {}
    for keyword, category in _KEYWORD_TO_CATEGORY.items():
        # Word-boundary match to avoid "r" matching inside "for" etc.
        pattern = r"(?<![a-zA-Z0-9])" + re.escape(keyword) + r"(?![a-zA-Z0-9])"
        if re.search(pattern, text_lower):
            matched_categories.setdefault(category, []).append(keyword)

    technologies = (
        matched_categories.get("languages", [])
        + matched_categories.get("ml_frameworks", [])
        + matched_categories.get("data_tools", [])
        + matched_categories.get("infra", [])
    )
    domains = matched_categories.get("ml_concepts", [])

    return {
        "skills": sorted(set(technologies + domains)),
        "technologies": sorted(set(technologies)),
        "domains": sorted(set(domains)),
        "matched_categories": matched_categories,
    }


async def process_resume_upload(file: UploadFile) -> tuple[str, dict]:
    """
    Convenience wrapper used by the route: reads the UploadFile, extracts
    raw text, then structured data. Returns (raw_text, extracted_skills).
    """
    file_bytes = await file.read()
    raw_text = extract_text(file_bytes, file.content_type, file.filename or "")
    extracted_skills = extract_structured_data(raw_text)
    return raw_text, extracted_skills