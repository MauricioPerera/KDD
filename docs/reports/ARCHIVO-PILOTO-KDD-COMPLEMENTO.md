# Evidencia histórica del piloto del complemento KDD

Detalle del [piloto del complemento](../../knowledge/piloto-kdd-complemento.md) hasta la versión 1.1.0.

## Evidencia

A corresponde a `e07e404b4a8576f26cf9b6d3628f7ce5cd8ccaa8` y B a `3cc5948dc0cf151519dbe8b595c30d7947159336`. Se compararon 25 registros, cinco escenarios en Codex para Windows, terminal en Ubuntu y Windows, y Actions en Ubuntu y Windows. Para cada escenario coincidieron el commit consumidor, el SHA efectivo de KDD y el sello. [Registros comparados](KDD-PLUGIN-PILOT-EVIDENCE.json)

| Escenario | Commit consumidor | SHA de KDD | Resultado en los cinco entornos | GitHub Actions |
| --- | --- | --- | --- | --- |
| A inicial | `fd36da8` | A | Verde, un caso ejecutado | [42927995990](https://github.com/MauricioPerera/delegate-codex-cli/actions/runs/42927995990) |
| Cambio a B | `340b6b3` | B | Verde, un caso ejecutado | [42928156535](https://github.com/MauricioPerera/delegate-codex-cli/actions/runs/42928156535) |
| Vuelta a A | `234112b` | A | Verde, un caso ejecutado | [42928172887](https://github.com/MauricioPerera/delegate-codex-cli/actions/runs/42928172887) |
| Inversión del orden | `fc1873d` | A | Rojo en la aserción de orden | [42928189260](https://github.com/MauricioPerera/delegate-codex-cli/actions/runs/42928189260) |
| Reversión | `b9518a9` | A | Verde, un caso ejecutado | [42928204122](https://github.com/MauricioPerera/delegate-codex-cli/actions/runs/42928204122) |

Los dos cambios de versión editaron únicamente el lock. La regresión cambió una línea de producción y falló en `test_kdd_prefix_is_deterministic_and_goal_is_last`. La reversión recuperó exactamente el árbol anterior a la regresión. Para repetir la prueba, hacer checkout de cada commit del consumidor y ejecutar el comando del piloto con Python 3.11. El workflow original pasó en el commit final. [CI original](https://github.com/MauricioPerera/delegate-codex-cli/actions/runs/42928204144)

En copias descartables se rechazaron un pin ausente o inválido, un commit remoto inexistente, un blob alterado, un contrato ausente y una política KDD sin referencia aprobada. Al invalidar el sello, la suite original siguió en verde y el lanzador rechazó el contrato antes de ejecutar el oráculo.

## KDD for Codex 1.1.0

La adopción reutilizable quedó integrada en el PR #179. El instalador
previsualiza y aplica `.kdd/validator.lock`, `.kdd/validate.py` y
`.github/workflows/kdd-validate.yml`. En `pi-style-agent`, reaplicar la misma
configuración devolvió `unchanged`. Actions verificó el SHA fijado en Ubuntu
y Windows. En ambos sistemas se detectó una regresión local de producto y la
validación volvió a pasar al revertirla.
[PR #179](https://github.com/MauricioPerera/KDD/pull/179) ·
[CI de pi-style-agent](https://github.com/MauricioPerera/pi-style-agent/actions/runs/42943814291)

El PR #180 incorporó el complemento 1.1.0 en
`ef5e1efab8e8cf99bb1060b07afab286f2f63f22`. Se verificaron la instalación
desde el marketplace Git, la instalación desde el ZIP y la actualización
desde `1.0.0+codex.20260921005515`. Codex cargó la skill `kdd-workflow` y se
comprobó el flujo de adopción en una copia del consumidor. La release
`kdd-codex-v1.1.0` fija ese mismo commit y distribuye el ZIP del marketplace.
[Guía de instalación](https://github.com/MauricioPerera/KDD/blob/main/plugins/kdd-codex/README.md) ·
[Release 1.1.0](https://github.com/MauricioPerera/KDD/releases/tag/kdd-codex-v1.1.0) ·
[PR #180](https://github.com/MauricioPerera/KDD/pull/180)

El tag fija la versión del complemento que instala Codex. Cada proyecto
selecciona por separado el SHA del validador en `.kdd/validator.lock`.
La skill guía la adopción y el lanzador del proyecto ejecuta la validación.
[Contrato de adopción](../../knowledge/contracts/reusable-kdd-adoption.md) ·
[Uso del instalador](https://github.com/MauricioPerera/KDD/blob/ef5e1efab8e8cf99bb1060b07afab286f2f63f22/tools/kdd-adoption/README.md)

## Piloto con política de calidad activa

El 11 de noviembre de 2026 el workflow generado pasó en
`MauricioPerera/kdd-plugin-quality-e2e` sobre el commit
`5db0353524d3f0ff89cc698c4c889f1f225d563c`. Ese commit también fue la
referencia aprobada del consumidor en `KDD_QUALITY_APPROVED_REF`. El lock
fijó el validador KDD en `ef5e1efab8e8cf99bb1060b07afab286f2f63f22`.
El proyecto conservó los 22 casos de slugs de la demo original.
[Commit del consumidor](https://github.com/MauricioPerera/kdd-plugin-quality-e2e/commit/5db0353524d3f0ff89cc698c4c889f1f225d563c) ·
[Política aprobada](https://github.com/MauricioPerera/kdd-plugin-quality-e2e/blob/5db0353524d3f0ff89cc698c4c889f1f225d563c/quality/product.json) ·
[Workflow generado](https://github.com/MauricioPerera/kdd-plugin-quality-e2e/blob/5db0353524d3f0ff89cc698c4c889f1f225d563c/.github/workflows/kdd-validate.yml)

| Sistema | Python | Comandos de calidad por pasada | Pasadas de calidad | Casos del runner gestionado | Evidencia |
| --- | --- | --- | --- | --- | --- |
| Ubuntu | 3.11.18 | 4 | 2 | 22 | [Job 130559791070](https://github.com/MauricioPerera/kdd-plugin-quality-e2e/actions/runs/43031606724/job/130559791070) |
| Windows | 3.11.9 | 4 | 2 | 22 | [Job 130559791370](https://github.com/MauricioPerera/kdd-plugin-quality-e2e/actions/runs/43031606724/job/130559791370) |

Los logs muestran `PASS quality: integrity, perimeter and all checks verified twice`.
En cada pasada se ejecutaron `contracts`, `functional`, `adversarial` y `cli`.
Después, el runner `python-unittest` ejecutó los 22 casos del contrato seleccionado.
El registro final `KDD_PILOT` de cada job identifica el mismo commit del
consumidor, la referencia aprobada, el SHA solicitado y verificado de KDD y
el sello del contrato. [Ejecución 43031606724, intento 1](https://github.com/MauricioPerera/kdd-plugin-quality-e2e/actions/runs/43031606724) ·
[Registros verificados](KDD-PLUGIN-QUALITY-EVIDENCE.json)

Para repetir el caso localmente, clona el consumidor y haz checkout de
`5db0353524d3f0ff89cc698c4c889f1f225d563c`. Con Git y Python 3.11, fija la
referencia del consumidor y ejecuta el mismo lanzador.

En Ubuntu, pasa la referencia al entorno del lanzador.

```sh
KDD_QUALITY_APPROVED_REF=5db0353524d3f0ff89cc698c4c889f1f225d563c python .kdd/validate.py
```

En Windows, define la variable en PowerShell.

```powershell
$env:KDD_QUALITY_APPROVED_REF = '5db0353524d3f0ff89cc698c4c889f1f225d563c'
python .kdd/validate.py
```

En ensayos locales de ambos sistemas, una referencia ausente detuvo el flujo
en la etapa de calidad. La referencia histórica también se rechazó porque
carece del `scripts/process_tree.py` que el verificador actual lee del commit
aprobado. El candidato revisado añadió ese helper y protegió los archivos de
adopción. El piloto se publicó en un repositorio separado para mantener
independiente la referencia de la demo original.
[Aprobación de calidad](../../knowledge/quality-approval.md)
