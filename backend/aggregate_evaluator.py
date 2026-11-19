"""
Phase 2 of the evaluation: compare a parsed student aggregate with the parsed
reference aggregate (thesis Chapter 3, "Structural and Metadata Evaluation").

The comparison runs in a fixed order - root, then metadata, then the body
level by level (breadth-first) - and returns EVERY finding in that order. The
caller decides what to show the student (see evaluation.py); because of the
order, the first error in the list is always the most global one.
"""

import difflib
from collections import deque

import error_taxonomy as tax
import metadat_comparison as metacomp

# Names at least this similar (0..1) are treated as a likely typo of an expected
# field rather than as a completely missing + extra pair.
_NAME_SIMILARITY_CUTOFF = 0.8

# Name the parser gives to anonymous objects/collections, e.g. the element
# inside `orders: [ { ... } ]`.
_UNNAMED = "_unnamed_"

_KIND_DESCRIPTIONS = {
    "attribute": "a simple attribute",
    "object": "an object { }",
    "collection": "a collection [ ]",
}


def _is_complex(node):
    return node.node_type in ('object', 'collection')


def _describe_kind(node):
    return _KIND_DESCRIPTIONS.get(node.node_type, node.node_type)


def _label(node, parent):
    """Human-readable name of ``node`` for messages."""
    if node.name != _UNNAMED:
        return f"'{node.name}'"
    if parent is not None and parent.name != _UNNAMED:
        return f"the element of '{parent.name}'"
    return "a nested element"


def _container_label(node, path):
    """Human-readable name of a compared container, using its path for context."""
    if node.name != _UNNAMED:
        return f"'{node.name}'"
    segments = path.split('.')
    if len(segments) >= 2 and segments[-2] != "[item]":
        return f"the element of '{segments[-2]}'"
    return "a nested element"


def _child_path(path, node):
    segment = "[item]" if node.name == _UNNAMED else node.name
    return f"{path}.{segment}" if path else segment


def is_useless_nesting(student_node, reference_node):
    """
    True if the student wrapped a single attribute in brackets where the
    reference has just that attribute, e.g. reference `dob`, student
    `dob: { dob }`. This loses no information, so it is a complication rather
    than a workload-dependent error.
    """
    return (
        reference_node.node_type == 'attribute'
        and _is_complex(student_node)
        and len(student_node.children) == 1
        and student_node.children[0].node_type == 'attribute'
    )


def evaluate_schemas_full(student_node, reference_node):
    """
    Run the complete structural + metadata comparison and return every
    finding, in evaluation order, as a list of :class:`error_taxonomy.Feedback`.

    Order: root kind and name, then metadata, then the body breadth-first.
    """
    feedback = []
    root_path = reference_node.name

    # 1. Root kind: object vs collection reflects the main access pattern.
    root_kind_matches = student_node.node_type == reference_node.node_type
    if not root_kind_matches:
        feedback.append(tax.make(
            "WRK_ROOT_TYPE_MISMATCH",
            f"The root of the aggregate is {_describe_kind(student_node)}, but the "
            f"workload needs {_describe_kind(reference_node)}.",
            path=root_path,
        ))

    # A different root name is not a design mistake.
    if student_node.name.lower() != reference_node.name.lower():
        feedback.append(tax.make(
            "COM_ROOT_NAME_DIFF",
            f"The root is named '{student_node.name}'; the expected name is "
            f"'{reference_node.name}'.",
            path=root_path,
        ))

    # 2. Metadata (identifier / partitionKey / required).
    feedback.extend(metacomp.compare_metadata(student_node, reference_node))

    # 3. Body, level by level. A root of the wrong kind is not compared
    #    further: its contents would differ only as a consequence.
    if root_kind_matches:
        feedback.extend(_compare_bodies(student_node, reference_node, root_path))
    return feedback


