# Contrato 21 — Ejemplo didáctico: router de mensajes (evento → decisión, en dos formas)

Prerrequisitos: contratos 01-20 cerrados, HEAD `9f47d91`, suite 239 verde 2×, CI verde en
ambas patas. Ejemplo mínimo que responde la pregunta "¿puedo contratar: si llega un
mensaje y el emisor es Y ejecutá A, si no B?" mostrando el mismo dominio en las DOS formas
contratables y su frontera:

1. **La decisión como CÓDIGO** (task contract): `route_message(message, routing) -> str` —
   función pura con oráculo congelado que fija cada caso borde que hoy vive "en la cabeza"
   (emisor ausente, no-string, mayúsculas, tabla vacía).
2. **La auditoría como DATOS** (rule contract): validar decisiones YA tomadas
   (`{sender, decision}`) contra la política vía `keyed_enums` — y la frontera medida: la
   rama `else` abierta (emisor NO enumerado → decisión B) es inexpresable porque las
   familias keyed se saltan cuando la clave no resuelve; queda `code_only`. Cuarto dominio
   y cuarta aparición de la clase "condicional con default abierto".

> Capa: contrato de ejecución. T1 (código) lleva su task contract en
> `knowledge/contracts/route-message.md` (oráculo del orquestador, sellado). T2 (auditoría
> como datos) es autoría del orquestador verificada por el gate (REPRO).

Decisiones de diseño (fijadas acá):
- La tabla de ruteo entra POR ARGUMENTO (`routing = {"senders": {...}, "default": "B"}`)
  — pureza, mismo patrón que `limits` en pagos.
- El emisor se normaliza a minúsculas antes de comparar (los emails no distinguen
  mayúsculas); fijado por el oráculo, no por convención tácita.
- Emisor ausente, no-string o no listado → ruta `default`. La función NUNCA lanza.
- Todo es artefacto de EJEMPLO (al `MANIFEST`): la plantilla queda neutral al instanciar.

## T1 — `route_message` (dev efímero)

OBJETIVO: `src/route_message.py` con
`def route_message(message: dict, routing: dict) -> str:` que hace pasar el oráculo
congelado `tests/test_route_message.py` (autorado y sellado por el orquestador). Función
pura, stdlib, sin red; budget en el task contract.

## T2 — Auditoría de ruteos como datos (autoría del orquestador)

OBJETIVO: `knowledge/data_models/message_routing.md` (Data Model indexado: la política,
el mapeo a familias y la frontera del else abierto);
`examples/rules/routing-audit.rules.json` (+ `routing-golden.json` sellado): `keyed_enums`
sobre `{sender, decision}` con `code_only` documentando el else abierto, y un caso golden
que lo ejercita (`code_only_miss`).

## Criterios de aceptación

- [ ] `python -m unittest tests/test_route_message.py` verde SIN modificar el oráculo
  (sello `tests_sha256` vigente).
- [ ] `python scripts/validate_rules.py examples/rules` exit 0 con
  `Resumen: 0 error(es) en 4 archivo(s)` (los 3 dominios previos byte-intactos + ruteos).
- [ ] Mutación PM (sobre copia): decisión incorrecta de un emisor enumerado marcada como
  válida en el golden → `REPRO`; golden aflojado sin re-sellar → `GOLDEN_FROZEN`.
- [ ] `python scripts/validate_contracts.py knowledge/contracts` exit 0 (task contract
  nuevo sellado), `python scripts/validate_okf.py knowledge` exit 0,
  `python scripts/validate_specs.py specs` exit 0 y
  `python scripts/lint_ascii.py scripts` exit 0.
- [ ] `python -m unittest discover -s tests -p "test_*.py"` suite completa 2× verde
  (incluye `test_init_project`: post-init el ejemplo entero se elimina con el manifiesto).
- [ ] Final: CI verde en ambas patas.

## Restricciones

- Tocar SOLO — T1 (dev): `src/route_message.py` (+ su REPORT en `.agents/logs/`).
  T2 (orquestador): `knowledge/contracts/route-message.md` (nuevo, sellado),
  `tests/test_route_message.py` (nuevo, congelado),
  `knowledge/data_models/message_routing.md` (nuevo), `knowledge/index.md` (enlace),
  `examples/rules/routing-audit.rules.json` y `routing-golden.json` (nuevos),
  `scripts/init_project.py` (MANIFEST), `CHANGELOG.md`, el spec y el reporte.
- Motor, gate y sus oráculos NO se tocan (el dominio nuevo debe caber con lo que hay; si
  no cabe, eso se documenta como frontera, no se parchea).
- Los specs `CONTRACT-01..20` y sus reportes son históricos: read-only.
- Python stdlib puro; sin red; sin LLM; mensajes ASCII; determinista.
- NO commitear hasta verificar. Si algo no se puede sin romper otro criterio, PARAR y
  reportar.
- ABORTAR SI: el oráculo congelado resultara internamente contradictorio, o la forma
  auditoría exigiera tocar motor/gate. PARAR, documentar con evidencia y marcar BLOQUEADO.

## Checklist antes de delegar

- [x] RECON corrido (2026-07-08): la semántica "keyed se salta si la clave no resuelve"
  está congelada en el oráculo del motor desde C17 — la frontera del else abierto es un
  hecho verificado del sistema, no una suposición; el gate soporta N dominios (3 hoy) sin
  cambios.
- [x] Todo criterio tiene comando + resultado esperado.
- [x] Red-team hecho: la normalización a minúsculas y el default ante ausente/no-string
  van fijados por tests (no por convención); el golden de auditoría incluye el caso que el
  declarativo NO ve (`code_only_miss`) para que la frontera quede ejercitada, no solo
  declarada; los 3 goldens previos son canario de regresión vía REPRO.
- [x] Perímetro declarado; una tarea de código (T1); cableado del orquestador (T2).
- [x] Condiciones de aborto explícitas.
