# CONTRACT-10 — Endurecer el nivel 1: oráculo congelado por máquina, rutas existentes y placeholders honestos — REPORT

Fecha: 2026-07-07
Spec: `specs/CONTRACT-10-endurecer-validadores.md` (con 1 enmienda durante la ejecución)

## Resumen ejecutivo

| Criterio | Veredicto | Evidencia |
|---|---|---|
| Validador de contratos | ✅ | `Resumen: 0 error(es), 0 warning(s) en 8 archivo(s)` (los 8 con `tests_sha256` vigente) |
| Mutación T1 (oráculo editado en copia) | ✅ exit 1, `FM_TESTS_FROZEN` con archivo + hash esperado + actual | mutación ejecutada por el PM sobre copia, nunca el repo real |
| Mutación T2 (target fantasma) | ✅ exit 1 nombrando la ruta; fixture íntegro → exit 0 | fixture propio del PM, no el del dev |
| T3 (`->` en ABORTAR SI) | ✅ fixture con flecha → exit 0; placeholder `<...>` → exit 1 | demo adversarial del PM con fixtures propios |
| Validadores specs + OKF | ✅ exit 0 (11 y 15 archivos) | corrida PM |
| Suite `unittest` | ✅ verde 2× (**148 tests**: 136 + 12 nuevos) | corridas del PM sobre el estado final |
| CI | ✅ ambas patas (`ubuntu-latest` y `windows-latest`) en success | run `28900048227` sobre el push de cierre |

## SPECS-PLACEHOLDER / T3 (commit `f4d657a`)

La regla ABORTAR de `validate_specs.py` detecta placeholders reales con
`re.search(r'<[^<>\n]+>')` sobre el bullet + continuaciones; un `->` legítimo ya no da
falso ERROR (reproducido en RECON con fixture propio antes de redactar el spec). Test
nuevo congela ambos lados; task contract `validate-specs.md` alineado. Retoques de
integración del PM: docstring stale del módulo y mensaje de error a ASCII.

## PATHS-EXIST / T2 (commit `a3516d4`, enmienda `8c8fec3`)

`validate_contracts.py` exige que `target` y `tests` resuelvan a archivos existentes
(`FM_PATH_target`/`FM_PATH_tests`), con raíz explícita `--repo-root` (default `.`,
precedente C07/T9); CLI y API retro-compatibles; fixtures reconstruidos con raíz temporal
explícita (sin auto-consistencia por cwd).

**La cláusula de aborto funcionó como está diseñada:** el dev PARÓ al detectar que
`test_gates_verdes_post_apply_en_copia` borra `tests/test_init_project.py` ANTES de
correr el validador en la copia — con el check nuevo, el contrato intocable
`init-project.md` apuntaba a un archivo borrado. El PM reprodujo (1 fallo exacto),
enmendó el spec (Enmienda 1: mover el unlink anti-recursión después de los validadores,
cero cambio de lógica) y re-delegó al MISMO dev con la autorización (1 re-delegación de
las 2 permitidas).

## FREEZE-ORACLE / T1 (commit `6407bb8`)

Clave opcional `tests_sha256` en el frontmatter: sha256 hex 64 del archivo `tests` con
newlines normalizados a LF — obligatorio porque el working tree de origen tiene LF en
disco con `core.autocrlf=true` (RECON): otro clon puede materializar CRLF y un hash de
bytes crudos rompería entre plataformas. Presente y distinto = ERROR con ambos hashes;
ausente = WARNING; formato inválido = ERROR. Los 8 contratos sellados con su hash real
(post T3/T2, para no dejar hashes stale). El export gate-nativo no cambia (la clave
viaja verbatim, hex ASCII).

## Verificación final del PM (independiente de los devs)

- Hash de `tests/test_users.py` recalculado por el PM = el sellado por el dev (coinciden).
- Mutación del oráculo en copia → `FM_TESTS_FROZEN`; clave ausente → WARNING exit 0;
  archivo reescrito con CRLF → mismo veredicto (normalización verificada).
- `python scripts/validate_contracts.py knowledge/contracts` → exit 0;
  `validate_specs specs` → exit 0; `validate_okf knowledge` → exit 0.
- `python -m unittest discover -s tests -p "test_*.py"`: 148 tests, OK — 2× consecutivas.
- Reportes de tarea de los devs (evidencia local, gitignorada):
  `.agents/logs/T{1,2,3}-REPORT.md`.

## Pendientes / ítems de seguimiento

- `tests_sha256` queda como práctica recomendada (WARNING si falta). Candidato futuro:
  promoverla a obligatoria para contratos con oráculo congelado pre-delegación (estilo
  C04), manteniéndola opcional para contratos de tooling.
