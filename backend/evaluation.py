"""Answer evaluation and feedback (de)serialization helpers."""

import json
from typing import List, Optional

from fastapi import HTTPException, status
from pydantic import ValidationError

from aggregate_evaluator import evaluate_schemas
from dto import QueryCreate
from json_sm_parser import parse_jsonsm


def feedback_to_json(feedback: List[str]) -> str:
    """Convert feedback list to JSON string for storage."""
    return json.dumps(feedback)


def feedback_from_json(feedback_json: Optional[str]) -> List[str]:
    """Convert stored JSON feedback back to list."""
    if not feedback_json:
        return []
    try:
        return json.loads(feedback_json)
    except (json.JSONDecodeError, TypeError):
        return []


def evaluate_aggregate_answer(student_answer: str, reference_answer: str) -> dict:
    """
    Evaluate student answer against reference using the aggregate evaluator.
    Parses both answers into schema nodes, then evaluates structurally.
    Returns dict with feedback, score, and is_correct status.
    """
    try:
        # Parse both schemas into node trees
        student_node = parse_jsonsm(student_answer)
        reference_node = parse_jsonsm(reference_answer)

        # Call the evaluate_schemas function from aggregate_evaluator
        feedback = evaluate_schemas(student_node, reference_node)

        # Compute score: 0-100 based on feedback length and severity
        # No feedback = 100, otherwise penalize based on critical/error/warning count
        if not feedback:
            score = 100
            is_correct = True
        else:
            critical_count = sum(1 for f in feedback if "CRITICAL" in f or "MISSING" in f)
            error_count = sum(1 for f in feedback if "ERROR" in f or "EXTRA" in f)
            warning_count = sum(1 for f in feedback if "WARNING" in f)

            # Scoring: Start at 100, deduct based on issues
            score = 100
            score -= critical_count * 25
            score -= error_count * 15
            score -= warning_count * 5
            score = max(0, score)

            is_correct = score == 100

        return {
            "feedback": feedback,
            "score": score,
            "is_correct": is_correct,
        }
    except Exception as e:
        return {
            "feedback": [f"ERROR: Evaluation failed: {str(e)}"],
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
