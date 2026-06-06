import { useState } from 'react';
import {
  explainError,
  giveHint,
  fixSchema,
  explainSuccess,
} from '../api/exercises';

// One hook owns ALL LLM state so SolvePage and LLMButtons stay clean.
// Each button has three pieces of state: data (cached result), loading, open (panel visible).
// On the first click it fetches; on subsequent clicks it just toggles the panel.

export function useLLM(token, exerciseId) {
  const [explainErrorData,    setExplainErrorData]    = useState(null);
  const [explainErrorLoading, setExplainErrorLoading] = useState(false);
  const [explainErrorOpen,    setExplainErrorOpen]    = useState(false);

  const [hintData,    setHintData]    = useState(null);
  const [hintLoading, setHintLoading] = useState(false);
  const [hintOpen,    setHintOpen]    = useState(false);

  const [fixData,    setFixData]    = useState(null);
  const [fixLoading, setFixLoading] = useState(false);
  const [fixOpen,    setFixOpen]    = useState(false);

  const [successData,    setSuccessData]    = useState(null);
  const [successLoading, setSuccessLoading] = useState(false);
  const [successOpen,    setSuccessOpen]    = useState(false);

  // Reset all panels when the student submits a new answer
  function reset() {
    setExplainErrorData(null);  setExplainErrorOpen(false);
    setHintData(null);          setHintOpen(false);
    setFixData(null);           setFixOpen(false);
    setSuccessData(null);       setSuccessOpen(false);
  }

  async function handleExplainError() {
    if (explainErrorData) { setExplainErrorOpen(v => !v); return; }
    setExplainErrorLoading(true);
    try {
      const data = await explainError(token, exerciseId);
      setExplainErrorData(data.explanation);
      setExplainErrorOpen(true);
    } finally {
      setExplainErrorLoading(false);
    }
  }

  async function handleGiveHint() {
    if (hintData) { setHintOpen(v => !v); return; }
    setHintLoading(true);
    try {
      const data = await giveHint(token, exerciseId);
      setHintData(data.explanation);
      setHintOpen(true);
    } finally {
      setHintLoading(false);
    }
  }

  async function handleFixSchema() {
    if (fixData) { setFixOpen(v => !v); return; }
    setFixLoading(true);
    try {
      const data = await fixSchema(token, exerciseId);
      setFixData(data.explanation);
      setFixOpen(true);
    } finally {
      setFixLoading(false);
    }
  }

  async function handleExplainSuccess() {
    if (successData) { setSuccessOpen(v => !v); return; }
    setSuccessLoading(true);
    try {
      const data = await explainSuccess(token, exerciseId);
      setSuccessData(data.explanation);
      setSuccessOpen(true);
    } finally {
      setSuccessLoading(false);
    }
  }

  return {
    reset,
    explainError:   { data: explainErrorData, loading: explainErrorLoading, open: explainErrorOpen, handle: handleExplainError },
    hint:           { data: hintData,         loading: hintLoading,         open: hintOpen,         handle: handleGiveHint },
    fix:            { data: fixData,          loading: fixLoading,          open: fixOpen,           handle: handleFixSchema },
    success:        { data: successData,      loading: successLoading,      open: successOpen,       handle: handleExplainSuccess },
  };
}
