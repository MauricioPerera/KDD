# CONTRACT-16 — Ejemplo de dominio: validación de pago por país — REPORT

Fecha: 2026-07-08
Spec: `specs/CONTRACT-16-ejemplo-pagos.md`

## Resumen ejecutivo

| Criterio | Veredicto | Evidencia |
|---|---|---|
| Oráculo congelado (14) | ✅ verde SIN modificar el archivo de tests (sello `tests_sha256` `e484831c...`) | corrida PM |
| Validador de contratos | ✅ exit 0 (incluye `validate-payment-limit.md` con sello vigente) | corrida PM |
| Validador OKF | ✅ exit 0 (nodo `payment_limits.md` enlazado desde `index.md`, sin huérfanos) | corrida PM |
| Validador de specs + lint ASCII | ✅ exit 0 | corrida PM |
| Suite `unittest` | ✅ verde 2× (**195 tests**) | corridas del PM sobre el estado final |
| Post-init neutral | ✅ `test_init_project` verde: el ejemplo de pagos se elimina con el manifiesto y los 3 gates quedan verdes en la copia | suite |
| CI | ✅ ambas patas en success | run del push de cierre |

## El caso resuelto (respuesta a "qué contratos congelados para finanzas")

Ejecutó el ciclo KDD completo sobre una feature de dominio financiero, como referencia
pública para quien pregunta por validación financiera:

1. **Orquestador**: autoró el nodo de datos
   [`payment_limits.md`](../../knowledge/data_models/payment_limits.md) (reglas de
   compliance: tope por país, divisas, verificación de beneficiario), el task contract
   [`validate-payment-limit.md`](../../knowledge/contracts/validate-payment-limit.md)
   anclado por enlace a ese nodo (no lo duplica), y el **oráculo congelado**
   `tests/test_payment_limit.py` (14 tests) sellado ANTES de delegar.
2. **Agente efímero**: ensambló su contexto (regla 7), leyó contrato + modelo + oráculo, e
   implementó SOLO `src/payment_limit.py` (pura, stdlib, sin red: la tabla `limits` entra
   por argumento) hasta poner el oráculo en verde.
3. **Gates nivel 1**: validador de contratos (con el sello del oráculo), OKF, specs, lint
   ASCII y suite — todos en CI dual-OS.
4. **Verificación del orquestador**: oráculo intacto (sello), suite 2×, y verificación
   **adversarial con fixtures propios** (no el oráculo): tope por país (400k pasa en AR,
   se rechaza en BR), `verified is True` literal (un `1` truthy no aprueba KYC),
   acumulación de 3 violaciones, robustez ante basura, y pureza (0 imports/IO/red).

Diseño clave para credibilidad de dominio: **la tabla de límites entra por argumento**, no
por red — la función queda pura y determinista, y la carga de compliance vive fuera del
oráculo. El veredicto lo da el gate corriendo los tests, nunca el modelo: una regla de
límite por país se verifica, no se opina.

## Decisión de diseño: ejemplo, no infraestructura

Se agregó al `MANIFEST` de `init_project` junto a `validate-user-record`: un proyecto real
que instancia la plantilla lo elimina al aplicar el init, y la plantilla vuelve a quedar
neutral al dominio. El `test_init_project` demuestra que post-init los 3 gates quedan
verdes. El gate cazó, durante el cableado, un efecto correcto: editar un comentario de
`test_init_project.py` (oráculo del contrato `init-project`) disparó `FM_TESTS_FROZEN`; se
re-selló ese contrato — la evidencia del cambio queda en el diff.

## Verificación final del PM (independiente del dev)

- 4 gates exit 0; oráculo 14/14; suite 2× consecutivas 195/195.
- Adversarial propio (arriba) verde; impl confirmada pura por grep.
- Ambos jobs del run de cierre en success.
- Reporte de tarea del dev (evidencia local, gitignorada): `.agents/logs/C16-REPORT.md`.

## Pendientes / ítems de seguimiento

Ninguno. El ejemplo queda como referencia de dominio financiero sin atar la plantilla a él.
