"""Motor de reglas declarativo (Contrato 17).

Evalua un record contra un rule-set declarativo (required/type/enums/bounds/refs/keyed)
y devuelve las violaciones, sin LLM ni red. Puro, determinista, stdlib.

Las familias v1 (required/type/bounds/enums/matches) tienen una UNICA implementacion
compartida por evaluate() y por el bloque `each` (ver _eval_v1): un fix a una familia
se aplica en un solo sitio, sin drift.
"""

import re


# --- Helpers internos compartidos (modulo-level, puros, sin estado) -------------

def _get_value(obj, field_path):
    """Navega un campo punteado en un dict anidado. Retorna None si ausente."""
    parts = field_path.split('.')
    current = obj
    for part in parts:
        if not isinstance(current, dict):
            return None  # Intermedio no-dict -> ausente
        current = current.get(part)
    return current


def _is_empty(value):
    """Verifica si un valor se considera vacío (None o string vacío)."""
    return value is None or value == ""


def _format_violation(field, msg):
    """Formatea un mensaje de violación."""
    return "{}: {}".format(field, msg)


# --- Familias v1: una implementacion por familia, reutilizada ------------------
# Cada helper recibe la lista de reglas de UNA familia y el record (o elemento)
# y devuelve la lista de violaciones de esa familia, en el mismo orden y con la
# misma semantica que tenia antes. Tanto evaluate() (sobre record) como el bloque
# `each` (sobre cada elemento) las invocan via _eval_v1, asi que un cambio de
# semantica en una familia se hace en un solo sitio.

def _check_required(rules, record):
    out = []
    for rule in rules:
        field = rule["field"]
        if _is_empty(_get_value(record, field)):
            out.append(_format_violation(field, "required"))
    return out


def _check_type(rules, record):
    out = []
    for rule in rules:
        field = rule["field"]
        kind = rule["kind"]
        value = _get_value(record, field)

        # type no se evalua si ausente (eso es required)
        if value is None:
            continue

        if kind == "number":
            # number excluye bool
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                out.append(_format_violation(field, "type must be number"))
        elif kind == "string":
            if not isinstance(value, str):
                out.append(_format_violation(field, "type must be string"))
        elif kind == "dict":
            if not isinstance(value, dict):
                out.append(_format_violation(field, "type must be dict"))
    return out


def _check_bounds(rules, record):
    out = []
    for rule in rules:
        field = rule["field"]
        value = _get_value(record, field)

        # bounds solo aplica a numbers
        if value is None or not isinstance(value, (int, float)) or isinstance(value, bool):
            continue

        if "gt" in rule and value <= rule["gt"]:
            out.append(_format_violation(field, "bounds violated"))
        elif "min" in rule and value < rule["min"]:
            out.append(_format_violation(field, "bounds violated"))
        elif "max" in rule and value > rule["max"]:
            out.append(_format_violation(field, "bounds violated"))
        elif rule.get("integer", False) and value != int(value):
            out.append(_format_violation(field, "bounds violated"))
    return out


def _check_enums(rules, record):
    out = []
    for rule in rules:
        field = rule["field"]
        value = _get_value(record, field)
        values = rule["values"]

        # Igualdad de valor (in)
        if value not in values:
            out.append(_format_violation(field, "not in enum"))
    return out


def _check_matches(rules, record):
    out = []
    for rule in rules:
        field = rule["field"]
        pattern = rule["pattern"]
        value = _get_value(record, field)

        # matches solo aplica si el valor es string (ausente/None se salta)
        if value is None or not isinstance(value, str):
            continue

        if not re.search(pattern, value):
            out.append(_format_violation(field, "pattern mismatch"))
    return out


def _eval_v1(ruleset_v1, record):
    """Evalua las familias v1 (required/type/bounds/enums/matches) sobre `record`.

    Implementacion unica compartida por evaluate() (sobre el record top-level) y por
    el bloque `each` (sobre cada elemento de la coleccion). Mantiene el orden y la
    semantica previos: required, type, bounds, enums, matches.
    """
    out = []
    if "required" in ruleset_v1:
        out += _check_required(ruleset_v1["required"], record)
    if "type" in ruleset_v1:
        out += _check_type(ruleset_v1["type"], record)
    if "bounds" in ruleset_v1:
        out += _check_bounds(ruleset_v1["bounds"], record)
    if "enums" in ruleset_v1:
        out += _check_enums(ruleset_v1["enums"], record)
    if "matches" in ruleset_v1:
        out += _check_matches(ruleset_v1["matches"], record)
    return out


