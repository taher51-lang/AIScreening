const BASE = "/api";

async function handleResponse(res) {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      // response wasn't JSON -- fall back to statusText
    }
    throw new Error(detail);
  }
  return res.json();
}

export async function fetchRoles() {
  const res = await fetch(`${BASE}/resume/roles`);
  return handleResponse(res); // RoleOption[]
}

export async function uploadResume(role, file) {
  const formData = new FormData();
  formData.append("role", role);
  formData.append("file", file);
  const res = await fetch(`${BASE}/resume/upload`, {
    method: "POST",
    body: formData,
  });
  return handleResponse(res); // SessionCreateResponse
}

export async function getCurrentQuestion(sessionId) {
  const res = await fetch(`${BASE}/interview/${sessionId}/current-question`);
  return handleResponse(res); // QuestionResponse
}

export async function submitAnswer(sessionId, questionId, answerText) {
  const res = await fetch(`${BASE}/interview/${sessionId}/answer`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question_id: questionId, answer_text: answerText }),
  });
  return handleResponse(res); // AnswerSubmitResponse
}

export async function getSummary(sessionId) {
  const res = await fetch(`${BASE}/interview/${sessionId}/summary`);
  return handleResponse(res); // SessionSummaryResponse
}