import re

class SchemaNode:
    def __init__(self, name, node_type="attribute", parent=None):
        self.name = name
        self.node_type = node_type  # "root", "object", "collection", or "attribute"
        self.children = []
        # Metadata fields (all as lists)
        self.identifier = []  # primary key field(s)
        self.partitionKey = []  # partition key(s) for distributed systems
        self.required = []  # list of required attribute names
        if parent:
            parent.children.append(self)

    def display(self, level=0):
        indent = "  " * level
        symbol = "[]" if self.node_type == "collection" else "{}" if self.node_type == "object" else "-"
        print(f"{indent}{symbol} {self.name}")
        for child in self.children:
            child.display(level + 1)

        # Display metadata if this is the root node
        if level == 0 and (self.identifier or self.partitionKey or self.required):
            if self.identifier:
                print(f"{indent}  identifier: {self.identifier}")
            if self.partitionKey:
                print(f"{indent}  partitionKey: {self.partitionKey}")
            if self.required:
                print(f"{indent}  required: {self.required}")
       

def parse_metadata(metadata_text):
    """
    Parse metadata section from @metadata: ... format.
    Supports multiple identifier combinations.
    
    Examples:
        @metadata:
          identifier: [id]                          # Single field identifier
          identifier: [{id}, {name, dob}]          # Multiple identifier options
          partitionKey: [customerId]
          required: [id, name, price]
    
    For identifiers with multiple options:
    - [{codcli}, {name,dob,place}] means either:
      * Option 1: codcli alone identifies the record
      * Option 2: combination of name, dob, place identifies the record
    
    Returns a dict with metadata fields:
    - identifier: list of identifier options, where each option is a list of fields
    - partitionKey: list of field names
    - required: list of field names
    """
    metadata = {
        "identifier": [],  # Will be list of lists for multiple options
        "partitionKey": [],
        "required": []
    }
    
    if not metadata_text:
        return metadata
    
    # Remove whitespace and @metadata: prefix
    metadata_text = metadata_text.strip()
    if metadata_text.startswith('@metadata:'):
        metadata_text = metadata_text[10:].strip()
    
    # Parse each line
    for line in metadata_text.split('\n'):
        line = line.strip()
        if not line:
            continue
        
        # Parse "key: value" format
        if ':' in line:
            key, value = line.split(':', 1)
            key = key.strip()
            value = value.strip()
            
            if key == "identifier":
                metadata["identifier"] = parse_identifier(value)
            elif key == "partitionKey":
                metadata["partitionKey"] = parse_simple_array(value)
            elif key == "required":
                metadata["required"] = parse_simple_array(value)
    
    return metadata

def parse_simple_array(val):
    """
    Parse simple array format: [item1, item2, ...] or item1
    Returns a flat list of strings.
    """
    if val.startswith('[') and val.endswith(']'):
        items = val[1:-1].split(',')
        return [item.strip() for item in items if item.strip()]
    else:
        return [val] if val else []

