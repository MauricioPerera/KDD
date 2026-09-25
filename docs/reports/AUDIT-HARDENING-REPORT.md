# Ajustes tras la auditoría de KDD

Fecha: 2026-09-05, zona America/Mexico_City. Base: `5dc26b448bd2c9f4826befc0e1c489fca5cb26ec`. Rama local: `fix/kdd-verification-hardening`.

## Resultado

Se corrigieron los falsos indicadores de verificación reproducidos en la auditoría y la exposición HTTP del tablero. La ejecución HTTP/MCP ahora comparte validación de contrato, comando y directorio. Se añadió comprobación opt-in contra un commit aprobado para detectar cambios simultáneos de test y sello.

## Cambios comprobados

- HTTP requiere token, rechaza orígenes ajenos y arranca en loopback. El cliente toma el token de la URL de arranque y lo conserva en la sesión de la pestaña.
- El comando ejecutado procede del contrato validado mediante el parser Python canónico. Las rutas deben permanecer dentro del proyecto. Un `testCommand` arbitrario en la creación de una tarea no sustituye al contrato.
- `done` requiere contrato, tests reconocidos aprobados, requisitos resueltos y hashes vigentes de contrato/target/oráculo. Cambiar los archivos, el contrato o el comando invalida la evidencia. Los reportes se guardan en el proyecto con ID de tarea en el nombre.
- El runner ya no cuenta un `echo`, un símbolo decorativo o un test omitido como prueba aprobada. Conserva el éxito del proceso como propiedad distinta.
- El vault conserva correctamente valores escapados, recarga sin retener claves eliminadas e inyecta valores al subproceso. La salida redacta coincidencias exactas de secretos conocidos.
- Seguridad exige un paquete ya sellado y comprueba schemas, hashes y coherencia con el lector vendorizado de solo lectura. Un fixture válido pasa sin modificaciones; alterar coverage provoca rechazo. La ausencia opcional aparece como SKIP; `--required` bloquea esa ausencia.
- `validate_baseline.py` detecta que contrato y test se modificaron conjuntamente contra un commit aprobado explícito. No selecciona HEAD automáticamente.
- CI incorpora typecheck y tests TypeScript en Windows/Linux con Node 24. Se corrigió un test preexistente que importaba `withMockDocument`, inexistente en fastwebmcp 0.4.2. Los fixtures nuevos no dependen de ejemplos eliminables por init_project.

## Validación local

Windows, Python 3.14.6, Node 24.16.0:

| Comando | Resultado |
|---|---|
| `python -m unittest discover -s tests -p 'test_*.py'` | 751 tests OK, dos pasadas: 42.681 s y 42.025 s |
| `npm --prefix tools/kdd-board test` | 10 tests OK, incluyendo HTTP real en puerto efímero y MCP con mock |
| `npm --prefix tools/kdd-board run typecheck` | Exit 0 |
| `node --check tools/kdd-board/public/app.js` | Exit 0 |
| `python scripts/preflight.py` | Exit 0; 18 PASS y 1 SKIP por ausencia de security/scan |
| `python scripts/audit_seals.py --strict` | 36 contratos, cero hallazgos |
| `python scripts/validate_contracts.py knowledge/contracts` | 36 contratos, cero errores/warnings |
| Validadores OKF, specs, changelog y lint ASCII | Exit 0 |
| `git diff --check` | Sin errores |

Las regresiones principales se escribieron y sellaron antes de modificar la implementación. Se conservaron las fallas iniciales observadas: cierre sin evidencia, echo contabilizado, escapes del vault, JSON sin sello y ausencia presentada como PASS. Se añadieron pruebas de integración para el paquete sellado válido, alteración posterior y canales HTTP/MCP. Los oráculos existentes de Python permanecieron intactos; se actualizaron dos tests del tablero para retirar una expectativa insegura y reparar la API de mock.

Salida local de comandos: `.agents/logs/python-final-1.txt`, `python-final-2.txt`, `preflight.txt` y reportes por contrato. La evidencia local está gitignorada; este reporte resume el resultado para revisión del diff.

## Límites y decisiones

No se ejecutó GitHub Actions ni Linux: el workflow quedó preparado y las comprobaciones locales se ejecutaron en Windows. No se afirma ausencia de flakiness a partir de dos pasadas. Persisten ResourceWarning preexistentes en tests de reglas, sin fallos de suite.

El tablero es para operadores de confianza: autenticación no equivale a sandbox. La redacción no impide exfiltración codificada o por red. Los hashes del tablero cubren contrato, target y oráculo, no todo el árbol de dependencias. El lector de seguridad verifica integridad, no identidad del productor ni correspondencia automática con HEAD. El baseline y el ejecutor necesitan protección externa para que un agente no pueda reemplazarlos. No se activó un gate remoto obligatorio ni se modificaron permisos del repositorio.

La optimización aplicada consiste en eliminar rutas de ejecución divergentes y aislar los tests del tablero en CI. No se introdujo cache ni se saltaron controles por archivos cambiados: eso requiere medir costos y modelar dependencias primero.

Migración y garantías: [verification-guarantees](../../knowledge/verification-guarantees.md). Estado antiguo del tablero requiere copia/reconciliación manual hacia `.kdd-board/tasks.json` del proyecto; nunca se sobrescribe automáticamente.
