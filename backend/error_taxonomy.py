"""
Error taxonomy for aggregate-schema evaluation (thesis Chapter 3, Table 3.1).

Every problem the evaluator can report is registered here once, as a stable
CODE with a fixed pedagogical CLASS. Keeping the taxonomy in one place means:

  * the codes are stable identifiers the frontend / thesis analysis can group on
    (e.g. "how many students made SYN_MISSING_COLON mistakes?"), independent of
    the exact wording of the human message;
  * the verdict follows from the classes of the findings alone, never from
    their wording: an answer is correct if and only if it contains no syntax,
    schema-dependent or workload-dependent error. Complications never make an
    answer incorrect.

The four classes:

  SYN - syntax error: the answer is not well-formed json-sm (Phase 1).
  SCH - schema-dependent error: contradicts a fact the ER schema alone fixes.
  WRK - workload-dependent error: contradicts a decision made for the workload.
  COM - complication: valid, but more complex than the reference requires.

Two further codes sit outside the taxonomy as engineering safety nets:
ENGINE_ERROR (unexpected internal failure) and LEGACY (findings stored in the
older, string-only format).
"""

from dataclasses import asdict, dataclass
from typing import Optional

# ---------------------------------------------------------------------------
# Pedagogical classes
# ---------------------------------------------------------------------------
CLASS_SYNTAX = "syntax"
CLASS_SCHEMA = "schema"
CLASS_WORKLOAD = "workload"
CLASS_COMPLICATION = "complication"

# Outside the taxonomy.
CLASS_INTERNAL = "internal"
CLASS_LEGACY = "legacy"

# Classes that make an answer incorrect. An engine failure also does, since
# the answer could not be shown to be correct.
ERROR_CLASSES = {CLASS_SYNTAX, CLASS_SCHEMA, CLASS_WORKLOAD, CLASS_INTERNAL}

# ---------------------------------------------------------------------------
# The taxonomy: code -> class
# ---------------------------------------------------------------------------
TAXONOMY = {
    # --- Syntax errors (Phase 1) -------------------------------------------
    "SYN_EMPTY":              CLASS_SYNTAX,
    "SYN_UNCLOSED_BRACKET":   CLASS_SYNTAX,
    "SYN_EXTRA_BRACKET":      CLASS_SYNTAX,
    "SYN_MISMATCHED_BRACKET": CLASS_SYNTAX,
    "SYN_MISSING_COLON":      CLASS_SYNTAX,
    "SYN_MISSING_COMMA":      CLASS_SYNTAX,
    "SYN_TRAILING_COMMA":     CLASS_SYNTAX,
    "SYN_UNEXPECTED_TOKEN":   CLASS_SYNTAX,

    # --- Schema-dependent errors -------------------------------------------
    "SCH_IDENTIFIER_MISSING":    CLASS_SCHEMA,
    "SCH_IDENTIFIER_UNEXPECTED": CLASS_SCHEMA,

    # --- Workload-dependent errors -----------------------------------------
    "WRK_ROOT_TYPE_MISMATCH":      CLASS_WORKLOAD,
    "WRK_MISSING_ELEMENT":         CLASS_WORKLOAD,
    "WRK_CONTAINER_KIND_MISMATCH": CLASS_WORKLOAD,
    "WRK_PARTITIONKEY_MISSING":    CLASS_WORKLOAD,
    "WRK_REQUIRED_MISSING":        CLASS_WORKLOAD,

    # --- Complications -----------------------------------------------------
    "COM_USELESS_NESTING": CLASS_COMPLICATION,
    "COM_EXTRA_ELEMENT":   CLASS_COMPLICATION,
    "COM_NAME_TYPO":       CLASS_COMPLICATION,
    "COM_ROOT_NAME_DIFF":  CLASS_COMPLICATION,

    # --- Outside the taxonomy ----------------------------------------------
    "ENGINE_ERROR": CLASS_INTERNAL,
    "LEGACY":       CLASS_LEGACY,
}


@dataclass
class Feedback:
    """One evaluation finding, carrying its taxonomy code + human message.

    ``line``/``col`` locate syntax errors in the raw text; ``path`` locates a
    structural/metadata finding in the schema tree (e.g. ``Student.courses``).
    """
    code: str
    message: str
    category: str
    line: Optional[int] = None
    col: Optional[int] = None
    path: Optional[str] = None

    @property
    def is_error(self) -> bool:
        """True if this finding makes the answer incorrect."""
        return self.category in ERROR_CLASSES

    def to_dict(self) -> dict:
        """JSON-serializable form, dropping empty location fields."""
        return {k: v for k, v in asdict(self).items() if v is not None}

    def __str__(self) -> str:
        if self.line is not None and self.col is not None:
            loc = f" (line {self.line}, col {self.col})"
        elif self.path:
            loc = f" (at {self.path})"
        else:
            loc = ""
        return f"[{self.code}] {self.message}{loc}"


def make(code: str, message: str, line: int = None, col: int = None, path: str = None) -> Feedback:
    """Build a :class:`Feedback`, looking up its class in the taxonomy.

    This is the only way findings are created, so no part of the system can
    decide on its own whether a problem is an error or a complication. An
    unregistered code raises ``ValueError``; the evaluation entry point turns
    that into an ENGINE_ERROR finding.
    """
    if code not in TAXONOMY:
        raise ValueError(f"Unknown taxonomy code: {code}")
    return Feedback(
        code=code,
        message=message,
        category=TAXONOMY[code],
        line=line,
        col=col,
        path=path,
    )
