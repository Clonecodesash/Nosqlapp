const BASE = '/api';

function authHeaders(token) {
  return { Authorization: `Bearer ${token}` };
}

export async function listSchemas(token) {
  const res = await fetch(`${BASE}/schemas`, { headers: authHeaders(token) });
  if (!res.ok) throw new Error('Failed to load schemas');
  return res.json();
}

export async function getSchema(token, schemaId) {
  const res = await fetch(`${BASE}/schemas/${schemaId}`, { headers: authHeaders(token) });
  if (!res.ok) throw new Error('Schema not found');
  return res.json();
}

export async function createSchema(token, formData) {
  const res = await fetch(`${BASE}/schemas`, {
    method: 'POST',
    headers: authHeaders(token),
    body: formData,
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail || 'Failed to create schema');
  }
  return res.json();
}

export async function updateSchema(token, schemaId, formData) {
  const res = await fetch(`${BASE}/schemas/${schemaId}`, {
    method: 'PUT',
    headers: authHeaders(token),
    body: formData,
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail || 'Failed to update schema');
  }
  return res.json();
}

export async function deleteSchema(token, schemaId) {
  const res = await fetch(`${BASE}/schemas/${schemaId}`, {
    method: 'DELETE',
    headers: authHeaders(token),
  });
  if (!res.ok) throw new Error('Failed to delete schema');
}
