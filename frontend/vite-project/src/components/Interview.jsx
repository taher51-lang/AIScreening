import { useEffect, useState } from "react";
import { getCurrentQuestion, submitAnswer } from "../api.js";

// Mirrors backend Settings.questions_per_session default (config.py).
// Update here if that default changes.
const TOTAL_QUESTIONS = 6;

export default function Interview({ sessionId, onComplete }) {
  const [question, setQuestion] = useState(null);
  const [answer, setAnswer] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadCurrentQuestion();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function loadCurrentQuestion() {
    setLoading(true);
    setError(null);
    getCurrentQuestion(sessionId)
      .then((q) => {
        setQuestion(q);
        setAnswer("");
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (!answer.trim() || !question) return;

    setSubmitting(true);
    setError(null);
    try {
      const result = await submitAnswer(sessionId, question.question_id, answer);
      if (result.session_status === "completed") {
        onComplete();
      } else {
        setQuestion(result.next_question);
        setAnswer("");
        setSubmitting(false);
      }
    } catch (err) {
      setError(err.message);
      setSubmitting(false);
    }
  }

  const progressPct = question
    ? Math.min(100, (question.sequence_number / TOTAL_QUESTIONS) * 100)
    : 0;

  return (
    <>
      <header className="masthead">
        <p className="masthead-eyebrow">Technical screening — in progress</p>
        <h1>Interview session</h1>
      </header>

      {question && (
        <>
          <div className="progress-row">
            <span>
              Question {question.sequence_number} of {TOTAL_QUESTIONS}
            </span>
          </div>
          <div className="progress-track">
            <div className="progress-fill" style={{ width: `${progressPct}%` }} />
          </div>
        </>
      )}

      <div className="card">
        {loading && (
          <div className="loading-state">
            <div className="spinner" />
            <span>Preparing your next question…</span>
          </div>
        )}

        {!loading && question && (
          <form onSubmit={handleSubmit}>
            <div className="tag-row">
              <span className="tag tag-topic">{question.topic}</span>
              {question.difficulty && (
                <span className={`tag tag-difficulty-${question.difficulty}`}>
                  {question.difficulty}
                </span>
              )}
            </div>

            <p className="question-text">{question.question_text}</p>

            <textarea
              className="answer-textarea"
              placeholder="Type your answer here…"
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              disabled={submitting}
              autoFocus
            />

            <button
              type="submit"
              className="btn-primary"
              disabled={!answer.trim() || submitting}
            >
              {submitting ? "Submitting…" : "Submit answer"}
            </button>

            {error && <div className="error-banner">{error}</div>}
          </form>
        )}

        {!loading && !question && error && (
          <div className="error-banner">{error}</div>
        )}
      </div>
    </>
  );
}