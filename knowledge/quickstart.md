---
type: 'Concept'
title: 'Quickstart: de clonar la plantilla a tu primer contrato en verde'
description: 'Tutorial paso a paso, ejecutable, desde clonar KDD hasta tener un task contract propio pasando los gates de Nivel 1. Complementa (no reemplaza) knowledge/validacion.md, que es la referencia normativa.'
tags: ['ccdd', 'okf', 'onboarding', 'reference']
---

# Quickstart

Tutorial ejecutable. Cada paso tiene un comando y el resultado esperado.
Para la referencia normativa completa (niveles de gate, budget, ciclo de
vida) ver [validacion.md](./validacion.md); esto es el camino corto para
llegar a tu primer contrato en verde.

## 0. Prerrequisitos

- Python 3.9+ en PATH (`python --version`).
- Git.
- Vocabulario minimo (definiciones completas en
  [OKF-SPEC](./OKF-SPEC.md) y [validacion.md](./validacion.md)):
  - **Task contract**: un `.md` en `knowledge/contracts/` que define UNA
    funcion a implementar — intent, firma, tests, restricciones.
  - **Oraculo congelado**: el archivo de tests de un contrato, escrito
    ANTES de implementar y sellado por hash (`tests_sha256`) para que no
    se pueda reescribir para hacer pasar una implementacion incorrecta.
  - **Gate**: un script determinista (`scripts/validate_*.py`) que
    verifica una propiedad mecanica (forma del contrato, tests en verde,
    complejidad bajo presupuesto). Nivel 1 = obligatorio en CI.

## 1. Clonar e instalar

```
git clone <tu-fork-o-el-template> mi-proyecto
cd mi-proyecto
python -m unittest discover -s tests -p "test_*.py"
```

Esperado: la suite completa termina en `OK` (el template trae ejemplos
funcionando). Si falla aca, es un problema de entorno (version de Python),
no de KDD — resolvelo antes de seguir.

## 2. Correr los gates de Nivel 1 tal cual vienen

```
python scripts/validate_contracts.py knowledge/contracts
python scripts/validate_test_commands.py knowledge/contracts .
```

Esperado: ambos en verde (`OK: todos los contratos son validos` /
`PASS` en cada linea, exit 0). Este es el estado de referencia: la
plantilla nace verde. La lista completa de gates de Nivel 1 esta en
[validacion.md](./validacion.md#nivel-1--incluido-y-obligatorio-local--ci).

## 3. Limpiar los ejemplos de la plantilla

```
python scripts/init_project.py --name "Mi Proyecto"
```

(dry-run: solo imprime el plan). Cuando estes conforme:

```
python scripts/init_project.py --apply --name "Mi Proyecto"
```

Esperado: borra `src/hello.py`, `src/users.py` y el resto de los
artefactos de EJEMPLO listados en el `MANIFEST` de
`scripts/init_project.py`, reescribe `knowledge/index.md` sin los enlaces
muertos, y cambia el H1 del README. `knowledge/contracts/TEMPLATE-task-contract.md`
NO se borra (no esta en el `MANIFEST`) — es tu punto de partida para el
paso siguiente.

Verificar que el repo sigue verde despues de limpiar:

```
python scripts/validate_contracts.py knowledge/contracts
python -m unittest discover -s tests -p "test_*.py"
```

## 4. Tu primer contrato propio

Toma la plantilla que sobrevivio al paso 3:

```
cp knowledge/contracts/TEMPLATE-task-contract.md knowledge/contracts/saludar.md
```

Ejemplo concreto — vamos a implementar `def saludar(nombre: str) -> str`
que devuelve `"Hola, <nombre>!"`.

**4.1 — Escribi el oraculo PRIMERO** (`tests/test_saludar.py`):

```python
import unittest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from saludar import saludar

class TestSaludar(unittest.TestCase):
    def test_nombre_simple(self):
        self.assertEqual(saludar("Ana"), "Hola, Ana!")

    def test_nombre_vacio(self):
        self.assertEqual(saludar(""), "Hola, !")

if __name__ == '__main__':
    unittest.main()
```

**4.2 — Sella el hash del oraculo:**

```
python scripts/validate_contracts.py --hash tests/test_saludar.py
```

Esperado: imprime 64 caracteres hex. Copialo.

**4.3 — Crea el stub del target** (`src/saludar.py`):

```python
def saludar(nombre: str) -> str:
    raise NotImplementedError
```

**4.4 — Completa `knowledge/contracts/saludar.md`** reemplazando cada
placeholder `<...>` (ver el bloque de instrucciones al final del archivo
copiado). Campos minimos para este ejemplo:

```yaml
task: saludar
intent: "Devolver un saludo con el nombre dado."
target: src/saludar.py
signature: "def saludar(nombre: str) -> str:"
test_command: "python -m unittest tests/test_saludar.py"
budget:
  max_cyclomatic_complexity: 2
  max_nesting_depth: 1
tests: "tests/test_saludar.py"
tests_sha256: "<el hash del paso 4.2>"
touch_only: ['src/saludar.py']
deps_allowed: []
forbids: ['network', 'subprocess', 'llm']
```

**4.5 — Valida el contrato (antes de implementar nada):**

```
python scripts/validate_contracts.py knowledge/contracts
```

Esperado: `OK: todos los contratos son validos`. Si da ERROR, el mensaje
nombra la seccion o clave faltante — corregi y repeti. Este paso es a
proposito ANTES de escribir la implementacion real: el contrato tiene que
estar bien formado antes de delegarlo (a un agente, a otra persona, o a
vos mismo).

**4.6 — Implementa** `src/saludar.py`:

```python
def saludar(nombre: str) -> str:
    return f"Hola, {nombre}!"
```

**4.7 — Verifica en verde:**

```
python -m unittest tests/test_saludar.py
python scripts/validate_test_commands.py knowledge/contracts .
```

Esperado: ambos exit 0, `saludar.md` aparece como `PASS` en la segunda
corrida. Ya tenes un contrato completo, verificado de punta a punta.

## 5. Siguiente paso

Antes de delegar trabajo a un agente, corre el preflight y mira que gates
fallarian sobre el repo actual, en una sola pasada local y sin instalar
nada (cero dependencias, no es un gate de CI):

```
python scripts/preflight.py
```

Esperado: una linea por gate con su estado `PASS`/`FAIL`/`TIMEOUT` y un
resumen `N/12`. Si algo falla, arreglalo antes de delegar — no tiene
sentido mandarle a un agente un repo que ya rompe un gate. Diagnostico
opt-in, mismo estatus que `benchmark_gates.py` (Nivel 1 sigue siendo 11
gates; el preflight suma `validate_attestation`, el local-only).

- Referencia normativa completa (niveles de gate, budget, perimetro,
  ciclo de vida draft->verified): [validacion.md](./validacion.md).
- Como delegar esta tarea a un agente en vez de implementarla vos mismo:
  [metodologia-ejecucion.md](./metodologia-ejecucion.md).
- Glosario completo de terminos CCDD/OKF: [OKF-SPEC.md](./OKF-SPEC.md).
