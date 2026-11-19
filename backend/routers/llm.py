"""LLM button-action endpoints (explain error, hint, fix, describe, explain, check).

Every action works on the user's latest attempt, whose verdict has already been
computed and stored, so nothing the model says can change it. The wrong-answer
actions are only available for a wrong verdict and the correct-answer actions
only for a correct one. Every request is recorded against the attempt.
"""

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from auth import get_current_user
from database import get_db
from dto import LLMExplanationOut
from evaluation import feedback_from_json
from llm_actions import (
    action_check_errors,
    action_describe_schema,
    action_explain_error,
    action_explain_schema,
    action_fix_schema,
    action_give_hint,
)
from models import Exercise, LLMInteraction, StudentExerciseAnswerLog, User

logger = logging.getLogger(__name__)

router = APIRouter()

LLM_UNAVAILABLE = "The explanation is unavailable right now. Your verdict is not affected; please try again later."


async def _latest_attempt(exercise_id: int, current_user: User, db: AsyncSession):
    """Latest submission of the current user + the exercise with reference and workload."""
    # Both students and teachers may submit/evaluate, so teachers can test their own exercises.
    log_result = await db.execute(
        select(StudentExerciseAnswerLog)
        .where(
            StudentExerciseAnswerLog.exercise_id == exercise_id,
            StudentExerciseAnswerLog.student_id == current_user.id,
        )
        .order_by(StudentExerciseAnswerLog.id.desc())
        .limit(1)
    )
    answer_log = log_result.scalars().first()
    if answer_log is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No answer submitted yet")

    ex_result = await db.execute(
        select(Exercise)
        .where(Exercise.id == exercise_id)
        .options(selectinload(Exercise.answer), selectinload(Exercise.queries))
    )
    exercise = ex_result.scalars().first()
    if exercise is None or exercise.answer is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Exercise or reference answer not found")

    return answer_log, exercise


def _require_verdict(answer_log: StudentExerciseAnswerLog, correct: bool):
    if bool(answer_log.is_correct) != correct:
        verdict = "correct" if correct else "wrong"
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"This help is only available when the answer is {verdict}.",
        )


def _current_finding(answer_log: StudentExerciseAnswerLog) -> dict:
    """The one finding shown to the student for a wrong answer."""
    shown = feedback_from_json(answer_log.evaluation_feedback)
    if not shown:
        return {"message": "No finding was recorded for this attempt."}
    return shown[0]


def _complications(answer_log: StudentExerciseAnswerLog) -> list[dict]:
    """The complications shown to the student for a correct answer."""
    return [
        finding for finding in feedback_from_json(answer_log.evaluation_feedback)
        if finding.get("category") == "complication"
    ]


async def _run_action(action: str, answer_log: StudentExerciseAnswerLog, db: AsyncSession, fn, *args):
    """Call the LLM off the event loop and record the request against the attempt."""
    try:
        text = await asyncio.to_thread(fn, *args)
    except RuntimeError as exc:
        logger.warning("LLM action %s failed for attempt %s: %s", action, answer_log.id, exc)
        db.add(LLMInteraction(answer_log_id=answer_log.id, action=action, response_text=None, succeeded=False))
        await db.commit()
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=LLM_UNAVAILABLE)

    db.add(LLMInteraction(answer_log_id=answer_log.id, action=action, response_text=text, succeeded=True))
    if action == "give-hint":
        answer_log.used_hint = True
    else:
        answer_log.used_llm_explanation = True
    await db.commit()
    return {"explanation": text}


# ── Wrong answer ─────────────────────────────────────────────────────────────

@router.post("/api/exercises/{exercise_id}/explain-error", response_model=LLMExplanationOut)
async def explain_error(
    exercise_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """What does this error mean? Restate the current finding in plain language."""
    answer_log, _ = await _latest_attempt(exercise_id, current_user, db)
    _require_verdict(answer_log, correct=False)
    return await _run_action(
        "explain-error", answer_log, db,
        action_explain_error, answer_log.answer_text, _current_finding(answer_log),
    )


@router.post("/api/exercises/{exercise_id}/give-hint", response_model=LLMExplanationOut)
async def give_hint(
    exercise_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Give me a hint: one conceptual cue, without revealing the solution."""
    answer_log, exercise = await _latest_attempt(exercise_id, current_user, db)
    _require_verdict(answer_log, correct=False)
    return await _run_action(
        "give-hint", answer_log, db,
        action_give_hint, answer_log.answer_text, exercise.answer.answer_text, _current_finding(answer_log),
    )


@router.post("/api/exercises/{exercise_id}/fix-schema", response_model=LLMExplanationOut)
async def fix_schema(
    exercise_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """How can I fix my schema? The smallest change that resolves the current finding."""
    answer_log, exercise = await _latest_attempt(exercise_id, current_user, db)
    _require_verdict(answer_log, correct=False)
    return await _run_action(
        "fix-schema", answer_log, db,
        action_fix_schema, answer_log.answer_text, exercise.answer.answer_text, _current_finding(answer_log),
    )


# ── Correct answer ───────────────────────────────────────────────────────────

@router.post("/api/exercises/{exercise_id}/describe-schema", response_model=LLMExplanationOut)
async def describe_schema(
    exercise_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Describe my schema: a factual walkthrough of the student's own schema."""
    answer_log, _ = await _latest_attempt(exercise_id, current_user, db)
    _require_verdict(answer_log, correct=True)
    return await _run_action(
        "describe-schema", answer_log, db,
        action_describe_schema, answer_log.answer_text,
    )


@router.post("/api/exercises/{exercise_id}/explain-schema", response_model=LLMExplanationOut)
async def explain_schema(
    exercise_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Explain my schema: why the design suits the exercise's workload."""
    answer_log, exercise = await _latest_attempt(exercise_id, current_user, db)
    _require_verdict(answer_log, correct=True)
    workload = [query.query_text for query in exercise.queries]
    return await _run_action(
        "explain-schema", answer_log, db,
        action_explain_schema, answer_log.answer_text, exercise.answer.answer_text, workload,
    )


@router.post("/api/exercises/{exercise_id}/check-errors", response_model=LLMExplanationOut)
async def check_errors(
    exercise_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Does my schema have any errors? Explain the complications found by the engine."""
    answer_log, _ = await _latest_attempt(exercise_id, current_user, db)
    _require_verdict(answer_log, correct=True)
    return await _run_action(
        "check-errors", answer_log, db,
        action_check_errors, answer_log.answer_text, _complications(answer_log),
    )
