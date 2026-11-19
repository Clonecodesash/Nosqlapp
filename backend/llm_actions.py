"""
LLM button-action functions for the aggregate-modelling exercises
(thesis Chapter 4, "The Student's Interactions").

Each action builds a system prompt + user prompt and calls the OpenAI Responses
API. The model never decides correctness: the verdict and the findings come
from the deterministic engine, and every action that concerns errors gives the
model the engine's finding as an established fact to explain.

    Action                      Verdict  Information given to the model
    What does this error mean?  Wrong    finding, student's answer
    Give me a hint              Wrong    finding, student's answer, reference
    How can I fix my schema?    Wrong    finding, student's answer, reference
    Describe my schema          Correct  student's answer
    Explain my schema           Correct  student's answer, reference, workload
    Does my schema have errors? Correct  engine's complications, student's answer
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
    """Send one stateless request to the OpenAI Responses API and return its text."""
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
                for content_item in output_item.get("content", []) or []:
                    if content_item.get("type") == "output_text" and content_item.get("text"):
                        return content_item["text"].strip()
            raise RuntimeError("LLM response did not include output text")

    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"LLM request failed: {exc.code} {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"LLM request failed: {exc.reason}") from exc


# =====================================================================
# SHARED PROMPT PIECES
# =====================================================================

_ROLE = (
    "You are a teaching assistant for aggregate-oriented NoSQL schema design. "
    "Students write aggregate schemas in json-sm notation: `Name: { ... }` is an object "
    "(a single embedded document), `name: [ ... ]` is a collection (a list of embedded "
    "elements), a bare name is a simple attribute, and an optional `@metadata:` block "
    "declares the identifier, the partition key and the required attributes. "
)

_FINDING_IS_FACT = (
    "A deterministic, rule-based checker has already evaluated the student's schema. Its "
    "finding is correct: do not question it, do not decide yourself whether the schema is "
    "right or wrong, and do not look for other problems. "
)

_CLASS_LABELS = {
    "syntax": "Syntax error",
    "schema": "Schema-dependent error",
    "workload": "Workload-dependent error",
    "complication": "Complication",
}


def _format_finding(finding: dict) -> str:
    """Render one engine finding as text for a prompt."""
    label = _CLASS_LABELS.get(finding.get("category"), "Finding")
    text = f"{label} [{finding.get('code', 'UNKNOWN')}]: {finding.get('message', '')}"
    if finding.get("line") is not None and finding.get("col") is not None:
        text += f" (line {finding['line']}, column {finding['col']})"
    elif finding.get("path"):
        text += f" (at {finding['path']})"
    return text


def _format_workload(workload: list[str]) -> str:
    return "\n".join(f"Q{i}: {query}" for i, query in enumerate(workload, start=1))


# =====================================================================
# WRONG ANSWER: explain, hint, fix
# =====================================================================

def action_explain_error(student_answer: str, finding: dict) -> str:
    """'What does this error mean?' - restate the current finding in plain language."""
    system_instructions = (
        _ROLE + _FINDING_IS_FACT +
        "Your task: restate the finding in plain, non-technical language and relate it to "
        "the student's own schema, saying which part of their schema it concerns and what it "
        "means for the data stored there. Explain only: do not suggest a correction, do not "
        "say how to fix it, and do not write any schema text. "
        "Answer in at most 3 sentences (under 80 words)."
    )
    prompt = (
        f"Checker finding:\n{_format_finding(finding)}\n\n"
        f"Student's schema:\n{student_answer}\n\n"
        "Explain this finding to the student."
    )
    return _call_llm_api(system_instructions, prompt)


def action_give_hint(student_answer: str, reference_answer: str, finding: dict) -> str:
    """'Give me a hint' - one conceptual cue towards the current finding."""
    system_instructions = (
        _ROLE + _FINDING_IS_FACT +
        "You are also given the teacher's reference schema. It is CONFIDENTIAL: it is shown "
        "to you only so that your hint points in the right direction. "
        "Your task: give ONE conceptual hint that makes the student reconsider the design "
        "decision behind the finding without stating the answer, for example by asking them "
        "to think about how many orders a customer can have. "
        "Never reveal any part of the reference beyond what the finding already says: do not "
        "name fields, structures or metadata values from it. Do not include any schema text "
        "or code. Answer in 1 or 2 sentences (under 50 words)."
    )
    prompt = (
        f"Checker finding:\n{_format_finding(finding)}\n\n"
        f"Student's schema:\n{student_answer}\n\n"
        f"Teacher's reference schema (confidential, do not reveal):\n{reference_answer}\n\n"
        "Give the student one conceptual hint."
    )
    return _call_llm_api(system_instructions, prompt)


def action_fix_schema(student_answer: str, reference_answer: str, finding: dict) -> str:
    """'How can I fix my schema?' - the smallest change resolving the current finding only."""
    system_instructions = (
        _ROLE + _FINDING_IS_FACT +
        "You are also given the teacher's reference schema. It is CONFIDENTIAL and must "
        "never be reproduced. "
        "Your task: propose the SMALLEST change to the student's schema that resolves ONLY "
        "this finding, and justify it in one sentence. Show only the changed fragment (one "
        "or two lines of json-sm at most), never a complete schema. Do not fix or mention "
        "anything else, even if you notice other differences from the reference: the student "
        "will resubmit and receive the next finding, if any. Under 80 words."
    )
    prompt = (
        f"Checker finding to resolve:\n{_format_finding(finding)}\n\n"
        f"Student's schema:\n{student_answer}\n\n"
        f"Teacher's reference schema (confidential, do not reproduce):\n{reference_answer}\n\n"
        "Propose the smallest change that resolves this finding."
    )
    return _call_llm_api(system_instructions, prompt)


# =====================================================================
# CORRECT ANSWER: describe, explain, check for errors
# =====================================================================

def action_describe_schema(student_answer: str) -> str:
    """'Describe my schema' - a factual walkthrough of the student's own schema."""
    system_instructions = (
        _ROLE +
        "Your task: give a factual walkthrough of the student's schema: the aggregate and "
        "whether its root is a single object or a collection, the attributes it contains, "
        "which related data is embedded and whether each embedded part is single (object) or "
        "multiple (collection), and the declared identifier, partition key and required "
        "attributes. Describe only: do not evaluate, judge quality or suggest changes. "
        "Under 50 words."
    )
    prompt = (
        f"Student's schema:\n{student_answer}\n\n"
        "Describe the structure of this schema."
    )
    return _call_llm_api(system_instructions, prompt)


