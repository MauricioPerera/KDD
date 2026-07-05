# CONTRACT-06 — `init_project`: instanciar la plantilla en un proyecto real — REPORT

Fecha: 2026-07-04
Spec: `specs/CONTRACT-06-init-project.md` (con 2 enmiendas durante la ejecución)

## Resumen ejecutivo

| Criterio | Veredicto | Evidencia |
|---|---|---|
| Suite en el repo real | ✅ verde 2× (**106 tests, 0 skipped**) | corridas PM idénticas |
| Validadores | ✅ exit 0 (7 contratos, 12 nodos) | corrida PM |
| Dry-run por default | ✅ plan legible, árbol intacto | corrida PM |
| **Proyecto inicializado nace sano** | ✅ reproducción fiel del PM: copia estilo clon + `--apply` → validadores exit 0 y suite `OK (skipped=14, 0 failures)` | corrida PM |
| Todo-o-nada | ✅ manifiesto incompleto → exit 2 sin tocar nada | tests |
| Bug latente de C05 corregido | ✅ `.agents/logs` no trackeado rompía la suite en clon fresco → `mkdir` en el helper | hallazgo de la reproducción del PM |

## Entregado (`b9d49ce`)

`scripts/init_project.py`: manifiesto explícito de 8 artefactos de ejemplo (constante, sin
heurísticas), dry-run por default, `--apply` todo-o-nada, reescritura de `index.md` sin
enlaces muertos, `--name` solo el título H1. Guards `skipUnless` en los tests acoplados a
ejemplos (4 autorizados por spec) y en los tests del init (por manifiesto importado, sin
duplicar la lista). README (EN/ES) con el paso de instanciación.

## Historia de la tarea (4 iteraciones — el proceso funcionando, no fallando)

1. **Intento 1: vacío** — el agente leyó 10 archivos y terminó sin escribir (modo de fallo
   conocido; forense por transcript). Relanzado, misma spec.
2. **Intento 2: PARÓ con hallazgo** — corrió el experimento real ANTES de implementar y
   detectó un 3er acoplamiento fuera de los 2 guards autorizados; frenó por la cláusula
   del contrato y preguntó. El orquestador autorizó (spec enmendado, `72c3245`).
3. **Intento 3: implementó** — 106 tests verdes; pero la **reproducción fiel del PM**
   (copia estilo clon real + apply) reveló 2 gaps que la copia del agente no simulaba:
   (A) bug latente de C05 — `_TMP_PARENT = .agents/logs` no existe en un clon fresco →
   15 ERRORs en cualquier clon, con o sin init; (B) los tests del init corren también en
   proyectos ya inicializados → 8 FAILs.
4. **Intento 4: fixes A y B** (mkdir de 2 líneas + guard por manifiesto + criterio
   estrella con copia fiel) → verde en las tres configuraciones: plantilla íntegra
   (0 skips), clon fresco, y proyecto inicializado (14 skips, 0 fallos).

Dos re-delegaciones con feedback (política: máx 2) + un relanzamiento por dev vacío + una
parada por cláusula — ninguna iteración se pagó dos veces: cada una heredó el análisis de
la anterior vía REPORT.

## Verificación final del PM (independiente)

Suite 2× en el repo real; init aplicado por el PM en copia propia construida desde
`git ls-files` (fiel a un clon), 3 gates verdes post-init; dry-run inocuo verificado.

## Pendientes / ítems de seguimiento

Ninguno. La plantilla ahora se valida, se ejercita, se certifica (nivel 1 y 2) y se
estrena — el ciclo de vida completo de una plantilla real.
