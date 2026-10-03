---
name: spec-to-code
version: 0.3
description: >
  Implement code changes from a specification or requirement by first
  exploring the existing codebase, separating facts, requirements,
  design decisions, assumptions, and risks, creating and reviewing an
  implementation plan, implementing the change, and verifying all
  important claims with appropriately scoped evidence.
---

# Spec to Code

## Purpose

Use this skill when implementing a feature or code change from:

- a specification
- a protocol document
- a design document
- a user requirement
- an existing implementation requirement

The goal is not only to generate working code.

The goal is to produce code that:

1. matches the actual requirement,
2. follows appropriate existing codebase patterns,
3. separates required behavior from implementation design,
4. avoids unsupported semantic assumptions,
5. preserves existing behavior unless change is required,
6. exposes important risks and consequences,
7. stops when a material human decision is required,
8. verifies claims with appropriately scoped evidence.

Do not jump directly from requirement to implementation.

Follow the phases below in order.

---

# Core Reasoning Model

Throughout this skill, distinguish the following categories.

## 1. FACT

A fact is something directly established by evidence.

Possible sources:

    SPEC
    USER
    EXISTING_CODE
    EXISTING_TEST
    PROJECT_DOC

Examples:

    The specification says each task has a priority.

    The existing parser returns payload_offset relative
    to the protocol header.

A fact must not contain an unstated design choice.

---

## 2. REQUIREMENT

A requirement defines WHAT behavior the implementation must provide.

Allowed semantic sources:

    USER
    SPEC
    EXISTING_CONTRACT
    HUMAN_DECISION

Examples:

    Same-priority tasks preserve submission order.

    IPv6 version must equal 6.

    Existing FIFO callers must continue to observe FIFO behavior.

Requirements must be testable or otherwise verifiable.

An implementation pattern is not by itself a semantic requirement source.

---

## 3. DESIGN_DECISION

A design decision defines HOW an approved requirement will be represented
or implemented.

Examples:

    Represent task priority as Task::priority.

    Store the field at the end of the structure.

    Use a linear scan to select the next task.

    Format one IPv6 address through a pointer-based helper.

A design decision must map to one or more requirements.

A design decision must not be presented as though it were directly required
by the specification unless the specification actually requires that design.

---

## 4. IMPLEMENTATION_PATTERN

An implementation pattern describes how the existing project commonly
implements similar behavior.

Examples:

    Functions return bool.

    Errors are returned through std::string&.

    Parsers validate buffer length before byte access.

    Naming uses snake_case.

Implementation patterns primarily guide HOW code is written.

They do not automatically define WHAT new semantics mean.

---

## 5. ASSUMPTION

An assumption is a semantic interpretation or design premise that is not
directly established by sufficient evidence.

Examples:

    A special protocol field value should mean remaining buffer length.

    Lower numeric values should mean higher priority.

    Missing priority should default to zero.

Assumptions must be reviewed before implementation.

---

## 6. RISK

A risk is a possible negative impact introduced or exposed by the change.

Examples:

    Public structure layout changes.

    Algorithmic complexity increases.

    Existing binary consumers may depend on structure layout.

A risk is not automatically a blocker.

Classify risks according to evidence.

---

## 7. CONSEQUENCE

A consequence is an observable property resulting from an approved design.

Examples:

    Linear scanning changes run_next from O(1) selection to O(n).

    Choosing default priority 0 with smaller-is-higher means default tasks
    cannot be outranked by any uint32_t value.

Consequences are not necessarily bugs.

Important consequences should be reported so humans can evaluate them.

---

# Fundamental Traceability Chain

Maintain this chain throughout the task:

    Source
      ↓
    Fact
      ↓
    Requirement          WHAT
      ↓
    Design Decision      HOW
      ↓
    Implementation
      ↓
    Test
      ↓
    Evidence
      ↓
    Claim

Do not silently skip layers.

A conclusion may cross layers only when the reasoning is explicitly stated.

---

# Evidence Principle

Evidence must directly support the conclusion for which it is used.

Related evidence is not sufficient by itself.

Do not combine partial evidence with unstated model reasoning and then present
the result as directly supported.

