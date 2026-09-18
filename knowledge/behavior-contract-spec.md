---
type: 'Concept'
title: 'Behavior contracts v1'
description: 'Optional, versioned behavior specifications and their evidence boundary.'
tags: ['behavior', 'verification', 'contracts']
---

# Behavior contracts v1

`behavior/v1` is an optional KDD layer for checking a declarative property against
one or more adapters. It complements task contracts and frozen tests. It does not
turn a green result into a universal proof.

A contract is a `*.behavior.json` document with exactly these keys:

```json
{
  "schema": "kdd-behavior/v1",
  "domain": {"type": "integer", "min": 0, "max": 100},
  "cases": {"mode": "exhaustive", "batch_size": 1000},
  "property": {"op": "eq", "args": [
    {"var": "result"},
    {"op": "mul", "args": [{"var": "input"}, {"const": 2}]}
  ]}
}
```

The allowed expression nodes are `eq`, `add`, `mul`, `input`, `result`, and safe
integer constants. Validation is deterministic and does not execute candidate code:

```text
python scripts/validate_behavior.py behavior
```

An execution adapter is trusted configuration maintained outside the candidate's
editable perimeter. It must state its command, source path, runtime version and
whether it builds an artifact. Evidence must report `PASS`, `FAIL`, `ERROR`, or
`UNSUPPORTED`; domain coverage, counterexamples, source/tool hashes and explicit
assumptions. Exhaustive execution proves only the observed bounded domain. A formal
backend such as Bend must report its own theorem, trusted computing base and the
link, if any, to the implementation being evaluated.

`run_behavior.py` is the opt-in reference runner. It receives explicit candidate,
contract, adapter-registry and evidence paths:

```text
python scripts/run_behavior.py --root examples/behavior --contract examples/behavior/double.behavior.json --adapters examples/behavior/adapters.json --adapters-sha256 <reviewed-sha256> --evidence reports/behavior.json
```

The example adapter is intentionally small. Production registries belong in a
protected CI/configuration repository, not in an agent-editable candidate tree.
The runner rejects a registry whose supplied reviewed hash does not match.
The included example registry covers Python and JavaScript; an unavailable runtime
is reported as `UNSUPPORTED`, never as a passing verification.
