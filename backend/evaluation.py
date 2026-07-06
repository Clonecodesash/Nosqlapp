"""Answer evaluation and feedback (de)serialization helpers."""

import json
from typing import List, Optional

from fastapi import HTTPException, status
from pydantic import ValidationError

import error_taxonomy as tax
from aggregate_evaluator import evaluate_schemas
from dto import QueryCreate
from json_sm_parser import check_syntax, parse_jsonsm


def feedback_to_json(feedback: List[dict]) -> str:
    """Convert a list of feedback dicts to a JSON string for storage."""
    return json.dumps(feedback)


def feedback_from_json(feedback_json: Optional[str]) -> List[dict]:
    """Convert stored JSON feedback back to a list of dicts.

    Legacy logs stored plain strings; those are normalised into the structured
    shape so old and new answer logs render the same way.
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
            normalized.append(tax.make("LEGACY", item).to_dict())
        elif isinstance(item, dict):
            normalized.append(item)
    return normalized


def _score_from_feedback(feedback_objs) -> dict:
    """Turn a list of Feedback objects into feedback dicts + score + correctness."""
    feedback = [f.to_dict() for f in feedback_objs]

    if not feedback_objs:
        return {"feedback": feedback, "score": 100, "is_correct": True}

    penalty = sum(tax.SEVERITY_WEIGHTS.get(f.severity, 15) for f in feedback_objs)
    score = max(0, 100 - penalty)
    # info-only findings (e.g. a different root name) do not make an answer wrong.
    is_correct = not any(f.severity in tax.BLOCKING_SEVERITIES for f in feedback_objs)
    return {"feedback": feedback, "score": score, "is_correct": is_correct}


def evaluate_aggregate_answer(student_answer: str, reference_answer: str) -> dict:
    """
    Evaluate a student answer against the reference using the aggregate evaluator.

    Phase 1 (syntax gate): if the student answer does not parse, return that
    single syntax finding with a score of 0 - it cannot be compared.
    Phase 2 (comparison): parse both answers and compare structure + metadata.

    Returns a dict with ``feedback`` (list of taxonomy dicts), ``score``, and
    ``is_correct``.
    """
    try:
        syntax_error = check_syntax(student_answer)
        if syntax_error:
            return {"feedback": [syntax_error.to_dict()], "score": 0, "is_correct": False}

        student_node = parse_jsonsm(student_answer)
        reference_node = parse_jsonsm(reference_answer)

        feedback_objs = evaluate_schemas(student_node, reference_node)
        return _score_from_feedback(feedback_objs)
    except Exception as e:
        return {
            "feedback": [tax.make("ENGINE_ERROR", f"Evaluation failed: {str(e)}").to_dict()],
            "score": 0,
            "is_correct": False,
        }


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
