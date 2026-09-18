"""Shared validation for optional KDD behavior contracts (schema behavior/v1)."""
import hashlib
import json
from pathlib import Path


SCHEMA = "kdd-behavior/v1"
SAFE_INTEGER = 2 ** 53 - 1


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8")), None
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, str(exc)


def _integer(value):
    return type(value) is int and abs(value) <= SAFE_INTEGER


def validate(document):
    """Return stable rule ids. This validates a declarative contract, never runs it."""
    findings = []
    if not isinstance(document, dict):
        return [("BHV_DOCUMENT", "top-level JSON value must be an object")]
    if document.get("schema") != SCHEMA:
        findings.append(("BHV_SCHEMA", "schema must be kdd-behavior/v1"))
    if set(document) != {"schema", "domain", "cases", "property"}:
        findings.append(("BHV_KEYS", "allowed keys are schema, domain, cases, property"))
    domain = document.get("domain")
    if not isinstance(domain, dict) or set(domain) != {"type", "min", "max"} or domain.get("type") != "integer":
        findings.append(("BHV_DOMAIN", "domain must be integer with min and max"))
    elif not (_integer(domain["min"]) and _integer(domain["max"]) and domain["min"] <= domain["max"]):
        findings.append(("BHV_DOMAIN_RANGE", "domain bounds must be ordered safe integers"))
    cases = document.get("cases")
    if not isinstance(cases, dict) or set(cases) != {"mode", "batch_size"} or cases.get("mode") != "exhaustive":
        findings.append(("BHV_CASES", "cases must select exhaustive mode and a batch_size"))
    elif not _integer(cases["batch_size"]) or not 1 <= cases["batch_size"] <= 10000:
        findings.append(("BHV_BATCH", "batch_size must be an integer from 1 to 10000"))
    if not _expression(document.get("property")):
        findings.append(("BHV_PROPERTY", "property must be an eq/add/mul expression over input/result/constants"))
    return findings


def _expression(node, depth=0):
    if depth > 16 or not isinstance(node, dict):
        return False
    if set(node) == {"var"}:
        return isinstance(node["var"], str) and node["var"] in {"input", "result"}
    if set(node) == {"const"}:
        return _integer(node["const"])
    if set(node) != {"op", "args"} or not isinstance(node["op"], str) or node["op"] not in {"eq", "add", "mul"}:
        return False
    return isinstance(node["args"], list) and len(node["args"]) == 2 and all(_expression(x, depth + 1) for x in node["args"])


def evaluate(node, input_value, result_value):
    if "var" in node:
        return input_value if node["var"] == "input" else result_value
    if "const" in node:
        return node["const"]
    a, b = (evaluate(x, input_value, result_value) for x in node["args"])
    if node["op"] == "eq":
        return a == b
    return a + b if node["op"] == "add" else a * b
