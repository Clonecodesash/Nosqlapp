# The Schema Parser

## Overview

Before a student's answer can be graded, the free text they type must be turned
into a structured, machine-comparable form. This is the responsibility of the
schema parser, implemented in the module `json_sm_parser.py`. The parser is the
foundation on which the rest of the evaluation engine rests: every later phase —
the syntax gate, the structural comparison, and the metadata comparison —
operates either on the token stream the parser produces or on the tree it builds.

The module has a deliberately layered design that separates three concerns that
are easy to conflate in a naïve implementation:

1. **A data model** — an explicit tree of `SchemaNode` objects that represents an
   aggregate as nested objects, collections, and attributes.
2. **Validation** — checking that the raw text is well-formed *before* it is
   interpreted, so that malformed input is rejected with a precise, positioned
   message rather than silently mis-parsed.
3. **Construction** — transforming validated text into the tree, together with
   its document-level metadata.

Keeping these concerns apart is what allows the engine to give a student a clear
"this is not yet well-formed" message in one situation and a detailed structural
critique in another, without the two kinds of feedback interfering. The remainder
of this section describes each layer in turn.

## The tree data model

The unit of the model is the `SchemaNode` class. A single node represents one
element of a schema — the root aggregate, an embedded object, a repeating
collection, or a leaf attribute — and is deliberately uniform so that the
comparison phase can treat every element the same way. Each node carries:

- a **name**, the identifier the student wrote (or the sentinel `_unnamed_` for an
  anonymous element, discussed below);
- a **type**, one of `root`, `object`, `collection`, or `attribute`, which
  records *what kind* of element it is and is the pivot on which structural
  comparison turns;
- an ordered list of **children**; and
- three **metadata** lists — `identifier`, `partitionKey`, and `required` — that
  are meaningful only on the root and are left empty elsewhere.

The distinction between an *object* (written with braces, `{ … }`) and a
*collection* (written with square brackets, `[ … ]`) is preserved in the node
type because it is central to aggregate modelling: embedding a single related
document is not the same design decision as embedding a repeating group, and the
evaluator must be able to tell a student when they have confused the two. Leaf
attributes carry no children, and the root additionally owns the parsed metadata
once construction is complete. The class also provides a small recursive
pretty-printer used during development to visualise a parsed tree; it plays no
part in grading.

## Validation before interpretation

A design principle of the parser is that a submission is *checked* before it is
*interpreted*. Two routines implement this principle at two levels of strictness.

### Bracket balance

The most fundamental well-formedness property of the language is that every brace
and square bracket is balanced and correctly nested. This is verified by a single
left-to-right scan that maintains a stack of open brackets, each remembered
together with the line and column at which it appeared. Three failure modes are
distinguished and reported with their exact position: an **unclosed** bracket
(the scan ends with the stack non-empty), an **unexpected closing** bracket (a
closer is met while the stack is empty), and a **mismatched** pair (an object
opened with a brace but closed with a square bracket, or vice versa). Reporting
the position of the *opening* bracket in the unclosed and mismatched cases is a
small but important usability choice, because that is where the student's
attention needs to go.

### The full syntax gate

Bracket balance alone does not guarantee that a submission is meaningful; a
student may also omit the colon that introduces a nested structure, or forget the
comma that separates two attributes. The complete syntax check therefore goes
beyond bracket counting and validates the answer against the grammar of the
language. It is built in two steps.

First, a **tokeniser** converts the raw text into a flat sequence of tokens —
identifiers, the individual punctuation symbols, and an end-of-input marker —
while advancing a line and column counter across skipped whitespace, so that
every token, and therefore every error, is anchored to a real position in the
student's text.

Second, a small **recursive-descent validator** walks that token sequence
according to the grammar

```text
entry     := IDENT (':' container)?          # a named leaf, or a named object/collection
           | container                       # an anonymous object/collection
container := '{' body '}' | '[' body ']'
body      := ( entry (',' entry)* )?         # comma-separated; no leading/double/trailing comma
```

Because the validator is a single left-to-right walk, the error it reports is
always the one that occurs *first in the text*, regardless of its kind — a
misplaced comma early in the answer is reported before an unclosed bracket later
on. When the walk detects a violation it raises an internal exception carrying a
single, fully-formed finding, and the walk unwinds immediately. This
exception-based control flow is what lets a deeply recursive validator abandon
its work at the very first problem without propagating a status flag through every
recursive call. The public entry point orchestrates the whole check: it rejects
an empty answer, separates the schema from the metadata block (which obeys a
different, line-oriented grammar and is checked only for bracket balance), runs
the grammar walk over the schema, and returns the first problem it finds, or
nothing at all when the answer is clean.

