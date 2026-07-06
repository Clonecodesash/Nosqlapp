# Chapter X — The Answer Evaluation Engine

## X.1 Introduction

A central contribution of this work is an automated evaluation engine that
grades a student's aggregate-schema answer against a reference answer supplied
by the teacher. The engine is entirely rule-based and deterministic: it does not
rely on a language model to decide correctness. Instead it parses both answers
into an explicit tree representation and compares them structurally, producing a
list of typed, human-readable findings. A large-language-model layer exists in
the system, but only as an *optional explanatory wrapper* around the findings
this engine produces (for example, to rephrase a finding in plainer language);
it never makes the correct/incorrect decision itself. Keeping the grading logic
symbolic makes the outcome reproducible, auditable, and cheap to run, which are
desirable properties for an assessment tool.

The engine is organised around two ideas that recur throughout this chapter.

1. **Two phases in strict order, one problem at a time.** First a *syntax
   phase* checks that the student answer is even well-formed — that brackets
   balance, that a colon separates a name from the structure it introduces, and
   that commas separate attributes. Only if the answer parses does the engine
   proceed to the *comparison phase*, which matches the student tree against the
   reference tree and reports structural and metadata differences. An answer
   that does not parse cannot be compared field by field, so the syntax phase
   acts as a gate and stops at the very first problem it finds. The comparison
   phase follows the same principle: although it computes the complete set of
   differences internally, it surfaces only the *first* one to the student, so
   that feedback is given one correction at a time rather than as an
   overwhelming list.

2. **A single error taxonomy.** Every problem the engine can report — whether a
   misplaced comma or a missing collection — is described once, in a central
   taxonomy, as a stable *code* with a fixed *category* and *severity*. This
   gives every finding a machine-stable identity independent of the exact
   wording shown to the student, which is what makes it possible later to ask
   questions such as *"how often do students forget the colon?"* across a whole
   cohort.

The evaluation logic is spread across five Python modules in the `backend`
package, summarised in Table X.1. The remainder of this chapter presents each
module in turn, following the natural flow of a submission through the system:
the schema language and its parser (§X.3), the syntax phase (§X.4), the taxonomy
(§X.5), the structural comparison (§X.6), the metadata comparison (§X.7), and
finally the orchestration, scoring, and persistence layer that ties them
together and exposes them to the web API (§X.8). §X.9 walks through worked
examples end to end, and §X.10 discusses design decisions and limitations.

**Table X.1 — Evaluation-related backend modules.**

| Module | Responsibility |
|---|---|
| `json_sm_parser.py` | Defines the schema tree (`SchemaNode`); parses the schema DSL and its metadata; performs the Phase-1 syntax check (tokeniser + grammar validator). |
| `error_taxonomy.py` | Central registry of error codes, categories, and severities; the `Feedback` value object shared by every other module. |
| `aggregate_evaluator.py` | Phase-2 structural comparison of the student tree against the reference tree. |
| `metadat_comparison.py` | Phase-2 comparison of the metadata block (identifier, partition key, required attributes). |
| `evaluation.py` | Orchestrates the phases, derives the correct/incorrect verdict, and serialises findings for storage and for the API. |

---

## X.2 The schema definition language

Students express an aggregate model in a small, JSON-like textual language. The
language was chosen to be light enough to type quickly during an exercise while
still capturing the modelling concepts that matter for aggregate design:
attributes, nesting, the distinction between an embedded object and a collection,
and document-level metadata.

A schema consists of a single named **root** followed by a body enclosed in
brackets, and an optional **metadata** block introduced by `@metadata:`. Two
kinds of bracket carry meaning:

- braces `{ … }` denote an **object** (a single embedded document), and
- square brackets `[ … ]` denote a **collection** (a repeating group).

Inside a body, attributes are separated by commas. A bare identifier is a
**leaf attribute**; an identifier followed by a colon and a bracket introduces a
nested **object** or **collection**. Listing X.1 shows a representative answer.

**Listing X.1 — An example schema in the DSL.**

```text
Student: {
  codcli,
  name,
  dob,
  courses: [
    { courseId, courseName, grade }
  ]
}

@metadata:
  identifier: [{codcli}, {name, dob, place}]
  partitionKey: [codcli]
  required: [codcli, name, dob, email]
```

Here `Student` is a root object with four leaf attributes and one nested
collection `courses`, whose items are anonymous objects. The metadata block
declares that a student is identified *either* by `codcli` alone *or* by the
combination `{name, dob, place}`, that data is partitioned by `codcli`, and that
four attributes must always be present.

Informally, the grammar the engine accepts for the schema portion is:

