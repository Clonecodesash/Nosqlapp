import json
import os
import urllib.error
import urllib.request

import json_sm_parser as parser
from metadat_comparison import compare_metadata


def evaluate_aggregate_answer(student_answer: str, reference_answer: str):
    feedback = []

    try:
        student_aggregates = parse_answer(student_answer)
    except Exception as exc:
        return {
            "is_correct": False,
            "score": 0,
            "feedback": [f"STUDENT PARSE ERROR: {exc}"],
        }

    try:
        reference_aggregates = parse_answer(reference_answer)
    except Exception as exc:
        return {
            "is_correct": False,
            "score": 0,
            "feedback": [f"REFERENCE PARSE ERROR: {exc}"],
        }

    if not student_aggregates:
        feedback.append("STRUCTURE ERROR: Student answer does not contain any aggregate.")
    if not reference_aggregates:
        feedback.append("REFERENCE ERROR: Correct answer does not contain any aggregate.")

    student_by_name = {node.name.lower(): node for node in student_aggregates}
    reference_by_name = {node.name.lower(): node for node in reference_aggregates}

    for aggregate_name, reference_node in reference_by_name.items():
        student_node = student_by_name.get(aggregate_name)
        if student_node is None:
            feedback.append(f"STRUCTURE ERROR: Missing aggregate '{reference_node.name}'.")
            continue

        feedback.extend(compare_node(student_node, reference_node, reference_node.name))
        feedback.extend(compare_metadata(student_node, reference_node))

    for aggregate_name, student_node in student_by_name.items():
        if aggregate_name not in reference_by_name:
            feedback.append(f"STRUCTURE WARNING: Unexpected aggregate '{student_node.name}'.")

    error_count = sum(1 for item in feedback if "ERROR" in item)
    warning_count = sum(1 for item in feedback if "WARNING" in item)
    score = max(0, 100 - (error_count * 20) - (warning_count * 5))

    if not feedback:
        feedback.append("Correct aggregate model.")

    return {
        "is_correct": error_count == 0,
        "score": score,
        "feedback": feedback,
    }


def compare_node(student_node, reference_node, path):
    feedback = []

    if student_node.node_type != reference_node.node_type:
        feedback.append(
            f"STRUCTURE ERROR: Type mismatch at '{path}'. "
            f"Expected {reference_node.node_type}, got {student_node.node_type}."
        )

    student_children = keyed_children(student_node)
    reference_children = keyed_children(reference_node)

    for child_name, reference_child in reference_children.items():
        child_path = f"{path}.{reference_child.name}"
        student_child = student_children.get(child_name)
        if student_child is None:
            feedback.append(f"STRUCTURE ERROR: Missing field '{child_path}'.")
            continue
        feedback.extend(compare_node(student_child, reference_child, child_path))

    for child_name, student_child in student_children.items():
        if child_name not in reference_children:
            feedback.append(f"STRUCTURE WARNING: Unexpected field '{path}.{student_child.name}'.")

    return feedback


def keyed_children(node):
    return {child.name.lower(): child for child in node.children}


def parse_answer(answer_text):
    aggregate_chunks = parser.split_aggregates(answer_text)
    if "@metadata:" in answer_text or len(aggregate_chunks) <= 1:
        return [parser.parse_jsonsm(answer_text)]
    return parser.process_all_aggregates(answer_text)


def feedback_to_json(feedback):
    return json.dumps(feedback, ensure_ascii=False)


def feedback_from_json(feedback):
    if not feedback:
        return []
    try:
        return json.loads(feedback)
    except json.JSONDecodeError:
        return [feedback]


def explain_answer_with_llm(student_answer: str, reference_answer: str, feedback: list[str]):
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    model = os.getenv("OPENAI_MODEL", "gpt-5-mini").strip()
    prompt = (
        "Compare the student's aggregate modeling answer with the teacher's reference answer. "
        "Explain whether they match, what is correct, and what is different. "
        "Use clear student-friendly language. Keep it under 200 words.\n\n"
        f"Evaluation feedback:\n{json.dumps(feedback, ensure_ascii=False, indent=2)}\n\n"
        f"Student answer:\n{student_answer}\n\n"
        f"Teacher reference answer:\n{reference_answer}"
    )
    payload = {
        "model": model,
        "instructions": (
            "You are a teaching assistant for aggregate modeling exercises. "
            "Do not invent requirements. Base the explanation only on the provided answers and feedback."
        ),
        "input": prompt,
        "max_output_tokens": 500,
    }

    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"LLM request failed: {exc.code} {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"LLM request failed: {exc.reason}") from exc

    explanation = response_payload.get("output_text")
    if explanation:
        return explanation.strip()

    for output_item in response_payload.get("output", []):
        for content_item in output_item.get("content", []):
            if content_item.get("type") == "output_text" and content_item.get("text"):
                return content_item["text"].strip()

    raise RuntimeError("LLM response did not include explanation text")
