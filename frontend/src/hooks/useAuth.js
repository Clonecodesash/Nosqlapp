import { useState } from 'react';

export function useAuth() {
  const [token, setToken] = useState(null);
  const [role, setRole]   = useState(null);

  function login(accessToken) {
    // Decode the JWT payload to extract the role without an extra API call
    const payload = JSON.parse(atob(accessToken.split('.')[1]));
    setToken(accessToken);
    setRole(payload.role);
  }

  function logout() {
    setToken(null);
    setRole(null);
  }

  return { token, role, login, logout };
}
