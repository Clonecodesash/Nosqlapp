from datetime import datetime
import asyncio
import json
import aggregate_evaluator
from mimetypes import guess_extension
from uuid import uuid4
from typing import List, Optional

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import selectinload, sessionmaker
from sqlalchemy.future import select
from sqlalchemy import text
from passlib.context import CryptContext
from jose import JWTError, jwt
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from dotenv import load_dotenv
import os
from pathlib import Path

from models import Base, ERSchema, Exercise, ExerciseAnswer, Query, StudentExerciseAnswerLog, User, UserRole
from aggregate_evaluator import (
    evaluate_schemas,
    action_explain_error_briefly,
    action_give_conceptual_hint,
    action_generate_corrected_schema,
    action_explain_success,
)
from json_sm_parser import parse_jsonsm

load_dotenv(Path(__file__).resolve().parent / ".env")
load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]
SECRET_KEY = os.environ["SECRET_KEY"]
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
AWS_REGION = os.getenv("AWS_REGION", "ap-northeast-1").strip()
AWS_S3_BUCKET = os.getenv("AWS_S3_BUCKET", "").strip()
AWS_S3_PUBLIC_BASE_URL = os.getenv("AWS_S3_PUBLIC_BASE_URL", "").strip()
AWS_S3_PRESIGNED_URL_EXPIRES_SECONDS = int(os.getenv("AWS_S3_PRESIGNED_URL_EXPIRES_SECONDS", "3600"))
SUPPORTED_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
}

engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# =====================================================================
# PYDANTIC MODELS
# =====================================================================

class UserCreate(BaseModel):
    username: str
    password: str = Field(..., min_length=6, max_length=72)
    role: UserRole


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    role: UserRole


class Token(BaseModel):
    access_token: str
    token_type: str


class QueryCreate(BaseModel):
    model_config = ConfigDict(validate_by_name=True)

    query_text: str = Field(..., alias="queryText")
    hint: Optional[str] = None


class QueryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, validate_by_name=True)

    id: int
    query_text: str = Field(..., alias="queryText")
    exercise_id: int = Field(..., alias="exerciseId")
    hint: Optional[str] = None


class ExerciseAnswerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, validate_by_name=True)

    id: int
    answer_text: str = Field(..., alias="answer")
    exercise_id: int = Field(..., alias="exerciseId")


class StudentExerciseAnswerSubmit(BaseModel):
    answer_text: str = Field(..., alias="answer")


class StudentExerciseAnswerLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, validate_by_name=True)

    id: int
    answer_text: str = Field(..., alias="answer")
    exercise_id: int = Field(..., alias="exerciseId")
    student_id: int = Field(..., alias="studentId")
    created_at: datetime = Field(..., alias="createdAt")
    evaluation_score: Optional[int] = Field(None, alias="score")
    is_correct: Optional[bool] = Field(None, alias="isCorrect")
    feedback: List[str] = Field(default_factory=list)
    attempt_number: int = Field(default=1, alias="attemptNumber")
    used_hint: bool = Field(default=False, alias="usedHint")
    used_llm_explanation: bool = Field(default=False, alias="usedLlmExplanation")


class CorrectAnswerOut(BaseModel):
    answer: str


class LLMExplanationOut(BaseModel):
    explanation: str


class ERSchemaCreate(BaseModel):
    model_config = ConfigDict(validate_by_name=True)

    name: str


class ERSchemaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, validate_by_name=True)

    id: int
    name: str
    image_url: str = Field(..., alias="image")
    image_s3_key: Optional[str] = Field(None, alias="imageS3Key")
    teacher_id: int = Field(..., alias="teacherId")


class ExerciseCreate(BaseModel):
    model_config = ConfigDict(validate_by_name=True)

    name: str
    er_schema_id: int = Field(..., alias="schemaId")
    queries: List[QueryCreate]
    answer_text: str = Field(..., alias="answer")


class ExerciseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, validate_by_name=True)

    id: int
    name: str
    er_schema_id: int = Field(..., alias="schemaId")
    teacher_id: int = Field(..., alias="teacherId")
    queries: List[QueryOut]
    answer: Optional[ExerciseAnswerOut] = None
    student_answer_logs: List[StudentExerciseAnswerLogOut] = Field(default_factory=list, alias="studentAnswers")


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/token")

app = FastAPI()


# =====================================================================
# DATABASE & AUTH SETUP
# =====================================================================

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


@app.on_event("startup")
async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_user_by_username(db: AsyncSession, username: str):
    result = await db.execute(select(User).where(User.username == username))
    return result.scalars().first()


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


def create_access_token(data: dict):
    return jwt.encode(data, SECRET_KEY, algorithm=ALGORITHM)


async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = await get_user_by_username(db, username)
    if user is None:
        raise credentials_exception
    return user


def require_teacher(user: User):
    if user.role != UserRole.teacher:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only teachers can perform this action")


def require_student(user: User):
    if user.role != UserRole.student:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only students can perform this action")


# =====================================================================
# S3 HELPERS
# =====================================================================

def require_s3_config():
    if not AWS_S3_BUCKET:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="AWS_S3_BUCKET is not configured")
    if not os.getenv("AWS_ACCESS_KEY_ID") or not os.getenv("AWS_SECRET_ACCESS_KEY"):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="AWS credentials are not configured")


def build_s3_public_url(object_key: str):
    if AWS_S3_PUBLIC_BASE_URL:
        return f"{AWS_S3_PUBLIC_BASE_URL.rstrip('/')}/{object_key}"
    return f"https://{AWS_S3_BUCKET}.s3.{AWS_REGION}.amazonaws.com/{object_key}"


def build_s3_uri(object_key: str):
    return f"s3://{AWS_S3_BUCKET}/{object_key}"


def create_s3_client():
    return boto3.client("s3", region_name=AWS_REGION, config=Config(signature_version="s3v4"))


def get_display_image_url(er_schema: ERSchema):
    if not er_schema.image_s3_key:
        return er_schema.image_url
    return create_presigned_image_url(er_schema.image_s3_key)


def create_presigned_image_url(object_key: str):
    require_s3_config()
    try:
        return create_s3_client().generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": AWS_S3_BUCKET, "Key": object_key},
            ExpiresIn=AWS_S3_PRESIGNED_URL_EXPIRES_SECONDS,
        )
    except ClientError as exc:
        error = exc.response.get("Error", {})
        code = error.get("Code", "ClientError")
        message = error.get("Message", "Failed to create image URL")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to create S3 image URL: {code} - {message}",
        )
    except BotoCoreError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to create S3 image URL: {type(exc).__name__}",
        )


async def read_uploaded_image(image: UploadFile):
    content_type = image.content_type or ""
    if content_type not in SUPPORTED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded image must be JPG, PNG, WebP, or GIF. HEIC is not supported by most browsers.",
        )

    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Image file is required")
    if len(image_bytes) > 5 * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Image must be 5MB or smaller")

    return image_bytes, content_type


def upload_image_to_s3(image_bytes: bytes, content_type: str):
    require_s3_config()
    extension = guess_extension(content_type) or ".bin"
    object_key = f"schemas/{uuid4().hex}{extension}"
    s3_client = create_s3_client()

    try:
        s3_client.put_object(
            Bucket=AWS_S3_BUCKET,
            Key=object_key,
            Body=image_bytes,
            ContentType=content_type,
        )
    except ClientError as exc:
        error = exc.response.get("Error", {})
        code = error.get("Code", "ClientError")
        message = error.get("Message", "Failed to upload image to S3")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to upload image to S3: {code} - {message}",
        )
    except BotoCoreError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to upload image to S3: {type(exc).__name__}",
        )

    return object_key, build_s3_uri(object_key)


