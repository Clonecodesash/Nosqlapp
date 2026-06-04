import enum

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship


Base = declarative_base()


class UserRole(str, enum.Enum):
    student = "student"
    teacher = "teacher"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    role = Column(Enum(UserRole))

    er_schemas = relationship("ERSchema", back_populates="teacher")
    exercises = relationship("Exercise", back_populates="teacher")
    answer_logs = relationship("StudentExerciseAnswerLog", back_populates="student")


class ERSchema(Base):
    __tablename__ = "er_schemas"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)                  # e.g., "E-Commerce System Diagram"
    image_url = Column(String, nullable=False)             # Cloud/S3 storage URL path
    image_s3_key = Column(String, nullable=True)           # S3 key name for structural deletion
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    
    teacher = relationship("User", back_populates="er_schemas")
    exercises = relationship(
        "Exercise", 
        back_populates="er_schema", 
        cascade="all, delete-orphan"
    )


class Exercise(Base):
    __tablename__ = "exercises"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)                  # e.g., "Task A: Customer Profile Nesting"
    er_schema_id = Column(Integer, ForeignKey("er_schemas.id"), nullable=False, index=True)
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

   
    er_schema = relationship("ERSchema", back_populates="exercises")
    teacher = relationship("User", back_populates="exercises")
    queries = relationship(
        "Query", 
        back_populates="exercise", 
        cascade="all, delete-orphan"
    )
    answer = relationship(
        "ExerciseAnswer", 
        back_populates="exercise", 
        cascade="all, delete-orphan", 
        uselist=False
    )
    student_answer_logs = relationship(
        "StudentExerciseAnswerLog", 
        back_populates="exercise", 
        cascade="all, delete-orphan",
        order_by="desc(StudentExerciseAnswerLog.created_at)"
    )


class Query(Base):
    """
    Bottom Level Asset: The individual English queries that guide the aggregate schema design.
    """
    __tablename__ = "queries"

    id = Column(Integer, primary_key=True, index=True)
    query_text = Column(Text, nullable=False)              # e.g., "Find all orders placed by a specific user"
    hint = Column(Text, nullable=True)                    # Optional hint provided by instructor
    exercise_id = Column(Integer, ForeignKey("exercises.id"), nullable=False, index=True)

    # Relationships
    exercise = relationship("Exercise", back_populates="queries")


class ExerciseAnswer(Base):
    """
    The Official Solution: Stores the teacher's reference model script for the exercise.
    """
    __tablename__ = "exercise_answers"

    id = Column(Integer, primary_key=True, index=True)
    answer_text = Column(Text, nullable=False)             # Master target structure (JSON-SM / Script)
    exercise_id = Column(Integer, ForeignKey("exercises.id"), unique=True, nullable=False, index=True)

    # Relationships
    exercise = relationship("Exercise", back_populates="answer")



class StudentExerciseAnswerLog(Base):
    """
    Tracks every singular attempt from a student, including structural parsing outcomes,
    evaluation outputs, and interaction with support modules (Hints and LLM generation).
    """
    __tablename__ = "student_exercise_answer_logs"

    id = Column(Integer, primary_key=True, index=True)
    answer_text = Column(Text, nullable=False)             # The raw schema string submission from the student
    
    # Structural Parsing feedback (Evaluation Engine Outputs)
    evaluation_feedback = Column(Text, nullable=True)       # Stringified array of errors (e.g., '["Missing ID link", "Unnested collection"]')
    evaluation_score = Column(Integer, nullable=True)      # Numeric assessment grade mapping 
    is_correct = Column(Boolean, nullable=True)            # Flag indicating a perfect structural pass

    # Granular Student Intervention Metrics (Critical Metrics for Thesis Chapter 4/5 Analytics)
    attempt_number = Column(Integer, nullable=False, default=1)           # Identifies iterative progression (1st, 2nd, 3rd try)
    used_hint = Column(Boolean, default=False, nullable=False)            # Checked static query hints
    used_llm_explanation = Column(Boolean, default=False, nullable=False) # Invoked generative system feedback wrapper
    llm_explanation_text = Column(Text, nullable=True)                     # Preserves snapshot of generative advice provided

    # System Tracking Foreign Keys
    exercise_id = Column(Integer, ForeignKey("exercises.id"), nullable=False, index=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    exercise = relationship("Exercise", back_populates="student_answer_logs")
    student = relationship("User", back_populates="answer_logs")