"""Answer evaluation and feedback (de)serialization helpers."""

import json
from typing import List, Optional

from fastapi import HTTPException, status
from pydantic import ValidationError

import error_taxonomy as tax
from aggregate_evaluator import evaluate_schemas_full
from dto import QueryCreate
from json_sm_parser import check_syntax, parse_jsonsm


def findings_to_json(findings: List[dict]) -> str:
    """Serialize the complete list of findings for storage.

    Every finding is stored, each with a ``shown`` flag marking the ones the
    student was given, so the full list stays available for analysis.
    """
    return json.dumps(findings)


def _load_findings(feedback_json: Optional[str]) -> List[dict]:
    """Load stored findings, normalising legacy formats.

    Legacy logs stored plain strings (or dicts without a ``shown`` flag); those
    are treated as shown so old and new answer logs render the same way.
    """
    if not feedback_json:
        return []
    try:
        data = json.loads(feedback_json)
    except (json.JSONDecodeError, TypeError):
        return []

    normalized = []
    for item in data:
        if isinstance(item, str):
            normalized.append({**tax.make("LEGACY", item).to_dict(), "shown": True})
        elif isinstance(item, dict):
            normalized.append({"shown": True, **item})
    return normalized


def _strip_flag(finding: dict) -> dict:
    return {k: v for k, v in finding.items() if k != "shown"}


def feedback_from_json(feedback_json: Optional[str]) -> List[dict]:
    """The findings that were shown to the student for a stored attempt."""
    return [_strip_flag(f) for f in _load_findings(feedback_json) if f["shown"]]


def all_findings_from_json(feedback_json: Optional[str]) -> List[dict]:
    """Every finding the engine produced for a stored attempt (for analysis)."""
    return [_strip_flag(f) for f in _load_findings(feedback_json)]


def _verdict(findings) -> dict:
    """
    Derive the verdict and the findings to show from the complete list.

    An answer is correct iff it contains no syntax, schema-dependent or
    workload-dependent error; complications never make it incorrect.
    - Wrong answer: only the FIRST error is shown (one problem at a time).
    - Correct answer: every complication is shown, as a suggestion.
    """
    errors = [f for f in findings if f.is_error]
    if errors:
        shown = [errors[0]]
    else:
        shown = [f for f in findings if f.category == tax.CLASS_COMPLICATION]

    shown_ids = {id(f) for f in shown}
    return {
        "is_correct": not errors,
        "feedback": [f.to_dict() for f in shown],
        "findings": [{**f.to_dict(), "shown": id(f) in shown_ids} for f in findings],
    }


def evaluate_aggregate_answer(student_answer: str, reference_answer: str) -> dict:
    """
    Evaluate a student answer against the reference.

    Phase 1 (syntax gate): if the student answer does not parse, the first
    syntax problem is the only finding and the answer is wrong.
    Phase 2 (comparison): parse both answers and compare root, metadata and
    body (breadth-first).

    Returns a dict with ``is_correct``, ``feedback`` (the findings shown to the
    student) and ``findings`` (every finding, each with a ``shown`` flag, for
    storage).
    """
    try:
        syntax_error = check_syntax(student_answer)
        if syntax_error:
            return _verdict([syntax_error])

        # A broken reference would make every answer look wrong; say so
        # explicitly (the teacher preview is where this should be caught).
        reference_error = check_syntax(reference_answer)
        if reference_error:
            return _verdict([tax.make(
                "ENGINE_ERROR",
                f"The reference answer of this exercise is not valid json-sm: {reference_error}",
            )])

        student_node = parse_jsonsm(student_answer)
        reference_node = parse_jsonsm(reference_answer)
        return _verdict(evaluate_schemas_full(student_node, reference_node))
    except Exception as e:
        return _verdict([tax.make("ENGINE_ERROR", f"Evaluation failed: {str(e)}")])


def parse_queries_payload(queries: str):
    """Parse JSON queries string into QueryCreate objects."""
    try:
        raw_queries = json.loads(queries)
    except json.JSONDecodeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Queries must be valid JSON")

    if not isinstance(raw_queries, list):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Queries must be a list")

    try:
        parsed_queries = [QueryCreate.model_validate(query) for query in raw_queries]
    except ValidationError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Each query must include queryText")
    if not parsed_queries:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Exercise must have at least one query")

    return parsed_queries