def evaluate(ruleset: dict, record: dict, refs: dict) -> list:
    """Evalua `record` contra `ruleset` (familias declarativas), resolviendo las
    familias keyed contra `refs`. Devuelve una lista de violaciones legibles (vacia =
    valido), ordenada deterministamente; cada violacion empieza con '<field>: ...'
    (field puede ser punteado/anidado). Funcion pura: sin IO, sin red, determinista."""

    violations = []

    # Familias v1 (implementacion unica en _eval_v1).
    violations += _eval_v1(ruleset, record)

    # Procesar familia 'refs'
    if "refs" in ruleset:
        for rule in ruleset["refs"]:
            field = rule["field"]
            collection = rule["collection"]
            value = _get_value(record, field)

            # refs se evalua solo si presente
            if value is None:
                continue

            if collection not in refs or value not in refs[collection]:
                violations.append(_format_violation(field, "ref not found"))

    # Procesar familia 'keyed_bounds'
    if "keyed_bounds" in ruleset:
        for rule in ruleset["keyed_bounds"]:
            field = rule["field"]
            key = rule["key"]
            table = rule["table"]
            max_path = rule["max_path"]

            value = _get_value(record, field)

            # keyed_bounds solo aplica a numbers
            if value is None or not isinstance(value, (int, float)) or isinstance(value, bool):
                continue

            # Resolver la clave
            key_value = _get_value(record, key)

            # Si la clave no resuelve en la tabla, saltamos (sin violacion)
            if table not in refs or key_value not in refs[table]:
                continue

            # Resolver el tope desde refs[table][key_value][max_path]
            max_limit = _get_value(refs[table][key_value], max_path)

            # Si el tope no existe, saltamos
            if max_limit is None:
                continue

            # Robustez ante refs malformadas: el tope debe ser numerico. Si max_path
            # resuelve a un str/dict/bool/etc. (ref malformada), NO lanza TypeError:
            # se reporta como violacion clara del campo. No puede ocurrir en los
            # goldens reales (todos declaran max_* numerico), pero el motor debe ser
            # agnostico y no estallar ante un rule-set mal formado.
            if isinstance(max_limit, bool) or not isinstance(max_limit, (int, float)):
                violations.append(_format_violation(field, "keyed bounds limit is not a number"))
                continue

            if value > max_limit:
                violations.append(_format_violation(field, "keyed bounds violated"))

    # Procesar familia 'keyed_enums'
    if "keyed_enums" in ruleset:
        for rule in ruleset["keyed_enums"]:
            field = rule["field"]
            key = rule["key"]
            table = rule["table"]
            values_path = rule["values_path"]

            value = _get_value(record, field)

            # keyed_enums se evalua si presente
            if value is None:
                continue

            # Resolver la clave
            key_value = _get_value(record, key)

            # Si la clave no resuelve en la tabla, saltamos (sin violacion)
            if table not in refs or key_value not in refs[table]:
                continue

            # Resolver el conjunto permitido desde refs[table][key_value][values_path]
            allowed_values = _get_value(refs[table][key_value], values_path)

            # Si el conjunto no existe, saltamos
            if allowed_values is None:
                continue

            # Robustez ante refs malformadas: el conjunto debe ser una coleccion de
            # opciones. Un str haria membership de SUBSTRING (falso negativo silencioso)
            # y un escalar lanza TypeError; ambos son refs malformadas -> violacion
            # clara, ni crash ni silencio. No puede ocurrir en los goldens reales
            # (todos declaran allowed_* como listas), pero el motor es agnostico.
            if isinstance(allowed_values, (str, bytes)) or not isinstance(
                    allowed_values, (list, tuple, set, frozenset)):
                violations.append(_format_violation(field, "keyed enum values are not a collection"))
                continue

            if value not in allowed_values:
                violations.append(_format_violation(field, "keyed enum not allowed"))

    # Procesar familia 'each'
    if "each" in ruleset:
        for each_rule in ruleset["each"]:
            collection = each_rule.get("collection")
            where = each_rule.get("where")
            rules = each_rule.get("rules", {})

            # Obtener la coleccion desde el record
            items = _get_value(record, collection)

            # Si no existe o no es lista, se salta
            if not isinstance(items, list):
                continue

            # Procesar cada elemento de la coleccion
            for idx, item in enumerate(items):
                # Si hay filtro where, verificar que el elemento lo cumpla
                # Si no cumple, esta rule no se aplica a este elemento
                if where:
                    where_field = where.get("field")
                    where_value = where.get("equals")
                    item_where_value = _get_value(item, where_field)
                    if item_where_value != where_value:
                        continue

                # La rule se aplica a este elemento. Si no es dict, es violacion
                if not isinstance(item, dict):
                    violations.append(_format_violation(
                        collection, "element at index {} is not a dict".format(idx)))
                    continue

                # Evaluar el subset v1 de reglas sobre este elemento (misma
                # implementacion unica que el record top-level).
                elem_violations = _eval_v1(rules, item)

                # Prefixar cada violacion con "collection: elemento <idx>."
                for elem_viol in elem_violations:
                    prefixed = "{}: elemento {}: {}".format(collection, idx, elem_viol)
                    violations.append(prefixed)

    # Ordenar deterministamente por campo (parte antes del ':')
    violations.sort(key=lambda v: v.split(":", 1)[0].strip())

    return violations