def _compare_bodies(student_root, reference_root, root_path):
    """
    Breadth-first comparison of the two trees.

    Each queue entry is a pair of matched nested structures. Processing a pair
    compares all of its children and queues the matched nested children, so
    every node at one level is compared before any node at the next level, and
    the shallowest problem always comes first.
    """
    feedback = []
    queue = deque([(student_root, reference_root, root_path)])
    while queue:
        s_node, r_node, path = queue.popleft()
        level_feedback, nested_pairs = _compare_children(s_node, r_node, path)
        feedback.extend(level_feedback)
        queue.extend(nested_pairs)
    return feedback


def _compare_children(s_node, r_node, path):
    """
    Compare the children of one matched pair of nodes by NAME (case-insensitive),
    NOT by position.

    Matching by name means a student who lists the right fields in a different
    order is not punished for the order, and a field that was moved out of one
    object into another shows up cleanly as missing here / extra there.

    When a reference field has no exact-name match, a close student name (likely
    typo) is matched instead, so 'nam' vs 'name' is reported as a spelling slip
    and still compared structurally.

    Returns (findings, nested pairs to compare at the next level).
    """
    feedback = []
    nested_pairs = []
    s_label = _container_label(s_node, path)
    r_label = _container_label(r_node, path)

    # Index the student's children by lowercased name. A list per name lets us
    # consume repeated names one at a time and, afterwards, see which student
    # children were never matched (those are the extra ones).
    student_by_name = {}
    for child in s_node.children:
        student_by_name.setdefault(child.name.lower(), []).append(child)

    matched = set()  # id() of student children that found a reference match

    def find_close_name(target):
        """Name of an as-yet-unused student child that closely resembles ``target``."""
        if target == _UNNAMED:
            return None
        available = [
            name for name, bucket in student_by_name.items()
            if bucket and name != _UNNAMED
        ]
        close = difflib.get_close_matches(
            target.lower(), available, n=1, cutoff=_NAME_SIMILARITY_CUTOFF
        )
        return close[0] if close else None

    # Walk the reference children: each one SHOULD exist in the student answer.
    for r_sub in r_node.children:
        child_path = _child_path(path, r_sub)
        candidates = student_by_name.get(r_sub.name.lower())
        is_typo = False

        # No exact match: try to recover a close (misspelled) name.
        if not candidates:
            alt = find_close_name(r_sub.name)
            if alt:
                candidates = student_by_name.get(alt)
                is_typo = True

        # Missing: the reference has this field, the student does not.
        if not candidates:
            feedback.append(tax.make(
                "WRK_MISSING_ELEMENT",
                f"Expected {_label(r_sub, r_node)} inside {r_label}, "
                f"but it is not in your answer.",
                path=child_path,
            ))
            continue

        s_sub = candidates.pop(0)
        matched.add(id(s_sub))

        if is_typo:
            feedback.append(tax.make(
                "COM_NAME_TYPO",
                f"'{s_sub.name}' looks like a misspelling of '{r_sub.name}'.",
                path=child_path,
            ))

        # Shape: leaf attribute, object or collection.
        if s_sub.node_type != r_sub.node_type:
            if is_useless_nesting(s_sub, r_sub):
                feedback.append(tax.make(
                    "COM_USELESS_NESTING",
                    f"{_label(s_sub, s_node)} wraps a single attribute in an extra level "
                    f"of nesting. It can be written as a plain attribute.",
                    path=child_path,
                ))
            else:
                feedback.append(tax.make(
                    "WRK_CONTAINER_KIND_MISMATCH",
                    f"{_label(s_sub, s_node)} is {_describe_kind(s_sub)}, but the workload "
                    f"needs {_describe_kind(r_sub)} here.",
                    path=child_path,
                ))
            # Contents of a structure of the wrong kind would differ only as a
            # consequence, so they are not compared.
            continue

        # Same kind of nested structure: compare its contents at the next level.
        if _is_complex(s_sub):
            nested_pairs.append((s_sub, r_sub, child_path))

    # Extra: student children that matched no reference field.
    for child in s_node.children:
        if id(child) not in matched:
            feedback.append(tax.make(
                "COM_EXTRA_ELEMENT",
                f"{_label(child, s_node)} inside {s_label} is not needed "
                f"by the workload.",
                path=_child_path(path, child),
            ))

    return feedback, nested_pairs
