import difflib

import error_taxonomy as tax
import json_sm_parser as gemjsonparse
import metadat_comparison as metacomp

# Names at least this similar (0..1) are treated as a likely typo of an expected
# field rather than as a completely missing + extra pair.
_NAME_SIMILARITY_CUTOFF = 0.8


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


def evaluate_answer(student_text, reference_text):
    """
    Top-level entry point that takes the RAW text of a student answer and a
    reference answer and returns a list of feedback messages.

    Two phases, in order:
      1. Syntax gate: the student answer is checked for syntax errors first
         (unbalanced/missing/mismatched brackets, empty answer). If anything
         is wrong, we STOP and return that single error - a schema that does
         not parse cannot be compared field-by-field.
      2. Comparison: only once the syntax is clean do we parse both answers
         into trees and compare them (structure + metadata).
    """
    syntax_error = gemjsonparse.check_syntax(student_text)
    if syntax_error:
        return [syntax_error]

    student_node = gemjsonparse.parse_jsonsm(student_text)
    reference_node = gemjsonparse.parse_jsonsm(reference_text)
    return evaluate_schemas(student_node, reference_node)


def evaluate_schemas(student_node, reference_node):
    """
    Main entry point for comparing a parsed student root node against a parsed
    reference root node.

    Like the Phase-1 syntax gate, the comparison reports ONE problem at a time:
    the full structural + metadata comparison is computed by
    :func:`evaluate_schemas_full`, but only the FIRST blocking finding
    (severity critical / error / warning) is handed back, wrapped in a list, so
    the student fixes one thing before resubmitting. Purely informational
    findings (e.g. a different root name) never surface on their own, and an
    otherwise-correct answer yields an empty list.
    """
    for finding in evaluate_schemas_full(student_node, reference_node):
        if finding.severity in tax.BLOCKING_SEVERITIES:
            return [finding]
    return []


def evaluate_schemas_full(student_node, reference_node):
    """
    Run the COMPLETE structural + metadata comparison and return every finding,
    in evaluation order, as a list of :class:`error_taxonomy.Feedback`.

    This is kept separate from :func:`evaluate_schemas` so the whole set of
    findings is still available (for analysis, teacher tooling, etc.) even
    though students are shown only the first one.
    """
    feedback = []
    root_path = reference_node.name

    # 1. Structural Root Check (Heuristic H1): object vs collection at the root.
    if student_node.node_type != reference_node.node_type:
        feedback.append(tax.make(
            "STR_ROOT_TYPE_MISMATCH",
            f"Root type mismatch: the reference is a {reference_node.node_type}, "
            f"but the student used a {student_node.node_type}.",
            path=root_path,
        ))

    # A different root name is informational only (does not affect correctness).
    if student_node.name.lower() != reference_node.name.lower():
        feedback.append(tax.make(
            "STR_ROOT_NAME_DIFF",
            f"Root name '{student_node.name}' differs from the reference '{reference_node.name}'.",
            path=root_path,
        ))

    # 2. Metadata (identifier / partitionKey / required).
    feedback.extend(metacomp.compare_metadata(student_node, reference_node))

    # 3. Structural recursion over the children.
    feedback.extend(evaluate_schemas_recursive(student_node, reference_node, path=root_path))
    return feedback


def _is_complex(node):
    return node.node_type in ('object', 'collection')


