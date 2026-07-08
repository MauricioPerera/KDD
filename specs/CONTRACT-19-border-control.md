# Contrato 19 — Segundo dominio: control de fronteras (generalidad de las familias)

Prerrequisitos: contratos 01-18 cerrados, HEAD `8167f43`, suite 233 verde 2×, CI verde en
ambas patas. C17 probó la vertiente rule contract con UN dominio (pagos) y C18 le dio su
gate. La generalidad de las 7 familias está afirmada, no demostrada: este contrato la mide
con un segundo dominio deliberadamente distinto — **control de fronteras**, el vocabulario
de `papers-please` de `MauricioPerera/game-protocol` (reglas `require-document`,
`ban-country`, `require-field-match`, `not-expired`; decisiones `approve/deny/detain`).
Si las familias alcanzan, la vertiente generaliza; lo que no quepa se declara `code_only`
y ES el resultado (la frontera medida en un dominio más).

> Capa: contrato de ejecución SIN tarea de código delegada: el motor (C17) y el gate (C18)
> no se tocan — la tesis es exactamente que un dominio nuevo es puro DATOS + doc, autoría
> del orquestador, verificada por el gate existente (`validate_rules`, regla REPRO).

Decisiones de diseño (fijadas acá):
- **Mapeo declarado** del vocabulario papers-please a familias: `ban-country` → `refs`
  (la tabla `countries` contiene SOLO países admitidos; desconocido o vetado = fuera de la
  tabla); `require-document` → `required` + `keyed_enums` (tipo de documento permitido POR
  país); `not-expired` → `bounds` con año de política FIJO (un "no vencido respecto de
  hoy" exigiría reloj y rompería el determinismo — el rule-set congela el año de corte, y
  la razón queda documentada); decisión → `enums`; días de estadía → `keyed_bounds` (tope
  POR país). El mapeo completo vive en el nodo del dominio.
- **Frontera esperada**: `require-field-match` (el nombre del documento debe COINCIDIR con
  el del solicitante) es igualdad ENTRE dos campos del record — ninguna familia lo expresa
  (comparan un campo contra constantes o tablas, no campos entre sí). Va como `code_only`
  con razón; coincide con game-protocol, que implementa esa regla como lógica del motor.
- **Ejemplo, no infraestructura**: nodo del dominio + rule-set + golden van al `MANIFEST`
  (se eliminan al instanciar). El motor, el gate y el formato no cambian.

## T1 — Dominio border-control como rule contract (autoría del orquestador)

OBJETIVO: `knowledge/data_models/border_rules.md` (Data Model, enlazado desde `index.md`:
reglas del dominio + tabla de mapeo vocabulario→familia + fronteras documentadas);
`examples/rules/border-control.rules.json` (las 7 familias ejercitadas; `code_only` con
`require-field-match` y su razón; `golden: {path, sha256}` sellado con `--hash`);
`examples/rules/border-golden.json` (≥10 casos decididos: válido, país fuera de tabla,
decisión inválida, documento vencido por año de política, tipo de documento no permitido
para el país, estadía sobre el tope del país, campos ausentes/mal tipados, acumulación, y
el caso frontera de field-match con su `code_only_miss`). Los 3 archivos al `MANIFEST`.

## Criterios de aceptación

- [ ] `python scripts/validate_rules.py examples/rules` exit 0 con
  `Resumen: 0 error(es) en 2 archivo(s)` (pagos + fronteras, ambos sellados y con el motor
  reproduciendo su golden — la regla REPRO del gate es la prueba de generalidad).
- [ ] Mutación PM (sobre copia): aflojar un caso del golden de fronteras → exit 1
  `GOLDEN_FROZEN`; quitar una familia del rule-set y re-sellar → exit 1 `REPRO` nombrando
  el caso.
- [ ] `python scripts/validate_contracts.py knowledge/contracts` exit 0,
  `python scripts/validate_okf.py knowledge` exit 0 (nodo nuevo enlazado),
  `python scripts/validate_specs.py specs` exit 0 y
  `python scripts/lint_ascii.py scripts` exit 0.
- [ ] `python -m unittest discover -s tests -p "test_*.py"` suite completa 2× verde
  (incluye `test_init_project`: post-init el dominio de fronteras se elimina con el
  manifiesto y el paso de rules queda verde por capa opcional).
- [ ] El reporte declara el veredicto de generalidad: qué reglas del vocabulario
  papers-please cupieron como datos y cuáles quedaron `code_only`, con el porqué.
- [ ] Final: CI verde en ambas patas.

## Restricciones

- Tocar SOLO: `knowledge/data_models/border_rules.md` (nuevo), `knowledge/index.md` (solo
  el enlace), `examples/rules/border-control.rules.json` (nuevo),
  `examples/rules/border-golden.json` (nuevo), `scripts/init_project.py` (SOLO agregar los
  3 artefactos al MANIFEST), `CHANGELOG.md` (entrada en Unreleased), el spec y el reporte.
- `scripts/rule_engine.py`, `scripts/validate_rules.py` y sus oráculos NO se tocan: si el
  dominio exigiera cambiarlos, eso contradice la tesis y se documenta como hallazgo.
- Los specs `CONTRACT-01..18` y sus reportes son históricos: read-only.
- Sin código nuevo; sin red; determinista (año de política fijo, no reloj).
- NO commitear hasta verificar. Si algo no se puede sin romper otro criterio, PARAR y
  reportar.
- ABORTAR SI: expresar el dominio exigiera una familia nueva o tocar motor/gate — eso NO
  se hace en este contrato: se documenta la clase exacta como hallazgo de frontera y el
  dominio se cierra con lo expresable declarado, o el contrato se marca BLOQUEADO si ni
  siquiera el nucleo del dominio cabe. PARAR, documentar con evidencia y decidir.

## Checklist antes de delegar

- [x] RECON corrido (2026-07-08): vocabulario papers-please leído del repo real
  (`RULE_TYPES = require-document, ban-country, require-field-match, not-expired`;
  `DECISIONS = approve, deny, detain`); gate C18 operativo sobre `examples/rules` (1
  archivo hoy, resumen honesto); las familias keyed existen desde C17.
- [x] Todo criterio tiene comando + resultado esperado.
- [x] Red-team hecho: la regla REPRO del gate impide un golden decorativo; el sello impide
  aflojarlo; el mapeo `not-expired` → año fijo evita el no-determinismo del reloj y queda
  documentado (no escondido); la frontera field-match se ejercita con un caso del golden
  (no solo se declara).
- [x] Perímetro declarado; sin tarea de código; sin concurrencia.
- [x] Condiciones de aborto explícitas.
