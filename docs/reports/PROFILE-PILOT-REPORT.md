# Verificación del perfil KDD con Reparto Justo

## Alcance

Experimento aislado sobre una copia local de `KDD-Pilot` (commit original
`9c41f16`). Se copiaron a esa copia los cambios del perfil, validadores,
contratos y tests relevantes de esta rama y se creó allí el commit experimental
`e44c7f1c8a50311e3921957d0d0758f0a00bd88b`. Ese commit sirve para
probar el mecanismo; **no representa una aprobación humana**.

## Resultados observados

| Caso | `suite` | `approved_baseline` | `contract_tests` | Resultado |
| --- | --- | --- | --- | --- |
| Producto sano | PASS | PASS | PASS, producto 3/3 e infraestructura 37/37 | exit 0 |
| `src/allocation.py` sustituido temporalmente por `NotImplementedError` | PASS | PASS | FAIL en `allocate-cents.md`, producto 2 PASS y 1 FAIL | exit 1 |

El archivo del producto se restauró byte por byte al terminar la prueba. La
suite heredada seguía verde en el caso roto; el nuevo paso detectó el defecto.

En el repositorio KDD, `python scripts/validate_baseline.py --all
--approved-ref 08e327ef3e39e3c53987b9db996c8e075bba9874` devuelve exit 1
y señala los cuatro contratos actualizados junto con sus cuatro oráculos. Es la
respuesta esperada hasta que un mantenedor apruebe una referencia nueva.

La [ejecución de CI 36178139712](https://github.com/MauricioPerera/KDD/actions/runs/36178139712)
completó los cuatro jobs: `board` pasó en Ubuntu y Windows; `validate`
falló en ambos solo en el paso final de baseline, frente al `main` anterior.

## Comprobaciones de regresión

- `python -m unittest tests.test_run_profile tests.test_validate_baseline
  tests.test_validate_test_commands`: 35 tests, PASS.
- `python -m unittest discover -s tests -p 'test_*.py'`: 835 tests, PASS.
- `python scripts/validate_contracts.py knowledge/contracts`: 47 contratos,
  0 errores y 0 warnings.
- `python scripts/validate_okf.py knowledge`: 87 nodos, 0 errores y 0 warnings.
- `python scripts/validate_budgets.py knowledge/contracts --repo-root .
  --contract run-profile`: PASS.
- `python scripts/lint_ascii.py scripts`: 0 errores.

## Reproducción

1. En una copia de `KDD-Pilot`, actualizar los archivos de perfil, baseline,
   gate de tests, contratos y oráculos de esta rama y hacer un commit
   experimental. Usar su SHA completo en
   `python scripts/run_profile.py --profile standard --approved-ref <SHA>`.
2. Sustituir temporalmente `src/allocation.py` por una función
   `allocate_cents` que lance `NotImplementedError` y repetir el comando.
3. Restaurar `src/allocation.py`. El primer comando sale 0; el segundo sale 1
   en `contract_tests`, aunque `suite` y `approved_baseline` sigan PASS.
4. Para verificar el control de re sellado, modificar el test y actualizar
   `tests_sha256` en su contrato sin cambiar el SHA aprobado. El gate de
   baseline debe rechazar ambos archivos.

## Límite de confianza

La CLI exige un SHA explícito, pero no puede demostrar quién lo aprobó. En
pull requests, el workflow usa por defecto el SHA de la rama base; aprobar un
oráculo nuevo requiere que un mantenedor configure una referencia de confianza
fuera del control del implementador. `main` está protegido: exige pull request,
los cuatro checks `validate` y `board` en Ubuntu y Windows (con rama actualizada),
aplica la regla a administradores y bloquea force push y eliminación de la rama.
Se verificó con la API de GitHub después de crear la regla. El resultado de CI
de esta rama seguirá rojo en el paso de baseline frente a `main` hasta la
aprobación de la referencia nueva.
