"""
Metadata Comparison Functions for Schema Evaluation

This module compares the metadata of the aggregate (identifier, partitionKey,
required attributes) between the student and reference schemas. Each attribute
list is compared as a case-insensitive set, so neither the order nor the
capitalisation of the listed attributes matters. Each mismatch is returned as an
:class:`error_taxonomy.Feedback` so it carries a stable code + class.

Only the cases in the thesis error catalogue are reported:

  * identifier     -> SCH_IDENTIFIER_MISSING / SCH_IDENTIFIER_UNEXPECTED
  * partition key  -> WRK_PARTITIONKEY_MISSING (absent or different)
  * required       -> WRK_REQUIRED_MISSING

Metadata the student declares beyond the reference (an identifier or partition
key where the reference has none, extra required attributes) is not reported.
"""

import error_taxonomy as tax
import json_sm_parser as parser


def compare_metadata(student_node, reference_node):
    """
    Compare metadata between student and reference schema nodes.

    Returns a list of findings, in the order identifier, partition key,
    required attributes.
    """
    feedback = []
    feedback.extend(compare_identifier(student_node, reference_node))
    feedback.extend(compare_partition_key(student_node, reference_node))
    feedback.extend(compare_required_attributes(student_node, reference_node))
    return feedback


def _lower_set(fields):
    return frozenset(str(f).strip().lower() for f in fields)


def _identifier_options(identifier):
    """
    Normalise a parsed identifier into a list of options, each a lowercase set.

    The parser returns a list of options (list of lists), e.g.
    [['codcli'], ['name', 'dob']]; a flat list is treated as one composite key.
    """
    if not identifier:
        return []
    if all(isinstance(option, list) for option in identifier):
        return [_lower_set(option) for option in identifier if option]
    return [_lower_set(identifier)]


def _format_options(identifier):
    """Render identifier options as {a}, {b, c} for messages."""
    if identifier and all(isinstance(option, list) for option in identifier):
        return ", ".join("{" + ", ".join(option) + "}" for option in identifier)
    return "{" + ", ".join(identifier or []) + "}"


def compare_identifier(student_node, reference_node):
    """
    Compare identifier fields between student and reference (schema-dependent).

    The reference may list alternative identifiers, e.g. [{codcli}, {name, dob}].
    The student's identifier is accepted if it matches ANY one of them; if the
    student also lists alternatives, every alternative must be one of the
    reference's options.
    """
    reference_options = _identifier_options(reference_node.identifier)
    if not reference_options:
        return []

    student_options = _identifier_options(student_node.identifier)
    if not student_options:
        return [tax.make(
            "SCH_IDENTIFIER_MISSING",
            "No identifier is declared. Add an identifier to the @metadata block.",
            path="@metadata.identifier",
        )]

    invalid = [option for option in student_options if option not in reference_options]
    if invalid:
        return [tax.make(
            "SCH_IDENTIFIER_UNEXPECTED",
            f"The identifier {_format_options(student_node.identifier)} does not identify "
            f"the root entity of the aggregate.",
            path="@metadata.identifier",
        )]
    return []


def compare_partition_key(student_node, reference_node):
    """
    Compare partition key fields between student and reference (workload-dependent).

    A partition key that is absent, or declared on different attributes than
    the reference, is reported as WRK_PARTITIONKEY_MISSING: the partition key
    required by the workload is not declared.
    """
    if not reference_node.partitionKey:
        return []

    if not student_node.partitionKey:
        return [tax.make(
            "WRK_PARTITIONKEY_MISSING",
            "No partition key is declared. Add a partition key to the @metadata block.",
            path="@metadata.partitionKey",
        )]

    if _lower_set(student_node.partitionKey) != _lower_set(reference_node.partitionKey):
        return [tax.make(
            "WRK_PARTITIONKEY_MISSING",
            f"The partition key [{', '.join(student_node.partitionKey)}] is not the one "
            f"the workload requires.",
            path="@metadata.partitionKey",
        )]
    return []


def compare_required_attributes(student_node, reference_node):
    """
    Compare required attributes between student and reference (workload-dependent).

    Every attribute the reference declares as required must also be declared
    required by the student.
    """
    if not reference_node.required:
        return []

    missing = _lower_set(reference_node.required) - _lower_set(student_node.required or [])
    if missing:
        return [tax.make(
            "WRK_REQUIRED_MISSING",
            f"Not declared as required: {', '.join(sorted(missing))}.",
            path="@metadata.required",
        )]
    return []


if __name__ == "__main__":
    schemareference = """
        Student: {
          codcli,
          name,
          dob,
          email
        }

        @metadata:
          identifier: [{codcli}, {name,dob}]
          required: [codcli, name, dob, email]
        """

    schemastudent = """
        Student: {
          codcli,
          name,
          dob:{month, year},
          email
        }

        @metadata:
          identifier: [{codcli},{name, dob}]
          required: [codcli, name, dob, email]
        """

    print("Comparing metadata between student and reference schemas...")
    studentschema = parser.parse_jsonsm(schemastudent)
    referenceschema = parser.parse_jsonsm(schemareference)
    for finding in compare_metadata(studentschema, referenceschema):
        print(finding)