```text
entry     := IDENT (':' container)?          # a named leaf, or a named object/collection
           | container                       # an anonymous object/collection (e.g. a collection item)
container := '{' body '}' | '[' body ']'
body      := ( entry (',' entry)* )?         # comma-separated; no leading/double/trailing comma
```

The metadata block has a different, line-oriented grammar and is parsed
separately (§X.3.4).

---

## X.3 Parsing

Parsing is implemented in `json_sm_parser.py`. It turns the raw text of an answer
into a tree of `SchemaNode` objects that the later phases can traverse. This
section describes the node model, bracket validation, the schema parser proper,
metadata parsing, and support for multiple aggregates in one submission.

### X.3.1 The `SchemaNode` model

Every element of a schema — the root, each embedded object or collection, and
each leaf attribute — is represented by a `SchemaNode`. A node stores its name,
its type, and its ordered list of children; the root additionally carries the
parsed metadata (Listing X.2).

**Listing X.2 — The tree node.**

```python
class SchemaNode:
    def __init__(self, name, node_type="attribute", parent=None):
        self.name = name
        self.node_type = node_type   # "root", "object", "collection", or "attribute"
        self.children = []
        # Metadata fields (populated on the root only)
        self.identifier = []         # primary-key field(s)
        self.partitionKey = []       # partition key(s)
        self.required = []           # required attribute names
        if parent:
            parent.children.append(self)
```

The `node_type` field is the pivot of the whole comparison: whether two matched
elements have the same type (leaf vs. object vs. collection) is one of the main
things the engine checks. `children` is an *ordered* list, but — importantly —
the comparison phase matches children by name rather than by position (§X.6), so
the order in which a student writes attributes does not affect the verdict.

### X.3.2 Bracket validation

Before any tree is built, the parser verifies that every brace and square
bracket is balanced and correctly matched. `validate_brackets(text)` performs a
single left-to-right scan using an explicit stack, tracking the line and column
of every opening bracket so that errors can point precisely at the offending
character. It distinguishes three failure modes:

1. an **unclosed** bracket (the stack is non-empty at end of input);
2. an **extra** closing bracket (a closer with an empty stack); and
3. a **mismatched** pair (e.g. an object opened with `{` but closed with `]`).

On any of these it raises a `ValueError` whose message names the kind of error
and its position. This routine is used both defensively inside the parser and,
in a wrapped form, by the syntax phase for the metadata block (§X.4).

### X.3.3 The schema parser

`parse_jsonsm(text)` produces the tree for one aggregate. Its steps are:

1. **Separate schema and metadata.** The text is split on the literal
   `@metadata:`; everything before it is the schema, everything after is the
   metadata block.
2. **Validate brackets** on the schema text (a safety net that mirrors the
   syntax phase).
3. **Parse the metadata** block, if present, into a dictionary (§X.3.4).
4. **Strip whitespace** from the schema so the recursive walker can operate on a
   compact character stream.
5. **Recursively parse** the schema with an inner `helper` function.
6. **Attach the metadata** (identifier, partition key, required) to the root
   node and return it.

The inner `helper` (Listing X.3, abridged) recognises the head of an element
with a regular expression, `([a-zA-Z0-9_]+)(:)?([\[\{])(.*)`, which captures an
optional name, an optional colon, and the opening bracket. It then walks the
remaining characters, maintaining a `depth` counter: a comma encountered at
`depth == 0` marks a sibling boundary, and the matching closing bracket
(detected when `depth` drops below zero) ends the current element. Each
top-level segment is parsed recursively into a child node. Identifiers with no
following bracket become leaf attributes, and bodies that begin directly with a
bracket become *anonymous* containers named `_unnamed_` (this is how the items of
a collection, written as bare `{ … }`, are represented).

**Listing X.3 — Core of the recursive schema walker (abridged).**

```python
def helper(data):
    match = re.match(r'([a-zA-Z0-9_]+)(:)?([\[\{])(.*)', data)
    if not match and data and data[0] in '{[':
        opener = data[0]
        node_type = "collection" if opener == "[" else "object"
        node = SchemaNode("_unnamed_", node_type)   # anonymous object/collection
        remainder = data[1:]
    elif not match:
        return SchemaNode(data, "attribute"), ""     # leaf attribute
    else:
        name, colon, opener, remainder = match.groups()
        node_type = "collection" if opener == "[" else "object"
        node = SchemaNode(name, node_type)

    depth = 0
    current_segment = ""
    for i, char in enumerate(remainder):
        if char in "{[": depth += 1
        if char in "}]": depth -= 1
        if char == "," and depth == 0:                # sibling boundary
            child, _ = helper(current_segment); node.children.append(child)
            current_segment = ""
        elif depth < 0:                               # end of this node
            if current_segment:
                child, _ = helper(current_segment); node.children.append(child)
            return node, remainder[i+1:]
        else:
            current_segment += char
    # (trailing segment handled after the loop)
    return node, ""
```