Always ask:

    What exactly does this evidence prove?

and:

    Does it prove the semantic behavior,
    or only justify an implementation choice?

---

# Phase 1: Explore

## Goal

Understand the project structure and locate all code relevant to the requested
change.

## Actions

Inspect:

- project structure
- README or project documentation
- specification documents
- build configuration
- relevant headers
- relevant implementations
- entry points
- call sites
- related data structures
- existing tests

Search for:

- relevant symbols
- related constants
- similar implementations
- existing error handling
- existing compatibility behavior
- existing tests

Do not modify files during this phase.

## Output

Produce:

### Project Structure

List only relevant project files and directories.

### Relevant Files

For each relevant file, explain why it matters.

### Entry Point

Identify where the requested behavior enters the code.

### Call Chain

Describe the relevant call chain.

### Related Data Structures

Identify structures whose semantics, layout, or ownership may be affected.

### Related Tests

Identify existing tests related to the behavior.

### Build and Test

Identify how the project is built and tested.

## Gate

Do not continue until you can answer:

- Where does the requested behavior enter the project?
- Which files implement the current behavior?
- Which data structures are involved?
- Which tests cover the current behavior?
- How is the project built?
- How are tests executed?

If important information is missing, continue exploring.

---

# Phase 2: Understand

## Goal

Understand current behavior before designing changes.

## Analyze

Identify:

- control flow
- data flow
- error flow
- input/output contracts
- offset semantics where relevant
- length semantics where relevant
- ownership/lifetime where relevant
- caller/callee responsibilities
- compatibility-sensitive boundaries
- algorithmic behavior relevant to the change

Do not infer semantics from names alone.

Trace how values are produced and consumed.

## Output

Produce:

### Current Behavior

Describe the relevant behavior end-to-end.

### Existing Contracts

Document behavior that existing callers rely on.

For every important conclusion, identify its evidence category:

    EXISTING_CODE
    EXISTING_TEST
    PROJECT_DOC
    INFERENCE

Do not present INFERENCE as an established contract.

## Gate

Do not continue until the relevant current behavior can be explained
end-to-end.

---

# Phase 3: Extract Existing Patterns

## Goal

Extract reusable engineering patterns from the existing code.

Identify patterns such as:

- function signature style
- return-value convention
- error propagation
- naming
- bounds checking
- endian conversion
- bit-field extraction
- output parameters
- offset conventions
- container usage
- file organization
- testing style

## Output

Produce:

### Existing Implementation Patterns

For example:

    Input:
        const uint8_t* data
        std::size_t length

    Output:
        Header&
        payload_offset&
        payload_length&
        error&

    Return:
        bool

    Error:
        set error string
        return false

    Bounds:
        validate length before accessing bytes

## Pattern Applicability Rule

Do not use a pattern merely because two things look similar.

Before applying an existing pattern to a new design decision, ask:

    What property makes this pattern applicable here?

Example:

Bad:

    id is uint32_t
    therefore priority should be uint32_t

The fact that two values are both fields does not establish that they share
the same domain or range.

Better:

    Existing counters representing the same bounded domain use uint32_t,
    and the specification defines the new value as belonging to that same
    domain.

## Pattern vs Semantics Rule

Existing patterns primarily answer:

    HOW does this project implement similar behavior?

Specifications and requirements answer:

    WHAT behavior is required?

Never use an existing implementation pattern as the sole evidence for a new
semantic requirement.

---

# Phase 4: Extract Requirements

## Goal

Convert the requested change into explicit, testable requirements.

Assign IDs:

    R1
    R2
    R3
    ...

## Requirement Source

For every requirement record one or more direct sources:

    USER
    SPEC
    EXISTING_CONTRACT
    HUMAN_DECISION

Do not use:

    EXISTING_PATTERN

as the sole semantic source.

## Requirement Provenance Rule

Do not expand a broad user request into narrower requirements without evidence.

Example:

User:

    Add IPv6 support.

This does not automatically establish:

    Add an IPv6 address formatting helper.

The helper may be a useful design decision, but it is not necessarily a user
requirement.