# =====================================================================
# EVALUATION & LLM HELPERS
# =====================================================================

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


def serialize_er_schema(schema: ERSchema):
    """Serialize ERSchema for API response."""
    return {
        "id": schema.id,
        "name": schema.name,
        "image": get_display_image_url(schema),
        "imageS3Key": schema.image_s3_key,
        "teacherId": schema.teacher_id,
    }


def serialize_exercise(exercise: Exercise, current_user: User):
    """Serialize Exercise for API response, showing only appropriate data based on user role."""
    payload = {
        "id": exercise.id,
        "name": exercise.name,
        "schemaId": exercise.er_schema_id,
        "teacherId": exercise.teacher_id,
        "queries": [
            {
                "id": query.id,
                "queryText": query.query_text,
                "exerciseId": query.exercise_id,
                "hint": query.hint,
            }
            for query in exercise.queries
        ],
        "answer": None,
        "studentAnswers": [],
    }
    
    if current_user.role == UserRole.teacher:
        if exercise.answer:
            payload["answer"] = {
                "id": exercise.answer.id,
                "answer": exercise.answer.answer_text,
                "exerciseId": exercise.answer.exercise_id,
            }
        payload["studentAnswers"] = [
            {
                "id": answer_log.id,
                "answer": answer_log.answer_text,
                "exerciseId": answer_log.exercise_id,
                "studentId": answer_log.student_id,
                "createdAt": answer_log.created_at.isoformat(),
                "score": answer_log.evaluation_score,
                "isCorrect": answer_log.is_correct,
                "feedback": feedback_from_json(answer_log.evaluation_feedback),
                "attemptNumber": answer_log.attempt_number,
                "usedHint": answer_log.used_hint,
                "usedLlmExplanation": answer_log.used_llm_explanation,
            }
            for answer_log in exercise.student_answer_logs
        ]
    
    return payload


# =====================================================================
# ENDPOINTS: AUTH
# =====================================================================