def parse_identifier(val):
    """
    Parse identifier field which can have multiple options with composite keys.
    
    Formats supported:
    1. [id]                           -> [["id"]]
    2. [id, name]                     -> [["id", "name"]]
    3. [{id}]                         -> [["id"]]
    4. [{id}, {name, dob}]            -> [["id"], ["name", "dob"]]
    5. [{id}, {name, dob, place}]     -> [["id"], ["name", "dob", "place"]]
    
    Returns a list of identifier options, where each option is a list of field names.
    """
    val = val.strip()
    
    # Handle empty case
    if not val:
        return []
    
    # If not wrapped in [], wrap it
    if not (val.startswith('[') and val.endswith(']')):
        val = f"[{val}]"
    
    # Remove outer brackets
    content = val[1:-1].strip()
    
    if not content:
        return []
    
    # Check if we have curly braces (composite keys) or simple comma-separated values
    if '{' in content:
        # Parse composite keys: {field1, field2}, {field3}, etc.
        identifier_options = []
        i = 0
        
        while i < len(content):
            # Skip whitespace and commas
            while i < len(content) and content[i] in ' ,':
                i += 1
            
            if i >= len(content):
                break
            
            # Expect '{'
            if content[i] == '{':
                i += 1
                # Find matching '}'
                fields = []
                current_field = ""
                while i < len(content) and content[i] != '}':
                    if content[i] == ',':
                        if current_field.strip():
                            fields.append(current_field.strip())
                        current_field = ""
                    else:
                        current_field += content[i]
                    i += 1
                
                # Add last field
                if current_field.strip():
                    fields.append(current_field.strip())
                
                if fields:
                    identifier_options.append(fields)
                
                # Skip closing '}'
                if i < len(content) and content[i] == '}':
                    i += 1
            else:
                i += 1
        
        return identifier_options
    else:
        # Simple case: comma-separated fields (all form a single composite key)
        fields = [f.strip() for f in content.split(',') if f.strip()]
        return [fields] if fields else []

def parse_jsonsm(text):
    # Split schema and metadata sections
    parts = text.split('@metadata:')
    schema_text = parts[0].strip()
    metadata_text = parts[1].strip() if len(parts) > 1 else ""
    
    # Parse metadata if present
    metadata = parse_metadata(metadata_text) if metadata_text else {"identifier": None, "partitionKey": None, "required": []}
    
    # Remove whitespace from schema for parsing
    schema_text = re.sub(r'\s+', '', schema_text)

    
    def helper(data):
        # Identify the main name and the content inside brackets
        # Matches: name:{content} or name[content], with optional :
        match = re.match(r'([a-zA-Z0-9_]+)(:)?([\[\{])(.*)', data)
        
        # Handle unnamed objects/collections (starting with { or [)
        if not match and data and data[0] in '{[':
            opener = data[0]
            closing_bracket = '}' if opener == '{' else ']'
            node_type = "collection" if opener == "[" else "object"
            node = SchemaNode("_unnamed_", node_type)  # Anonymous object/collection
            remainder = data[1:]  # Skip the opening bracket
        elif not match:
            # Simple attribute (leaf node)
            return SchemaNode(data, "attribute"), ""
        else:
            name, colon, opener, remainder = match.groups()
            node_type = "collection" if opener == "[" else "object"
            node = SchemaNode(name, node_type)

        # Parse internal components
        i = 0
        current_segment = ""
        depth = 0
        
        while i < len(remainder):
            char = remainder[i]
            if char in "{[": depth += 1
            if char in "}]": depth -= 1
            
            # If we hit a comma at the top level of this bracket, it's a sibling
            if char == "," and depth == 0:
                if current_segment:
                    child, _ = helper(current_segment)
                    node.children.append(child)
                current_segment = ""
            # If we hit the closing bracket for this node
            elif depth < 0:
                if current_segment:
                    child, _ = helper(current_segment)
                    node.children.append(child)
                return node, remainder[i+1:]
            else:
                current_segment += char
            i += 1
               
      
        # # Append any remaining segment
        if current_segment:
            child, _ = helper(current_segment)
            node.children.append(child)
        
        return node, ""

    root_tree, _ = helper(schema_text)
    
    # Attach metadata to root node
    root_tree.identifier = metadata["identifier"]
    root_tree.partitionKey = metadata["partitionKey"]
    root_tree.required = metadata["required"]
    
    return root_tree

