"""LLM button-action endpoints (explain error, hint, fix, describe, etc.)."""

import asyncio

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
    action_explain_error_briefly,
    action_explain_schema,
    action_explain_success,
    action_generate_corrected_schema,
    action_give_conceptual_hint,
)
from models import Exercise, StudentExerciseAnswerLog, User

router = APIRouter()


@router.post("/api/exercises/{exercise_id}/explain-error", response_model=LLMExplanationOut)
async def explain_error_briefly(
    exercise_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """LLM Button 1: Explain the error in student's answer."""
    # Both students and teachers may submit/evaluate, so teachers can test their own exercises.

    # Get latest answer log
    log_result = await db.execute(
        select(StudentExerciseAnswerLog)
        .where(
            StudentExerciseAnswerLog.exercise_id == exercise_id,
            StudentExerciseAnswerLog.student_id == current_user.id,
        )
        .order_by(StudentExerciseAnswerLog.created_at.desc())
        .limit(1)
    )
    answer_log = log_result.scalars().first()

    if answer_log is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No answer submitted yet")

    # Get exercise and reference answer
    ex_result = await db.execute(
        select(Exercise).where(Exercise.id == exercise_id).options(selectinload(Exercise.answer))
    )
    exercise = ex_result.scalars().first()

    if exercise is None or exercise.answer is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Exercise or reference answer not found")

    try:
        feedback = feedback_from_json(answer_log.evaluation_feedback)
        explanation = await asyncio.to_thread(
            action_explain_error_briefly,
            answer_log.answer_text,
            exercise.answer.answer_text,
            feedback,
        )

        # Mark that student used LLM
        answer_log.used_llm_explanation = True
        await db.commit()

        return {"explanation": explanation}
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))


@router.post("/api/exercises/{exercise_id}/give-hint", response_model=LLMExplanationOut)
async def give_conceptual_hint(
    exercise_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """LLM Button 2: Give a conceptual hint to guide student."""
    # Both students and teachers may submit/evaluate, so teachers can test their own exercises.

    # Get latest answer log
    log_result = await db.execute(
        select(StudentExerciseAnswerLog)
        .where(
            StudentExerciseAnswerLog.exercise_id == exercise_id,
            StudentExerciseAnswerLog.student_id == current_user.id,
        )
        .order_by(StudentExerciseAnswerLog.created_at.desc())
        .limit(1)
    )
    answer_log = log_result.scalars().first()

    if answer_log is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No answer submitted yet")

    # Get exercise and reference answer
    ex_result = await db.execute(
        select(Exercise).where(Exercise.id == exercise_id).options(selectinload(Exercise.answer))
    )
    exercise = ex_result.scalars().first()

    if exercise is None or exercise.answer is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Exercise or reference answer not found")

    try:
        feedback = feedback_from_json(answer_log.evaluation_feedback)
        hint = await asyncio.to_thread(
            action_give_conceptual_hint,
            answer_log.answer_text,
            exercise.answer.answer_text,
            feedback,
        )

        # Mark that student used hint
        answer_log.used_hint = True
        await db.commit()

        return {"explanation": hint}
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))


@router.post("/api/exercises/{exercise_id}/fix-schema", response_model=LLMExplanationOut)
async def fix_schema(
    exercise_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """LLM Button 3: Generate corrected schema from student's answer."""
    # Both students and teachers may submit/evaluate, so teachers can test their own exercises.

    # Get latest answer log
    log_result = await db.execute(
        select(StudentExerciseAnswerLog)
        .where(
            StudentExerciseAnswerLog.exercise_id == exercise_id,
            StudentExerciseAnswerLog.student_id == current_user.id,
        )
        .order_by(StudentExerciseAnswerLog.created_at.desc())
        .limit(1)
    )
    answer_log = log_result.scalars().first()

    if answer_log is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No answer submitted yet")

    # Get exercise and reference answer
    ex_result = await db.execute(
        select(Exercise).where(Exercise.id == exercise_id).options(selectinload(Exercise.answer))
    )
    exercise = ex_result.scalars().first()

    if exercise is None or exercise.answer is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Exercise or reference answer not found")

    try:
        feedback = feedback_from_json(answer_log.evaluation_feedback)
        corrected = await asyncio.to_thread(
            action_generate_corrected_schema,
            answer_log.answer_text,
            exercise.answer.answer_text,
            feedback,
        )

        # Mark that student used LLM
        answer_log.used_llm_explanation = True
        await db.commit()

        return {"explanation": corrected}
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))


