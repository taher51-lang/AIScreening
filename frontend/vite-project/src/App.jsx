import { useState } from "react";
import Landing from "./components/Landing.jsx";
import Interview from "./components/Interview.jsx";
import Summary from "./components/Summary.jsx";

// Simple view-state machine: no router needed for a 3-screen linear flow.
const VIEW = { LANDING: "landing", INTERVIEW: "interview", SUMMARY: "summary" };

export default function App() {
  const [view, setView] = useState(VIEW.LANDING);
  const [sessionId, setSessionId] = useState(null);

  function handleSessionStart(session) {
    setSessionId(session.session_id);
    setView(VIEW.INTERVIEW);
  }

  function handleInterviewComplete() {
    setView(VIEW.SUMMARY);
  }

  return (
    <div className="app-shell">
      {view === VIEW.LANDING && <Landing onSessionStart={handleSessionStart} />}
      {view === VIEW.INTERVIEW && (
        <Interview sessionId={sessionId} onComplete={handleInterviewComplete} />
      )}
      {view === VIEW.SUMMARY && <Summary sessionId={sessionId} />}
    </div>
  );
}