Note that in the regular expression the colon is *optional*: the parser will
happily build a tree from `Student { … }` as well as `Student: { … }`. This
leniency is deliberate — the parser's job is to build a tree, and the
*enforcement* of the colon is the responsibility of the syntax phase (§X.4),
which runs first and rejects the colon-less form before the parser is ever
reached on the grading path.

### X.3.4 Metadata parsing

The metadata block is parsed by `parse_metadata`, which reads it line by line as
`key: value` pairs and dispatches on the key. Three keys are recognised:
`identifier`, `partitionKey`, and `required`. Partition key and required are
simple comma-separated lists parsed by `parse_simple_array`.

The identifier is richer, because an aggregate may be identified by *any one of
several* alternative key combinations. `parse_identifier` therefore returns a
*list of options*, where each option is itself a list of field names. Two
notations are supported and normalised to the same shape:

- a plain list such as `[customerId, date]`, read as a *single composite*
  option → `[["customerId", "date"]]`; and
- brace-grouped alternatives such as `[{codcli}, {name, dob, place}]`, read as
  *two* options → `[["codcli"], ["name", "dob", "place"]]`.

The brace-grouped form is parsed by an explicit character scan that collects the
fields inside each `{ … }` group. This normalised representation is what makes
the "match any valid option" logic in the metadata comparison (§X.7) concise.

### X.3.5 Multiple aggregates in one submission

Some exercises call for more than one aggregate. `split_aggregates(text)` scans
the text for each `Name: {` or `Name: [` header and uses bracket-depth tracking
to extract the balanced span belonging to that aggregate, returning the
individual aggregate strings. `process_all_aggregates(text)` then runs each
through `parse_jsonsm` to produce one tree per aggregate. The single-answer
grading path used by the web API evaluates one aggregate at a time; these helpers
support exercises and tooling that operate on a set of aggregates.

---

## X.4 Phase 1 — the syntax check

The syntax phase answers a single question: *is this answer well-formed enough to
be compared at all?* It is implemented in `json_sm_parser.py` as a tokeniser
followed by a grammar validator, and it is the first thing the grading path runs.
Its guiding principle is to **stop at the first error**, because a student who has
made a bracket or comma mistake needs to fix that before any structural feedback
is meaningful, and reporting a cascade of downstream errors caused by one typo is
confusing.

### X.4.1 Tokenisation

`_tokenize_schema(text)` converts the raw schema text into a list of tokens of
the form `(type, value, line, col)`. Whitespace is skipped but still advances the
line and column counters, so that every token — and therefore every error —
carries the exact position of the real character in the student's submission.
The token types are `IDENT` (an identifier), the individual punctuation
characters `{ } [ ] : ,`, `UNKNOWN` for any other character, and a sentinel
`EOF` appended at the end.

### X.4.2 Grammar validation in one pass

`_validate_schema_grammar(text)` walks the token stream as a small
recursive-descent validator over the grammar of §X.2. Crucially, it validates
brackets, colons, and commas **in a single left-to-right pass**, so the error it
reports is always the one that occurs *first in the text*, regardless of its
kind. Two mutually recursive procedures drive the walk:

- `parse_entry` expects either an identifier (optionally followed by `:` and a
  container) or an anonymous container. If it sees an identifier immediately
  followed by `{` or `[`, it reports a **missing colon**; if it sees a `:` not
  followed by a container, it reports a **colon with no container**.
- `parse_container` consumes a `{`/`[`, then repeatedly parses an entry followed
  by either a comma or the matching closer. From this loop fall out the comma
  and bracket diagnostics: a closer of the wrong kind is a **mismatched
  bracket**; end-of-input inside a container is an **unclosed bracket**; two
  entries with no comma between them is a **missing comma**; a comma immediately
  before a closer is a **trailing comma**; and two commas in a row is a **double
  comma**. A leading comma and other stray tokens are caught by `parse_entry`.

The first violation is signalled by raising an internal `_SyntaxProblem`
exception carrying a fully-formed `Feedback` object (§X.5); the walk unwinds and
that single finding is returned. This exception-based control flow is what lets
the deeply recursive walker abandon its work cleanly at the first error without
threading a "stop" flag through every call.

### X.4.3 The public entry point

`check_syntax(text)` is the function the rest of the system calls. It applies the
checks in the order a student should address them (Listing X.4):

1. an **empty** answer is rejected immediately;
2. the schema portion (before `@metadata:`) is validated by the grammar walker;
   and