def action_explain_schema(student_answer: str, reference_answer: str, workload: list[str]) -> str:
    """'Explain my schema' - why the (correct) design suits the exercise's workload."""
    system_instructions = (
        _ROLE +
        "The rule-based checker has judged the student's schema CORRECT; do not question "
        "this and do not suggest changes. You are given the workload (the queries the schema "
        "must serve) and the teacher's reference design, which the student's schema agrees "
        "with. Your task: explain why this design suits the workload: which queries benefit "
        "from each embedding decision, why the partition key supports the expected access, "
        "and what trade-offs the design accepts, such as duplicated data. Tie each point to "
        "the actual queries, not to generic advice. Under 150 words."
    )
    prompt = (
        f"Workload:\n{_format_workload(workload)}\n\n"
        f"Student's schema:\n{student_answer}\n\n"
        f"Teacher's reference schema:\n{reference_answer}\n\n"
        "Explain why the student's design suits this workload."
    )
    return _call_llm_api(system_instructions, prompt)


def action_check_errors(student_answer: str, complications: list[dict]) -> str:
    """'Does my schema have any errors?' - explain the engine's complications, if any."""
    system_instructions = (
        _ROLE +
        "The rule-based checker has judged the student's schema CORRECT: it contains no "
        "errors. It may still have reported complications: parts that are valid but more "
        "complex than needed, such as extra fields, redundant nesting or names that differ "
        "from the expected ones. You are given that list. If the list is empty, confirm "
        "clearly that the schema has no errors and nothing to simplify. Otherwise, explain "
        "each complication as an opportunity to simplify the design. Do not look for problems "
        "of your own and never say the schema is wrong. Under 120 words."
    )
    if complications:
        listed = "\n".join(f"- {_format_finding(c)}" for c in complications)
    else:
        listed = "(none)"
    prompt = (
        f"Complications reported by the checker:\n{listed}\n\n"
        f"Student's schema:\n{student_answer}\n\n"
        "Tell the student whether their schema has any errors, and explain any complications."
    )
    return _call_llm_api(system_instructions, prompt)
