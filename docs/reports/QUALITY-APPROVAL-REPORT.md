# Aprobación integrada de calidad en la plantilla

## Resultado

Se trasladó el aprendizaje del gestor de gastos a un verificador genérico `scripts/verify_quality.py`, una política de ejemplo, reglas de adopción y el paso de aprobación del workflow existente. No se incorporaron SQLite ni reglas de negocio del gestor a la plantilla.

El runner exige política y referencia Git explícitas. Lee la política desde ese commit, protege política/oráculos tanto en worktree como en índice, calcula cambios committed/staged/unstaged/untracked no ignorados, ejecuta checks declarados sin shell dos veces y vuelve a comprobar integridad después de cada comando. Categorías funcional y adversarial son obligatorias; UI se declara cuando corresponde. Timeout, comando ausente, configuración inválida o violación de integridad impiden PASS.

CI deja de tener un echo de pruebas del proyecto: si existe quality.json exige referencia aprobada; si no hay configuración declara SKIP, sin atribuir aprobación de calidad a una aplicación. Se conserva la validación anterior de la plantilla. Los proyectos deben revisar comandos, dependencias y baseline: no se eligen automáticamente.

## Método y pruebas

- Contrato y 12 pruebas congelados en `4e14cb1b030d30043c4c3981d05d68b1853b72a1`, antes de delegar. Baseline rojo: 12 ejecutadas, falla el caso positivo porque el runner aún rechaza todo. Contexto ensamblado antes de delegar: 4459/13000 tokens estimados; guardrails aprobados.
- Implementador separado editó únicamente scripts/verify_quality.py. El oráculo conserva exactamente el contenido congelado. En revisión final el PM corrigió texto heredado del contrato validate-baseline (nombre de interfaz, ejemplos y referencia al tablero), sin cambiar los requisitos detallados de la sección Política ni los tests. La revisión del contrato queda versionada separadamente respecto del baseline inicial; no se afirma que ambos contratos sean idénticos.
- 12 pruebas del contrato pasan dos veces (12.480 s y 12.724 s, ejecución del implementador), luego incluidas en las ejecuciones independientes completas del PM.
- 5 pruebas adicionales del PM pasan: modificación de oráculo por un comando, archivo fuera de perímetro generado por un comando, manipulación del índice oculta por worktree restaurado, ejecutable ausente y timeout booleano inválido.
- Suite completa del PM: **768 pruebas aprobadas dos veces**, 82.920 s y 79.019 s. Son 751 anteriores + 12 del contrato + 5 adversariales. Las salidas FAIL de fixtures negativos impresas por la suite no son fallos de la suite: el resultado unittest es OK y exit 0.
- 3 pruebas adicionales ejecutan el cuerpo Python real del workflow sobre repositorios temporales: configuración ausente -> SKIP; política sin aprobación -> rechazo; política y commit válidos -> ejecuta runner real. Estas pasan dos veces aparte de las dos suites anteriores.
- Validación estructural local: 38 contratos y 75 nodos OKF, cero errores/advertencias; scripts ASCII conformes. El oráculo original del nuevo contrato se compara contra el commit previo a implementación. Preflight exit 0: 18 aprobados y 1 SKIP por evidencia opcional ausente, que no se contabiliza como verificada.

La matriz CI Windows/Linux existente descubrirá también estos tests cuando se ejecute remotamente. Solo se ejecutó localmente en Windows con Python 3.14.6; no se afirma resultado remoto, Linux ni compatibilidad medida en todas las versiones.

## Límites y adopción

La política de ejemplo contiene nombres ilustrativos y requiere adaptación. No aprueba un proyecto sin oráculos reales. Declarar la categoría adversarial o UI no demuestra fuerza del comando; se necesita revisión y evaluación por defectos introducidos. El runner no calcula complejidad ni convierte un DOM simulado en E2E. No es sandbox y depende del ejecutor/commit elegidos por un revisor confiable.

La integración hace obligatorio el gate cuando el proyecto configura su política. Una plantilla sin aplicación ni política se identifica como no configurada: no recibe una garantía universal. El conteo de 18 gates estructurales no cambia: esta entrada compone los checks elegidos por el proyecto.

Los ajustes previos de auditoría/tablero del workspace se conservaron. La aprobación del nuevo módulo no implica reescribir, publicar ni desplegar esos cambios.

Guía: [protocolo](../../knowledge/quality-approval.md), [ejemplo](../../examples/quality-approval/README.md). Evidencia local reproducible en .agents/logs/verify-quality-RED.txt, verify-quality-CONTEXT.txt, template-quality-suite-{1,2}.txt, quality-adversarial.txt y quality-workflow{,-2}.txt (logs ignorados por diseño).
