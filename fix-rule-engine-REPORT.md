# Fix Rule Engine — REPORT

Worktree: `fix/rule-engine`. Archivo tocado: **`scripts/rule_engine.py`** (unico dentro de `touch_only` que requirio cambios; `scripts/validate_rules.py` no necesito cambios). `tests/test_rule_engine.py` y `knowledge/contracts/validate-rules.md` NO fueron tocados (sello `tests_sha256` intacto, verificado mas abajo).

## Objetivos

- (a) Eliminar la duplicacion de las familias v1 (`required`/`type`/`bounds`/`enums`/`matches`) entre `evaluate_v1_subset()` y el cuerpo de `evaluate()`.
- (b) Hacer `keyed_bounds` y `keyed_enums` robustos ante refs malformadas (no `TypeError`).

---

## (a) Duplicacion eliminada

**Antes**: la logica de cada familia v1 existia DOS veces — una vez dentro del cuerpo de `evaluate()` (sobre `record`) y otra dentro de la nested `evaluate_v1_subset()` (sobre cada elemento de `each`). Un fix a una familia habia que aplicarlo en los dos sitios (drift).

**Despues**: se extrajeron helpers de modulo, una unica implementacion por familia, y un unico agregador `_eval_v1` usado tanto por `evaluate()` (record top-level) como por el bloque `each` (cada elemento). La nested `evaluate_v1_subset` se elimino.

Snippet real del archivo resultante:

```python
def _check_required(rules, record):
    out = []
    for rule in rules:
        field = rule["field"]
        if _is_empty(_get_value(record, field)):
            out.append(_format_violation(field, "required"))
    return out

# ... _check_type, _check_bounds, _check_enums, _check_matches (una cada familia) ...

def _eval_v1(ruleset_v1, record):
    """Evalua las familias v1 (required/type/bounds/enums/matches) sobre `record`.
    Implementacion unica compartida por evaluate() (record top-level) y por el
    bloque `each` (cada elemento de la coleccion)."""
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
```

Y en `evaluate()`, las cinco familias v1 se redujeron a una sola linea que reutiliza lo de arriba:

```python
    # Familias v1 (implementacion unica en _eval_v1).
    violations += _eval_v1(ruleset, record)
```

Y el bloque `each` ahora llama al mismo agregador sobre cada elemento (antes llamaba a la nested `evaluate_v1_subset`):

```python
                # Evaluar el subset v1 de reglas sobre este elemento (misma
                # implementacion unica que el record top-level).
                elem_violations = _eval_v1(rules, item)
```

Verificacion de que la duplicacion desaparecio: `grep` de los cuerpos de familia fuera de los helpers:

```
$ grep -n "value <= rule\|value < rule\|value > rule\|re.search(pattern" scripts/rule_engine.py
scripts/rule_engine.py:119:        if "gt" in rule and value <= rule["gt"]:
scripts/rule_engine.py:125:        elif "max" in rule and value > rule["max"]:
scripts/rule_engine.py:135:        if not re.search(pattern, value):
```

Antes esos patrones aparecian DOS veces (en `evaluate_v1_subset` y en `evaluate`); ahora aparecen UNA sola vez, dentro del helper correspondiente. `evaluate()` ya no contiene logica de familia v1 duplicada.

---

## (b) Robustez keyed_bounds / keyed_enums ante refs malformadas

**Antes (bugs reproducidos)**:

- `keyed_bounds`: si `max_path` resolvia a un `str`, `value > max_limit` lanzaba `TypeError`.
- `keyed_enums`: si `values_path` resolvia a un `str`, `value not in allowed_values` hacia membership de SUBSTRING (falso negativo silencioso); si resolvia a un `int`, lanzaba `TypeError`.

**Despues**: si el valor resuelto por `max_path`/`values_path` no es del tipo esperado, se reporta una violacion de regla clara (no crash, no silencio). Snippet real:

