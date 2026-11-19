import { useEffect, useState } from 'react';

function decodeTokenPayload(accessToken) {
  const payloadSegment = accessToken.split('.')[1];
  if (!payloadSegment) {
    throw new Error('Login response contained an invalid access token.');
  }

  const base64Payload = payloadSegment
    .replace(/-/g, '+')
    .replace(/_/g, '/')
    .padEnd(Math.ceil(payloadSegment.length / 4) * 4, '=');
  const bytes = Uint8Array.from(atob(base64Payload), character => character.charCodeAt(0));
  return JSON.parse(new TextDecoder().decode(bytes));
}

// True if the token has an expiry ("exp", in seconds) that has already passed.
function isExpired(payload) {
  return typeof payload.exp === 'number' && payload.exp * 1000 <= Date.now();
}

function getStoredAuth() {
  const accessToken = sessionStorage.getItem('accessToken');
  if (!accessToken) {
    return { token: null, role: null, username: null, userId: null };
  }

  try {
    const payload = decodeTokenPayload(accessToken);
    if (isExpired(payload)) {
      sessionStorage.removeItem('accessToken');
      return { token: null, role: null, username: null, userId: null };
    }
    return {
      token: accessToken,
      role: payload.role,
      username: payload.sub,
      userId: payload.id ?? null,
    };
  } catch {
    sessionStorage.removeItem('accessToken');
    return { token: null, role: null, username: null, userId: null };
  }
}

export function useAuth() {
  const [auth, setAuth] = useState(getStoredAuth);

  function login(accessToken) {
    const payload = decodeTokenPayload(accessToken);
    sessionStorage.setItem('accessToken', accessToken);
    setAuth({
      token: accessToken,
      role: payload.role,
      username: payload.sub,
      userId: payload.id ?? null,
    });
  }

  function logout() {
    sessionStorage.removeItem('accessToken');
    setAuth({ token: null, role: null, username: null, userId: null });
  }

  // Log out automatically when the token expires during a session, so the
  // user is sent back to the login page instead of seeing failed requests.
  useEffect(() => {
    if (!auth.token) return undefined;
    let payload;
    try {
      payload = decodeTokenPayload(auth.token);
    } catch {
      return undefined;
    }
    if (typeof payload.exp !== 'number') return undefined;
    const msLeft = payload.exp * 1000 - Date.now();
    // setTimeout cannot wait longer than ~24 days; clamp so it never fires early.
    const timer = setTimeout(logout, Math.min(Math.max(msLeft, 0), 2147483647));
    return () => clearTimeout(timer);
  }, [auth.token]);

  return { ...auth, login, logout };
}
