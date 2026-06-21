"""Pydantic request/response models (data transfer objects) for the API."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from models import UserRole


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
