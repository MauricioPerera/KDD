# SPRINT-04 - Nivel 2 sin MCP

Estado: closed (verificado localmente). Una tarea: native-level2. Autorizacion: "Adelante".

## Objetivo y perimetro
Ejecutar una verificacion Python real mediante motor CCDD local fijado por commit.
Adaptador, setup, oraculo congelado, documentacion y evidencia; sin publicar ni cambiar
el motor upstream. Dependencia: motor e6073e1 completo, Git, Python y deps de parsing.

## Presupuesto y bloqueos
Tokens/coste no medidos. Un ciclo de implementacion, correcciones guiadas por pruebas.
Parar ante necesidad de sandbox hostil, cambios upstream, soporte multi-lenguaje/grupos
o instalacion global. No delegacion; revision propia, sin agentes adicionales.

## Aceptacion
- [x] 17 tests unitarios del adaptador en verde, oraculo sellado sin cambios.
- [x] Setup limpio y gate real PASS/FAIL sin MCP; paridad con CLI upstream.
- [x] Rechazo por sello, revision, presupuesto, cambios y timeout.
- [x] 843 tests de regresion OK; preflight 18 PASS, 1 SKIP de seguridad opcional ausente.

## Evidencia
`.agents/logs/native-level2-REPORT.md`. Entorno Windows / Python 3.14.6.
Demo real: mcp_loaded=false, direct_cli_parity=true; fallos en gate1-tests y
gate2-complexity; oraculo alterado INVALID antes del motor; TIMEOUT real y limpieza
de exports. Setup repetido rechaza FileExistsError sin pisar runtime existente.
Primer preflight durante implementacion fallo por test_command aun en rojo; el final
pasa tras corregir conversion de escalares mini-YAML y alias de rutas Windows.
42 sellos auditados, 0 hallazgos. Sin CI remoto ni validacion POSIX en esta sesion.
Complejidad del propio adaptador no medida como Nivel 2. No sandbox ni firma humana.
No hubo push, PR ni merge. El runtime local queda en .kdd-runtime (gitignorado).
