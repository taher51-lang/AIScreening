# AI-Powered Role-Based Candidate Screening System

A system that simulates a structured technical interview where questions are
generated dynamically — grounded in a candidate's resume, their target role,
and a role-specific corpus of textbooks — via a Retrieval-Augmented
Generation (RAG) pipeline.

Built for the AI/ML & Backend Engineering Intern take-home assignment.

---

## 1. What this system does

Per the assignment brief, the system supports the full candidate-entry →
interview → summary flow:

1. **Candidate entry** — a candidate uploads a resume (PDF or plain text)
   and selects a target role.
2. **Resume processing** — the resume is parsed and skills, technologies,
   and domain exposure are extracted.
3. **Context construction** — a topic to test is selected from the role's
   full expected knowledge, and matched against the resume to decide
   question difficulty (see [Difficulty scaling](#difficulty-scaling)
   below).
4. **Knowledge retrieval (RAG)** — the selected topic is turned into a
   natural-language query and used to retrieve grounded, relevant chunks
   from a role-specific vector store built from the assignment's provided
   textbooks.
5. **Question generation** — an LLM generates one interview question at a
   time, grounded strictly in the retrieved material.
6. **Interactive interview** — the candidate answers through the UI; the
   system persists session state and generates the next question only
   after the current one is answered.
7. **Response handling** — every question, its retrieval provenance
   (which book/page/section it came from), and the candidate's answer are
   stored in a structured, queryable form.
8. **Final output** — a structured summary of the session, including an
   LLM-generated overview, strengths, gaps, and the full Q&A transcript.

---

## 2. Tech stack

| Layer | Choice | Why |
|---|---|---|
| Frontend | React (Vite) | Fast to build, no SSR overhead needed for a 3-screen flow |
| Backend | FastAPI | Async-first, Pydantic validation, natural fit for an AI pipeline that calls external APIs |
| Orchestration | LangGraph | The interview flow is a genuine state machine (plan → retrieve → generate); modeling it explicitly beats an implicit chain of function calls |
| Vector store | Chroma | Embedded, persistent, zero extra infrastructure |
| Embeddings | sentence-transformers (local) or Cohere (API) — pluggable | Started with Cohere, switched to local after hitting free-tier rate limits during bulk textbook ingestion; kept both behind one config flag |
| LLM | Groq — `openai/gpt-oss-120b` | Fast inference for iterative generation during development |
| Database | SQLite via SQLModel | Zero setup, sufficient for session-scoped interview data, easy migration path to Postgres later if needed |

---

## 3. System architecture

```
backend/
├── main.py                    # FastAPI app: instantiation, CORS, router registration
├── config.py                  # env-driven settings (pydantic-settings)
├── api/                        # route layer — validation + delegation only, no business logic
│   ├── routes_resume.py        # POST /api/resume/upload, GET /api/resume/roles
│   └── routes_interview.py     # question/answer/summary lifecycle endpoints
├── services/                    # business logic layer
│   ├── resume_service.py        # PDF/text extraction + skill taxonomy matching
│   ├── retrieval_service.py     # topic planning, difficulty scoring, query construction
│   └── session_service.py       # session lifecycle: create → question loop → complete → summary
├── graph/
│   └── interview_graph.py       # LangGraph pipeline: plan_topic -> retrieve -> generate_question
├── core/                          # low-level, domain-agnostic infrastructure
│   ├── embeddings.py              # provider-switchable embedding function (local | cohere)
│   ├── vector_store.py            # Chroma wrapper
│   └── retrieval_strategies.py    # pluggable retrieval: semantic | mmr | hybrid (BM25+semantic)
├── models/
│   ├── db_models.py               # SQLModel ORM tables (persistence shape)
│   └── schemas.py                 # Pydantic API request/response shapes (API contract)
├── db/
│   └── database.py                 # engine, session dependency, init_db()
└── ingestion/
    ├── ingest.py                   # one-off batch ingestion script (run once, not on request path)
    ├── loaders.py                  # streaming PyMuPDF extraction + section-title detection
    ├── role_topics.py              # role -> book -> topic mapping (grounded in real TOCs)
    └── source_books/               # the provided textbook PDFs

frontend/
├── src/
│   ├── App.jsx                     # 3-screen view-state machine
│   ├── api.js                      # API client matching backend schemas exactly
│   └── components/
│       ├── Landing.jsx              # role selection + resume upload
│       ├── Interview.jsx            # question/answer loop
│       └── Summary.jsx              # insights + full transcript
```

### Modularity, concretely

This isn't split into folders for appearance — each boundary reflects a real
separation of concerns the assignment explicitly asks for:

- **API routes never contain business logic.** A route validates input,
  calls a service function, and returns the response. All actual decision
  logic lives in `services/`.
- **Pydantic schemas (`models/schemas.py`) are separate from ORM models
  (`models/db_models.py`)**, even where fields overlap — the API contract
  and the persistence shape are allowed to evolve independently.
- **`graph/interview_graph.py` never touches the database.** It's a pure
  function: `(role, resume context, sequence_number) -> generated
  question`. `session_service.py` is solely responsible for persistence.
  This keeps "orchestrating the AI/ML pipeline" and "interfacing with
  storage systems" — two responsibilities the assignment lists separately
  — genuinely separate in code, not just nominally.
- **`core/` holds domain-agnostic infrastructure** (Chroma access,
  embedding functions, retrieval strategies) with zero awareness of
  resumes, sessions, or interviews. **`services/`** holds the
  domain-aware logic that uses `core/` to do something specific. This
  mirrors real backend layering, not an arbitrary file split.
- **Configuration is entirely environment-variable driven**
  (`config.py`, via `pydantic-settings`) — no hardcoded API keys, paths,
  or model names anywhere in the codebase.

---

## 4. The AI/ML pipeline (core focus)

### 4.1 Knowledge ingestion

- PDFs are loaded via **PyMuPDF**, chosen over `pypdf`-based loaders for
  more reliable text-ordering on dense academic textbooks (multi-column
  sections, math notation, headers/footers).
- Loading is **streaming** (`iter_pdf_pages` is a generator), so peak
  memory during ingestion is bounded by batch size, not by the size of
  the largest textbook.
- Each page's likely **section heading is detected via a font-size
  heuristic** (any span notably larger than the page's median font size,
  short enough to be a heading, not a page number) and carried forward as
  running state until the next heading is found.
- Chunking uses **`RecursiveCharacterTextSplitter`** (chunk size ~900
  chars, ~20% overlap, splitting on paragraph boundaries first) to avoid
  cutting concept explanations mid-thought.
- Every chunk is tagged with metadata: **`{source_book, page_number,
  section_title, role_tag}`** — this is what gives the system
  traceability (assignment section 7.5) of exactly which page and section
  a generated question came from.
- A book that's relevant to more than one role gets one row inserted per
  role, so retrieval filtering by role stays simple and exact.
- Ingestion is a **one-off batch script** (`ingest.py`), run manually at
  setup time — deliberately kept off the live request path so PDF
  processing never adds latency to an interview session.

### 4.2 Role scoping, grounded in the actual provided corpus

The assignment explicitly requires using the provided textbooks as the
primary knowledge source, not generic queries. Role topic checklists were
built directly from each book's real table of contents — not invented —
and roles were scoped to what the provided corpus actually covers:

| Role | Books used | Topics (drawn from real chapters) |
|---|---|---|
| `ai_ml_engineer` | *Machine Learning* (Tom Mitchell), *Machine Learning for Absolute Beginners* | concept learning, decision trees, neural networks, model evaluation, Bayesian learning, computational learning theory, instance-based learning, genetic algorithms, reinforcement learning |
| `data_scientist_applied_ml` | *Introduction to Machine Learning with Python*, *Master Machine Learning Algorithms* (Brownlee) | applied supervised learning, feature engineering, model selection in practice, algorithm walkthroughs, data preprocessing |
| `advanced_ml_researcher` | *Pattern Recognition and Machine Learning* (Bishop), *Artificial Intelligence, Machine Learning, and Deep Learning* | probabilistic graphical models, pattern recognition theory, advanced neural architectures, Bayesian inference |

(Note: the Hundred-Page ML Book listed in the original assignment
resources was not available in this submission's source materials, so
`ai_ml_engineer`'s topic list was scoped only to content genuinely present
in Mitchell's book and the Beginners text — no topic references content
outside the actual ingested corpus.)

### 4.3 Retrieval mechanism

**Query construction** is not a bare topic string — it's shaped
differently depending on difficulty:
- *Advanced* (topic matches a resume skill): `"<topic>, with practical
  application and implementation details relevant to <matched skill>"`
- *Foundational* (no resume match): `"core concepts and theoretical
  foundations of <topic>"`

**Retrieval strategy is pluggable**, switchable via a single env var
(`RETRIEVAL_STRATEGY`) with zero code changes required elsewhere:

- **`semantic`** — plain top-k cosine similarity.
- **`mmr`** *(default)* — Maximal Marginal Relevance: fetches a larger
  candidate pool, then greedily selects results that are relevant *but
  diverse from each other*. Chosen as the default because this corpus is
  domain-homogeneous — a topic term like "Bayesian learning" is repeated
  throughout an entire textbook chapter, so plain top-k similarity tends
  to return several near-duplicate chunks restating the same paragraph.
  MMR avoids this redundancy, giving the LLM richer, more varied grounding
  context.
- **`hybrid`** — BM25 (sparse, exact-term) + semantic (dense), fused via
  LangChain's `EnsembleRetriever`. Included for completeness and
  experimentation, but not the default: BM25 earns its keep when query
  terms are *rare* in a corpus, and that's not the case here — topic terms
  are locally dense (mentioned many times within their own chapter), so
  exact-term frequency isn't a strong discriminating signal for this
  specific corpus.

All chunks are retrieved filtered by `role_tag`, so retrieval never
crosses into content ingested for a different role.

### 4.4 Question generation

Retrieved chunks (with their book/page/section provenance) are formatted
into a numbered reference block and passed to the LLM (Groq,
`openai/gpt-oss-120b`) alongside the topic, difficulty, and matched resume
skill. The system prompt explicitly constrains the model to:
- output only the question text (no preamble, no answer),
- stay grounded in the provided reference material,
- match the requested difficulty,
- avoid generic/templated phrasing.

### 4.5 Resume utilisation & difficulty scaling

The resume's extracted skills influence the interview in one specific,
well-defined way: **difficulty, not topic eligibility.**

Topics are drawn from the role's *full* expected-knowledge checklist
(shuffled, seeded by `session_id` for per-session reproducibility) —
**not** sampled from the candidate's claimed skills. This is a deliberate
design choice: sampling topics only from what a resume mentions would mean
a thin resume produces an easy interview by never touching unlisted
topics, and a padded resume produces a harder one by accident — neither is
a fair assessment. Every candidate for a given role is tested against the
same topic coverage; only the *difficulty* of each topic is personalized:

- If the picked topic overlaps with something in the resume's extracted
  skills/domains → **`advanced`** (deeper, applied question, referencing
  the matched skill).
- If it doesn't → **`foundational`** (baseline conceptual question).

This is currently **resume-static**: difficulty is decided once, upfront,
from the resume alone, and does not change based on how well the
candidate answers during the session. True behavioral adaptivity
(adjusting difficulty based on answer quality) was considered and
deliberately scoped out — see [Assumptions & out of scope](#6-assumptions--out-of-scope).

### 4.6 Output structuring & traceability

Every `Question` row persists its full retrieval provenance
(`retrieved_context`: a list of `{source_book, page_number, section_title,
chunk_text}`), so it's possible to trace exactly which pages of which
book justified any generated question — satisfying the assignment's
traceability requirement without needing a separate audit log.

The pipeline is: **Context (retrieval) → Question (generation) → Answer
(candidate) → Storage (SQLite)**, with each stage's output persisted
before the next stage runs.

---

## 5. Data layer

SQLite via SQLModel (doubles as ORM model + Pydantic-style schema).

| Table | Purpose |
|---|---|
| `Session` | One candidate session: role, resume filename/raw text, extracted skills (JSON), status |
| `Question` | One generated question: topic, difficulty, question text, full retrieval provenance (JSON) |
| `Answer` | One candidate response, one-to-one with `Question` (separate table, since a question can exist in an "asked but not yet answered" state) |
| `SessionSummary` | Final LLM-generated summary + structured insights (strengths/gaps), computed once and cached |

Sessions are identified by a generated UUID, not a user account — see
below.

---

## 6. Assumptions & out of scope

- **No authentication.** The assignment brief never mentions user accounts
  or login; sessions are scoped by a generated `session_id` (UUID), which
  satisfies "session continuity" and "structured records" without adding
  infrastructure that has no grading signal in the brief and would add
  friction to the demo.
- **Difficulty is resume-static, not behaviorally adaptive.** Difficulty
  is set once from the resume and doesn't change based on answer quality
  during the session. True adaptivity (judging each answer and adjusting
  the next question's difficulty accordingly) is a natural extension but
  was scoped out to fit the 48-hour window.
- **The Hundred-Page ML Book** referenced in the original assignment
  resource list was not available in this submission's source materials;
  `ai_ml_engineer`'s topic checklist was scoped to only the content
  actually ingested (Mitchell + Absolute Beginners), per the requirement
  to ground retrieval in the actual provided corpus rather than inventing
  topics with no backing content.
- **Resume-to-topic matching is keyword/taxonomy-based, not LLM-based.**
  This was a deliberate choice to keep resume processing fast, free, and
  independent of the (separately-chosen) LLM provider. It means
  conceptually-related terms that don't share vocabulary (e.g. "PyTorch"
  vs. "neural networks") aren't automatically linked unless the taxonomy
  encodes that relationship. Documented as a known limitation, not a
  silent gap.

---

## 7. Evaluation

Retrieval and generation quality were evaluated with LangSmith:

- **Retrieval score: 0.84**
- **LLM (generation) score:** also strong, evaluated qualitatively

on top of the default MMR retrieval strategy.

---

## 8. Creativity & extensions beyond baseline

- **Pluggable retrieval strategy** (semantic / MMR / hybrid) behind one
  interface, switchable via a single env var — built specifically to A/B
  test retrieval quality on this corpus rather than committing to one
  strategy upfront.
- **Provider-switchable embeddings** (local sentence-transformers vs.
  Cohere API) behind one factory function, so a rate-limit or
  disk-space constraint on one provider doesn't require touching
  ingestion or retrieval code.
- **Resume-driven difficulty scaling**, grounded in a fixed role-topic
  checklist rather than resume-only sampling, for a fairer per-role
  assessment (see section 4.5).
- **Full retrieval traceability** persisted per question (book, page,
  section), enabling an audit trail from generated question back to
  source material.

---

## 9. Setup & running

### Prerequisites
- Python 3.11+, Node 18+
- A Groq API key
- Either a Cohere API key, or local disk space for
  `sentence-transformers`/`torch` (see `EMBEDDING_PROVIDER` below)

### Backend

```bash
cd backend
pip install -r requirements.txt
```

Create a `.env` file in `backend/`:

```
GROQ_API_KEY=your_groq_key
LLM_MODEL_NAME=openai/gpt-oss-120b

EMBEDDING_PROVIDER=local          # or "cohere"
COHERE_API_KEY=your_cohere_key    # only needed if EMBEDDING_PROVIDER=cohere

DATABASE_URL=sqlite:///./interview.db
CHROMA_PERSIST_DIR=./chroma_db
RETRIEVAL_STRATEGY=mmr            # semantic | mmr | hybrid
```

Place the provided textbook PDFs into `backend/ingestion/source_books/`
(exact filenames must match `backend/ingestion/role_topics.py`), then run
ingestion once:

```bash
python -m backend.ingestion.ingest
```

Start the API:

```bash
uvicorn backend.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Visit `http://localhost:5173` (the dev server proxies `/api` requests to
`http://localhost:8000`).

---

## 10. Possible future improvements

- Behavioral difficulty adaptation based on answer quality, not just the
  resume snapshot.
- LLM-based resume extraction as an alternative to keyword taxonomy
  matching, for better handling of conceptually-related but
  differently-worded skills.
- A `RolePlan` persisted per session (currently recomputed deterministically
  on the fly) if richer topic-sequencing logic is added later.
- Streaming question generation to the frontend for perceived latency
  reduction.