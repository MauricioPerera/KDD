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
editable perimeter. The reference registry declares name, tool, source and command.
Evidence records adapter status (`PASS`, `FAIL`, `ERROR`, or `UNSUPPORTED`), domain
coverage, counterexamples and source/contract/registry hashes. Runtime versions,
tool hashes and build provenance are not implemented by the reference runner.
Exhaustive execution establishes only the observed bounded domain. A formal
backend such as Bend must report its own theorem, trusted computing base and the
link, if any, to the implementation being evaluated.

`run_behavior.py` is the opt-in reference runner. It receives explicit candidate,
contract, adapter-registry and evidence paths:

```text
python scripts/run_behavior.py --root examples/behavior --contract examples/behavior/double.behavior.json --contract-sha256 <reviewed-contract-sha256> --adapters examples/behavior/adapters.json --adapters-sha256 <reviewed-adapters-sha256> --evidence reports/behavior.json
```

The example adapter is intentionally small. Production registries belong in a
protected CI/configuration repository, not in an agent-editable candidate tree.
Both CLI and Python API require independently approved hashes for the contract and
registry. A missing or mismatching hash fails before candidate execution. Computing
fresh hashes from candidate-controlled files at verification time is not approval.
The runner checks contract, registry and source integrity around each batch; this
is boundary detection, not a sandbox or protection from transient edits restored
between checks. Run untrusted candidates in an external isolated environment with
a trusted executor, approved configuration and resource limits. See
[quality approval](quality-approval.md) for the independent-reference boundary.
The included example registry covers Python and JavaScript; an unavailable runtime
is reported as `UNSUPPORTED`, never as a passing verification.
