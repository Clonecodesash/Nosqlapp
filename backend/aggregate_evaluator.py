import json
import os
import urllib.error
import urllib.request

import json_sm_parser as gemjsonparse
import metadat_comparison as metacomp


# =====================================================================
# PART 1: THE CORE POSITION-BASED EVALUATOR CODE
# =====================================================================

def is_useless_nesting(student_node, reference_node):
    """
    Returns True if student nesting is deeper than the reference 
    without looking at the names of the nodes.
    """
    if reference_node is None:
        return True
    
    # If reference is a simple attribute, any student nesting is useless
    if reference_node.node_type not in ['object', 'collection']:
        return True

    # If reference has multiple children, it's a legitimate structure
    if len(reference_node.children) != 1:
        return True

    # Check the first child of each
    ref_child = reference_node.children[0]
    student_child = student_node.children[0]

    # If both are containers, the nesting is technically justified structurally
    if ref_child.node_type in ['object', 'collection'] and \
       student_child.node_type in ['object', 'collection']:
        return False
        
    return True


def evaluate_schemas(student_node, reference_node):
    """
    Main entry point for comparing a parsed student root node 
    against a parsed reference root node.
    """
    feedback = []
    
    # 1. Structural Root Check (Heuristic H1)
    if student_node.node_type != reference_node.node_type:
        feedback.append(f"CRITICAL: Root type mismatch. Reference is {reference_node.node_type}, "
                        f"but student used {student_node.node_type}.")
    
    # Optional: Keep the name check for the Root only as an info message
    if student_node.name.lower() != reference_node.name.lower():
        feedback.append(f"INFO: Root name '{student_node.name}' differs from reference '{reference_node.name}'.")

    # 2. Check Metadata using the imported module
    feedback.extend(metacomp.compare_metadata(student_node, reference_node))
    
    # 3. Start the structural recursion
    feedback.extend(evaluate_schemas_recursive(student_node, reference_node))
    return feedback


def evaluate_schemas_recursive(s_node, r_node):
    """
    Core recursive engine: Compares trees strictly by POSITION (index).
    """
    inner_feedback = []
    
    # Use max length to find missing or extra elements
    max_idx = max(len(s_node.children), len(r_node.children))
    
    for i in range(max_idx):
        s_sub = s_node.children[i] if i < len(s_node.children) else None
        r_sub = r_node.children[i] if i < len(r_node.children) else None

        # Case 1: Missing
        if s_sub is None:
            inner_feedback.append(f"MISSING: Expected an element at position {i+1} inside '{s_node.name}' "
                                  f"(similar to reference '{r_sub.name}').")
            continue
            
        # Case 2: Extra
        if r_sub is None:
            inner_feedback.append(f"EXTRA: Unexpected extra element '{s_sub.name}' at position {i+1} inside '{s_node.name}'.")
            continue

        # Case 3: Both exist - Compare Shape and Type
        s_is_complex = s_sub.node_type in ['object', 'collection']
        r_is_complex = r_sub.node_type in ['object', 'collection']
        
        # 3.1 Basic Structural Type Check (Flat vs Nested)
        if s_is_complex != r_is_complex:
            expected = "complex (nested)" if r_is_complex else "simple (flat)"
            found = "complex" if s_is_complex else "simple"
            inner_feedback.append(f"TYPE ERROR: Item '{s_sub.name}' at position {i+1} should be {expected}, but found {found}.")
        
        # 3.2 Subtype Check: Object vs Collection
        elif s_is_complex and r_is_complex:
            if s_sub.node_type != r_sub.node_type:
                inner_feedback.append(
                    f"STRUCTURE ERROR: Item '{s_sub.name}' at position {i+1} is defined as a "
                    f"{s_sub.node_type.upper()}, but the reference expects a {r_sub.node_type.upper()}."
                )

        # 3.3 Useless Nesting Check (Heuristic H2)
        if s_is_complex and len(s_sub.children) == 1:
            if is_useless_nesting(s_sub, r_sub):
                inner_feedback.append(f"WARNING (H2): Useless nesting at '{s_sub.name}' (position {i+1}). "
                                      f"Flatten this structure to reduce depth.")

        # 3.4 Recursive call (drill down)
        if s_is_complex and r_is_complex:
            inner_feedback.extend(evaluate_schemas_recursive(s_sub, r_sub))
            
    return inner_feedback


def print_comparison_report(results):
    """Utility helper to print structural validation output cleanly to the console."""
    for name, res in results.items():
        print(f"Aggregate: {name} | Status: {res['status'].upper()}")
        print("-" * 50)
        if not res['feedback']:
            print("  Structure is Valid")
        else:
            for item in res['feedback']:
                print(f"  • {item}")
        print()


# =====================================================================
# PART 2: THE FOUR INDEPENDENT LLM BUTTON CALL FUNCTIONS
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
        "'Look at the order of fields in your root object'). Keep it under 75 words."
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