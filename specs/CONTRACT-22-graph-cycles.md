# Contrato 22 — Checker de ciclos de grafo: la frontera #3 cerrada por código

Prerrequisitos: contratos 01-21 cerrados, HEAD `20fc426`, suite 248 verde 2×, CI verde en
ambas patas. C20 midió y declaró la tercera clase de frontera de la vertiente rule
contract: **propiedades globales del grafo** ("ningún ciclo entre nodos" en las
`connections` de un workflow) son inexpresables por elemento — quedaron `code_only`. Este
contrato cierra esa frontera por la vía que la doctrina manda: un **task contract** de
código con oráculo congelado, completando en el dominio workflows la dupla que C21
demostró en ruteo (datos para lo uniforme + código para lo no-uniforme).

> Capa: contrato de ejecución. T1 (código, dev efímero) lleva su task contract en
> `knowledge/contracts/check-graph.md` (oráculo del orquestador, sellado). Motor y gate NO
> se tocan.

Decisiones de diseño (fijadas acá):
- Firma `def find_graph_cycles(connections: dict) -> list:` — estilo violaciones del
  repo (lista de strings legibles, vacía = sin ciclos), cada una nombrando el camino del
  ciclo con prefijo `connections:` (coherente con el campo del golden de C20).
- **Forma canónica de ciclo**: cada ciclo se reporta UNA vez, rotado para empezar en su
  nodo lexicográficamente menor (`A -> B -> A`, nunca también `B -> A -> B`); violaciones
  ordenadas — determinismo total.
- `connections = {nodo: [destinos]}`. Entradas malformadas (no-dict, destinos no-lista,
  destinos no-string) se saltan sin lanzar — la forma la valida el rule contract del
  dominio (C20); este checker solo decide ciclos.
- Artefactos de EJEMPLO (al `MANIFEST`): checker, oráculo y contrato acompañan al dominio
  workflows y se eliminan al instanciar.

## T1 — `find_graph_cycles` (dev efímero)

OBJETIVO: `src/check_workflow_graph.py` que hace pasar el oráculo congelado
`tests/test_check_graph.py` (autorado y sellado por el orquestador: acíclico, self-loop,
ciclo de 2, ciclo largo, diamante SIN ciclo — convergencia no es ciclo —, ciclo en un
componente desconectado, múltiples ciclos reportados una vez cada uno en forma canónica,
malformados sin lanzar, determinismo). Stdlib puro; budget en el task contract.

## T2 — Cierre del mapa de fronteras (autoría del orquestador)

OBJETIVO: `knowledge/data_models/workflow_policy.md` actualiza su frontera #1: "ciclos del
grafo" pasa de pendiente a **cerrada por el task contract
[check-graph](../contracts/check-graph.md)** (la dupla del dominio completa). Verificación
cruzada del PM: el caso `FRONTERA ciclo` del golden de C20 (`A->B->A`, invisible para el
declarativo) es detectado por el checker.

## Criterios de aceptación

- [ ] `python -m unittest tests/test_check_graph.py` verde SIN modificar el oráculo
  (sello vigente).
- [ ] Verificación cruzada: `find_graph_cycles` sobre las `connections` del caso FRONTERA
  del golden de workflows devuelve exactamente 1 ciclo — el código ve lo que el
  declarativo declaró no ver.
- [ ] `python scripts/validate_rules.py examples/rules` exit 0 (4 dominios byte-intactos:
  este contrato no toca rule-sets ni goldens).
- [ ] `python scripts/validate_contracts.py knowledge/contracts` exit 0 (contrato nuevo
  sellado), `python scripts/validate_okf.py knowledge` exit 0,
  `python scripts/validate_specs.py specs` exit 0 y
  `python scripts/lint_ascii.py scripts` exit 0.
- [ ] `python -m unittest discover -s tests -p "test_*.py"` suite completa 2× verde
  (incluye `test_init_project` con los artefactos nuevos en el MANIFEST).
- [ ] Final: CI verde en ambas patas.

## Restricciones

- Tocar SOLO — T1 (dev): `src/check_workflow_graph.py` (+ su REPORT en `.agents/logs/`).
  T2 (orquestador): `knowledge/contracts/check-graph.md` (nuevo, sellado),
  `tests/test_check_graph.py` (nuevo, congelado),
  `knowledge/data_models/workflow_policy.md` (solo la sección de fronteras),
  `scripts/init_project.py` (MANIFEST), `CHANGELOG.md`, el spec y el reporte.
- Motor, gate, rule-sets y goldens existentes NO se tocan.
- Los specs `CONTRACT-01..21` y sus reportes son históricos: read-only.
- Python stdlib puro; sin red; sin LLM; mensajes ASCII; determinista.
- NO commitear hasta verificar. Si algo no se puede sin romper otro criterio, PARAR y
  reportar.
- ABORTAR SI: el oráculo congelado fuera internamente contradictorio (p. ej. la forma
  canónica de ciclo resultara ambigua en algún caso del oráculo). PARAR, documentar con
  evidencia y marcar BLOQUEADO.

## Checklist antes de delegar

- [x] RECON corrido (2026-07-08): el caso FRONTERA del golden de C20 existe con
  `connections {A:[B], B:[A]}` y `code_only_miss ["connections"]`; el rule-set de
  workflows documenta la razón exacta que este contrato cierra.
- [x] Todo criterio tiene comando + resultado esperado.
- [x] Red-team hecho: el diamante-sin-ciclo está en el oráculo (convergencia ≠ ciclo, el
  falso positivo clásico de DFS mal hecho); la forma canónica impide inflar el conteo
  reportando el mismo ciclo rotado; malformados sin lanzar para que el checker componga
  con el rule contract sin pisarse (la forma es de C20, los ciclos son de acá).
- [x] Perímetro declarado; una tarea de código (T1); cableado del orquestador (T2).
- [x] Condiciones de aborto explícitas.
