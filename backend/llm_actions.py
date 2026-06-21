"""
LLM button-action functions for the aggregate-modelling exercises.

Each action builds a system prompt + user prompt and calls the OpenAI Responses
API. These were split out of aggregate_evaluator.py so the structural evaluator
stays free of any network/LLM concerns.
"""

import json
import os
import urllib.error
import urllib.request


# =====================================================================
# LLM TRANSPORT HELPERS
# =====================================================================

def get_openai_client_config():
    """Helper to fetch common environment configs."""
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    model = os.getenv("OPENAI_MODEL", "gpt-5-mini").strip()
    return api_key, model


def _call_llm_api(system_instructions: str, prompt: str) -> str:
    """Internal helper engine to execute HTTP urllib standard requests to OpenAI."""
    api_key, model = get_openai_client_config()

    payload = {
        "model": model,
        "instructions": system_instructions,
        "input": prompt,
        "max_output_tokens": 600,
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

            # Read textual fields safely from the API response layout
            explanation = response_payload.get("output_text")
            if explanation:
                return explanation.strip()
            for output_item in response_payload.get("output", []):
                for content_item in output_item.get("content", []):
                    if content_item.get("type") == "output_text" and content_item.get("text"):
                        return content_item["text"].strip()
            raise RuntimeError("LLM response did not include output text")

    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"LLM request failed: {exc.code} {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"LLM request failed: {exc.reason}") from exc


# =====================================================================
# THE INDEPENDENT LLM BUTTON CALL FUNCTIONS
# =====================================================================

# --- BUTTON ACTION 1: Explain Error ---
def action_explain_error_briefly(student_answer: str, reference_answer: str, feedback: list[str]) -> str:
    """
    Triggers when the student clicks 'Explain Error'.
    Translates automated structural feedback list items into plain, non-technical English descriptions.
    """
    system_instructions = (
        "You are an objective aggregate modeling teaching assistant. Your sole job is to decipher "
        "the raw evaluation feedback array for the student. "
        "Explain what positional mismatches, extra items, or missing fields occurred in clear, "
        "jargon-free language. Keep it brief, factual, and under 100 words. "
        "Do not offer suggestions, fixes, or solutions yet."
    )

    prompt = (
        f"Automated evaluation feedback codes:\n{json.dumps(feedback, indent=2)}\n\n"
        f"Student's submission:\n{student_answer}\n\n"
        "Explain these specific structural errors to the student briefly."
    )
    return _call_llm_api(system_instructions, prompt)


# --- BUTTON ACTION 2: Give Me a Hint ---
def action_give_conceptual_hint(student_answer: str, reference_answer: str, feedback: list[str]) -> str:
    """
    Triggers when the student clicks 'Give Me a Hint'.
    Provides educational cues regarding positioning or layout rules without altering raw scripts.
    """
    system_instructions = (
        "You are an encouraging mentor. Do not tell the student exactly what failed, and "
        "NEVER provide code blocks or modified schemas. Instead, look at the reference structure "
        "and the student's errors, and give them a strategic design hint or puzzle-solving clue "
        "(e.g., 'Check if you nested a collection too deeply inside your main block' or "
        "'Look at the order of fields in your root object'). Keep it under  words."
    )

    prompt = (
        f"Student's Attempt:\n{student_answer}\n\n"
        f"Teacher's Target Layout:\n{reference_answer}\n\n"
        f"Error Context:\n{json.dumps(feedback, indent=2)}\n\n"
        "Give the student one actionable, conceptual hint to steer them in the right direction."
    )
    return _call_llm_api(system_instructions, prompt)


# --- BUTTON ACTION 3: Fix My Schema ---
def action_generate_corrected_schema(student_answer: str, reference_answer: str, feedback: list[str]) -> str:
    """
    Triggers when the student clicks 'Fix My Schema'.
    Returns a modified text model matching structural criteria step-by-step.
    """
    system_instructions = (
        "You are an expert data architect assistant. Your job is to correct the student's schema. "
        "Modify the student's answer so that it perfectly aligns with the teacher's structure and layout sequence. "
        "Output the corrected aggregate schema code blocks clearly."
    )

    prompt = (
        f"Errors to resolve:\n{json.dumps(feedback, indent=2)}\n\n"
        f"Student's Incorrect Schema:\n{student_answer}\n\n"
        f"Target Teacher Reference:\n{reference_answer}\n\n"
        "Provide the fully corrected schema, along with a 1-sentence note explaining what major block changed."
    )
    return _call_llm_api(system_instructions, prompt)


# --- BUTTON ACTION 4: Explain Why It's Correct ---
def action_explain_success(student_answer: str, reference_answer: str) -> str:
    """
    Triggers if evaluation arrays are clear.
    Highlights design wins like ideal flat layout properties or correct mapping.
    """
    system_instructions = (
        "You are a computer science professor validating a perfect assignment submission. "
        "Explain to the student why their positioning, nesting structures, and entity-relationship choices "
        "represent an excellent, optimized aggregate design strategy."
    )

    prompt = (
        f"Student's Valid Schema:\n{student_answer}\n\n"
        f"Teacher Reference Schema:\n{reference_answer}\n\n"
        "Write a brief, positive architectural validation under 100 words explaining why this model succeeds."
    )
    return _call_llm_api(system_instructions, prompt)


# --- BUTTON ACTION 5: Describe My Aggregate Schema ---
def action_describe_schema(student_answer: str, reference_answer: str) -> str:
    """
    Triggers when the student clicks 'Describe my  schema'.
    Gives a plain, structural walkthrough of the collections, documents, and
    nesting the student modelled — what it is, not whether it is good.
    """
    system_instructions = (
        "You are an aggregate modeling teaching assistant. Describe the student's aggregate "
        "schema objectively: list the collections, the documents/fields they contain, and how "
        "entities are embedded or referenced. Be factual and structural — do not judge quality "
        "or suggest changes. Keep it under 120 words."
    )

    prompt = (
        f"Student's Aggregate Schema:\n{student_answer}\n\n"
        "Describe the structure of this aggregate schema for the student."
    )
    return _call_llm_api(system_instructions, prompt)


# --- BUTTON ACTION 6: Explain My Schema ---
def action_explain_schema(student_answer: str, reference_answer: str) -> str:
    """
    Triggers when the student clicks 'Explain my schema'.
    Explains the design rationale behind the student's modelling choices.
    """
    system_instructions = (
        "You are a database design mentor. Explain the reasoning behind the student's aggregate "
        "schema: why the embedding and referencing choices make sense, what access patterns they "
        "support, and the trade-offs involved. Be educational and concise, under 120 words."
    )

    prompt = (
        f"Student's Aggregate Schema:\n{student_answer}\n\n"
        f"Teacher Reference Schema:\n{reference_answer}\n\n"
        "Explain the design rationale of the student's schema."
    )
    return _call_llm_api(system_instructions, prompt)


# --- BUTTON ACTION 7: Does My Schema Have Any Errors ---
def action_check_errors(student_answer: str, reference_answer: str) -> str:
    """
    Triggers when the student clicks 'Does my schema have any errors'.
    Reviews the student's schema for structural problems or modelling mistakes.
    """
    system_instructions = (
        "You are an aggregate modeling reviewer. Inspect the student's schema for structural "
        "errors, modelling mistakes, or deviations from the reference. If there are none, say so "
        "clearly and confirm the schema is valid. If there are issues, list them plainly. "
        "Keep it under 120 words and do not rewrite the schema."
    )

    prompt = (
        f"Student's Aggregate Schema:\n{student_answer}\n\n"
        f"Teacher Reference Schema:\n{reference_answer}\n\n"
        "Report whether the student's schema has any errors."
    )
    return _call_llm_api(system_instructions, prompt)
