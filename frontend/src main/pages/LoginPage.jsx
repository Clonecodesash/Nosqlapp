import React, { useState } from 'react';

function LoginPage({ setToken, setRole }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRoleLocal] = useState('student');
  const [isRegister, setIsRegister] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    if (password.length < 6 || password.length > 72) {
      setError('Password must be between 6 and 72 characters');
      return;
    }

    if (isRegister) {
      const res = await fetch('/api/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password, role }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        setError(detail?.detail || 'Registration failed');
        return;
      }
    }
    const res = await fetch('/api/token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({ username, password }).toString(),
    });
    if (!res.ok) {
      const detail = await res.json().catch(() => null);
      setError(detail?.detail || 'Login failed');
      return;
    }
    const data = await res.json();
    setToken(data.access_token);
    // Decode JWT to get role
    const payload = JSON.parse(atob(data.access_token.split('.')[1]));
    setRole(payload.role);
  };

  return (
    <div className="auth-shell">
      <section className="auth-panel">
        <div className="brand-mark">Query Modeling</div>
        <div>
          <h1>Build exercises, collect answers, review every attempt.</h1>
          <p>Teachers create visual query exercises with hints. Students submit answers while the system keeps a clean answer history.</p>
        </div>
      </section>

      <main className="auth-card-wrap">
        <div className="auth-card">
          <p className="eyebrow">{isRegister ? 'Create account' : 'Welcome back'}</p>
          <h2>{isRegister ? 'Register' : 'Login'}</h2>

          <form className="form" onSubmit={handleSubmit}>
            <label className="field">
              Username
              <input
                type="text"
                placeholder="teacher01"
                value={username}
                onChange={e => setUsername(e.target.value)}
                required
              />
            </label>

            <label className="field">
              Password
              <input
                type="password"
                placeholder="6 to 72 characters"
                value={password}
                onChange={e => setPassword(e.target.value)}
                minLength={6}
                maxLength={72}
                required
              />
            </label>

            {isRegister && (
              <label className="field">
                Role
                <select value={role} onChange={e => setRoleLocal(e.target.value)}>
                  <option value="student">Student</option>
                  <option value="teacher">Teacher</option>
                </select>
              </label>
            )}

            {error && <div className="error-box">{error}</div>}

            <button className="primary-btn" type="submit">
              {isRegister ? 'Register and login' : 'Login'}
            </button>
          </form>

          <button className="ghost-btn" onClick={() => setIsRegister(r => !r)} style={{ marginTop: 16 }}>
            {isRegister ? 'Already have an account? Login' : 'Need an account? Register'}
          </button>
        </div>
      </main>
    </div>
  );
}

export default LoginPage;
