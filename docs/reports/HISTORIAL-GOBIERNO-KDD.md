# Historial de verificación del objetivo de gobierno de KDD

Registro histórico de las cinco entregas de [CONTRACT-34](../../specs/CONTRACT-34-kdd-governance-closure.md). Los estados de integración corresponden al momento de cada medición. El [objetivo](../../knowledge/kdd-governance-closure.md) conserva los criterios y las responsabilidades.

KG-1 esta verificado en el candidato 4d968eafd33cf76f28f97f1d7d78bddf62b758a4
del [PR 148](https://github.com/MauricioPerera/KDD/pull/148), sin fusionar a main.
El [CI 41239179528](https://github.com/MauricioPerera/KDD/actions/runs/41239179528)
paso los 136 contratos y dos suites de 1721 casos en cada sistema, sin fallos,
errores ni omisiones de fixture. Conserva 10 SKIP declarados en Ubuntu y 9 en
Windows por pasada. La extension de inventario se reviso por separado en
4e698f52f27a970a0be83c7db9854a687bf0f803; no agrega un cierre historico.

KG-2 esta verificado en c5b309bd3084af9f921d32d4af92b413eeb586e4 del
[PR 150](https://github.com/MauricioPerera/KDD/pull/150), dependiente del PR 148
sin fusionar. El [CI 41243512201](https://github.com/MauricioPerera/KDD/actions/runs/41243512201)
pasa los 139 contratos y dos suites de 1743 casos por sistema, con el mismo
inventario, sin fallos, errores u omisiones de fixture; conserva 10 SKIP en
Ubuntu y 9 en Windows por pasada. El primer intento Windows agoto 600s en
init-project y se conserva; la repeticion paso sin cambiar codigo, oraculos,
workflows o limites. La investigacion aislada de rendimiento no se integro.


KG-3 esta verificado en 9ab50143ba3f3a8db768d5e1e4324b523eb02d39 del
[PR 151](https://github.com/MauricioPerera/KDD/pull/151), apilado sobre KG-2 sin
fusionar. El [CI 41252212507](https://github.com/MauricioPerera/KDD/actions/runs/41252212507)
pasa 141 contratos y dos suites de 1771 casos en cada sistema, con el mismo
inventario, cero fallos, errores u omisiones de fixture. Conserva 10 SKIP
normales en Ubuntu y 9 en Windows por pasada. El board pasa en ambos sistemas.
La evaluacion independiente sigue pendiente; no se afirma generalizacion.

KG-4 esta verificado en e202760c01b7d5d1978f1419859f2919f586a838 del
[PR 152](https://github.com/MauricioPerera/KDD/pull/152), apilado sobre KG-3 sin
fusionar. El [CI 41256786660](https://github.com/MauricioPerera/KDD/actions/runs/41256786660)
pasa 143 contratos y dos suites de 1796 casos por sistema, con inventario
identico, cero fallos, errores u omisiones de fixture. Conserva 10 SKIP normales
en Ubuntu y 9 en Windows por pasada; el board pasa en ambos sistemas. Esta
condicion se comprobo antes de modificar las tres fuentes autorizadas de KG-5.

KG-5 esta verificado en bc96b6df1c51fc4f664e6bb115d1a000d2282b3a del
[PR 155](https://github.com/MauricioPerera/KDD/pull/155), apilado sobre KG-4 sin
fusionar. El [CI 41264496192](https://github.com/MauricioPerera/KDD/actions/runs/41264496192)
completo 147 contratos y dos suites de 1852 casos por sistema, con inventario
identico, cero fallos, errores u omisiones de fixture. Conserva 10 SKIP normales
en Ubuntu y 9 en Windows por pasada; el board pasa en ambos sistemas. Ledger,
contexto y mediciones reales se observaron 2x por sistema contra el commit publicado.

Se conservan las aprobaciones d10ae37136da409df99c5010986efad78f878df6,
2eb28774b7043ff043ea33d141254604603a66db y la correccion exacta del fixture
8dad3baf4a1ba1ad92fd11e5705b3d2ef36394bb, sin alterar sus aserciones ni el ranking.
El primer CI 41263994076 rechazo la topologia antes de las suites. La integracion
de reemplazo reproduce el mismo arbol con una historia soportada por el auditor,
conservando los commits originales. El intento 1 de 41264496192 agoto 600s en
init-project Windows; el intento 2 paso sin cambiar codigo, oraculos, workflows
ni limites. Esos resultados se conservan. Los hashes y enlaces no acreditan
comprension, identidad humana ni ejecucion de los tests enlazados; no se afirma
evaluacion independiente ni generalizacion.