The rationale for stopping at the first error is pedagogical rather than
technical. A single missing bracket or comma typically cascades into a long list
of spurious downstream complaints; surfacing only the first, precisely located
problem keeps the feedback focused on the one thing the student must fix before
anything else can be assessed.

## Constructing the tree

Once an answer is known to be well-formed, it is turned into a `SchemaNode` tree.
Construction proceeds in a fixed sequence: the text is split into its schema and
metadata parts on the `@metadata:` marker; the schema's brackets are validated a
final time as a safety net; the metadata block is parsed (below); all whitespace
is stripped from the schema so that the builder can work on a compact character
stream; the tree is built by a recursive helper; and finally the parsed metadata
is attached to the resulting root.

The recursive helper interprets a compact string representing one element. It
recognises the head of that element — an optional name, an optional colon, and an
opening bracket — and classifies the element accordingly. A name followed by a
brace becomes an *object* node and a name followed by a square bracket becomes a
*collection* node; a bare identifier with no following bracket is a *leaf
attribute*; and a fragment that begins directly with a bracket, as the items of a
collection do, becomes an **anonymous** container named with the sentinel
`_unnamed_`. Having identified the element, the helper scans the remainder while
maintaining a nesting-depth counter: a comma encountered at depth zero marks the
boundary between two sibling children, and the closing bracket that returns the
depth below zero ends the current element. Each delimited fragment is parsed
recursively into a child node, so the nested textual structure is mirrored
faithfully by the nested tree.

It is worth noting that the construction grammar is intentionally *more lenient*
than the syntax gate: the recursive helper will, for instance, accept a name that
is not followed by a colon. This is not an oversight but a division of labour —
the builder's sole responsibility is to produce a tree, while the *enforcement* of
the language's rules is delegated to the syntax gate, which always runs first on
the grading path and rejects the ill-formed input before the builder is ever
reached. Concentrating the rules in one place keeps the builder simple and avoids
duplicating the grammar across two components that could drift out of agreement.

## Parsing the metadata block

The metadata block that may follow a schema declares document-level properties:
the identifier, the partition key, and the required attributes. It is parsed
separately from the schema because it follows a simple line-oriented
`key: value` grammar rather than the nested bracket grammar of the schema itself.

The partition key and the required attributes are ordinary comma-separated lists
and are read directly into flat lists of field names. The identifier is more
expressive, because an aggregate may legitimately be identified by *any one of
several* alternative key combinations — for example, a customer might be
identified by a customer code alone, or, failing that, by the combination of name
and date of birth. To capture this, the identifier parser normalises every
accepted notation to the same canonical shape: a *list of options*, in which each
option is itself a list of one or more field names. Both a plain list, understood
as a single composite key, and a brace-grouped list of alternatives are folded
into this representation. This normalisation is deliberately performed at parse
time so that the later comparison can express its rule — *the student's identifier
is correct if it matches any one of the reference's options* — as a direct set
comparison, with no special cases.

## Supporting multiple aggregates

Although a single graded answer concerns one aggregate, some exercises ask a
student to model several. Two helper routines support this. The first scans a body
of text for each aggregate header and uses bracket-depth tracking to extract the
balanced span of text belonging to that aggregate, yielding the individual
aggregate definitions. The second feeds each of those definitions through the
tree constructor, returning one `SchemaNode` tree per aggregate. These helpers
leave the single-answer grading path unchanged while making the same parsing
machinery available to tooling and exercises that operate on a set of aggregates.

## Summary

The parser converts unstructured student text into the typed tree that the rest
of the engine compares, and it does so through a clear separation of validation
from construction. Well-formedness is established first, by a positioned bracket
check and a grammar-driven syntax gate that reports the earliest problem and
nothing more; only then is the text interpreted into a `SchemaNode` tree, with its
document-level metadata normalised into a form that makes the subsequent
comparison concise. This layering — a lenient builder guarded by a strict,
front-loaded validator, over a uniform tree model — is what gives the evaluation
engine both robust, position-accurate error reporting and a clean structure to
grade against.