Similarly:

Specification:

    Each task has a priority.

This establishes:

    Each task must have an associated priority.

It does not by itself establish:

    Add uint32_t priority to struct Task.

That is a design decision.

## Output

Produce:

### Requirements

Example:

    R1 Each task has an associated priority.
       Source: SPEC

    R2 Higher-priority pending tasks execute first.
       Source: SPEC

    R3 Same-priority tasks preserve submission order.
       Source: SPEC

### Out of Scope

Explicitly define behavior not part of the requested change.

Example:

    O1 Preemption of running tasks.
    O2 Thread safety.
    O3 Priority aging.

## Gate

Each requirement must be:

- understandable
- implementable
- verifiable
- traceable to a direct semantic source

If a semantic requirement has no direct source:

    do not invent one;
    move the unresolved question to Phase 6.

---

# Phase 5: Design

## Goal

Design the minimum implementation needed to satisfy the approved requirements.

Create explicit design decisions.

Assign IDs:

    D1
    D2
    D3
    ...

## Design Decision Format

For each decision record:

    ID
    Decision
    Requirements satisfied
    Evidence / rationale
    Alternatives considered
    Consequences
    Risks

Example:

    D1
    Decision:
        Represent priority as Task::priority.

    Requirements:
        R1

    Rationale:
        Keeps priority associated with the task object and preserves
        existing Scheduler method signatures.

    Alternatives:
        submit(task, priority)
        internal PendingTask wrapper

    Consequences:
        Task layout changes.

    Risks:
        Possible ABI impact if external binary consumers exist.

## Design Evidence Rule

A design decision does not require the specification to dictate the exact
implementation.

The agent may make reasonable HOW decisions when:

1. requirements are already clear,
2. the decision does not invent new semantic behavior,
3. the decision follows applicable project patterns,
4. material consequences are identified,
5. no unresolved compatibility boundary requires human approval.

## Semantic Leakage Rule

Before accepting a design decision, ask:

    Does this HOW decision silently define new WHAT behavior?

Example:

    Append priority with default value 0.

This contains two different decisions:

    HOW:
        Add a field at the end of Task.

    WHAT:
        Missing priority means priority 0.

The HOW may be autonomous.

The WHAT requires semantic evidence or human decision.

Separate them.

## Minimal Change Rule

Prefer the smallest design that satisfies the approved requirements.

Do not add behavior merely because it appears:

- convenient
- future-proof
- common
- defensive
- easy to support

Extra behavior still requires justification.

---

# Phase 6: Assumption Review

## Goal

Find unsupported semantic assumptions before implementation.

Search requirements and design decisions for reasoning such as:

- probably
- usually
- should
- assume
- normally
- likely
- for compatibility
- convenient
- future-proof
- default
- special-case behavior
- implicit numeric direction
- implicit range or type semantics

Create an assumption table.

Example:

| ID | Assumption | Proposed Behavior | Evidence | Decision |
|----|------------|-------------------|----------|----------|
| A1 | lower value means higher priority | compare using `<` | none | CLARIFY |
| A2 | missing priority means 0 | default to 0 | none | CLARIFY |

## Direct Evidence Rule

An assumption may only be accepted when evidence directly supports the
specific semantic behavior.

The following is not sufficient:

    The specification mentions a special value.

therefore:

    choose a particular fallback behavior.

Similarly:

    Existing field X uses uint32_t.

does not directly establish:

    new field Y should use uint32_t.

## Decisions

Every assumption must end in one of:

    ACCEPT
    REJECT
    CLARIFY
    DEFER_OUT_OF_SCOPE

### ACCEPT

Allowed only when sufficient evidence supports the behavior.

### REJECT

Do not implement the assumed behavior.

### CLARIFY

Trigger the appropriate STOP condition.

### DEFER_OUT_OF_SCOPE

Do not implement the behavior and record it explicitly.

## Human Decision Rule

After the human resolves an ambiguity:

1. record the decision,
2. classify its source as HUMAN_DECISION,
3. update affected requirements or design decisions,
4. re-check dependent assumptions,
5. continue only when the decision chain is consistent.