3. if a metadata block is present, its **bracket balance** is checked (only
   balance, because the metadata block obeys a different `key: value` grammar in
   which colons and commas are legal in positions the schema grammar would
   reject).

It returns the first `Feedback` found, or `None` when the answer is
syntactically clean.

**Listing X.4 — The syntax gate.**

```python
def check_syntax(text):
    import error_taxonomy as tax

    if not text or not text.strip():
        return tax.make("SYN_EMPTY", "The answer is empty. Write a schema before submitting.")

    parts = text.split('@metadata:')
    schema_text = parts[0]
    metadata_text = parts[1] if len(parts) > 1 else ""

    if not schema_text.strip():
        return tax.make("SYN_EMPTY",
                        "No schema found before '@metadata:'. Write the aggregate structure first.")

    try:
        _validate_schema_grammar(schema_text)
    except _SyntaxProblem as problem:
        return problem.feedback

    if metadata_text.strip():
        meta_error = _bracket_balance_feedback(metadata_text, "@metadata")
        if meta_error:
            return meta_error

    return None
```

---

## X.5 The error taxonomy

A recurring difficulty in feedback systems is that findings are represented as
free-text strings, so any later analysis must resort to fragile substring
matching (for example, testing whether a message *contains* the word
"CRITICAL"). The taxonomy in `error_taxonomy.py` removes this fragility by giving
every possible finding a **stable code** with an associated **category** and
**severity**, defined in exactly one place.

Three categories mirror the phases of evaluation: `syntax` (Phase 1),
`structure`, and `metadata` (both Phase 2). Four severities order the findings by
seriousness — `critical`, `error`, `warning`, `info` — and each severity carries
a numeric weight used later for the verdict (Table X.2).

**Table X.2 — Severities and their weights.**

| Severity | Weight | Meaning |
|---|---|---|
| `critical` | 25 | A fundamental structural mismatch (e.g. wrong root type). |
| `error` | 15 | A definite mistake (missing field, wrong type, bad metadata). |
| `warning` | 5 | A likely problem or code smell (extra field, redundant nesting, likely typo). |
| `info` | 0 | Neutral information that does not affect correctness (e.g. a different root name). |

The taxonomy itself is a dictionary mapping each code to its
`(category, severity)` pair. Table X.3 lists the full set of codes.

**Table X.3 — The error taxonomy.**

| Code | Category | Severity | Raised when |
|---|---|---|---|
| `SYN_EMPTY` | syntax | error | The answer is empty. |
| `SYN_UNCLOSED_BRACKET` | syntax | error | A `{`/`[` is never closed. |
| `SYN_EXTRA_BRACKET` | syntax | error | A closer has no matching opener. |
| `SYN_MISMATCHED_BRACKET` | syntax | error | A bracket is closed by the wrong kind. |
| `SYN_MISSING_COLON` | syntax | error | A name is followed directly by `{`/`[`. |
| `SYN_COLON_NO_CONTAINER` | syntax | error | A `:` is not followed by a container. |
| `SYN_MISSING_COMMA` | syntax | error | Two attributes are not comma-separated. |
| `SYN_DOUBLE_COMMA` | syntax | error | Two commas appear in a row. |
| `SYN_LEADING_COMMA` | syntax | error | A comma appears before the first attribute. |
| `SYN_TRAILING_COMMA` | syntax | error | A comma appears before a closing bracket. |
| `SYN_UNEXPECTED_TOKEN` | syntax | error | A stray or misplaced token. |
| `STR_ROOT_TYPE_MISMATCH` | structure | critical | Root object/collection kind differs. |
| `STR_ROOT_NAME_DIFF` | structure | info | Root name differs from the reference. |
| `STR_MISSING_ELEMENT` | structure | error | A reference field is absent from the answer. |
| `STR_EXTRA_ELEMENT` | structure | warning | An answer field has no reference counterpart. |
| `STR_NAME_TYPO` | structure | warning | A field name closely resembles an expected one. |
| `STR_TYPE_MISMATCH` | structure | error | A field is flat where it should be nested, or vice versa. |
| `STR_CONTAINER_KIND_MISMATCH` | structure | error | An object is used where a collection is expected, or vice versa. |
| `STR_CHILD_COUNT_MISMATCH` | structure | warning | Two matched containers hold different numbers of fields. |
| `STR_USELESS_NESTING` | structure | warning | A redundant single-child wrapper adds needless depth. |
| `META_IDENTIFIER_MISSING` | metadata | error | The reference has an identifier; the answer has none. |
| `META_IDENTIFIER_MISMATCH` | metadata | error | The identifier matches none of the valid options. |
| `META_IDENTIFIER_UNEXPECTED` | metadata | warning | The answer declares an identifier the reference does not. |
| `META_PARTITIONKEY_MISSING` | metadata | error | The reference has a partition key; the answer has none. |
| `META_PARTITIONKEY_MISMATCH` | metadata | error | The partition-key fields differ. |
| `META_PARTITIONKEY_UNEXPECTED` | metadata | warning | The answer declares a partition key the reference does not. |
| `META_REQUIRED_MISSING` | metadata | error | Required attributes are missing. |
| `META_REQUIRED_UNEXPECTED` | metadata | warning | The answer marks extra attributes as required. |
| `ENGINE_ERROR` | structure | error | An unexpected internal failure during evaluation. |
| `LEGACY` | structure | info | A finding restored from an older, string-only stored log. |