def evaluate_schemas_recursive(s_node, r_node, path=""):
    """
    Core recursive engine: compares trees by matching children NAMES
    (case-insensitive), NOT by their position.

    Matching by name means a student who lists the right fields in a different
    order is not punished for the order, and a field that was moved out of one
    object into another shows up cleanly as MISSING here / EXTRA there instead
    of throwing off every position after it.

    When a reference field has no exact-name match, we look for a close student
    name (likely typo) before declaring it missing, so 'nam' vs 'name' is
    reported as a spelling issue and still compared structurally.
    """
    inner_feedback = []

    # Index the student's children by lowercased name. A list per name lets us
    # consume repeated names one at a time and, afterwards, see which student
    # children were never matched (those are the EXTRA ones).
    student_by_name = {}
    for child in s_node.children:
        student_by_name.setdefault(child.name.lower(), []).append(child)

    matched = set()  # id() of student children that found a reference match

    def find_close_name(target):
        """Name of an as-yet-unused student child that closely resembles ``target``."""
        available = [name for name, bucket in student_by_name.items() if bucket]
        close = difflib.get_close_matches(
            target.lower(), available, n=1, cutoff=_NAME_SIMILARITY_CUTOFF
        )
        return close[0] if close else None

    # Walk the reference children: each one SHOULD exist in the student answer.
    for r_sub in r_node.children:
        child_path = f"{path}.{r_sub.name}" if path else r_sub.name
        candidates = student_by_name.get(r_sub.name.lower())
        is_typo = False

        # No exact match: try to recover a close (misspelled) name.
        if not candidates:
            alt = find_close_name(r_sub.name)
            if alt:
                candidates = student_by_name.get(alt)
                is_typo = True

        # Case 1: Missing - reference has this field, the student does not.
        if not candidates:
            inner_feedback.append(tax.make(
                "STR_MISSING_ELEMENT",
                f"Expected '{r_sub.name}' inside '{r_node.name}', "
                f"but it was not found in the student answer.",
                path=child_path,
            ))
            continue

        s_sub = candidates.pop(0)
        matched.add(id(s_sub))

        if is_typo:
            inner_feedback.append(tax.make(
                "STR_NAME_TYPO",
                f"'{s_sub.name}' looks like a misspelling of the expected '{r_sub.name}'.",
                path=child_path,
            ))

        # Case 2: Both exist - compare shape and type.
        s_is_complex = _is_complex(s_sub)
        r_is_complex = _is_complex(r_sub)

        # 2.1 Flat vs nested.
        if s_is_complex != r_is_complex:
            expected = "complex (nested)" if r_is_complex else "simple (flat)"
            found = "complex" if s_is_complex else "simple"
            inner_feedback.append(tax.make(
                "STR_TYPE_MISMATCH",
                f"Item '{s_sub.name}' should be {expected}, but it is {found}.",
                path=child_path,
            ))

        # 2.2 Object vs collection (only meaningful when both are complex).
        elif s_is_complex and r_is_complex and s_sub.node_type != r_sub.node_type:
            inner_feedback.append(tax.make(
                "STR_CONTAINER_KIND_MISMATCH",
                f"Item '{s_sub.name}' is a {s_sub.node_type.upper()}, "
                f"but the reference expects a {r_sub.node_type.upper()}.",
                path=child_path,
            ))

        # 2.3 Same number of children (only when both are the same kind of container).
        if s_is_complex and r_is_complex and s_sub.node_type == r_sub.node_type:
            if len(s_sub.children) != len(r_sub.children):
                inner_feedback.append(tax.make(
                    "STR_CHILD_COUNT_MISMATCH",
                    f"'{s_sub.name}' has {len(s_sub.children)} field(s), "
                    f"but the reference has {len(r_sub.children)}.",
                    path=child_path,
                ))

        # 2.4 Useless nesting (Heuristic H2).
        if s_is_complex and len(s_sub.children) == 1 and is_useless_nesting(s_sub, r_sub):
            inner_feedback.append(tax.make(
                "STR_USELESS_NESTING",
                f"Useless nesting at '{s_sub.name}'. Flatten this structure to reduce depth.",
                path=child_path,
            ))

        # 2.5 Drill down into matching nested structures.
        if s_is_complex and r_is_complex:
            inner_feedback.extend(evaluate_schemas_recursive(s_sub, r_sub, path=child_path))

    # Case 3: Extra - student children that matched no reference field.
    for child in s_node.children:
        if id(child) not in matched:
            inner_feedback.append(tax.make(
                "STR_EXTRA_ELEMENT",
                f"Unexpected element '{child.name}' inside '{s_node.name}'.",
                path=f"{path}.{child.name}" if path else child.name,
            ))

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
