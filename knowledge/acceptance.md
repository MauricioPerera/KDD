---
type: 'Concept'
title: 'Aceptacion por obligacion verificable'
description: 'Politica aprobada, inventario de oraculos y matriz de evidencia bloqueante por contrato.'
tags: ['ccdd', 'quality', 'verification']
---

# Aceptacion por obligacion

Este es el punto de aceptacion para nuevas entregas. Complementa [validacion](validacion.md) y [quality-approval](quality-approval.md); no convierte el verde de la plantilla en una aprobacion del producto.

## Estados y requisitos

| Estado | Evidencia |
|---|---|
| `structure_valid` | Contratos validos y archivos aprobados intactos; aun no demuestra ejecucion satisfactoria. |
| `tests_approved` | Los oraculos principales de todos los contratos seleccionados ejecutaron casos reales en dos corridas; las obligaciones restantes pueden fallar. |
| `acceptance_approved` | Todas las obligaciones requeridas tienen evidencia ejecutada satisfactoria y el snapshot permanece intacto. |

Un error o estado intermedio produce exit 1. El reporte JSON contiene filas `PASS`, `FAIL` o `NOT_RUN`; ninguna fila ausente o inconclusa cuenta como PASS. No usa HEAD como aprobacion implicita. La referencia es un SHA completo aprobado externamente, aunque el programa no autentica a quien lo aprueba.

## Inventario y ejecucion

Cada contrato declara `oracle_files`, lista exacta que incluye `tests`, helpers de pruebas, fixtures relevantes y configuracion del runner. No incluye implementacion ni intersecta `touch_only`. La lista aprobada, no la del candidato, decide que proteger. El baseline local y el gate confiable del PR comparan todos esos archivos; el perfil de aceptacion comprueba tambien el index y el perimetro real.

El revisor inspecciona la completitud del inventario. No se descubren automaticamente cargas dinamicas, servicios o dependencias del sistema. Fijar las dependencias externas y revisar el entorno de ejecucion. No colocar helpers ejecutables fuera del inventario ni en archivos ignorados que las pruebas consuman.

Los fixtures binarios se comparan byte a byte: declararlos con `-text` en `.gitattributes` antes de aprobar. Los controles leen esa declaracion del SHA aprobado, nunca de atributos cambiados por el candidato; los archivos con bytes NUL tambien se comparan exactamente. El texto mantiene normalizacion CR/LF por compatibilidad con checkout Windows. El revisor debe clasificar correctamente fixtures consumidos como bytes, incluso si contienen solo ASCII. Requiere Git con `check-attr --source`; sin ese instrumento, bloquea. Para checkout uniforme del texto se recomienda `text eol=lf`.

`test_runner` admite:

- `python-unittest`: comando `python -m unittest tests/test_x.py` o modulos completos como `tests.test_x`. El runner usa el interprete actual con aislamiento de variables Python y un cache temporal, registra casos y su archivo. Rechaza selectors, discovery implicito, cero casos, skips y expected failures.
- `node-test`: comando `node --test tests/test_x.mjs` o `.js`/`.ts` compatible con el runtime. Un reporter confiable recoge las sumas por archivo de `node:test`; un archivo vacio o stdout TAP inventado no cuenta. Requiere Node.js 24. Rechaza skips/todos y archivos sin casos registrados.

Todos los archivos seleccionados deben estar inventariados y tener casos ejecutados. El timeout bloquea; `test_timeout` fija el plazo del oraculo principal (180s por defecto, maximo 3600s) y cada check declara su propio plazo; terminar con exit 0 sin evidencia tambien bloquea. Los comandos libres historicos conservan su comprobacion de exit code y no ofrecen aceptacion. Para otro framework se necesita un adapter revisado que identifique archivo y casos; no reemplazarlo por un comando libre para obtener verde.

Los alias Python que declaran version (por ejemplo `python3.14`) deben coincidir con el interprete actual. La evidencia registra el argv instrumentado y la version de Python, para distinguir el comando declarado de la invocacion que realmente corrio.

