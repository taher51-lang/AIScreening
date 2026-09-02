import { useEffect, useState } from "react";
import { getSummary } from "../api.js";

export default function Summary({ sessionId }) {
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    getSummary(sessionId)
      .then((data) => {
        setSummary(data);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, [sessionId]);

  return (
    <>
      <header className="masthead">
        <p className="masthead-eyebrow">Technical screening — complete</p>
        <h1>Interview summary</h1>
      </header>

      <div className="card">
        {loading && (
          <div className="loading-state">
            <div className="spinner" />
            <span>Assembling your summary…</span>
          </div>
        )}

        {error && <div className="error-banner">{error}</div>}

        {summary && (
          <>
            <p className="summary-text">{summary.summary_text}</p>

            <div className="insight-columns">
              <div className="insight-block">
                <h3>Strengths</h3>
                <ul>
                  {(summary.insights.strengths || []).map((s, i) => (
                    <li key={i}>{s}</li>
                  ))}
                  {(summary.insights.strengths || []).length === 0 && (
                    <li>None noted</li>
                  )}
                </ul>
              </div>
              <div className="insight-block">
                <h3>Areas to revisit</h3>
                <ul>
                  {(summary.insights.gaps || []).map((g, i) => (
                    <li key={i}>{g}</li>
                  ))}
                  {(summary.insights.gaps || []).length === 0 && <li>None noted</li>}
                </ul>
              </div>
            </div>

            <div className="transcript">
              <h3>Full transcript</h3>
              {summary.questions_and_answers.map((qa, i) => (
                <div className="transcript-item" key={i}>
                  <p className="transcript-question">
                    {i + 1}. {qa.question_text}
                  </p>
                  <p className="transcript-answer">
                    {qa.answer_text || "No answer recorded"}
                  </p>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </>
  );
}