# Prueba local de regresión entre dos commits

KDD adoptó de T3 Code la idea de ejecutar una misma prueba contra el commit
que exhibe el fallo y el que incorpora la corrección. El diagnóstico usa un
oráculo sellado de `unittest` y deja un recibo JSON ligado a ambos commits.
[Comparación en T3 Code](https://github.com/pingdotgg/t3code/blob/d8f315a81f5f8244742d98a8aacb02a7668bcd6e/scripts/prove-scenario.ts#L205-L261) ·
[Contrato de KDD](../../knowledge/contracts/regression-proof.md)

## Los cuatro intentos

El comando recibe dos SHA completos, el nombre del contrato y un
`--expect-failure` por cada ID que debe fallar en la base. Comprueba que la
base sea ancestro estricto del candidato y que contrato, sello e inventario de
oráculos coincidan. Materializa los árboles Git originales en cuatro copias
temporales independientes y verifica sus rutas, modos y blobs. Tras cada
ejecución vuelve a cotejar el contrato y los archivos del oráculo.

| Orden | Ejecución | Resultado exigido |
| --- | --- | --- |
| 1 | Base, intento 1 | Fallan exactamente los IDs declarados, cada uno por `AssertionError` |
| 2 | Base, intento 2 | Se repiten los mismos fallos de aserción |
| 3 | Candidato, intento 1 | Pasan todos los casos |
| 4 | Candidato, intento 2 | Pasan todos los casos otra vez |

Las cuatro ejecuciones deben registrar los mismos IDs y huellas de los
métodos ejecutados. El recibo v1 incluye `base_commit`, `candidate_commit`,
`oracle_sha256` con el hash de los bytes de cada archivo y `attempts` con el
lado, el número, el estado, los IDs, los fallos y las huellas. Un segundo
intento exitoso conserva cualquier fallo del primero. El código de salida
`0` corresponde a `proven`, `1` a `inconclusive` y `2` a `invalid`. Una
comparación rechazada durante la preparación queda sin intentos.

## Alcance del comando

- Admite contratos `python-unittest` con selección explícita de módulos o
  archivos incluidos en `oracle_files`. El registro usa los callbacks de
  `unittest` y exige métodos simples con origen dentro de ese inventario.
  Los wrappers, cierres, valores por defecto, subtests e invocadores
  personalizados quedan fuera del alcance.
- Los errores de ejecución, omisiones, fallos marcados como esperados,
  inventarios incompletos y vencimientos dejan la comparación inconclusa.
  Cada intento tiene el plazo del contrato.
- Requiere los commits en un repositorio con historia completa y árboles
  materializables como archivos y directorios regulares. Las copias se crean
  fuera del checkout y la ejecución usa un proceso con caché de bytecode
  aislada. Está diseñado para commits de confianza. Los procesos de prueba
  pueden usar las dependencias y recursos del entorno del operador.
- Es evidencia local y optativa de repetibilidad. El resultado cubre los
  casos seleccionados en ese entorno. La aceptación de una entrega y la
  aprobación humana del baseline tienen sus propios requisitos.
  [Aceptación](../../knowledge/acceptance.md) ·
  [Política de calidad](../../knowledge/quality-approval.md)

## Caso real del fixture HTTP de Pages

El PR #227 sincronizó el vencimiento simulado con los eventos HTTP del fixture.
El oráculo comprueba el plazo nativo de una consulta ordinaria, la cancelación
tras una lista vacía y la cancelación tras recibir cabeceras con el cuerpo
pendiente. Usa Node y un servidor HTTP por loopback. El plazo del contrato
para cada intento de la prueba local es de 90 s.
[PR #227](https://github.com/MauricioPerera/KDD/pull/227) ·
[Contrato del fixture](https://github.com/MauricioPerera/KDD/blob/456135406921a30628372b559fd90ec03d2391fb/knowledge/contracts/pages-artifact-fixture-timing.md)

En Windows con Python nativo, `3447c4c` devolvió `assertion_failure` en sus dos
intentos, con los tres IDs esperados. `4561354` devolvió `passed` en sus dos
intentos, con esos mismos IDs y huellas. El archivo
`tests/test_pages_artifact_fixture_timing.py` tuvo SHA-256
`6471efff0ad0147feacf18ebf876a4f6a578100c37522fcc5519f2ac7f0ac460` en ambos
commits. El recibo global devolvió `proven`.

La reproducción siguiente usa Bash desde la raíz de KDD, con los dos commits
disponibles y las dependencias del fixture instaladas (Python 3.11, Node 24
y PyYAML). Si falta el candidato, el historial está disponible en
`refs/pull/227/head` de `origin`.

```bash
case_prefix=tests.test_pages_artifact_fixture_timing.PagesArtifactFixtureTiming
python scripts/prove_regression.py --repo-root . \
  --base 3447c4c4b880316f7d4caa70ad47b008bf70f0f9 \
  --candidate 456135406921a30628372b559fd90ec03d2391fb \
  --contract pages-artifact-fixture-timing \
  --expect-failure "$case_prefix.test_regular_http_lookup_uses_the_native_production_deadline" \
  --expect-failure "$case_prefix.test_empty_list_abort_waits_for_http_even_after_slow_startup" \
  --expect-failure "$case_prefix.test_pending_body_abort_follows_headers_even_after_slow_startup" \
  > pages-regression-proof.json
```

## Verificación de main tras el PR #228

El merge `f894275f62d154e4455cc52bfb0f27375f453aef` del 26 de noviembre de 2026
conservó el baseline aprobado `f57c475` y el commit de implementación
`059377b`. En GitHub Actions las dos pasadas de cada sistema reconciliaron los
mismos 2.770 IDs, con los 2.747 anteriores y las 23 integraciones del comando.
La cobertura de Python se midió en la primera pasada.
[PR #228](https://github.com/MauricioPerera/KDD/pull/228) ·
[CI de main, intento 1](https://github.com/MauricioPerera/KDD/actions/runs/45855543495/attempts/1)

| Sistema | Casos por pasada | Cobertura de líneas | Cobertura de ramas | Board |
| --- | --- | --- | --- | --- |
| Ubuntu | 2.770 y 2.770 | 75,14 % | 68,77 % | 133 casos |
| Windows | 2.770 y 2.770 | 77,20 % | 70,09 % | 135 casos |

Los dos jobs de post-init de Windows completaron 1.333 casos cada uno con
el runtime `39e402e`. La ventana común verificada fue de **468 s** frente
al límite de 600 s. El despliegue de Pages del mismo SHA consumió el
inventario verificado de 2.770 IDs. En el sitio publicado se comprobó el
enlace a ese CI y la igualdad byte por byte del contrato de regresión.
[Ventana de post-init](https://github.com/MauricioPerera/KDD/actions/runs/45855543495) ·
[Despliegue de Pages](https://github.com/MauricioPerera/KDD/actions/runs/45861165895)
