import React, { useEffect, useState } from 'react';
import Topbar from '../components/Topbar';
import SchemaCard from '../components/SchemaCard';
import TeacherSidebar from '../components/TeacherSidebar';
import { listSchemas, createSchema, updateSchema, deleteSchema } from '../api/schemas';

export default function SchemasPage({ token, role, onLogout, onSelectSchema }) {
  const [schemas, setSchemas] = useState([]);
  const [error,   setError]   = useState('');
  const [editingSchema, setEditingSchema] = useState(null);

  useEffect(() => {
    loadSchemas();
  }, []);

  async function loadSchemas() {
    try {
      setSchemas(await listSchemas(token));
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleSchemaSaved(editingId, formData) {
    if (editingId) {
      await updateSchema(token, editingId, formData);
    } else {
      await createSchema(token, formData);
    }
    setEditingSchema(null);
    await loadSchemas();
  }

  async function handleDeleteSchema(schema) {
    if (!window.confirm(`Delete schema "${schema.name}"? This also deletes its exercises.`)) return;
    try {
      await deleteSchema(token, schema.id);
      if (editingSchema?.id === schema.id) setEditingSchema(null);
      await loadSchemas();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="app-shell">
      <Topbar role={role} onLogout={onLogout} />

      <main className="main-grid">
        {role === 'teacher' && (
          <TeacherSidebar
            selectedSchema={null}
            schemaToEdit={editingSchema}
            onSchemaSaved={handleSchemaSaved}
            onExerciseSaved={() => {}}
            onClearSchemaEdit={() => setEditingSchema(null)}
          />
        )}

        <section className={role === 'teacher' ? '' : 'panel'}
          style={role !== 'teacher' ? { gridColumn: '1 / -1' } : undefined}>

          {error && <div className="error-box" style={{ marginBottom: 14 }}>{error}</div>}

          <div className="section-title">
            <div>
              <h2>ER Schemas</h2>
              <p>Select a schema to {role === 'student' ? 'view exercises' : 'manage exercises'}</p>
            </div>
            <span className="count-badge">{schemas.length} total</span>
          </div>

          {schemas.length === 0 ? (
            <div className="empty-state">No schemas available yet.</div>
          ) : (
            <div className="exercise-list">
              {schemas.map(schema => (
                <SchemaCard
                  key={schema.id}
                  schema={schema}
                  role={role}
                  onClick={() => onSelectSchema(schema)}
                  onEdit={setEditingSchema}
                  onDelete={handleDeleteSchema}
                />
              ))}
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
