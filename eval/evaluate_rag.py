"""
RAG Evaluation Harness.

Runs evaluation tests on the modular pipeline (Resume Parsing -> Topic Planning -> Retrieval -> Question Generation).
Displays step-by-step inputs, query transformations, retrieved ChromaDB chunks, and final generated questions.
"""

import sys
import json
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from eval.sample_resumes import SAMPLE_RESUMES
from backend.services.retrieval_service import plan_topic, build_query, retrieve_chunks
from backend.graph import interview_graph


def run_evaluation(num_questions_per_role: int = 2, output_report_path: str = "eval/eval_report.md"):
    print("=" * 80)
    print("🚀 RUNNING RAG PIPELINE EVALUATION HARNESS")
    print("=" * 80)

    report_lines = [
        "# 🧪 RAG Pipeline Evaluation Report\n",
        "This report details the exact data flow through the modular RAG pipeline: ",
        "**Parsed Resume Skills -> Topic Planning -> Query Construction -> ChromaDB Retrieved Chunks -> Generated Question**.\n",
        "---\n"
    ]

    for role, sample_data in SAMPLE_RESUMES.items():
        extracted_skills = sample_data["extracted_skills"]
        session_id = f"eval-session-{role.lower().replace(' ', '-')}"

        print(f"\n📋 EVALUATING ROLE: {role}")
        print(f"   Parsed Resume Skills: {extracted_skills['skills']}")

        report_lines.append(f"## Role: {role}\n")
        report_lines.append(f"### 📥 Input Parsed Resume\n")
        report_lines.append(f"- **Skills**: `{', '.join(extracted_skills['skills'])}`")
        report_lines.append(f"- **Domains**: `{', '.join(extracted_skills['domains'])}`")
        report_lines.append(f"- **Experience Level**: `{extracted_skills['experience_level']}`\n")

        for seq in range(1, num_questions_per_role + 1):
            print(f"\n   --------------------------------------------------")
            print(f"   Question Sequence #{seq}")

            # 1. Topic Planning
            topic_plan = plan_topic(
                role=role,
                extracted_skills=extracted_skills,
                session_id=session_id,
                sequence_number=seq
            )

            # 2. Query Building
            query = build_query(topic_plan)

            # 3. Vector Store Retrieval
            chunks = retrieve_chunks(topic_plan, role=role)

            # 4. Question Generation
            question_data = interview_graph.generate_question(
                role=role,
                extracted_skills=extracted_skills,
                session_id=session_id,
                sequence_number=seq
            )

            print(f"   🎯 Topic: {topic_plan.topic} | Difficulty: {topic_plan.difficulty} | Matched Skill: {topic_plan.matched_skill}")
            print(f"   🔍 Built Query: '{query}'")
            print(f"   📚 Chunks Retrieved: {len(chunks)}")
            print(f"   ❓ Generated Question:\n      {question_data['question_text']}")

            report_lines.append(f"### Question #{seq}\n")
            report_lines.append(f"- **Planned Topic**: `{topic_plan.topic}`")
            report_lines.append(f"- **Difficulty**: `{topic_plan.difficulty}` (Justified by matched skill: `{topic_plan.matched_skill}`)")
            report_lines.append(f"- **Built Query**: `\"{query}\"`\n")

            report_lines.append("#### 📚 Retrieved Grounding Chunks (ChromaDB)\n")
            if chunks:
                for idx, chunk in enumerate(chunks, 1):
                    report_lines.append(
                        f"{idx}. **Source**: {chunk.source_book} (p. {chunk.page_number}, section: *{chunk.section_title}*)\n"
                        f"   ```text\n   {chunk.text[:250].strip()}...\n   ```\n"
                    )
            else:
                report_lines.append("*No grounding chunks retrieved from vector store.*\n")

            report_lines.append("#### ❓ Final Generated Question\n")
            report_lines.append(f"> {question_data['question_text']}\n")
            report_lines.append("---\n")

    # Write Markdown Report
    report_file = ROOT_DIR / output_report_path
    report_file.parent.mkdir(parents=True, exist_ok=True)
    with open(report_file, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))

    print("\n" + "=" * 80)
    print(f"✅ EVALUATION COMPLETE! Detailed report saved to: {report_file}")
    print("=" * 80)


if __name__ == "__main__":
    run_evaluation(num_questions_per_role=2)
