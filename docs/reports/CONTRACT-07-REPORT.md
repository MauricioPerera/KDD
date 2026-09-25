# CONTRACT-07 — Correcciones del audit externo — REPORT

Fecha: 2026-07-04
Spec: `specs/CONTRACT-07-audit-fixes.md`

## Resumen ejecutivo

| Criterio | Veredicto | Evidencia |
|---|---|---|
| Validador de contratos | ✅ | `Resumen: 0 error(es), 0 warning(s) en 7 archivo(s)` |
| Validador OKF sobre la KB | ✅ | `Resumen: 0 error(es), 0 warning(s) en 12 archivo(s)` |
| Suite `unittest` | ✅ verde 2× (116 tests, +10 vs baseline 106) | corridas del PM sobre el estado final |
| T7: `.txt` existente → error; carpeta → ok | ✅ | tests nuevos en `test_validate_okf.py` (21 verdes) |
| T8: regex real + reporte solo-configurados + invariante byte a byte | ✅ | 26 tests verdes; `cmp` exit 0 del ensamblador con config actual |
| T9: export independiente del cwd; parsers fijados; código muerto fuera | ✅ | 19 tests verdes; `cmp` idéntico re-corrido por el PM desde cwd distinto |
| CI | ✅ | run verde sobre el push de cierre |

## OKF-LINKS / T7 (commit `bd245ea`)

Regla única en spec y validador: un enlace válido resuelve dentro de `knowledge/` a un
archivo `.md` existente o a una carpeta existente; archivo existente no-`.md` → ERROR.
`OKF-SPEC.md` §4, docstrings del validador y task contract `validate-okf.md` alineados;
2 tests nuevos fijan ambos lados de la regla. La KB real sigue validando exit 0.

## CTX-HONESTO / T8 (commit `49346a9`)

`regex_deny` evalúa `re.search` real; patrón inválido → `ValueError` que lo nombra (sin
fallback silencioso a literal). `truncate`/`summarize` documentados como el mismo corte por
caracteres (solo difiere el marcador); `summarize` se mantiene por compatibilidad con la
plantilla publicada. El reporte del ensamblador lista solo guardrails configurados.
`ccdd/context.json` no necesitó cambios (patrones sin metacaracteres → mismo veredicto);
invariante verificado byte a byte (`cmp` exit 0). Desvío auto-corregido por el dev: un
literal `api_key=` que él mismo introdujo en el nodo contrato disparaba el abort; inspección
puntual del diff del nodo confirmó que la corrección es coherente.

## EXPORT-CWD / T9 (commit `764959f`)

`--repo-root` explícito (default `.`) resuelto a absoluto; el export es independiente del
cwd y los tests fijan la convención con rutas explícitas (ya no `getcwd()` en ambos lados).
Nuevo `tests/test_parser_coherence.py`: fixtures compartidas parseadas por los dos parsers
de frontmatter deben producir output idéntico — fija el dialecto sin acoplar los scripts.
Chequeo muerto de `validate_contracts.py` eliminado.

## Verificación final del PM (independiente del dev)

- `python -m unittest discover -s tests -p "test_*.py"`: 116 tests, OK — 2× consecutivas.
- `python scripts/validate_contracts.py knowledge/contracts`: exit 0.
- `python scripts/validate_okf.py knowledge`: exit 0.
- Export desde la raíz vs desde un cwd en otra unidad con `--repo-root`/`--out-dir`
  explícitos: `cmp` idéntico (corrida propia del PM, no la del dev).
- Reportes de tarea del dev (evidencia local, gitignorada): `.agents/logs/T{7,8,9}-REPORT.md`.

## Pendientes / ítems de seguimiento

- **Preexistente (no regresión de C07, detectado por el PM al verificar T9):**
  `export_gate_contract.py` con `--out-dir` en una unidad de Windows distinta a
  `--repo-root` falla con `ValueError` de `os.path.relpath` entre unidades, y el mensaje
  lo etiqueta engañosamente como "contrato invalido". Candidato a tarea futura: detectar el
  caso cross-drive y fallar con mensaje de I/O honesto (o soportarlo con rutas absolutas).
- Del audit quedaron fuera de alcance (documentado, no accionable en-repo): la parte
  semántica de §4/§6 de OKF-SPEC no verificable por máquina, y las referencias externas de
  `metodologia-ejecucion.md` (28 contratos del proyecto origen).