Do not continue treating a resolved human decision as an AI assumption.

## Gate

Do not continue while a material semantic assumption remains unresolved.

---

# Phase 7: Implementation Plan

## Goal

Create a concrete implementation plan before editing code.

For every step include:

### Step N

**File**

File to modify or create.

**Requirements**

Requirement IDs satisfied.

**Design Decisions**

Design IDs implemented.

**Change**

Specific symbols and behavior to change.

**Reason**

Why the change is required.

**Dependencies**

Other decisions or steps it depends on.

**Consequences**

Important behavioral, complexity, layout, or compatibility consequences.

**Verification**

How the step will be verified.

## Interface Review

For any new or modified interface, ask:

- Does every parameter have one clear meaning?
- Can the function determine exactly what object/value it operates on?
- Is any parameter broader than necessary?
- Does the interface silently encode unresolved semantics?
- Does it follow applicable project style?

Do not defer obvious interface ambiguity to implementation.

---

# Phase 8: Plan Review

## Goal

Audit the plan before coding.

Perform all mappings below.

## Requirement -> Design

Every requirement must be satisfied by one or more design decisions.

## Design -> Requirement

Every design decision must map back to:

- a requirement,
- a necessary implementation dependency,
- or a preserved existing contract.

## Design -> Implementation Plan

Every approved design decision must have a concrete implementation step.

## Plan -> Verification

Every important behavior change must have a verification method.

## Review For

Identify:

- missing requirements
- requirement expansion
- WHAT/HOW confusion
- unsupported assumptions
- unnecessary design decisions
- scope creep
- ambiguous interfaces
- public API changes
- ABI/layout changes
- serialization changes
- complexity changes
- compatibility risks
- important design consequences

## Cross-Layer Jump Review

Explicitly inspect for reasoning shaped like:

    SPEC fact
        ↓
    implementation representation

without an explicit design decision.

Also inspect:

    EXISTING_PATTERN
        ↓
    new semantic behavior

and:

    TEST expectation
        ↓
    requirement

These are suspicious jumps and must be justified.

---

# Compatibility Review

Classify compatibility findings as follows.

## POTENTIAL_RISK

A theoretical compatibility risk exists, but there is no evidence that the
affected boundary is used in a compatibility-sensitive way.

Record it.

Do not automatically stop.

## CONFIRMED_RISK

Evidence shows the change crosses a compatibility-sensitive boundary such as:

- shared-library ABI
- public binary interface
- serialized persistent data
- shared memory
- externally consumed structure layout
- stable public API
- fixed wire/storage representation

If the requirement does not explicitly authorize the impact:

    STOP.

## Human Acceptance Rule

The model must not write:

    accepted
    approved
    acceptable

for a significant compatibility impact unless supported by:

- explicit USER decision,
- explicit HUMAN_DECISION,
- SPEC requirement,
- or an established project contract showing compatibility is irrelevant.

The model may identify a risk.

It may not grant human approval to itself.

---

# Risk Evidence Rule

Risk claims must obey the same evidence discipline as functional claims.

Do not write:

    Consumers must recompile.

when there is no evidence that external consumers exist.

Write:

    Task layout changed.

    If external binary consumers depend on this layout,
    they may require recompilation or adaptation.

    No evidence of such consumers was found.

Distinguish:

    confirmed impact
    potential impact
    hypothetical impact

Do not convert hypothetical consumers into known consumers.

---

# Consequence Review

For every important design decision, identify observable consequences.

Consider:

- time complexity
- space complexity
- data layout
- ordering
- default behavior
- representable value range
- error behavior
- performance characteristics
- compatibility
- extensibility

Do not automatically classify every consequence as a risk.

Example:

    run_next selection changes from O(1) to O(n).

This is a consequence.

It becomes a risk only when workload expectations make the change potentially
problematic.

---

# Phase 8 Gate

Do not implement if:

- a requirement has no design,
- a design has no justification,
- a major plan step has no requirement/design mapping,
- a material semantic assumption remains unresolved,
- an interface remains materially ambiguous,
- a design silently introduces unresolved semantics,
- or a confirmed compatibility risk requires human confirmation.

