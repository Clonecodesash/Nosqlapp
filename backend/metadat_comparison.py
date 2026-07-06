import error_taxonomy as tax
import json_sm_parser as parser



"""
Metadata Comparison Functions for Schema Evaluation

This module provides functions to compare metadata (identifier, partitionKey, required attributes)
between reference and student schemas. Each mismatch is returned as an
:class:`error_taxonomy.Feedback` so it carries a stable code + severity.
"""

def compare_metadata(student_node, reference_node):
    """
    Compare metadata between student and reference schema nodes.
    
    Returns a list of feedback messages for any mismatches.
    
    Args:
        student_node: SchemaNode with student's schema metadata
        reference_node: SchemaNode with reference schema metadata
    
    Returns:
        list: Feedback messages about metadata mismatches
    """
    feedback = []
    
    # Compare identifier
    feedback.extend(compare_identifier(student_node, reference_node))
    
    # Compare partition key
    feedback.extend(compare_partition_key(student_node, reference_node))
    
    # Compare required attributes
    feedback.extend(compare_required_attributes(student_node, reference_node))
    
    return feedback


def compare_identifier(student_node, reference_node):
    """
    Compare identifier fields between student and reference.
    
    The identifier is the  field(s) of the aggregate which  facilitate unique identification.
    Now supports multiple identifier options (alternative combinations).
    
    identifier_options: List of possible identifier combinations (e.g., [{codcli}, {name, dob, place}])
    identifier: Deprecated - single identifier list (kept for backward compatibility)
    
    The student's identifier is valid if it matches ANY of the reference's identifier options.
    """
    feedback = []
    
    # Check if reference has identifier_options (new format with multiple combinations)
    if hasattr(reference_node, 'identifier_options') and reference_node.identifier_options:
        if not student_node.identifier:
            feedback.append(tax.make(
                "META_IDENTIFIER_MISSING",
                f"Missing identifier. Reference specifies one of: "
                f"{reference_node.identifier_options}, but student has none.",
                path="@metadata.identifier",
            ))
        else:
            # Convert student identifier to lowercase set for comparison
            student_id_lower = set(f.lower() for f in student_node.identifier)
            # Check if student's identifier matches ANY of the valid options
            is_valid = False
            for option in reference_node.identifier_options:
                option_lower = set(f.lower() for f in option)
                if student_id_lower == option_lower:
                    is_valid = True
                    break

            if not is_valid:
                # Format the valid options for display
                valid_options_str = ", ".join(
                    [f"{{{', '.join(opt)}}}" for opt in reference_node.identifier_options]
                )
                feedback.append(tax.make(
                    "META_IDENTIFIER_MISMATCH",
                    f"Identifier mismatch. Student uses {student_node.identifier}, "
                    f"but must be one of: {valid_options_str}.",
                    path="@metadata.identifier",
                ))
    
    # Fallback for legacy single identifier format
    elif reference_node.identifier:
        if not student_node.identifier:
            feedback.append(tax.make(
                "META_IDENTIFIER_MISSING",
                f"Missing identifier. Reference specifies {reference_node.identifier}, "
                f"but student has none.",
                path="@metadata.identifier",
            ))
        else:
            # 1. Normalize student input: 
            # If student is [['field']], flatten it to ['field']
            s_id = student_node.identifier
            if len(s_id) > 0 and isinstance(s_id[0], list):
                s_id = s_id[0]
            
            student_id_set = set(str(f).lower() for f in s_id)

            # 2. Check if the Reference is actually a list of options (list of lists)
            # Example: [['codcli'], ['name', 'dob']]
            ref_val = reference_node.identifier
            is_valid = False

            if len(ref_val) > 0 and isinstance(ref_val[0], list):
                # Iterate through options just like in the modern logic
                for option in ref_val:
                    option_set = set(str(f).lower() for f in option)
                    if student_id_set == option_set:
                        is_valid = True
                        break
                
                if not is_valid:
                    feedback.append(tax.make(
                        "META_IDENTIFIER_MISMATCH",
                        f"Identifier mismatch. Reference uses {ref_val}, "
                        f"but student uses {student_node.identifier}.",
                        path="@metadata.identifier",
                    ))
            else:
                # 3. Standard single-list comparison (The original logic)
                ref_id_set = set(str(f).lower() for f in ref_val)

                if ref_id_set != student_id_set:
                    missing = ref_id_set - student_id_set
                    extra = student_id_set - ref_id_set

                    if missing and extra:
                        feedback.append(tax.make(
                            "META_IDENTIFIER_MISMATCH",
                            f"Identifier mismatch. Missing: {missing}, Extra: {extra}.",
                            path="@metadata.identifier",
                        ))
                    elif missing:
                        feedback.append(tax.make(
                            "META_IDENTIFIER_MISMATCH",
                            f"Identifier mismatch. Reference uses {ref_val}, but student uses {s_id}.",
                            path="@metadata.identifier",
                        ))
                    else:
                        feedback.append(tax.make(
                            "META_IDENTIFIER_UNEXPECTED",
                            f"Unexpected identifier fields. Reference uses {ref_val}, but student uses {s_id}.",
                            path="@metadata.identifier",
                        ))

            # --- END OF IMPROVED LOGIC ---
    # elif reference_node.identifier:
    #     if not student_node.identifier:
    #         feedback.append(
    #             f"METADATA ERROR: Missing identifier. "
    #             f"Reference specifies {reference_node.identifier}, but student has none."
    #         )
    #     else:
    #         # Compare as sets (case-insensitive)
    #         # Convert to strings first in case identifier contains nested structures
    #         ref_id_lower = set(str(f).lower() for f in reference_node.identifier)
    #         student_id_lower = set(str(f).lower() for f in student_node.identifier)
            
    #         if ref_id_lower != student_id_lower:
    #             missing = ref_id_lower - student_id_lower
    #             extra = student_id_lower - ref_id_lower
                
    #             if missing and extra:
    #                 feedback.append(
    #                     f"METADATA ERROR: Identifier mismatch. "
    #                     f"Missing: {missing}, Extra: {extra}."
    #                 )
    #             elif missing:
    #                 feedback.append(
    #                     f"METADATA ERROR: Identifier mismatch. "
    #                     f"Reference uses {reference_node.identifier}, but student uses {student_node.identifier}."
                        
    #                 )
    #             else:
    #                 feedback.append(
    #                     f"METADATA WARNING: Unexpected identifier fields. "
    #                     f"Reference uses {reference_node.identifier}, but student uses {student_node.identifier}."
    #                 )
    elif student_node.identifier:
        feedback.append(tax.make(
            "META_IDENTIFIER_UNEXPECTED",
            f"Student specifies identifier {student_node.identifier}, but reference has none.",
            path="@metadata.identifier",
        ))

    return feedback