Los detalles del reporter estan definidos por la [documentacion oficial de node:test](https://nodejs.org/api/test.html#custom-reporters); su comportamiento se comprueba sobre el runtime Node 24. Los [contratos de ejecucion](contracts/oracle-execution.md) fijan los casos adversariales.

## Politica aprobada

Crear `acceptance.json` antes de implementar. Es JSON version 1, con claves exactas:

```json
{
  "schema_version": 1,
  "implementation": ["src/saludar.py"],
  "pm": [],
  "contracts": [{
    "path": "knowledge/contracts/saludar.md",
    "checks": [
      {"obligation": "signature", "tests": "tests/test_signature.py", "test_runner": "python-unittest", "test_command": "python -m unittest tests/test_signature.py", "timeout": 60},
      {"obligation": "dependencies", "tests": "tests/test_dependencies.py", "test_runner": "python-unittest", "test_command": "python -m unittest tests/test_dependencies.py", "timeout": 60},
      {"obligation": "budget", "tests": "tests/test_budget.py", "test_runner": "python-unittest", "test_command": "python -m unittest tests/test_budget.py", "timeout": 60},
      {"obligation": "forbids", "tests": "tests/test_forbids.py", "test_runner": "python-unittest", "test_command": "python -m unittest tests/test_forbids.py", "timeout": 60},
      {"obligation": "invariants", "tests": "tests/test_invariants.py", "test_runner": "python-unittest", "test_command": "python -m unittest tests/test_invariants.py", "timeout": 60}
    ]
  }]
}
```

Es una muestra de politica, no incluye esos archivos de pruebas: crearlos y agregarlos al `oracle_files` del contrato antes de aprobar. Para requisitos especificos, declarar ademas `acceptance_obligations: ['upgrade', 'ui', 'AC-1']` y un check por cada nombre. No se pueden sustituir las obligaciones internas de integridad, ejecucion y perimetro.

| Obligacion | Instrumento que el revisor debe exigir |
|---|---|
| Firma | Comprobar el punto publico, argumentos y tipo/contenedor de retorno exigidos; AST o adapter de lenguaje cuando corresponda. |
| Dependencias | Comprobar imports/manifiestos frente a `deps_allowed`, con alcance y resolucion explicitados. |
| Budget | Medir el target frente a cada tope declarado; puede usar `validate_budgets` para Python o un medidor de lenguaje apropiado. No aprobar un lenguaje omitido por el medidor. |
| Prohibiciones | Comprobar cada prohibicion con un instrumento que cubra su alcance; un diagnostico UNVERIFIED no basta. |
| Invariantes | Probar cada propiedad del cuerpo, ejemplos y casos adversariales. Usar IDs adicionales cuando se necesite trazabilidad individual. |

El ejecutor exige que esos checks existan, esten protegidos y ejecuten pruebas reales. **El nombre de un check y su cantidad de casos no prueban cobertura semantica.** Quien aprueba debe leer sus asserts, justificar el instrumento y demostrar que rechaza violaciones representativas de la obligacion. Una suite con `assert True` sigue siendo un mal oraculo, incluso si un runner mide correctamente su ejecucion. Este limite es inevitable sin una especificacion formal completa; no se presenta el resultado como prueba universal de correccion.

Las listas `implementation` y `pm` son rutas exactas aprobadas y disjuntas del inventario protegido. Cada ruta de implementacion debe estar cubierta por el `touch_only` de al menos un contrato seleccionado. Se inspeccionan commits, staged, unstaged y nuevos no ignorados. No incluir en `pm` archivos de implementacion para evitar sus restricciones. El PM aprueba artefactos documentales y el revisor comprueba esa clasificacion.

## Ejecucion y CI

```text
python scripts/verify_acceptance.py --policy acceptance.json --approved-ref SHA_APROBADO --json-output .agents/logs/acceptance.json
python scripts/run_profile.py --profile acceptance --acceptance-policy acceptance.json --approved-ref SHA_APROBADO
```

El reporte vincula referencia aprobada, hashes de politica/contrato/inventario/implementacion, comando, runner, cantidad de casos, salida real y hash de salida. Se comprueba integridad y snapshot antes y despues de cada corrida. Cualquier cambio durante verificacion bloquea. La evidencia local es reproducible, pero no una firma criptografica del productor.

En CI, una politica presente en el candidato **o en la referencia aprobada** activa este paso; borrarla no lo degrada a SKIP. El workflow reutilizable admite `acceptance_policy_path` y `acceptance_required: true`; este ultimo bloquea tambien una politica ausente desde el inicio. El JSON se publica como artifact por sistema operativo. Sin politica, el proyecto historico muestra `Acceptance: NOT_EVALUATED`; ese verde no acepta una entrega nueva.

## Repetibilidad y confianza

Dos corridas son una comprobacion basica de repetibilidad. No demuestran determinismo ni ausencia de flaky. Para concurrencia, tiempo y orden, revisar semillas, escenarios, numero de repeticiones y condiciones. Registrar fallos sin contarlos como deteccion de una mutacion cuando la herramienta no pudo ejecutarse.

Los oraculos aprobados, runtimes y runner se consideran confiables. No existe sandbox frente a codigo hostil que pueda alterar el propio proceso o acceder al sistema. La proteccion de ramas y aprobacion externa siguen siendo necesarias. Ver [garantias y limites](verification-guarantees.md).