---

# Neutral STOP Policy

When a STOP condition requires a human decision, present options neutrally.

Do not label an option as:

    Recommended
    Preferred
    Best
    Default
    Safest

unless the user explicitly asks for a recommendation.

Do not preselect an option.

For each materially different option provide:

    Option
    Behavior
    Impact
    Trade-offs

Example:

    Option 1
    Behavior:
        Lower numeric values mean higher priority.

    Impact:
        Comparison uses `<`.

    Trade-offs:
        If default is 0 and type is unsigned,
        default tasks cannot be outranked.

    Option 2
    Behavior:
        Higher numeric values mean higher priority.

    Impact:
        Comparison uses `>`.

    Trade-offs:
        Default-value semantics must still be defined.

Then ask for the exact human decision.

The purpose of STOP is to expose a decision boundary, not to steer the human
toward the model's preferred answer.

---

# Phase 9: Implement

## Goal

Execute the approved plan.

## Rules

Follow:

- approved requirements
- approved human decisions
- approved design decisions
- applicable existing project patterns
- approved implementation plan

Avoid unrelated refactoring.

Do not silently deviate from the plan.

## Plan Deviation Rule

If implementation reveals a plan defect:

1. stop the affected implementation step,
2. describe the defect,
3. identify affected requirements and design decisions,
4. determine whether semantics change,
5. propose the smallest correction,
6. re-run relevant Phase 6 and Phase 8 checks,
7. continue only when justified.

Record all deviations.

## Mechanical Deviation

A purely mechanical deviation that does not change semantics may continue
after being recorded and checked.

Examples:

    build generator unavailable
    source file path differs
    harmless compiler-specific command adjustment

Do not use "mechanical deviation" to hide semantic changes.

---

# Phase 10: Regression Review

## Goal

Determine whether existing behavior may have changed.

Inspect the final diff.

Check:

- modified existing paths
- public interfaces
- data structure layout
- ABI impact
- serialization formats
- ordering behavior
- default behavior
- offset/length semantics
- existing error behavior
- complexity
- existing tests
- unrelated changes

For each affected existing behavior, identify regression evidence.

## Regression Language Rule

Do not claim:

    behavior unchanged

unless evidence supports the entire claimed behavior space.

Prefer:

    No regression was observed within existing test coverage.

or:

    The reviewed implementation path is unchanged and existing tests continue
    to pass.

Distinguish:

    source unchanged
    control flow unchanged
    tests unchanged
    tests passing
    behavior proven unchanged

These are not equivalent.

---

# Phase 11: Test

## Goal

Verify both new behavior and existing behavior.

Tests should include, where applicable:

### Positive

Valid expected behavior.

### Negative

Invalid inputs.

### Boundary

Minimum, maximum, exact boundary, empty state, malformed input.

### Ordering

When behavior depends on ordering or priority.

### Regression

Existing behavior that must remain unchanged.

### Consequence

Important observable consequences when practical to test.

## Discriminating Test Values

Use values capable of distinguishing correct implementations from common
incorrect implementations.

For bit fields:

    use non-zero asymmetric values.

For ordering:

    use non-monotonic priorities.

Example:

    5, 1, 3

rather than:

    1, 2, 3

For stable ordering:

    include repeated values separated by other values.

Example:

    1, 1, 2, 1

## Special-Value Rule

Do not create a test that silently defines unresolved semantics.

A test verifies an approved requirement or design consequence.

A test must not manufacture a requirement after implementation.

If expected behavior is unresolved:

    return to Phase 6.

## Run

Run:

- build
- existing tests
- new tests

Record actual commands and results when available.

---

# Phase 12: Evidence Audit

## Goal

Check whether verification claims are actually supported.

For each important claim create:

    Claim -> Evidence -> Assessment

Assessment must be one of:

    SUPPORTED
    PARTIALLY_SUPPORTED
    UNSUPPORTED

Example:

