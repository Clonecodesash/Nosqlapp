"""
Error taxonomy for aggregate-schema evaluation.

Every problem the evaluator can report is described here as a stable CODE with a
fixed CATEGORY and SEVERITY. Keeping the taxonomy in one place means:

  * the codes are stable identifiers the frontend / thesis analysis can group on
    (e.g. "how many students made SYN_MISSING_COLON mistakes?"), independent of
    the exact wording of the human message;
  * severity (used for scoring) lives with the code, so scoring never has to
    guess it by sniffing substrings out of the message text.

There are two phases of evaluation, mirrored by the categories:

  Phase 1 - SYNTAX  : is the answer even well-formed? Checked first; the caller
                      stops at the FIRST syntax error and reports only that one,
                      because an answer that does not parse cannot be compared.
  Phase 2 - STRUCTURE / METADATA : only once syntax is clean, compare the
                      student's tree against the reference tree.
"""

from dataclasses import asdict, dataclass
from typing import Optional

# ---------------------------------------------------------------------------
# Categories & severities
# ---------------------------------------------------------------------------
CATEGORY_SYNTAX = "syntax"
CATEGORY_STRUCTURE = "structure"
CATEGORY_METADATA = "metadata"

SEVERITY_CRITICAL = "critical"
SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"
SEVERITY_INFO = "info"

# Points deducted from a starting score of 100 for each finding of this severity.
SEVERITY_WEIGHTS = {
    SEVERITY_CRITICAL: 25,
    SEVERITY_ERROR: 15,
    SEVERITY_WARNING: 5,
    SEVERITY_INFO: 0,
}

# Severities that mean "not yet correct". info-only feedback still counts as correct.
BLOCKING_SEVERITIES = {SEVERITY_CRITICAL, SEVERITY_ERROR, SEVERITY_WARNING}

# ---------------------------------------------------------------------------
# The taxonomy: code -> (category, severity)
# ---------------------------------------------------------------------------
TAXONOMY = {
    # --- Phase 1: syntax --------------------------------------------------
    "SYN_EMPTY":              (CATEGORY_SYNTAX, SEVERITY_ERROR),
    "SYN_UNCLOSED_BRACKET":   (CATEGORY_SYNTAX, SEVERITY_ERROR),
    "SYN_EXTRA_BRACKET":      (CATEGORY_SYNTAX, SEVERITY_ERROR),
    "SYN_MISMATCHED_BRACKET": (CATEGORY_SYNTAX, SEVERITY_ERROR),
    "SYN_MISSING_COLON":      (CATEGORY_SYNTAX, SEVERITY_ERROR),
    "SYN_COLON_NO_CONTAINER": (CATEGORY_SYNTAX, SEVERITY_ERROR),
    "SYN_MISSING_COMMA":      (CATEGORY_SYNTAX, SEVERITY_ERROR),
    "SYN_DOUBLE_COMMA":       (CATEGORY_SYNTAX, SEVERITY_ERROR),
    "SYN_LEADING_COMMA":      (CATEGORY_SYNTAX, SEVERITY_ERROR),
    "SYN_TRAILING_COMMA":     (CATEGORY_SYNTAX, SEVERITY_ERROR),
    "SYN_UNEXPECTED_TOKEN":   (CATEGORY_SYNTAX, SEVERITY_ERROR),

    # --- Phase 2: structure ----------------------------------------------
    "STR_ROOT_TYPE_MISMATCH":      (CATEGORY_STRUCTURE, SEVERITY_CRITICAL),
    "STR_ROOT_NAME_DIFF":          (CATEGORY_STRUCTURE, SEVERITY_INFO),
    "STR_MISSING_ELEMENT":         (CATEGORY_STRUCTURE, SEVERITY_ERROR),
    "STR_EXTRA_ELEMENT":           (CATEGORY_STRUCTURE, SEVERITY_WARNING),
    "STR_NAME_TYPO":               (CATEGORY_STRUCTURE, SEVERITY_INFO),
    "STR_TYPE_MISMATCH":           (CATEGORY_STRUCTURE, SEVERITY_ERROR),
    "STR_CONTAINER_KIND_MISMATCH": (CATEGORY_STRUCTURE, SEVERITY_ERROR),
    "STR_CHILD_COUNT_MISMATCH":    (CATEGORY_STRUCTURE, SEVERITY_WARNING),
    "STR_USELESS_NESTING":         (CATEGORY_STRUCTURE, SEVERITY_WARNING),

    # --- Phase 2: metadata -----------------------------------------------
    "META_IDENTIFIER_MISSING":     (CATEGORY_METADATA, SEVERITY_ERROR),
    "META_IDENTIFIER_MISMATCH":    (CATEGORY_METADATA, SEVERITY_ERROR),
    "META_IDENTIFIER_UNEXPECTED":  (CATEGORY_METADATA, SEVERITY_WARNING),
    "META_PARTITIONKEY_MISSING":   (CATEGORY_METADATA, SEVERITY_ERROR),
    "META_PARTITIONKEY_MISMATCH":  (CATEGORY_METADATA, SEVERITY_ERROR),
    "META_PARTITIONKEY_UNEXPECTED": (CATEGORY_METADATA, SEVERITY_WARNING),
    "META_REQUIRED_MISSING":       (CATEGORY_METADATA, SEVERITY_ERROR),
    "META_REQUIRED_UNEXPECTED":    (CATEGORY_METADATA, SEVERITY_WARNING),

    # --- Fallbacks --------------------------------------------------------
    "ENGINE_ERROR":                (CATEGORY_STRUCTURE, SEVERITY_ERROR),
    "LEGACY":                      (CATEGORY_STRUCTURE, SEVERITY_INFO),
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
    severity: str
    line: Optional[int] = None
    col: Optional[int] = None
    path: Optional[str] = None

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
    """Build a :class:`Feedback`, looking up category/severity from the taxonomy.

    An unknown code degrades gracefully to a structure-level error rather than
    raising, so a typo'd code never crashes an evaluation.
    """
    category, severity = TAXONOMY.get(code, (CATEGORY_STRUCTURE, SEVERITY_ERROR))
    return Feedback(
        code=code,
        message=message,
        category=category,
        severity=severity,
        line=line,
        col=col,
        path=path,
    )
