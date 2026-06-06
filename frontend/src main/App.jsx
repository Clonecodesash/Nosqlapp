import React, { useState } from 'react';
import LoginPage from './pages/LoginPage';
import MainPage from './pages/MainPage';

function App() {
  const [token, setToken] = useState(null);
  const [role, setRole] = useState(null);

  const handleLogout = () => {
    setToken(null);
    setRole(null);
  };

  if (!token) {
    return <LoginPage setToken={setToken} setRole={setRole} />;
  }
  return <MainPage token={token} role={role} onLogout={handleLogout} />;
}

export default App;
