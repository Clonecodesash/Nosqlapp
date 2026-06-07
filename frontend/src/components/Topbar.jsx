import React from 'react';

export default function Topbar({ role, username, onLogout }) {
  return (
    <header className="topbar">
      <div className="topbar-inner">
        <h1 style={{ margin: 0 }}>Aggregate Modeling</h1>
        <div className="topbar-actions">
          <span className="role-pill">
            {username ? `${username} · ${role}` : role}
          </span>
          <button className="secondary-btn" type="button" onClick={onLogout}>
            Logout
          </button>
        </div>
      </div>
    </header>
  );
}
