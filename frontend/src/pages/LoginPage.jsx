import React, { useState } from 'react';

export default function LoginPage({ onLogin }) {
  const [username,    setUsername]    = useState('');
  const [password,    setPassword]    = useState('');
  const [role,        setRole]        = useState('student');
  const [teacherInviteCode, setTeacherInviteCode] = useState('');
  const [isRegister,  setIsRegister]  = useState(false);
  const [error,       setError]       = useState('');
  const [loading,     setLoading]     = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');
    if (password.length < 6 || password.length > 72) {
      setError('Password must be between 6 and 72 characters');
      return;
    }

    setLoading(true);
    try {
      if (isRegister) {
        const res = await fetch('/api/register', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            username,
            password,
            role,
            ...(role === 'teacher' && { teacher_invite_code: teacherInviteCode }),
          }),
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
        body: new URLSearchParams({ username, password }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        setError(detail?.detail || 'Login failed');
        return;
      }
      const data = await res.json();
      onLogin(data.access_token);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed. Please try again.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-shell">
      <section className="auth-panel">
        <div className="brand-mark">Aggregate Lab</div>
        <div>
          <h1>Design aggregates around the queries they need to serve.</h1>
          <p>
            Practise NoSQL schema design through hands-on exercises. Build an aggregate for a given data model and query workload, then get clear feedback on its syntax, structure, and fit for the workload.
          </p>
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
                <select
                  value={role}
                  onChange={e => {
                    setRole(e.target.value);
                    setTeacherInviteCode('');
                  }}
                >
                  <option value="student">Student</option>
                  <option value="teacher">Teacher</option>
                </select>
              </label>
            )}
            {isRegister && role === 'teacher' && (
              <label className="field">
                Teacher invite code
                <input
                  type="password"
                  autoComplete="off"
                  value={teacherInviteCode}
                  onChange={e => setTeacherInviteCode(e.target.value)}
                  required
                />
              </label>
            )}
            {error && <div className="error-box">{error}</div>}
            <button className="primary-btn" type="submit" disabled={loading}>
              {loading ? 'Please wait…' : isRegister ? 'Register and login' : 'Login'}
            </button>
          </form>

          <button
            className="ghost-btn"
            onClick={() => setIsRegister(r => !r)}
            style={{ marginTop: 16 }}
          >
            {isRegister ? 'Already have an account? Login' : 'Need an account? Register'}
          </button>
        </div>
      </main>
    </div>
  );
}
