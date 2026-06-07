import { useState } from 'react';

export function useAuth() {
  const [token, setToken]       = useState(null);
  const [role, setRole]         = useState(null);
  const [username, setUsername] = useState(null);

  function login(accessToken) {
    // Decode the JWT payload to extract the role and username without an extra API call
    const payload = JSON.parse(atob(accessToken.split('.')[1]));
    setToken(accessToken);
    setRole(payload.role);
    setUsername(payload.sub);
  }

  function logout() {
    setToken(null);
    setRole(null);
    setUsername(null);
  }

  return { token, role, username, login, logout };
}
