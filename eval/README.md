# 🧪 RAG Evaluation Suite (`eval/`)

This directory contains a standalone evaluation harness for testing, inspecting, and auditing the modular RAG pipeline without modifying backend API code.

## 📂 Structure

- **`sample_resumes.py`**: Sample candidate resume skill profiles for target roles (`ai_ml_engineer`, `data_scientist_applied_ml`, `advanced_ml_researcher`).
- **`evaluate_rag.py`**: Evaluation script that executes each stage of the modular pipeline:
  1. **Parsed Resume Input** (Skills, Domains)
  2. **Topic Planning & Difficulty Determination**
  3. **Query Construction**
  4. **ChromaDB Vector Store Retrieval** (Exact chunks, source book, page, section, text)
  5. **Question Generation**
- **`eval_report.md`**: Generated markdown report containing the complete trace of all evaluation runs.

## 🚀 Running the Evaluation

To run the evaluation suite locally:

```bash
python eval/evaluate_rag.py
```

This will output the live execution steps to standard output and update `eval/eval_report.md`.
