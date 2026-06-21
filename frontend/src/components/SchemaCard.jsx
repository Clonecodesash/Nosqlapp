import React, { useState } from 'react';

export default function SchemaCard({ schema, role, userId, onClick, onEdit, onDelete }) {
  const [broken, setBroken] = useState(false);

  // Only the owner teacher may edit/delete (matches the backend ownership check).
  const canManage = role === 'teacher' && schema.teacherId === userId;

  return (
    <article
      className="exercise-card exercise-card-clickable"
      onClick={onClick}
    >
      {broken ? (
        <div className="image-fallback">
          Image cannot be displayed. Upload JPG, PNG, WebP, or GIF.
        </div>
      ) : (
        <img
          className="exercise-media"
          src={schema.image}
          alt={schema.name}
          onError={() => setBroken(true)}
        />
      )}
      <div className="exercise-body">
        <div className="meta-row">
          <h3>{schema.name}</h3>
          {canManage && (
            <div className="row-actions">
              <button
                className="secondary-btn"
                type="button"
                onClick={e => { e.stopPropagation(); onEdit(schema); }}
              >
                Edit
              </button>
              <button
                className="secondary-btn danger-btn"
                type="button"
                onClick={e => { e.stopPropagation(); onDelete(schema); }}
              >
                Delete
              </button>
            </div>
          )}
        </div>
      </div>
    </article>
  );
}
