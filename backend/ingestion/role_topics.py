"""
Role -> book -> topic mapping.

This is NOT new content -- it's a thin scaffold built from each book's own
table of contents, used to (a) tag chunks with metadata at ingestion time
and (b) construct retrieval queries later. Book filenames are expected to
live in `backend/ingestion/source_books/`.
"""

ROLE_TOPICS = {
    "ai_ml_engineer": {
        "books": [
            "MachineLearningTomMitchell.pdf",
            "Machine Learning For Absolute Beginners.pdf",
        ],
        "topics": [
            "concept learning and hypothesis space",
            "decision tree learning",
            "artificial neural networks",
            "evaluating hypotheses and model evaluation",
            "bayesian learning",
            "computational learning theory",
            "instance-based learning",
            "genetic algorithms",
            "reinforcement learning",
        ],
    },
    "data_scientist_applied_ml": {
        "books": [
            "Introduction to Machine Learning with Python ( PDFDrive.com )-min.pdf",
            "Master Machine Learning Algorithms - Discover how they work and Implement Them From Scratch by Jason Brownlee (z-lib.org).pdf",
        ],
        "topics": [
            "applied supervised learning workflows",
            "feature engineering",
            "model selection and evaluation in practice",
            "algorithm implementation walkthroughs",
            "data preprocessing",
        ],
    },
    "advanced_ml_researcher": {
        "books": [
            "Bishop-Pattern-Recognition-and-Machine-Learning-2006.pdf",
            "Artificial Intelligence, Machine Learning, and Deep Learning.pdf",
        ],
        "topics": [
            "probabilistic graphical models",
            "pattern recognition theory",
            "advanced neural network architectures",
            "bayesian inference",
        ],
    },
}


def all_book_filenames() -> list[str]:
    seen = set()
    for role_config in ROLE_TOPICS.values():
        for book in role_config["books"]:
            seen.add(book)
    return sorted(seen)


def role_for_book(book_filename: str) -> list[str]:
    """A book may be shared across roles in principle; return all roles that use it."""
    return [
        role
        for role, config in ROLE_TOPICS.items()
        if book_filename in config["books"]
    ]