def split_aggregates(text):
    """
    Split text containing multiple aggregates into individual aggregate texts.
    Each aggregate has the format: AggregateName: { content } or AggregateeName: [ content ]
    Returns a list of individual aggregate strings.
    """
    aggregates = []
    i = 0
    
    while i < len(text):
        # Skip whitespace
        while i < len(text) and text[i].isspace():
            i += 1
        
        if i >= len(text):
            break
        
        # Find the start of an aggregate: Name: { or Name: [
        match = re.match(r'([a-zA-Z0-9_]+)\s*:\s*([\[\{])', text[i:])
        if not match:
            i += 1
            continue
        
        # Found an aggregate start
        aggregate_start = i
        bracket_pos = i + match.start(2)
        opening_bracket = text[bracket_pos]
        closing_bracket = '}' if opening_bracket == '{' else ']'
        
        # Find matching closing bracket by tracking depth
        depth = 0
        j = bracket_pos
        while j < len(text):
            if text[j] in '{[':
                depth += 1
            elif text[j] in '}]':
                depth -= 1
                if depth == 0:
                    # Found the closing bracket - extract the aggregate
                    aggregate_text = text[aggregate_start:j+1].strip()
                    aggregates.append(aggregate_text)
                    i = j + 1
                    break
            j += 1
        else:
            # No matching closing bracket found, move forward
            i += 1
    
    return aggregates

def process_all_aggregates(text):
    """
    Process each aggregate separately through the schema parser.
    Returns a list of SchemaNode trees, one for each aggregate.
    """
    aggregates = split_aggregates(text)
    trees = []
    for aggregate_text in aggregates:
        tree = parse_jsonsm(aggregate_text)
        trees.append(tree)
    return trees


student_schema = """
Student: {
  codcli,
  name,
  dob,
  place,
  email,
  courses: [
    {
      courseId,
      courseName,
      grade
    }
  ]
}

 @metadata:
          identifier: [{codcli}, {name, dob, place}]
          partitionKey: [codcli]
          required: [codcli, name, dob, email]
"""

# ============ Test Cases for Identifier Parsing ============

if __name__ == "__main__":
    # Test Case 1: Multiple identifier options
    schema1 = """
    Student: {
      codcli,
      name,
      dob,
      email
    }
    
    @metadata:
      identifier: [{codcli}, {name, dob}]
      required: [codcli, name, dob, email]
    """
    
    tree1 = parse_jsonsm(schema1)

    print("Test 1 - Multiple Identifier Options:")
    print(f"  Parsed identifier: {tree1.identifier}")
    tree1.display()
    print(f"  Expected: [['codcli'], ['name', 'dob']]")
    print()
    
    # Test Case 2: Single field identifier
    schema2 = """
    Product: {
      productId,
      name,
      price
    }
    
    @metadata:
      identifier: [productId]
      required: [productId, name]
    """
    
    tree2 = parse_jsonsm(schema2)
    print("Test 2 - Single Field Identifier:")
    print(f"  Parsed identifier: {tree2.identifier}")
    print(f"  Expected: [['productId']]")
    print()
    
    # Test Case 3: Composite identifier (multiple fields as one option)
    schema3 = """
    Order: {
      orderId,
      customerId,
      date
    }
    
    @metadata:
      identifier: [customerId, date]
      required: [orderId, customerId, date]
    """
    
    tree3 = parse_jsonsm(schema3)
    print("Test 3 - Composite Identifier (single option):")
    print(f"  Parsed identifier: {tree3.identifier}")
    print(f"  Expected: [['customerId', 'date']]")
    print()
    
    # Test Case 4: Complex case with multiple composite options
    schema4 = """
    Customer: {
      customerId,
      email,
      name,
      phone,
      dob
    }
    
    @metadata:
      identifier: [{customerId}, {email}, {name, dob}]
      partitionKey: [customerId]
      required: [customerId, email]
    """
    
    tree4 = parse_jsonsm(schema4)
    print("Test 4 - Multiple Options with Composites:")
    print(f"  Parsed identifier: {tree4.identifier}")
    print(f"  Expected: [['customerId'], ['email'], ['name', 'dob']]")
    print()

    parsed_identifier = parse_identifier("[ {name, dob, place}]")
    print(f"  Parsed identifier from string: {parsed_identifier}")