```python
            # Robustez ante refs malformadas: el tope debe ser numerico. Si max_path
            # resuelve a un str/dict/bool/etc. (ref malformada), NO lanza TypeError:
            # se reporta como violacion clara del campo.
            if isinstance(max_limit, bool) or not isinstance(max_limit, (int, float)):
                violations.append(_format_violation(field, "keyed bounds limit is not a number"))
                continue
```

```python
            # Robustez ante refs malformadas: el conjunto debe ser una coleccion de
            # opciones. Un str haria membership de SUBSTRING (falso negativo silencioso)
            # y un escalar lanza TypeError; ambos son refs malformadas -> violacion.
            if isinstance(allowed_values, (str, bytes)) or not isinstance(
                    allowed_values, (list, tuple, set, frozenset)):
                violations.append(_format_violation(field, "keyed enum values are not a collection"))
                continue
```

Evidencia: por que estos casos no pueden ocurrir en los goldens reales (pero el motor es agnostico y no debe estallar ante un rule-set mal formado):

```
$ grep -n "max_amount\|max_stay_days\|max_execution_timeout\|allowed_currencies\|allowed_docs\|allowed\"" examples/rules/*golden.json
examples/rules/border-golden.json:5:      "AR": { "allowed_docs": ["passport", "id_card"], "max_stay_days": 90 },
examples/rules/border-golden.json:6:      "BR": { "allowed_docs": ["passport"], "max_stay_days": 60 },
examples/rules/border-golden.json:7:      "US": { "allowed_docs": ["passport", "visa"], "max_stay_days": 180 }
examples/rules/payment-golden.json:5:      "AR": { "max_amount": 500000, "allowed_currencies": ["USD", "ARS"] },
examples/rules/payment-golden.json:6:      "BR": { "max_amount": 300000, "allowed_currencies": ["USD", "BRL"] },
examples/rules/payment-golden.json:7:      "US": { "max_amount": 1000000, "allowed_currencies": ["USD"] }
```

Todos los `max_*` son numericos y todos los `allowed_*` son listas. Las nuevas guardas no disparan en oro valido; solo atrapan rule-sets mal formados.

### Ejemplo ejecutado a mano (refs malformadas ya NO lanzan TypeError)

```
$ python -c "
import sys; sys.path.insert(0,'scripts')
import rule_engine

# keyed_bounds: max_path resuelve a un str (ref malformada) -> NO TypeError, violacion clara
rs={'keyed_bounds':[{'field':'amount','key':'country','table':'limits','max_path':'max_amount'}]}
refs={'limits':{'AR':{'max_amount':'FIVE_HUNDRED_THOUSAND'}}}
rec={'country':'AR','amount':1000}
print('keyed_bounds(str limit):', rule_engine.evaluate(rs,rec,refs))

# keyed_bounds: max_path resuelve a un dict
refs2={'limits':{'AR':{'max_amount':{'a':1}}}}
print('keyed_bounds(dict limit):', rule_engine.evaluate(rs,rec,refs2))

# keyed_enums: values_path resuelve a un str -> NO silencio (antes devolvia []), violacion clara
rs2={'keyed_enums':[{'field':'currency','key':'country','table':'limits','values_path':'allowed_currencies'}]}
refs3={'limits':{'AR':{'allowed_currencies':'USD'}}}
rec3={'country':'AR','currency':'USD'}
print('keyed_enums(str values):', rule_engine.evaluate(rs2,rec3,refs3))

# keyed_enums: values_path resuelve a un int -> NO TypeError, violacion clara
refs4={'limits':{'AR':{'allowed_currencies':3}}}
print('keyed_enums(int values):', rule_engine.evaluate(rs2,rec3,refs4))

# sanity: refs bien formadas se comportan igual que antes
good={'limits':{'AR':{'max_amount':500000,'allowed_currencies':['USD','ARS']}}}
rsboth={'keyed_bounds':[{'field':'amount','key':'country','table':'limits','max_path':'max_amount'}],
        'keyed_enums':[{'field':'currency','key':'country','table':'limits','values_path':'allowed_currencies'}]}
print('good 500000+USD:', rule_engine.evaluate(rsboth,{'country':'AR','amount':500000,'currency':'USD'},good))
print('good 500001+EUR:', rule_engine.evaluate(rsboth,{'country':'AR','amount':500001,'currency':'EUR'},good))
"
keyed_bounds(str limit): ['amount: keyed bounds limit is not a number']
keyed_bounds(dict limit): ['amount: keyed bounds limit is not a number']
keyed_enums(str values): ['currency: keyed enum values are not a collection']
keyed_enums(int values): ['currency: keyed enum values are not a collection']
good 500000+USD: []
good 500001+EUR: ['amount: keyed bounds violated', 'currency: keyed enum not allowed']
```

