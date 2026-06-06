import React, { useState } from 'react';

export default function SchemaCard({ schema, role, onClick, onEdit }) {
  const [broken, setBroken] = useState(false);

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
          {role === 'teacher' && (
            <button
              className="secondary-btn"
              type="button"
              onClick={e => { e.stopPropagation(); onEdit(schema); }}
            >
              Edit
            </button>
          )}
        </div>
      </div>
    </article>
  );
}