def compare_partition_key(student_node, reference_node):
    """
    Compare partition key fields between student and reference.
    
    The partition key is used for distributed systems to determine data placement.
    Both are lists of field names.
    """
    feedback = []
    
    if reference_node.partitionKey:
        if not student_node.partitionKey:
            feedback.append(tax.make(
                "META_PARTITIONKEY_MISSING",
                f"Missing partition key. Reference specifies {reference_node.partitionKey}, "
                f"but student has none.",
                path="@metadata.partitionKey",
            ))
        else:
            # Compare as sets (case-insensitive)
            ref_pk_lower = set(f.lower() for f in reference_node.partitionKey)
            student_pk_lower = set(f.lower() for f in student_node.partitionKey)

            if ref_pk_lower != student_pk_lower:
                missing = ref_pk_lower - student_pk_lower
                extra = student_pk_lower - ref_pk_lower

                if missing and extra:
                    feedback.append(tax.make(
                        "META_PARTITIONKEY_MISMATCH",
                        f"Partition key mismatch. Missing: {missing}, Extra: {extra}.",
                        path="@metadata.partitionKey",
                    ))
                elif missing:
                    feedback.append(tax.make(
                        "META_PARTITIONKEY_MISMATCH",
                        f"Partition key mismatch. Reference uses {reference_node.partitionKey}, "
                        f"but student uses {student_node.partitionKey}.",
                        path="@metadata.partitionKey",
                    ))
                else:
                    feedback.append(tax.make(
                        "META_PARTITIONKEY_UNEXPECTED",
                        f"Unexpected partition key fields. Reference uses {reference_node.partitionKey}, "
                        f"but student uses {student_node.partitionKey}.",
                        path="@metadata.partitionKey",
                    ))
    elif student_node.partitionKey:
        feedback.append(tax.make(
            "META_PARTITIONKEY_UNEXPECTED",
            f"Student specifies partition key {student_node.partitionKey}, but reference has none.",
            path="@metadata.partitionKey",
        ))

    return feedback


