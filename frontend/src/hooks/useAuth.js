import { useState } from 'react';

export function useAuth() {
  const [token, setToken]       = useState(null);
  const [role, setRole]         = useState(null);
  const [username, setUsername] = useState(null);
  const [userId, setUserId]     = useState(null);

  function login(accessToken) {
    // Decode the JWT payload to extract the role, username and id without an extra API call
    const payload = JSON.parse(atob(accessToken.split('.')[1]));
    setToken(accessToken);
    setRole(payload.role);
    setUsername(payload.sub);
    setUserId(payload.id ?? null);
  }

  function logout() {
    setToken(null);
    setRole(null);
    setUsername(null);
    setUserId(null);
  }

  return { token, role, username, userId, login, logout };
}