| Claim | Evidence | Assessment |
|-------|----------|------------|
| Existing FIFO behavior has no observed regression | existing tests + design reasoning | SUPPORTED within tested scope |
| Same-priority ordering is stable | explicit stable-order test | SUPPORTED within tested scope |
| Large-N performance is acceptable | no benchmark | UNSUPPORTED |

## Evidence Scope Rule

Evidence supports only the scope it actually exercises.

Examples:

    One happy-path test
        does not prove boundary handling.

    Existing tests passing
        does not prove all historical behavior is unchanged.

    Source inspection
        does not prove runtime behavior in all environments.

    A test of chosen behavior
        does not prove the behavior was required by the specification.

    A structure layout change
        does not prove external ABI breakage if no external consumer is known.

## Claim Strength Rule

Never upgrade:

    tests passed

into:

    implementation is completely correct

without sufficient evidence.

Avoid broad claims such as:

- fully correct
- completely verified
- all edge cases handled
- behavior unchanged
- fully compliant

unless evidence directly supports that scope.

Prefer:

    supported within tested scope
    no regression observed in existing tests
    not fully verified
    potential risk
    out of scope

---

# Phase 13: Verification Report

Produce the final report using the following structure.

## Implementation Status

Short summary of what was implemented.

---

## Requirement Status

For every requirement:

    R1 PASS / FAIL / PARTIAL

Include source and supporting evidence.

---

## Design Decisions

List important design decisions:

| ID | Decision | Requirement | Rationale | Consequence |
|----|----------|-------------|-----------|-------------|

Do not report design decisions as specification facts.

---

## Changes

List relevant files and behavior changes.

---

## Assumptions

List all assumptions and final decisions:

    ACCEPT
    REJECT
    CLARIFY
    DEFER_OUT_OF_SCOPE

For each include:

    Evidence
    Decision source

If resolved by a human, write:

    HUMAN_DECISION

rather than presenting it as model reasoning.

---

## Test Results

Report actual build and test results.

Do not report tests as executed unless they were actually executed.

---

## Regression Status

Describe regression evidence and its limits.

---

## Verified

List behavior supported by sufficient evidence.

---

## Not Fully Verified

List behavior with incomplete evidence.

---

## Out of Scope

Repeat explicitly excluded behavior.

---

## Known Risks

For each risk include:

    Classification:
        POTENTIAL_RISK
        CONFIRMED_RISK

    Evidence

    Possible Impact

Use conditional language for hypothetical impacts.

---

## Design Consequences

List important consequences that are not necessarily failures.

Examples:

    run_next selection changed from O(1) to O(n).

    default priority is the highest representable priority under the selected
    ordering semantics.

---

## Plan Deviations

For each deviation include:

    Original plan
    Reason
    Affected requirement/design
    Revised decision
    Evidence

---

## Evidence Audit

Include the final:

    Claim
    Evidence
    Assessment

table.

---

# Mandatory Stop Conditions

Stop and ask for human clarification when any of the following occurs.

## STOP-1: Specification Conflict

The specification conflicts with established existing behavior and intended
behavior is unclear.

Report:

    conflicting evidence
    affected requirement
    materially different interpretations

Do not choose silently.

---

## STOP-2: Requirement Ambiguity

A requirement has multiple materially different semantic interpretations.

Examples:

    "higher priority" without numeric direction

    "minimal compatibility changes" without defining required behavior

Report the alternatives neutrally.

---

## STOP-3: Unsupported Semantic Assumption

Implementation requires behavior not directly defined by:

- SPEC
- USER
- EXISTING_CONTRACT
- HUMAN_DECISION

Related evidence is insufficient.

If a proposed behavior requires combining partial evidence with unstated model
reasoning:

    STOP.

---

## STOP-4: Major Plan Defect

Implementation reveals that a core design decision is incorrect and the
correction materially changes:

- behavior
- interface
- architecture
- requirements
- compatibility

Stop and report the defect.

Small mechanical corrections may be recorded and reviewed without requiring a
human decision when semantics remain unchanged.

---

## STOP-5: Confirmed Compatibility Risk

Evidence confirms a significant:

- API
- ABI
- serialization
- persistent-data
- shared-memory
- wire-format
- externally consumed layout

compatibility impact that was not explicitly authorized.

