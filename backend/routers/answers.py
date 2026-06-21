"""Student answer submission and correct-answer retrieval."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from auth import get_current_user
from database import get_db
from dto import CorrectAnswerOut, StudentExerciseAnswerLogOut, StudentExerciseAnswerSubmit
from evaluation import evaluate_aggregate_answer, feedback_to_json
from models import Exercise, StudentExerciseAnswerLog, User, UserRole

router = APIRouter()


@router.post(
    "/api/exercises/{exercise_id}/answers",
    response_model=StudentExerciseAnswerLogOut,
    status_code=status.HTTP_201_CREATED,
)
async def submit_exercise_answer(
    exercise_id: int,
    answer_data: StudentExerciseAnswerSubmit,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Submit a student answer for an exercise."""
    # Both students and teachers may submit/evaluate, so teachers can test their own exercises.

    result = await db.execute(
        select(Exercise)
        .where(Exercise.id == exercise_id)
        .options(selectinload(Exercise.answer))
    )
    exercise = result.scalars().first()

    if exercise is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exercise not found")
    if exercise.answer is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Exercise has no reference answer")

    # Evaluate the answer
    evaluation = evaluate_aggregate_answer(answer_data.answer_text, exercise.answer.answer_text)

    # Get attempt number
    attempt_result = await db.execute(
        select(StudentExerciseAnswerLog)
        .where(StudentExerciseAnswerLog.exercise_id == exercise_id, StudentExerciseAnswerLog.student_id == current_user.id)
        .order_by(StudentExerciseAnswerLog.attempt_number.desc())
        .limit(1)
    )
    last_attempt = attempt_result.scalars().first()
    attempt_number = (last_attempt.attempt_number + 1) if last_attempt else 1

    # Create answer log
    answer_log = StudentExerciseAnswerLog(
        exercise_id=exercise_id,
        student_id=current_user.id,
        answer_text=answer_data.answer_text,
        evaluation_feedback=feedback_to_json(evaluation["feedback"]),
        evaluation_score=evaluation["score"],
        is_correct=evaluation["is_correct"],
        attempt_number=attempt_number,
    )

    db.add(answer_log)
    await db.commit()
    await db.refresh(answer_log)

    return {
        "id": answer_log.id,
        "answer": answer_log.answer_text,
        "exerciseId": answer_log.exercise_id,
        "studentId": answer_log.student_id,
        "createdAt": answer_log.created_at,
        "score": answer_log.evaluation_score,
        "isCorrect": answer_log.is_correct,
        "feedback": evaluation["feedback"],
        "attemptNumber": answer_log.attempt_number,
        "usedHint": answer_log.used_hint,
        "usedLlmExplanation": answer_log.used_llm_explanation,
    }


@router.get("/api/exercises/{exercise_id}/correct-answer", response_model=CorrectAnswerOut)
async def get_correct_answer(
    exercise_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the correct answer for an exercise (student must have submitted first)."""
    result = await db.execute(
        select(Exercise)
        .where(Exercise.id == exercise_id)
        .options(selectinload(Exercise.answer))
    )
    exercise = result.scalars().first()

    if exercise is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exercise not found")
    if exercise.answer is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Exercise has no reference answer")

    # Students must have submitted before viewing
    if current_user.role == UserRole.student:
        log_result = await db.execute(
            select(StudentExerciseAnswerLog.id)
            .where(
                StudentExerciseAnswerLog.exercise_id == exercise_id,
                StudentExerciseAnswerLog.student_id == current_user.id,
            )
            .limit(1)
        )
        if log_result.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Submit an answer before viewing the correct answer",
            )

    return {"answer": exercise.answer.answer_text}
