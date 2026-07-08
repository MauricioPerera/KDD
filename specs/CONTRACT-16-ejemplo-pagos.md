# Contrato 16 — Ejemplo de dominio: validación de pago por país (contratos congelados para finanzas)

Prerrequisitos: contratos 01-15 cerrados, HEAD sincronizado, suite verde 2×, CI verde en
ambas patas, release v1.0.0. Una pregunta recurrente sobre KDD es "qué contratos congelados
sirven para validación financiera". La plantilla es agnóstica al dominio a propósito, así
que la respuesta honesta es un EJEMPLO resuelto —no un dominio incrustado en el tooling—
que muestre el patrón: límite por país + verificación de beneficiario como función pura,
oráculo congelado por hash y veredicto por gate determinista, nunca por el modelo.

> Capa: este es un **contrato de ejecución** (nivel proyecto). La tarea de código lleva su
> **task contract** CCDD en `knowledge/contracts/validate-payment-limit.md`, anclado al
> nodo de datos `knowledge/data_models/payment_limits.md`.

Decisión de diseño (fijada acá): el ejemplo se agrega como **artefacto de EJEMPLO**, no
como infraestructura. Va al `MANIFEST` de `init_project` junto a `validate-user-record`, de
modo que un proyecto real que instancia la plantilla lo **elimina** al aplicar el init y la
plantilla vuelve a quedar neutral. Es un caso de referencia, no un dominio permanente.

## F-PAYMENTS (T1) — `validate_payment_limit` anclada al modelo de límites por país

OBJETIVO: `src/payment_limit.py` con
`def validate_payment_limit(payment: dict, limits: dict) -> list:` que valida un pago
contra las **reglas de compliance por país** declaradas en
`knowledge/data_models/payment_limits.md` (el task contract ENLAZA el nodo, no lo duplica —
regla 3 de la skill). Devuelve lista de violaciones legibles (vacía = válido). El detalle
normativo vive en el task contract `knowledge/contracts/validate-payment-limit.md` y en los
tests congelados `tests/test_payment_limit.py` (autorados por el orquestador ANTES de
delegar, sellados por `tests_sha256`, INTOCABLES para el implementador). La tabla de límites
entra por argumento (`limits`), no por red: la función es pura y determinista.

## Criterios de aceptación

- [ ] `python -m unittest tests/test_payment_limit.py` verde SIN modificar el archivo de
  tests (el sello `tests_sha256` fija el oráculo).
- [ ] `python scripts/validate_contracts.py knowledge/contracts` exit 0 (incluye el task
  contract nuevo con su sello vigente) y `python scripts/validate_okf.py knowledge` exit 0
  (nodo de datos nuevo enlazado desde `index.md`, sin huérfanos).
- [ ] `python scripts/validate_specs.py specs` exit 0 y
  `python scripts/lint_ascii.py scripts` exit 0.
- [ ] `python -m unittest discover -s tests -p "test_*.py"` suite completa 2× verde,
  incluyendo `tests/test_init_project.py`: post-init en la copia, el ejemplo de pagos se
  elimina junto con el resto del manifiesto y los 3 gates quedan verdes (la plantilla
  instanciada nace neutral).
- [ ] Evidencia del ensamblador (regla 7) en el REPORT del agente.
- [ ] Final: CI verde en ambas patas.

## Restricciones

- Tocar SOLO: `src/payment_limit.py` (+ el REPORT del agente en `.agents/logs/`).
  Tests, contrato, nodo de datos, `init_project.py`, `index.md`, specs y CI: intocables
  para el implementador (los autora/cablea el orquestador).
- Python stdlib puro; `re` no es necesario; prohibidos red, subprocess, IO de archivos.
- Los specs `CONTRACT-01..15` y sus reportes son históricos: read-only.
- NO commitear (el PM commitea la tarea verificada). Si algo no se puede sin romper otro
  criterio, PARAR y reportar.
- ABORTAR SI: cumplir el oráculo exigiera red/subprocess (la tabla `limits` entra por
  argumento, no se consulta), o el oráculo congelado contradijera el nodo de datos
  enlazado. PARAR, documentar con evidencia en el reporte y marcar BLOQUEADO.

## Checklist antes de delegar

- [x] RECON corrido (2026-07-08): oráculo `tests/test_payment_limit.py` sellado
  (`e484831c...`); `validate_contracts` exit 0 sobre el contrato; los 14 tests del oráculo
  verdes contra una implementación de referencia; mutación del oráculo dispara
  `FM_TESTS_FROZEN`. `MANIFEST` e `index.md` cableados; sin conteo hardcodeado del
  manifiesto en los tests (usan `set(MANIFEST)` dinámico).
- [x] Todo criterio de aceptación tiene comando + resultado esperado.
- [x] Red-team hecho: la tabla de límites por argumento cierra la vía de "consultar red y
  pasar igual"; `verified is True` literal (no truthy) impide que un beneficiario casual
  pase KYC; el tope por país (no global) está fijado por un test que contrasta AR vs BR.
- [x] Perímetro declarado; una sola tarea de código; el resto lo cablea el orquestador.
- [x] Condiciones de aborto explícitas.