The model must not accept the risk on behalf of the human.

---

## STOP-6: Design Decision Requires Missing Semantics

A HOW decision cannot be completed without inventing a WHAT decision.

Example:

    Design:
        add priority field with a default value

but:

    Requirement:
        does not define what missing priority means.

Separate the decisions.

The representational HOW may proceed only after the semantic WHAT is resolved.

---

# Stop Report Format

When a STOP condition is triggered, report:

## STOP

**Type**

STOP-N

**Affected Requirements**

R...

**Affected Design Decisions**

D...

**Problem**

What cannot safely be determined.

**Evidence**

What current sources establish.

**Missing Decision**

What remains undefined.

**Options**

For each option:

    Behavior
    Impact
    Trade-offs

Do not mark any option as recommended unless the user explicitly asks for a
recommendation.

**Required Human Decision**

Ask the exact question needed to continue.

Do not continue past the affected semantic decision until it is resolved.

---

# Final Self-Review

Before completing the task, perform this checklist.

## Source / Fact

- Did I distinguish direct facts from inference?
- Did I identify the source of important facts?

## Requirements

- Does every requirement have a direct semantic source?
- Did I accidentally expand a broad request into extra requirements?

## Design

- Did I separate WHAT from HOW?
- Does every design decision map to a requirement?
- Did any design decision silently create new semantics?
- Did I use an existing pattern only where it is actually applicable?

## Assumptions

- Are unresolved semantic assumptions gone?
- Did human decisions get recorded as HUMAN_DECISION?

## Compatibility

- Did I distinguish potential from confirmed risk?
- Did I avoid accepting risk on behalf of the human?
- Did I avoid claiming external consumers exist without evidence?

## Consequences

- Did I report important complexity, layout, ordering, or default-behavior
  consequences?
- Did I distinguish consequence from risk?

## Tests

- Do tests verify requirements rather than manufacture them?
- Are discriminating values used?
- Are relevant regression tests present?

## Evidence

- Does each important claim have evidence?
- Is the claim scoped to what the evidence actually proves?

## STOP Behavior

- Did I stop where a material semantic decision required human input?
- Were STOP options neutral?
- Did I avoid "Recommended", "Preferred", or preselected choices unless the
  user explicitly asked for advice?

---

# Core Principles

1. Evidence before assumption.

2. Understand before modifying.

3. Facts, requirements, design decisions, implementation patterns,
   assumptions, risks, and consequences are different categories.

4. Requirements define WHAT.

5. Design decisions define HOW.

6. Existing implementation patterns primarily guide HOW.
   They do not automatically define WHAT.

7. A specification fact must not silently become an implementation
   representation without an explicit design decision.

8. A HOW decision must not silently introduce new WHAT semantics.

9. Related evidence is not direct evidence.

10. Pattern similarity alone is not sufficient evidence that a pattern is
    applicable.

11. Every requirement should map to design.

12. Every design decision should map back to a requirement or necessary
    preserved contract.

13. Every important design decision should map to implementation and
    verification.

14. Tests verify approved behavior.
    Tests must not define unresolved behavior.

15. Passing tests are evidence, not proof of everything.

16. Verification claims must not exceed their evidence.

17. Risk claims must not exceed their evidence.

18. Hypothetical compatibility consumers must remain hypothetical unless
    evidence confirms them.

19. Important design consequences should be exposed even when they are not
    bugs.

20. Preserve existing behavior unless change is required.

21. Prefer minimal changes over speculative future-proofing.

22. The model may identify compatibility risk.
    It may not accept significant compatibility risk on behalf of the human.

23. STOP options must be neutral unless the user explicitly requests a
    recommendation.

24. When semantics are materially ambiguous, stop instead of guessing.

25. Correctly stopping is a successful outcome when evidence is insufficient.

26. A successful build proves compilation in that tested environment.

27. Passing tests prove only the behavior exercised by those tests.

28. The final report must distinguish:
    what was required,
    what was designed,
    what was implemented,
    what was tested,
    what was verified,
    what remains uncertain,
    what consequences were introduced,
    and what is out of scope.