Antes del fix, las dos primeras (`keyed_bounds` str) y la cuarta (`keyed_enums` int) lanzaban `TypeError`; la tercera (`keyed_enums` str) devolvia `[]` en silencio (falso negativo). Ahora todas reportan violacion clara y las refs bien formadas siguen igual.

---

## Definicion de Hecho — verificacion real

### 1. `python -m unittest tests/test_rule_engine.py -v` (sin modificar ese archivo)

```
$ python -m unittest tests.test_rule_engine -v 2>&1 | tail -8
test_number_excluye_bool (tests.test_rule_engine.TestType.test_number_excluye_bool) ... ok
test_number_rechaza_string (tests.test_rule_engine.TestType.test_number_rechaza_string) ... ok
test_string_y_dict (tests.test_rule_engine.TestType.test_string_y_dict) ... ok

----------------------------------------------------------------------
Ran 32 tests in 0.001s

OK
```

Sello `tests_sha256` del contrato intacto (el archivo de tests no se toco):

```
$ python scripts/validate_contracts.py --hash tests/test_rule_engine.py
154fb9f6e2645161930fb03728dedc5dde422d6aa3e55ac7a39a889cccc1c319
```

Coincide con `tests_sha256` declarado en `knowledge/contracts/validate-rules.md`.

### 2. `python -m unittest tests/test_validate_rules.py -v` sigue en verde

```
$ python -m unittest tests.test_validate_rules -v 2>&1 | tail -8
test_code_only_miss_no_cuenta_como_divergencia (tests.test_validate_rules.TestReproduccion.test_code_only_miss_no_cuenta_como_divergencia) ... ok
test_divergencia_motor_golden (tests.test_validate_rules.TestRepro... test_divergencia_motor_golden) ... ok
test_par_valido_sin_findings (tests.test_validate_rules.TestValido.test_par_valido_sin_findings) ... ok

----------------------------------------------------------------------
Ran 19 tests in 0.324s

OK
```

### 3. `python scripts/preflight.py` en el mismo resultado que al arrancar (19/19 PASS)

Antes y despues: `Summary: 19/19`.

```
$ python scripts/preflight.py 2>&1 | tail -5
validate_test_coverage_findings: PASS
validate_test_commands: PASS
scan_secrets: PASS
validate_attestation: PASS
Summary: 19/19
```

### 4. Evidencia concreta (snippet + ejemplo ejecutado)

Incluida arriba: snippet real de `_eval_v1` + helpers (dedup) y `grep` que muestra que la logica de familia v1 ahora aparece una sola vez; ejemplo `python -c "..."` donde refs malformadas en `keyed_bounds`/`keyed_enums` ya NO lanzan `TypeError` (sino violacion clara), con sanity check de refs bien formadas.

---

## Scope del cambio

```
$ git status --short
 M scripts/rule_engine.py
```

Un solo archivo modificado, dentro de `touch_only`. `validate_rules.py` no requirio cambios. `tests/test_rule_engine.py` y el contrato `.md` no fueron tocados (sha verificado). El contrato sigue valido:

```
$ python scripts/validate_contracts.py knowledge/contracts 2>&1 | tail -3
OK: todos los contratos son validos

Resumen: 0 error(es), 0 warning(s) en 33 archivo(s)
```