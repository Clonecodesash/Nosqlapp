"""Convert ORM objects into the dict shapes returned by the API."""

from evaluation import feedback_from_json
from models import ERSchema, Exercise, User, UserRole
from s3_utils import get_display_image_url


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
