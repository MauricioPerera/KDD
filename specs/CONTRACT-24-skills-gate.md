# Contrato 24 — Gate de skills: los activos de agente custodiados por máquina

Prerrequisitos: contratos 01-23 cerrados, HEAD `f70cafd`, suite 279 verde 2×, CI verde en
ambas patas. Sexto dominio, y el primero que custodia **activos reales del repo** en vez
de ejemplos: las skills de agente (`skills/` — copias versionadas — y `.agents/skills/`).
RECON (2026-07-08, ejecutado sobre los activos reales): el escaneo previo del gate ya
encontró **3 enlaces rotos reales** — `skills/delegar-glm-ccdd` (×2) y `skills/pm-glm-ccdd`
(×1) enlazan `../kdd-okf-ccdd-hybrid/SKILL.md`, que no existe ni en `skills/` ni como
skill operativa local; y `.agents/skills/kdd-okf-ccdd-hybrid` tiene un enlace ILUSTRATIVO
(ejemplo DO de la sección 3) sin backticks que cualquier checker flaggearía. Byte-identidad
repo↔operativa verificada para las 5 copias (la reparación debe respetar la regla de
sincronía: operativa primero, copia byte-idéntica después).

> Capa: contrato de ejecución. T1 (código, dev efímero) lleva su task contract en
> `knowledge/contracts/skills-gate.md`. T2 (reparaciones + cableado) es del orquestador.
> El gate es INFRAESTRUCTURA (no va al MANIFEST): custodia activos permanentes.

Decisiones de diseño (fijadas acá):
- **Checks del gate** (por cada subdirectorio con skill): `SKILL.md` presente; frontmatter
  parseable (mismo dialecto mini-YAML que los validadores — tercera copia deliberada, y
  `test_parser_coherence` se extiende a 3 vías para fijar el dialecto); `name` presente,
  kebab-case e igual al nombre del directorio; `description` presente con largo en
  [50, 1024] (cota informada por RECON: las reales van de 400 a 780; 1024 es el tope
  práctico de descripción de skill); cuerpo no vacío; enlaces markdown relativos (fuera
  de code spans/fences, mismo stripping que `validate_okf`) resuelven a un archivo
  existente; `name` único entre todos los directorios escaneados.
- **Reparaciones del RECON** (T2, respetando la sincronía): los cross-links rotos de las
  copias pasan a la URL canónica del repo (la skill híbrida vive en KDD, no como sibling
  local) — fix en la copia OPERATIVA (`~/.claude/skills/`) primero y sync byte-idéntico a
  `skills/`; el enlace ilustrativo de la skill híbrida pasa a code span (backticks), la
  convención que la propia KB usa para ejemplos.
- **Capa opcional**: directorio ausente → INFO + exit 0 (un proyecto instanciado puede no
  conservar `skills/`); directorio presente se valida estricto.
- CLI multi-directorio: `python scripts/validate_skills.py <dir> [<dir>...]` — un solo
  paso de CI cubre `skills/` y `.agents/skills`.

## T1 — `scripts/validate_skills.py` (dev efímero)

OBJETIVO: el gate con los checks de arriba, contra el oráculo congelado
`tests/test_validate_skills.py` (autorado y sellado por el orquestador: válida pasa; sin
SKILL.md, name ausente/no-kebab/distinto del dir, description ausente/corta/larga, cuerpo
vacío, enlace roto, enlace en code span ignorado, names duplicados entre dirs, dir ausente
INFO exit 0, multi-dir, los activos reales del repo pasan limpios post-T2, exit codes).
Estilo `validate_okf`; findings ordenados; stdlib puro; ASCII; determinista.
`tests/test_parser_coherence.py` se extiende a 3 vías (mismas fixtures, tercer parser).

## T2 — Reparaciones + cableado (autoría del orquestador)

Fixes de los 3 enlaces (doctrina de sincronía); paso de CI
`python scripts/validate_skills.py skills .agents/skills`; task contract sellado;
`knowledge/validacion.md` y README ganan la línea del gate (sin duplicar); CHANGELOG.

## Criterios de aceptación

- [ ] `python -m unittest tests/test_validate_skills.py` verde SIN modificar el oráculo.
- [ ] `python scripts/validate_skills.py skills .agents/skills` exit 0 sobre los activos
  REALES (post-reparaciones) con resumen honesto de cuántas skills se validaron.
- [ ] Byte-identidad preservada: `diff` vacío entre cada `~/.claude/skills/<s>/SKILL.md`
  reparada y su copia `skills/<s>/SKILL.md`.
- [ ] Mutación PM (sobre copia): romper un enlace de una skill → exit 1 nombrándolo;
  duplicar un name entre dirs → exit 1.
- [ ] `python -m unittest tests/test_parser_coherence.py` OK (3 parsers, mismo dialecto).
- [ ] Los 5 gates existentes exit 0 y suite completa 2× verde.
- [ ] Final: CI verde en ambas patas (7º paso nuevo).

## Restricciones

- Tocar SOLO — T1 (dev): `scripts/validate_skills.py`, `tests/test_parser_coherence.py`
  (SOLO extender a 3 vías, sin debilitar) (+ su REPORT). T2 (orquestador):
  `~/.claude/skills/{delegar-glm-ccdd,pm-glm-ccdd}/SKILL.md` + sus copias `skills/`
  (byte-idénticas), `.agents/skills/kdd-okf-ccdd-hybrid/SKILL.md` (solo backticks del
  ejemplo), `tests/test_validate_skills.py` (nuevo, congelado),
  `knowledge/contracts/skills-gate.md` (nuevo, sellado),
  `.github/workflows/validate.yml` (solo agregar paso), `knowledge/validacion.md`,
  `README.md` (línea del gate EN/ES), `CHANGELOG.md`, el spec y el reporte.
- Motor, gate de rules, sus oráculos y los dominios de ejemplo NO se tocan.
- Los specs `CONTRACT-01..23` y sus reportes son históricos: read-only.
- Python stdlib puro; sin red; sin LLM; mensajes ASCII; determinista.
- NO commitear hasta verificar. Si algo no se puede sin romper otro criterio, PARAR y
  reportar.
- ABORTAR SI: reparar los enlaces exigiera cambiar CONTENIDO doctrinal de una skill (los
  fixes son solo de referencia/formato); o la extensión de coherencia a 3 vías revelara
  que el tercer parser NO puede compartir dialecto sin cambiar los otros dos (eso es un
  hallazgo, no un parche). PARAR, documentar con evidencia y marcar BLOQUEADO.

## Checklist antes de delegar

- [x] RECON corrido (2026-07-08, activos reales): 3 enlaces rotos encontrados y
  diagnosticados (2 cross-links de copias + 1 ilustrativo sin backticks); byte-identidad
  repo↔operativa verificada 5/5; largos reales de description 400-780 (cotas [50,1024]
  informadas por datos); `kdd-okf-ccdd-hybrid` NO existe como skill operativa local (el
  fix correcto es la URL canónica, no un path relativo a un sibling inexistente).
- [x] Todo criterio tiene comando + resultado esperado.
- [x] Red-team hecho: el stripping de code spans evita falsos positivos sobre enlaces
  ilustrativos (y el ilustrativo real se pasa a backticks — la convención de la KB);
  la byte-identidad es CRITERIO (no promesa) con diff vacío; el dialecto del tercer
  parser queda fijado por la coherencia a 3 vías, no por fe.
- [x] Perímetro declarado; una tarea de código (T1); reparaciones del orquestador (T2).
- [x] Condiciones de aborto explícitas.