@app.post("/api/register", response_model=UserOut)
async def register(user: UserCreate, db: AsyncSession = Depends(get_db)):
    """Register a new user."""
    db_user = await get_user_by_username(db, user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    hashed_password = get_password_hash(user.password)
    new_user = User(username=user.username, hashed_password=hashed_password, role=user.role)
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user


@app.post("/api/token", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    """Login and get JWT token."""
    user = await get_user_by_username(db, form_data.username)
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")
    
    access_token = create_access_token({"sub": user.username, "role": user.role.value})
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/api/me", response_model=UserOut)
async def read_users_me(current_user: User = Depends(get_current_user)):
    """Get current user info."""
    return current_user


# =====================================================================
# ENDPOINTS: ER SCHEMAS
# =====================================================================

@app.post("/api/schemas", response_model=ERSchemaOut, status_code=status.HTTP_201_CREATED)
async def create_schema(
    name: str = Form(...),
    image: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new ER schema (teacher only)."""
    require_teacher(current_user)
    
    image_bytes, image_content_type = await read_uploaded_image(image)
    image_s3_key, image_url = upload_image_to_s3(image_bytes, image_content_type)
    
    schema = ERSchema(
        name=name,
        image_url=image_url,
        image_s3_key=image_s3_key,
        teacher_id=current_user.id,
    )
    db.add(schema)
    await db.commit()
    await db.refresh(schema)
    
    return serialize_er_schema(schema)


@app.get("/api/schemas", response_model=List[ERSchemaOut])
async def list_schemas(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all ER schemas visible to the current user."""
    result = await db.execute(select(ERSchema).order_by(ERSchema.id.desc()))
    return [serialize_er_schema(schema) for schema in result.scalars().all()]


@app.get("/api/schemas/{schema_id}", response_model=ERSchemaOut)
async def get_schema(
    schema_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific ER schema."""
    result = await db.execute(select(ERSchema).where(ERSchema.id == schema_id))
    schema = result.scalars().first()
    
    if schema is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schema not found")
    
    return serialize_er_schema(schema)


@app.put("/api/schemas/{schema_id}", response_model=ERSchemaOut)
async def update_schema(
    schema_id: int,
    name: str = Form(...),
    image: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update an ER schema (teacher only)."""
    require_teacher(current_user)
    
    result = await db.execute(select(ERSchema).where(ERSchema.id == schema_id))
    schema = result.scalars().first()
    
    if schema is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schema not found")
    if schema.teacher_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the owner teacher can edit this schema")
    
    schema.name = name
    
    if image is not None and image.filename:
        image_bytes, image_content_type = await read_uploaded_image(image)
        image_s3_key, image_url = upload_image_to_s3(image_bytes, image_content_type)
        schema.image_s3_key = image_s3_key
        schema.image_url = image_url
    
    await db.commit()
    await db.refresh(schema)
    
    return serialize_er_schema(schema)


@app.delete("/api/schemas/{schema_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schema(
    schema_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete an ER schema (teacher only)."""
    require_teacher(current_user)
    
    result = await db.execute(select(ERSchema).where(ERSchema.id == schema_id))
    schema = result.scalars().first()
    
    if schema is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schema not found")
    if schema.teacher_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the owner teacher can delete this schema")
    
    await db.delete(schema)
    await db.commit()


# =====================================================================
# ENDPOINTS: EXERCISES
# =====================================================================

@app.post("/api/exercises", response_model=ExerciseOut, status_code=status.HTTP_201_CREATED)
async def create_exercise(
    payload: ExerciseCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new exercise under an ER schema (teacher only)."""
    require_teacher(current_user)

    # Verify schema exists and belongs to current user
    schema_result = await db.execute(select(ERSchema).where(ERSchema.id == payload.er_schema_id))
    schema = schema_result.scalars().first()
    if schema is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schema not found")
    if schema.teacher_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Can only create exercises under your own schemas")

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


@app.get("/api/exercises", response_model=List[ExerciseOut])
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


@app.get("/api/schemas/{schema_id}/exercises", response_model=List[ExerciseOut])
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


@app.get("/api/exercises/{exercise_id}", response_model=ExerciseOut)
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


@app.put("/api/exercises/{exercise_id}", response_model=ExerciseOut)
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


@app.delete("/api/exercises/{exercise_id}", status_code=status.HTTP_204_NO_CONTENT)
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


# =====================================================================
# ENDPOINTS: STUDENT ANSWERS & EVALUATION
# =====================================================================

@app.post(
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
    require_student(current_user)
    
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


@app.get("/api/exercises/{exercise_id}/correct-answer", response_model=CorrectAnswerOut)
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


# =====================================================================
# ENDPOINTS: LLM BUTTON ACTIONS
# =====================================================================

@app.post("/api/exercises/{exercise_id}/explain-error", response_model=LLMExplanationOut)
async def explain_error_briefly(
    exercise_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """LLM Button 1: Explain the error in student's answer."""
    require_student(current_user)
    
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


@app.post("/api/exercises/{exercise_id}/give-hint", response_model=LLMExplanationOut)
async def give_conceptual_hint(
    exercise_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """LLM Button 2: Give a conceptual hint to guide student."""
    require_student(current_user)
    
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


@app.post("/api/exercises/{exercise_id}/fix-schema", response_model=LLMExplanationOut)
async def fix_schema(
    exercise_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """LLM Button 3: Generate corrected schema from student's answer."""
    require_student(current_user)
    
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


@app.post("/api/exercises/{exercise_id}/explain-success", response_model=LLMExplanationOut)
async def explain_success(
    exercise_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """LLM Button 4: Explain why the answer is correct (for perfect submissions)."""
    require_student(current_user)
    
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


@app.get("/api/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}