Every finding produced anywhere in the engine is an instance of the `Feedback`
dataclass (Listing X.5). Besides its code, message, category, and severity, a
finding carries optional location information: `line` and `col` locate a *syntax*
error in the raw text, whereas `path` locates a *structural or metadata* finding
within the schema tree (for example `Student.courses.grade`). The `to_dict`
method yields a JSON-serialisable form that drops empty location fields, and
`__str__` renders a finding for logs and consoles.

**Listing X.5 — The `Feedback` value object and its factory.**

```python
@dataclass
class Feedback:
    code: str
    message: str
    category: str
    severity: str
    line: Optional[int] = None
    col: Optional[int] = None
    path: Optional[str] = None

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None}

    def __str__(self) -> str:
        if self.line is not None and self.col is not None:
            loc = f" (line {self.line}, col {self.col})"
        elif self.path:
            loc = f" (at {self.path})"
        else:
            loc = ""
        return f"[{self.code}] {self.message}{loc}"


def make(code, message, line=None, col=None, path=None) -> Feedback:
    category, severity = TAXONOMY.get(code, (CATEGORY_STRUCTURE, SEVERITY_ERROR))
    return Feedback(code=code, message=message, category=category,
                    severity=severity, line=line, col=col, path=path)
```

The `make` factory is the only way findings are created. Because it looks up the
category and severity from the taxonomy, no call site can accidentally invent a
severity, and an unknown code degrades gracefully to a structure-level error
rather than raising. This single choke point is what guarantees the taxonomy is
authoritative.

---

## X.6 Phase 2 — structural evaluation

Once an answer has passed the syntax gate, it is parsed and compared against the
reference tree by `aggregate_evaluator.py`. The comparison is a recursive
tree-matching procedure whose defining choice is that **children are matched by
name, not by position.**

### X.6.1 Why name-based matching

An earlier, position-based comparison punished a student for listing the correct
fields in a different order, and — worse — a single field inserted or removed
near the top of an object threw off the alignment of *every* field after it,
turning one mistake into a cascade of spurious errors. Matching by name fixes
both problems: order no longer matters, and a field that has been moved from one
object to another surfaces cleanly as *missing here* and *extra there* rather
than corrupting everything downstream.

### X.6.2 The root check and orchestration

The comparison is split into two functions. `evaluate_schemas_full` performs the
*complete* comparison and returns every difference, in evaluation order: it
compares the root *type* (an object/collection mismatch at the root is a
`critical` `STR_ROOT_TYPE_MISMATCH`), records any difference in the root *name*
as neutral `info` (`STR_ROOT_NAME_DIFF`), delegates the metadata comparison to
`metadat_comparison.py` (§X.7), and finally recurses into the children. Each
finding is tagged with a `path` built from the names on the way down, so the
reader can see exactly where in the tree the problem lies (Listing X.6a).

**Listing X.6a — The complete comparison.**

```python
def evaluate_schemas_full(student_node, reference_node):
    feedback = []
    root_path = reference_node.name

    if student_node.node_type != reference_node.node_type:
        feedback.append(tax.make(
            "STR_ROOT_TYPE_MISMATCH",
            f"Root type mismatch: the reference is a {reference_node.node_type}, "
            f"but the student used a {student_node.node_type}.",
            path=root_path))

    if student_node.name.lower() != reference_node.name.lower():
        feedback.append(tax.make(
            "STR_ROOT_NAME_DIFF",
            f"Root name '{student_node.name}' differs from the reference "
            f"'{reference_node.name}'.", path=root_path))

    feedback.extend(metacomp.compare_metadata(student_node, reference_node))
    feedback.extend(evaluate_schemas_recursive(student_node, reference_node, path=root_path))
    return feedback
```

