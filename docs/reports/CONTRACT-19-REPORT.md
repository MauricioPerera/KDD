# CONTRACT-19 — Segundo dominio: control de fronteras — REPORT

Fecha: 2026-07-08
Spec: `specs/CONTRACT-19-border-control.md`

## Resumen ejecutivo

| Criterio | Veredicto | Evidencia |
|---|---|---|
| **Gate sobre ambos dominios (generalidad)** | ✅ `Resumen: 0 error(es) en 2 archivo(s)` — el motor SIN TOCARSE reproduce el golden de fronteras (11 casos) | corrida PM |
| Mutación: golden aflojado | ✅ `GOLDEN_FROZEN` | mutación PM sobre copia |
| Mutación: familia quitada + golden RE-SELLADO | ✅ `REPRO` nombrando el caso (`require-document keyed`) y ambos conjuntos | mutación PM |
| 4 validadores + lint | ✅ exit 0 (nodo `border_rules.md` enlazado; 19 specs) | corrida PM |
| Suite `unittest` | ✅ verde 2× (233 tests — sin código nuevo, sin tests nuevos: la verificación del dominio ES el gate) | corridas PM |
| Post-init neutral | ✅ los 3 artefactos de fronteras en el MANIFEST | `test_init_project` en suite |
| CI | ✅ ambas patas en success | run del push de cierre |

## El veredicto de generalidad

**Las 7 familias generalizan.** El vocabulario completo de `papers-please` (game-protocol)
se expresó como datos sin tocar una línea del motor ni del gate: `ban-country` → `refs`,
`require-document` → `required` + `keyed_enums` (tipo de documento POR país, con campo
anidado `doc.type`), `not-expired` → `bounds` con año de política fijo, decisiones →
`enums`, tope de estadía → `keyed_bounds`. Un dominio nuevo costó exactamente: 1 nodo de
datos + 1 rule-set + 1 golden sellado. Cero código.

**La frontera, por segunda vez, es la misma clase**: `require-field-match` (igualdad ENTRE
dos campos del record: `doc.owner` vs `applicant_name`) no cabe en familias que comparan
contra constantes o tablas. Quedó `code_only` con razón y un caso del golden que la
ejercita — coincide con game-protocol, que la implementa como lógica del motor. Dos
dominios, dos fronteras, ambas de la familia "comparación no-uniforme" (pagos: identidad
`is True`; fronteras: igualdad cross-field). Si aparece un tercer dominio con la misma
clase, una familia `field_match` declarativa sería la extensión natural — pero eso es
evidencia para decidirlo, no alcance de C19.

**Determinismo sobre reloj**: `not-expired` relativo a "hoy" rompería el gate; el rule-set
congela el año de política (2027) como dato y el nodo documenta el porqué y cómo renovarlo
(editar + re-sellar, diff visible).

## Ejecución

Sin tarea de código delegada, por diseño: la tesis era que un dominio nuevo es puro
datos + doc del orquestador, verificado por el gate existente (regla REPRO). Se cumplió a
la primera corrida del gate.

## Verificación final del PM

- Gate 2/2 dominios exit 0 con resumen honesto; mutaciones exactas (arriba).
- 4 validadores + lint exit 0; suite 2× consecutivas 233/233.

## Pendientes / ítems de seguimiento

Ninguno bloqueante. Candidato futuro (con evidencia de 2 dominios, no urgente): familia
declarativa `field_match` para igualdad entre campos, si un tercer dominio repite la clase.
