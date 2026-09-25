# CONTRACT-17 — Rule contract: reglas de negocio como datos — REPORT

Fecha: 2026-07-08
Spec: `specs/CONTRACT-17-rule-contract.md`

## Resumen ejecutivo

| Criterio | Veredicto | Evidencia |
|---|---|---|
| Oráculo del motor (18) | ✅ verde SIN modificarlo (sello `ecd4f82f...`) | corrida PM |
| **Equivalencia declarativo ↔ código (el experimento)** | ✅ 3/3: el motor sobre el rule-set reproduce el veredicto de `src/payment_limit.py` sobre todo el golden, salvo la regla `code_only` | corrida PM |
| Validadores contratos + OKF | ✅ exit 0 (12 contratos; nodo `rule-contract-spec.md` enlazado) | corrida PM |
| Validador specs + lint ASCII | ✅ exit 0 | corrida PM |
| Suite `unittest` | ✅ verde 2× (**216 tests**) | corridas del PM sobre el estado final |
| Post-init neutral | ✅ el rule-set/golden/equivalencia de pagos se eliminan con el manifiesto; motor y nodo de formato permanecen | `test_init_project` en la suite |
| CI | ✅ ambas patas en success | run del push de cierre |

## El veredicto del experimento (respuesta a "¿se puede validar reglas como datos?")

**Sí, casi entero — y la frontera es medible y estrecha.** Las reglas de compliance de
pagos (límite por país, divisas permitidas por país, país habilitado, monto positivo,
beneficiario dict con cuenta) se expresan como **datos declarativos** y el motor determinista
reproduce exactamente los mismos veredictos que el validador de **código** de C16 sobre un
golden set de 11 pagos decididos.

**La única regla que NO cabe como dato** (marcada `code_only` con su razón): "beneficiario
`verified` es exactamente `True`". Un `enum` por igualdad de valor no la puede expresar
porque en Python `1 == True` y `hash(1) == hash(True)`, así que `1` pertenece a `[true]`.
Distinguir `True` exacto de `1` es identidad/tipo, no un conjunto de valores: ese endurecimiento
de KYC vive en código. Es exactamente la frontera dato/lógica que game-protocol declara para
sus propias reglas ("un type nuevo exige código, eso es lógica no dato").

**Contribución sobre game-protocol:** para llegar hasta ahí hicieron falta familias `keyed`
(`keyed_bounds`/`keyed_enums`: el tope/conjunto se busca en una tabla por el valor de otro
campo) y acceso a campos anidados, que van más allá de las familias estáticas
(`refs/bounds/enums`) de game-protocol. Con eso, "límite POR PAÍS" es dato, no código.

## T1 — Motor de reglas (`scripts/rule_engine.py`, dev efímero)

`evaluate(ruleset, record, refs) -> list`: 7 familias declarativas, campos punteados,
orden determinista, nunca lanza, **agnóstico al dominio** (cero imports; no conoce pagos).
Implementado por agente efímero nativo contra el oráculo congelado, sin re-delegaciones.

## Cableado y oráculos (orquestador)

Nodo de formato `knowledge/rule-contract-spec.md` (infra, indexado); rule-set
`examples/rules/payment-compliance.rules.json` + golden `payment-golden.json` +
`tests/test_payment_rules_equivalence.py` (EJEMPLO, al MANIFEST). El golden se **verificó
contra el código de C16** al autorarse (ground-truth 11/11 consistente) antes de congelarlo.

## Verificación final del PM (independiente del dev)

- Oráculo 18/18; equivalencia 3/3; 4 gates exit 0; suite 2× 216/216.
- Adversarial propio con ruleset sintético (no el oráculo ni pagos): required/type/bounds,
  keyed excedido, keyed se salta clave irresoluble, no lanza ante basura, motor puro.
- **Desvío del PM, no del dev:** el test de equivalencia (artefacto del orquestador, no
  perímetro del dev) tenía un bug de autoría — `validate_payment_limit` guardado como
  atributo de clase sin `staticmethod` recibía `self`. El dev lo diagnosticó correctamente y
  NO lo tocó (respetó el congelado); lo corrigió el PM. Evidencia de que el perímetro se
  respeta en ambas direcciones.
- Reporte de tarea del dev (evidencia local, gitignorada): `.agents/logs/C17-REPORT.md`.

## Pendientes / ítems de seguimiento

Ninguno bloqueante. Camino natural (no en C17): un `validate_rules.py` CLI que valide un
rule contract completo (rule-set + golden) como gate de nivel 1, y aplicar la vertiente a
otro dominio (papers-please de game-protocol es candidato directo: control de fronteras =
misma forma que compliance de pagos).
