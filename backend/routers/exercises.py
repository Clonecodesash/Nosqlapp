"""Exercise CRUD and listing endpoints."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from auth import get_current_user, require_teacher
from database import get_db
from dto import ExerciseCreate, ExerciseOut
from models import ERSchema, Exercise, ExerciseAnswer, Query, User, UserRole
from serializers import serialize_exercise

router = APIRouter()


@router.post("/api/exercises", response_model=ExerciseOut, status_code=status.HTTP_201_CREATED)
async def create_exercise(
    payload: ExerciseCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new exercise under an ER schema (teacher only)."""
    require_teacher(current_user)

    # Any teacher may add exercises under any schema; the exercise is owned by its creator.
    schema_result = await db.execute(select(ERSchema).where(ERSchema.id == payload.er_schema_id))
    schema = schema_result.scalars().first()
    if schema is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schema not found")

    if not payload.queries:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Exercise must have at least one query")

    exercise = Exercise(
        name=payload.name,
        er_schema_id=payload.er_schema_id,
        teacher_id=current_user.id,
    )
    exercise.queries = [
        Query(query_text=query.query_text, hint=query.hint)
        for query in payload.queries
    ]
    exercise.answer = ExerciseAnswer(answer_text=payload.answer_text)

    db.add(exercise)
    await db.commit()

    result = await db.execute(
        select(Exercise)
        .where(Exercise.id == exercise.id)
        .options(
            selectinload(Exercise.queries),
            selectinload(Exercise.answer),
            selectinload(Exercise.student_answer_logs),
        )
    )
    return serialize_exercise(result.scalars().first(), current_user)


@router.get("/api/exercises", response_model=List[ExerciseOut])
async def list_exercises(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all exercises."""
    options = [selectinload(Exercise.queries)]
    if current_user.role == UserRole.teacher:
        options.extend([selectinload(Exercise.answer), selectinload(Exercise.student_answer_logs)])

    result = await db.execute(select(Exercise).options(*options).order_by(Exercise.id.desc()))
    return [serialize_exercise(exercise, current_user) for exercise in result.scalars().all()]


@router.get("/api/schemas/{schema_id}/exercises", response_model=List[ExerciseOut])
async def list_exercises_for_schema(
    schema_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all exercises belonging to a specific ER schema."""
    schema_result = await db.execute(select(ERSchema).where(ERSchema.id == schema_id))
    if schema_result.scalars().first() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schema not found")

    options = [selectinload(Exercise.queries)]
    if current_user.role == UserRole.teacher:
        options.extend([selectinload(Exercise.answer), selectinload(Exercise.student_answer_logs)])

    result = await db.execute(
        select(Exercise)
        .where(Exercise.er_schema_id == schema_id)
        .options(*options)
        .order_by(Exercise.id.desc())
    )
    return [serialize_exercise(exercise, current_user) for exercise in result.scalars().all()]


@router.get("/api/exercises/{exercise_id}", response_model=ExerciseOut)
async def get_exercise(
    exercise_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific exercise."""
    result = await db.execute(
        select(Exercise)
        .where(Exercise.id == exercise_id)
        .options(
            selectinload(Exercise.queries),
            selectinload(Exercise.answer),
            selectinload(Exercise.student_answer_logs),
        )
    )
    exercise = result.scalars().first()
    if exercise is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exercise not found")

    return serialize_exercise(exercise, current_user)


@router.put("/api/exercises/{exercise_id}", response_model=ExerciseOut)
async def update_exercise(
    exercise_id: int,
    payload: ExerciseCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update an exercise (teacher only)."""
    require_teacher(current_user)

    if not payload.queries:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Exercise must have at least one query")

    result = await db.execute(
        select(Exercise)
        .where(Exercise.id == exercise_id)
        .options(
            selectinload(Exercise.queries),
            selectinload(Exercise.answer),
            selectinload(Exercise.student_answer_logs),
        )
    )
    exercise = result.scalars().first()

    if exercise is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exercise not found")
    if exercise.teacher_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the owner teacher can edit this exercise")

    exercise.name = payload.name

    if exercise.answer is None:
        exercise.answer = ExerciseAnswer(answer_text=payload.answer_text)
    else:
        exercise.answer.answer_text = payload.answer_text

    exercise.queries = [
        Query(query_text=query.query_text, hint=query.hint)
        for query in payload.queries
    ]

    await db.commit()

    updated_result = await db.execute(
        select(Exercise)
        .where(Exercise.id == exercise_id)
        .options(
            selectinload(Exercise.queries),
            selectinload(Exercise.answer),
            selectinload(Exercise.student_answer_logs),
        )
    )
    return serialize_exercise(updated_result.scalars().first(), current_user)


@router.delete("/api/exercises/{exercise_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_exercise(
    exercise_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete an exercise (teacher only)."""
    require_teacher(current_user)

    result = await db.execute(select(Exercise).where(Exercise.id == exercise_id))
    exercise = result.scalars().first()

    if exercise is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exercise not found")
    if exercise.teacher_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the owner teacher can delete this exercise")

    await db.delete(exercise)
    await db.commit()