def compare_required_attributes(student_node, reference_node):
    """
    Compare required attributes between student and reference.
    
    Required attributes are fields that must be present in every document.
    """
    feedback = []
    
    if reference_node.required:
        # Convert to lowercase for case-insensitive comparison
        ref_required_lower = [attr.lower() for attr in reference_node.required]
        student_required_lower = [attr.lower() for attr in student_node.required]
        
        # Find missing required attributes (in reference but not in student)
        missing = set(ref_required_lower) - set(student_required_lower)
        if missing:
            feedback.append(tax.make(
                "META_REQUIRED_MISSING",
                f"Missing required attributes: {', '.join(sorted(missing))}.",
                path="@metadata.required",
            ))

        # Find extra required attributes (in student but not in reference)
        extra = set(student_required_lower) - set(ref_required_lower)
        if extra:
            feedback.append(tax.make(
                "META_REQUIRED_UNEXPECTED",
                f"Unexpected required attributes: {', '.join(sorted(extra))}.",
                path="@metadata.required",
            ))
    elif student_node.required:
        feedback.append(tax.make(
            "META_REQUIRED_UNEXPECTED",
            f"Student specifies required attributes {student_node.required}, but reference has none.",
            path="@metadata.required",
        ))

    return feedback


def validate_identifier_exists(node, aggregate_name):
    """
    Validate that an identifier is defined for the aggregate.
    
    Args:
        node: SchemaNode to validate
        aggregate_name: Name of the aggregate for error messages
    
    Returns:
        list: Feedback messages if identifier is missing
    """
    feedback = []
    
    if not node.identifier:
        feedback.append(
            f"METADATA WARNING: Aggregate '{aggregate_name}' has no identifier defined. "
            f"Please specify @metadata: identifier: [field1, field2, ...]"
        )
    
    return feedback


def validate_required_attributes(node, aggregate_name):
    """
    Validate that required attributes are defined for the aggregate.
    
    Args:
        node: SchemaNode to validate
        aggregate_name: Name of the aggregate for error messages
    
    Returns:
        list: Feedback messages if required attributes are missing
    """
    feedback = []
    
    if not node.required:
        feedback.append(
            f"METADATA WARNING: Aggregate '{aggregate_name}' has no required attributes defined. "
            f"Please specify @metadata: required: [field1, field2, ...]"
        )
    
    return feedback


def get_metadata_summary(node):
    """
    Get a summary of all metadata for a node.
    
    Args:
        node: SchemaNode
    
    Returns:
        dict: Dictionary with identifier, partitionKey, and required
    """
    return {
        "identifier": node.identifier,
        "partitionKey": node.partitionKey,
        "required": node.required
    }



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
    print("\nStudent Schema:")
    studentschema.display()
    referenceschema = parser.parse_jsonsm(schemareference)
    print("\nReference Schema:")
    referenceschema.display()
    metadata_feedback = compare_metadata(studentschema, referenceschema)

    print(metadata_feedback)
