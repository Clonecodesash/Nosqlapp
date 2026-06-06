import React from 'react';
import { useAuth } from './hooks/useAuth';
import LoginPage    from './pages/LoginPage';
import SchemasPage  from './pages/SchemasPage';
import ExercisesPage from './pages/ExercisesPage';
import SolvePage    from './pages/SolvePage';
import { useState } from 'react';

// Navigation state — three levels deep: schema → exercise → solve
// No React Router needed for this project size.
function useNav() {
  const [schema,   setSchema]   = useState(null);
  const [exercise, setExercise] = useState(null);

  return {
    schema,
    exercise,
    goToExercises: (s)  => { setSchema(s); setExercise(null); },
    goToSolve:     (ex) => setExercise(ex),
    goToSchemas:   ()   => { setSchema(null); setExercise(null); },
    goBack:        ()   => setExercise(null),
  };
}

export default function App() {
  const { token, role, login, logout } = useAuth();
  const nav = useNav();

  if (!token) {
    return <LoginPage onLogin={login} />;
  }

  if (!nav.schema) {
    return (
      <SchemasPage
        token={token}
        role={role}
        onLogout={logout}
        onSelectSchema={nav.goToExercises}
      />
    );
  }

  if (!nav.exercise) {
    return (
      <ExercisesPage
        token={token}
        role={role}
        schema={nav.schema}
        onLogout={logout}
        onBack={nav.goToSchemas}
        onSelectExercise={nav.goToSolve}
      />
    );
  }

  return (
    <SolvePage
      token={token}
      role={role}
      schema={nav.schema}
      exercise={nav.exercise}
      onLogout={logout}
      onBack={nav.goBack}
    />
  );
}
