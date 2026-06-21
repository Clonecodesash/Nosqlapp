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