The public `evaluate_schemas` (Listing X.6b) is a thin wrapper that applies the
*one-problem-at-a-time* policy described in §X.1: it scans the complete list in
order and returns only the **first blocking** finding — the first whose severity
is `critical`, `error`, or `warning`. Purely informational findings (such as a
different root name) are therefore never surfaced on their own, and an
otherwise-correct answer yields an empty list. The full list is still produced by
`evaluate_schemas_full`, so it remains available for teacher tooling or
cohort-level analysis even though the student sees only one item.

**Listing X.6b — Reducing to the first blocking finding.**

```python
def evaluate_schemas(student_node, reference_node):
    for finding in evaluate_schemas_full(student_node, reference_node):
        if finding.severity in tax.BLOCKING_SEVERITIES:
            return [finding]
    return []
```

Because the recursion visits reference children in order and, within each child,
applies its checks in a fixed sequence (type, then container kind, then child
count, then nesting), the "first blocking" finding is deterministic and
corresponds to the earliest, outermost problem in the student's answer.

### X.6.3 The recursive comparison

`evaluate_schemas_recursive(s_node, r_node, path)` is the heart of Phase 2. It
first indexes the student's children by lower-cased name into buckets, so that
repeated names can be consumed one at a time and, at the end, any student child
that was never matched can be reported as *extra*. It then walks the reference
children and, for each one, performs the following steps.

**1. Locate the counterpart (with typo tolerance).** It looks up the reference
name among the student buckets. If there is no exact match, it does not
immediately give up: it asks `difflib.get_close_matches` for an as-yet-unused
student name that closely resembles the expected one (similarity ≥ 0.80). If one
is found, the two are matched anyway and a `warning`-level `STR_NAME_TYPO` is
recorded, so that `nam` against an expected `name` is reported as a spelling slip
and *still compared structurally*, rather than producing the misleading pair
*"`name` is missing"* and *"`nam` is extra"*. If neither an exact nor a close
match exists, the field is genuinely absent and an `error`-level
`STR_MISSING_ELEMENT` is emitted.

**2. Compare type (flat vs. nested).** If the reference field is a container but
the student's is a leaf (or vice versa), that is an `error`-level
`STR_TYPE_MISMATCH` — the student has, for instance, written `dob` as a plain
attribute where an embedded `{ day, month, year }` object was expected.

**3. Compare container kind (object vs. collection).** When both are containers
but of different kinds — an object where a collection was expected, or the
reverse — an `error`-level `STR_CONTAINER_KIND_MISMATCH` is raised.