@router.post("/api/exercises/{exercise_id}/explain-success", response_model=LLMExplanationOut)
async def explain_success(
    exercise_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """LLM Button 4: Explain why the answer is correct (for perfect submissions)."""
    # Both students and teachers may submit/evaluate, so teachers can test their own exercises.

    # Get latest answer log
    log_result = await db.execute(
        select(StudentExerciseAnswerLog)
        .where(
            StudentExerciseAnswerLog.exercise_id == exercise_id,
            StudentExerciseAnswerLog.student_id == current_user.id,
        )
        .order_by(StudentExerciseAnswerLog.created_at.desc())
        .limit(1)
    )
    answer_log = log_result.scalars().first()

    if answer_log is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No answer submitted yet")
    if not answer_log.is_correct:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Answer is not correct")

    # Get exercise and reference answer
    ex_result = await db.execute(
        select(Exercise).where(Exercise.id == exercise_id).options(selectinload(Exercise.answer))
    )
    exercise = ex_result.scalars().first()

    if exercise is None or exercise.answer is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Exercise or reference answer not found")

    try:
        explanation = await asyncio.to_thread(
            action_explain_success,
            answer_log.answer_text,
            exercise.answer.answer_text,
        )

        return {"explanation": explanation}
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))


async def _latest_answer_and_exercise(exercise_id: int, current_user: User, db: AsyncSession):
    """Shared lookup for the schema-review LLM buttons: latest submission + reference answer."""
    log_result = await db.execute(
        select(StudentExerciseAnswerLog)
        .where(
            StudentExerciseAnswerLog.exercise_id == exercise_id,
            StudentExerciseAnswerLog.student_id == current_user.id,
        )
        .order_by(StudentExerciseAnswerLog.created_at.desc())
        .limit(1)
    )
    answer_log = log_result.scalars().first()
    if answer_log is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No answer submitted yet")

    ex_result = await db.execute(
        select(Exercise).where(Exercise.id == exercise_id).options(selectinload(Exercise.answer))
    )
    exercise = ex_result.scalars().first()
    if exercise is None or exercise.answer is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Exercise or reference answer not found")

    return answer_log, exercise


@router.post("/api/exercises/{exercise_id}/describe-schema", response_model=LLMExplanationOut)
async def describe_schema(
    exercise_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """LLM Button: Describe the student's aggregate schema (structural walkthrough)."""
    answer_log, exercise = await _latest_answer_and_exercise(exercise_id, current_user, db)
    try:
        explanation = await asyncio.to_thread(
            action_describe_schema,
            answer_log.answer_text,
            exercise.answer.answer_text,
        )
        return {"explanation": explanation}
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))


@router.post("/api/exercises/{exercise_id}/explain-schema", response_model=LLMExplanationOut)
async def explain_schema(
    exercise_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """LLM Button: Explain the design rationale of the student's schema."""
    answer_log, exercise = await _latest_answer_and_exercise(exercise_id, current_user, db)
    try:
        explanation = await asyncio.to_thread(
            action_explain_schema,
            answer_log.answer_text,
            exercise.answer.answer_text,
        )
        return {"explanation": explanation}
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))


@router.post("/api/exercises/{exercise_id}/check-errors", response_model=LLMExplanationOut)
async def check_errors(
    exercise_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """LLM Button: Review the student's schema for errors."""
    answer_log, exercise = await _latest_answer_and_exercise(exercise_id, current_user, db)
    try:
        explanation = await asyncio.to_thread(
            action_check_errors,
            answer_log.answer_text,
            exercise.answer.answer_text,
        )
        return {"explanation": explanation}
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
