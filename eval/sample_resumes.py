"""
Sample candidate profiles / parsed resumes for evaluation.
Includes technical skill sets across supported target roles in backend/ingestion/role_topics.py.
"""

SAMPLE_RESUMES = {
    "ai_ml_engineer": {
        "display_name": "AI / ML Engineer",
        "raw_text": """
        Senior ML Engineer with 4 years of experience building neural networks, PyTorch pipelines, and reinforcement learning agents.
        Proficient in back-propagation, gradient descent, deep learning architectures, CNNs, transformers, and model optimization.
        Experienced with hyperparameter tuning, loss functions, and deploying ML models to production.
        """,
        "extracted_skills": {
            "skills": [
                "pytorch",
                "neural networks",
                "back-propagation",
                "deep learning",
                "reinforcement learning",
                "transformers",
                "gradient descent",
                "model optimization"
            ],
            "domains": ["machine learning", "deep learning", "artificial intelligence"],
            "experience_level": "mid-senior"
        }
    },
    "data_scientist_applied_ml": {
        "display_name": "Data Scientist (Applied ML)",
        "raw_text": """
        Data Scientist specializing in statistical modeling, hypothesis testing, linear regression, decision trees, and exploratory data analysis.
        Skilled in Python, pandas, scikit-learn, feature engineering, and evaluating model metrics (precision, recall, ROC-AUC).
        """,
        "extracted_skills": {
            "skills": [
                "statistical modeling",
                "linear regression",
                "decision trees",
                "scikit-learn",
                "feature engineering",
                "hypothesis testing",
                "pandas"
            ],
            "domains": ["data science", "statistics", "predictive analytics"],
            "experience_level": "mid"
        }
    },
    "advanced_ml_researcher": {
        "display_name": "Advanced ML Researcher",
        "raw_text": """
        Machine Learning Researcher focusing on probabilistic graphical models, pattern recognition theory, Bayesian inference, and deep learning architectures.
        Experienced in writing research papers, deriving mathematical proofs, and developing novel deep learning algorithms.
        """,
        "extracted_skills": {
            "skills": [
                "probabilistic graphical models",
                "pattern recognition theory",
                "bayesian inference",
                "deep learning",
                "mathematical proofs"
            ],
            "domains": ["machine learning research", "pattern recognition"],
            "experience_level": "senior"
        }
    }
}