**4. Compare child count.** When both are containers *of the same kind*, a
difference in the number of children is reported as a `warning`-level
`STR_CHILD_COUNT_MISMATCH`. This is deliberately a warning rather than an error:
the per-field *missing*/*extra* findings already pinpoint *which* fields differ,
and the count is offered as a quick structural summary rather than an independent
penalty.

**5. Flag useless nesting.** A heuristic, `is_useless_nesting`, detects a
redundant single-child wrapper — a container the student has nested one level
deeper than the reference justifies — and raises a `warning`-level
`STR_USELESS_NESTING` recommending that the structure be flattened.

**6. Recurse.** When both counterparts are containers, the procedure recurses
into them, extending the `path` with the current field name.

After all reference children have been processed, any student child that was
never matched is reported as a `warning`-level `STR_EXTRA_ELEMENT`. Listing X.7
shows the matching-and-typo core of the loop.

**Listing X.7 — Locating each reference field, with typo tolerance (excerpt).**

```python
for r_sub in r_node.children:
    child_path = f"{path}.{r_sub.name}" if path else r_sub.name
    candidates = student_by_name.get(r_sub.name.lower())
    is_typo = False

    if not candidates:                       # no exact match -> try a close name
        alt = find_close_name(r_sub.name)
        if alt:
            candidates = student_by_name.get(alt)
            is_typo = True

    if not candidates:                       # genuinely absent
        inner_feedback.append(tax.make(
            "STR_MISSING_ELEMENT",
            f"Expected '{r_sub.name}' inside '{r_node.name}', but it was not found ...",
            path=child_path))
        continue

    s_sub = candidates.pop(0)
    matched.add(id(s_sub))
    if is_typo:
        inner_feedback.append(tax.make(
            "STR_NAME_TYPO",
            f"'{s_sub.name}' looks like a misspelling of the expected '{r_sub.name}'.",
            path=child_path))
    # ... type, container-kind, child-count, useless-nesting checks, then recurse ...
```

### X.6.4 The useless-nesting heuristic

`is_useless_nesting(student_node, reference_node)` encodes a small piece of
modelling judgement: nesting is only *useful* if the reference also nests at that
point. It returns `True` (nesting is redundant) when the reference counterpart is
a leaf, or has a number of children other than one, or has a single child that is
not itself a container while the student's is. In other words, a lone extra
wrapper the student has introduced around a scalar is flagged, but a legitimately
nested structure that the reference shares is not. This keeps the heuristic
conservative, so that it nudges rather than nags.

---

## X.7 Phase 2 — metadata comparison

`metadat_comparison.py` compares the three metadata facets attached to the root:
the identifier, the partition key, and the required attributes. All comparisons
are case-insensitive and set-based, so ordering and letter case never matter, and
every difference is returned as a `Feedback` from the metadata category.

**Identifier.** The identifier is the most involved because the reference may
admit several alternative key combinations (§X.3.4). The student's identifier is
considered valid if, treated as a case-insensitive set, it equals *any one* of
the reference's options. If it matches none, a `META_IDENTIFIER_MISMATCH` is
raised that lists the acceptable options; if the reference requires an identifier
and the student supplied none, a `META_IDENTIFIER_MISSING` is raised; and if the
student supplied one where the reference expects none, a warning-level
`META_IDENTIFIER_UNEXPECTED` is raised. The comparison also normalises the
several shapes the parsed identifier can take (a flat list, a single-option list
of lists, or a multi-option list of lists) before comparing.

**Partition key.** The partition-key fields are compared as case-insensitive
sets. A difference is decomposed into *missing* and *extra* fields, yielding a
`META_PARTITIONKEY_MISMATCH` (error) when the student's set is wrong, a
`META_PARTITIONKEY_MISSING` (error) when the reference has a partition key and the
student has none, and a `META_PARTITIONKEY_UNEXPECTED` (warning) in the reverse
case.

**Required attributes.** The set of required attribute names is compared the same
way: names present in the reference but absent from the student's set produce a
`META_REQUIRED_MISSING` (error), and names the student marked required beyond
those the reference expects produce a `META_REQUIRED_UNEXPECTED` (warning).

---

## X.8 Orchestration, verdict, and persistence

`evaluation.py` is the seam between the pure evaluation engine and the
application. Its `evaluate_aggregate_answer(student_answer, reference_answer)`
function drives the whole pipeline in the correct order (Listing X.8):

1. **Syntax gate.** It calls `check_syntax` on the student answer. If a syntax
   problem is found, it returns *that finding alone*, with an immediate verdict of
   incorrect — the answer cannot be compared, so no structural feedback is
   attempted.
2. **Parse.** Otherwise it parses both the student and reference answers into
   trees.
3. **Compare.** It runs `evaluate_schemas` to obtain the list of structural and
   metadata findings.
4. **Score and decide.** It converts the findings into the verdict (below).

The whole body is wrapped so that any unexpected internal failure is turned into
a single `ENGINE_ERROR` finding rather than propagating an exception to the API.

**Listing X.8 — The orchestration entry point.**

```python
def evaluate_aggregate_answer(student_answer, reference_answer) -> dict:
    try:
        syntax_error = check_syntax(student_answer)
        if syntax_error:
            return {"feedback": [syntax_error.to_dict()], "score": 0, "is_correct": False}

        student_node = parse_jsonsm(student_answer)
        reference_node = parse_jsonsm(reference_answer)

        feedback_objs = evaluate_schemas(student_node, reference_node)
        return _score_from_feedback(feedback_objs)
    except Exception as e:
        return {"feedback": [tax.make("ENGINE_ERROR", f"Evaluation failed: {e}").to_dict()],
                "score": 0, "is_correct": False}
```

### X.8.1 Deriving the verdict

Because the taxonomy already assigns a severity (and weight) to every finding,
the verdict is computed directly from the findings, with no substring inspection
of messages (Listing X.9). An answer is judged **correct** only when it produces
*no* finding of a blocking severity — that is, no `critical`, `error`, or
`warning`. Purely `info` findings, such as a differently-named root, do not make
an answer wrong. (A numeric score is also computed, by deducting each finding's
weight from a starting value of 100, but in the current interface it is not shown
to the student; the correct/incorrect verdict is what the user interface presents,
tinting its panel blue for a correct answer and red for an incorrect one.)

**Listing X.9 — Verdict from findings.**

```python
def _score_from_feedback(feedback_objs) -> dict:
    feedback = [f.to_dict() for f in feedback_objs]
    if not feedback_objs:
        return {"feedback": feedback, "score": 100, "is_correct": True}

    penalty = sum(tax.SEVERITY_WEIGHTS.get(f.severity, 15) for f in feedback_objs)
    score = max(0, 100 - penalty)
    is_correct = not any(f.severity in tax.BLOCKING_SEVERITIES for f in feedback_objs)
    return {"feedback": feedback, "score": score, "is_correct": is_correct}
```

### X.8.2 Serialisation and backward compatibility

Findings are stored with each answer log so that past attempts can be reviewed.
`feedback_to_json` serialises the list of finding dictionaries to a JSON string,
and `feedback_from_json` restores it. Because an earlier version of the system
stored findings as plain strings, the restore routine is tolerant: any legacy
string it encounters is wrapped into the structured shape under the `LEGACY`
code, so that old and new answer logs render uniformly in the interface. The API
exposes findings through a `FeedbackItem` schema whose fields mirror the
`Feedback` object, and the front end renders each finding with a small
severity-coloured badge, its message, and its code.

---

## X.9 Worked examples

This section traces several answers through the engine against the reference of
Listing X.1, to show the two phases and the taxonomy in action.

**A well-formed, correct answer.** An answer identical in structure and metadata
to the reference passes the syntax gate, produces no blocking findings, and is
judged correct.

**A missing colon —** `Student { codcli, name }`. The syntax phase reaches the
identifier `Student` immediately followed by `{`, and — before any comparison —
returns the single finding
`[SYN_MISSING_COLON] Missing ':' between 'Student' and '{' … (line 1, col 9)`.
Nothing else is reported, illustrating the *stop-at-first-error* gate.

**A missing comma —** `Student: { codcli name, dob }`. The gate reports
`[SYN_MISSING_COMMA] Missing ',' before 'name' … (line 1, col 20)` and stops.

**A mismatched bracket —** `Student: { codcli, name ]`. The gate reports
`[SYN_MISMATCHED_BRACKET] '{' opened at line 1, col 10 is closed by ']' …` and
stops.

**A structural answer with several mistakes.** Consider an answer that spells
`name` as `nam`, writes `dob` as an embedded object rather than a leaf, omits two
fields inside the collection item, adds an unexpected `hobby` attribute, and
under-specifies the metadata. This answer is syntactically clean, so it reaches
Phase 2. Internally, `evaluate_schemas_full` records the whole set of
differences — a warning `STR_NAME_TYPO` for `nam` (which is nonetheless matched
to `name`), an error `STR_TYPE_MISMATCH` for `dob`, a warning
`STR_CHILD_COUNT_MISMATCH` and two errors `STR_MISSING_ELEMENT` inside the
collection, a warning `STR_EXTRA_ELEMENT` for `hobby`, and metadata errors for
the missing partition key and required attributes — each tagged with its path in
the tree. Following the one-problem-at-a-time policy, however, `evaluate_schemas`
surfaces only the *first* of these blocking findings to the student. Because at
least one blocking finding is present, the verdict is incorrect; once the student
fixes that first issue and resubmits, the next-earliest problem is revealed in
turn.

---

## X.10 Design decisions and limitations

**Separation of concerns.** Keeping the taxonomy in its own module, and forcing
every finding through the `make` factory, means severity and category are defined
exactly once. Scoring and the correct/incorrect decision never re-derive a
finding's seriousness from its wording; they read it from the finding itself.
This is the single most important structural decision in the engine.

**Two phases with a hard gate, and one problem at a time.** Refusing to compare
an answer that does not parse, and reporting only the first syntax error, keeps
early feedback focused and avoids the confusion of cascaded errors. The
comparison phase applies the same discipline: it computes every difference but
shows the student only the first blocking one, so corrections are made
incrementally. The cost is that a student sees problems one at a time and must
resubmit to reveal the next; this is an intentional trade-off in favour of
clarity over completeness. Because the full set of differences is still computed
by `evaluate_schemas_full`, a future teacher-facing view could present the
complete list without any change to the engine.

**Name-based, typo-tolerant matching.** Matching children by name rather than by
position, and recovering close misspellings before declaring a field missing,
makes the structural feedback robust to superficial differences and keeps it
aligned with what a human grader would say. The similarity threshold (0.80) is a
tunable constant.

**Lenient parser, strict gate.** The parser deliberately tolerates a missing
colon so that it can still build a tree; enforcement lives in the syntax phase.
On the grading path this is invisible, because the gate runs first, but it does
mean the parser and the gate encode the grammar in two places, which must be kept
consistent.

**Known limitations.** The engine grades structure and metadata, not semantics: it
cannot tell whether an embedding decision is a *good* modelling choice, only
whether it matches the reference, so it presumes a single canonical reference
answer. The `_unnamed_` placeholder used for anonymous collection items surfaces
in some messages and reads a little awkwardly. And while a numeric score is
computed internally, it is not currently surfaced to students; the interface
presents only the binary verdict. These are natural avenues for future
refinement.
```
