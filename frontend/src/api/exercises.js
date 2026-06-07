const BASE = '/api';

function authHeaders(token) {
  return { Authorization: `Bearer ${token}` };
}

function jsonHeaders(token) {
  return { ...authHeaders(token), 'Content-Type': 'application/json' };
}

// ── Exercises ─────────────────────────────────────────────────────────────────

export async function listExercises(token, schemaId = null) {
  // Fix: was calling /api/schemas/:id/exercises which didn't exist on the backend.
  // Now correctly calls /api/exercises?schema_id=X
  const url = schemaId
    ? `${BASE}/exercises?schema_id=${schemaId}`
    : `${BASE}/exercises`;
  const res = await fetch(url, { headers: authHeaders(token) });
  if (!res.ok) throw new Error('Failed to load exercises');
  return res.json();
}

export async function getExercise(token, exerciseId) {
  const res = await fetch(`${BASE}/exercises/${exerciseId}`, {
    headers: authHeaders(token),
  });
  if (!res.ok) throw new Error('Exercise not found');
  return res.json();
}

export async function createExercise(token, payload) {
  const res = await fetch(`${BASE}/exercises`, {
    method: 'POST',
    headers: jsonHeaders(token),
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail || 'Failed to create exercise');
  }
  return res.json();
}

export async function updateExercise(token, exerciseId, payload) {
  const res = await fetch(`${BASE}/exercises/${exerciseId}`, {
    method: 'PUT',
    headers: jsonHeaders(token),
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail || 'Failed to update exercise');
  }
  return res.json();
}

export async function deleteExercise(token, exerciseId) {
  const res = await fetch(`${BASE}/exercises/${exerciseId}`, {
    method: 'DELETE',
    headers: authHeaders(token),
  });
  if (!res.ok) throw new Error('Failed to delete exercise');
}

// ── Student answers ───────────────────────────────────────────────────────────

export async function submitAnswer(token, exerciseId, answerText) {
  const res = await fetch(`${BASE}/exercises/${exerciseId}/answers`, {
    method: 'POST',
    headers: jsonHeaders(token),
    body: JSON.stringify({ answer: answerText }),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail || 'Failed to submit answer');
  }
  return res.json();
}

export async function getCorrectAnswer(token, exerciseId) {
  const res = await fetch(`${BASE}/exercises/${exerciseId}/correct-answer`, {
    headers: authHeaders(token),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail || 'Failed to load correct answer');
  }
  return res.json();
}

// ── LLM hint endpoints ────────────────────────────────────────────────────────

async function llmCall(token, exerciseId, action) {
  const res = await fetch(`${BASE}/exercises/${exerciseId}/${action}`, {
    method: 'POST',
    headers: authHeaders(token),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail || `LLM call failed: ${action}`);
  }
  return res.json();
}

export const explainError    = (token, id) => llmCall(token, id, 'explain-error');
export const giveHint        = (token, id) => llmCall(token, id, 'give-hint');
export const fixSchema       = (token, id) => llmCall(token, id, 'fix-schema');
export const explainSuccess  = (token, id) => llmCall(token, id, 'explain-success');
