---
type: 'Architecture'
title: 'Nivel 2 nativo sin transporte MCP'
description: 'Adaptador local al motor CCDD fijado por commit con sellos, limites y evidencia explicita.'
tags: ['ccdd', 'native', 'validation']
---

# Nivel 2 nativo

Complementa [validacion](./validacion.md). MCP es un transporte opcional; el motor
CCDD es el mismo. Este perfil inicial admite contratos KDD de funcion Python,
no grupos ni otros lenguajes. Las capacidades no soportadas bloquean explicitamente.
No modifica el conteo ni las dependencias de los gates de Nivel 1.

## Instalacion y uso

Desde la raiz de KDD, con Python 3.10+, Git y acceso a red SOLO para setup:

```sh
python scripts/setup_native_level2.py --runtime .kdd-runtime
python scripts/native_level2.py knowledge/contracts/mi-tarea.md --repo-root . --engine-root .kdd-runtime/engine --python .kdd-runtime/venv/Scripts/python.exe
```

En POSIX usar `.kdd-runtime/venv/bin/python`. El setup exige destino inexistente,
no instala globalmente ni pisa runtimes previos. Si falla, conserva el directorio
parcial para diagnostico; usar otro destino o retirarlo manualmente. Los tests del
proyecto pueden requerir dependencias adicionales en ese entorno: no se instalan
automaticamente. El test_command se conserva; `python` se resuelve mediante el PATH
del interprete elegido. No se sustituyen runners declarados por otros.

Prueba reproducible del motor real, en directorio temporal propio:

```sh
python -m examples.native_level2.demo --engine-root .kdd-runtime/engine --python .kdd-runtime/venv/Scripts/python.exe
```

Compara metricas/veredicto con la CLI upstream y comprueba fallos reales de tests,
presupuesto y sello. La prueba unitaria independiente del runtime es
`python -m unittest tests.test_native_level2`.

Se utiliza un checkout completo de ccdd-gate en el commit
`e6073e124ca506da6750aa41485350b717b2ff28`, no el wheel que puede omitir recursos.
El setup instala PyYAML 6.0.3 y jsonschema 4.23.0 en un venv. No instala MCP ni
proveedores LLM. Dependencias transitivas no estan bloqueadas por hash: no es una
instalacion hermetica. El adaptador exige commit exacto, checkout limpio y recursos
de schema/umbrales presentes antes y despues del gate. Requiere Git al verificar.

## Frontera de confianza

El operador aprueba motor, interprete, contrato y adaptador; estos deben estar fuera
del alcance de escritura del implementador en un despliegue real. Un hash evidencia
integridad, no firma humana ni identidad. El commit identifica la politica upstream;
no se afirma verificacion criptografica de firmas de umbrales. El host conserva su
referencia aprobada (ver [garantias](./verification-guarantees.md)).

Antes de ejecutar: Nivel 1 sobre el contrato, sello SHA256 LF, rutas confinadas a la
raiz, perfil Python y presupuesto positivo bajo topes. Topes explicitos del perfil:
cyclomatic 20, nesting 4, lines 80, params 5. Claves omitidas se completan con estos
topes, declarados en effective_budget de la evidencia; ninguna clave invalida se ignora.

El export temporal propio se crea exclusivamente en la raiz, sin pisar exports del
usuario. Conserva el comando original, usa test_cwd repo-relativo (default raiz) y
activa require_test_approval con hash de bytes crudos SOLO tras comprobar el sello LF.
Esto no re-sella el contrato ni los tests originales. No usa el exportador legacy,
cuyo cwd historico es el directorio del target; ambos formatos permanecen separados.

El proceso aislado por interprete (`-I`) importa el motor directamente sin MCP, exige
schema/dependencias y ejecuta task_gate.gate. No es sandbox: los tests ejecutan codigo
arbitrario con permisos y entorno del operador. Nunca usar con codigo hostil o secretos
de produccion. Timeout default 120 segundos, terminacion del arbol de procesos (best
effort; no cubre procesos que se independicen), sin cuotas de CPU/memoria/disco.

## Evidencia y limites

JSON en stdout: ok, verdict, stage, engine_commit, hashes raw de contrato/target/tests,
sello LF, effective_budget, resultado del motor y tiempo. Exit 0 PASS, 1 FAIL,
2 INVALID/ERROR/TIMEOUT. Un motor ausente, salida invalida, recursos ausentes o timeout
nunca produce PASS/SKIP. Salida del hijo limitada a 1 MiB al leerla; los buffers internos
de captura de tests del motor no estan acotados por este adaptador.

Hashes antes/despues de contrato, target, tests y export invalidan un PASS si cambian.
No cubren dependencias transitivas ni cambios que se reviertan durante la ejecucion.
No prueban calidad del oraculo, numero real de tests, ni ausencia de efectos laterales.
El resultado upstream tambien contiene detalles de fallos de tests: tratar el JSON
como evidencia potencialmente sensible. La evidencia no se firma ni persiste sola;
el host captura stdout en su almacenamiento protegido.

No se integra aun en KDD-Board, scheduler o planificador. La incorporacion al sprint
consiste en ejecutar este comando como verificacion explicita y conservar su resultado.
