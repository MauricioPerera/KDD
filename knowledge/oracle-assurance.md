---
type: 'Concept'
title: 'Garantia de oraculos exigida por una politica revisada'
description: 'Estructura soportada, contramuestras exactas, controles sanos y evidencia sin confundir integridad, deteccion y juicio humano.'
tags: ['governance', 'quality', 'oracles', 'mutation']
---

# KG-3: candidato verificado en CI

El [objetivo de gobierno](kdd-governance-closure.md) exige que los controles
aplicables se ejecuten. La [matriz de operaciones](operation-controls.md)
distingue preparar una tarea de aprobar un producto. Esta propuesta agrega
la revision requerida del oraculo al punto de aprobacion del producto; no
ejecuta mutaciones al preparar o iniciar una tarea ni al leer historia.

Baseline humano aprobado: 44695e90e0e55ec0b1549c8c58d31ad8d6a5d623.
La implementacion candidata conserva todos los oraculos anteriores y los nuevos
congelados. La verificacion dual-OS 2x del candidato concluyo correctamente.
Contratos: [atribucion](contracts/mutation-attribution.md) y
[revision obligatoria de producto](contracts/quality-oracle-reviews.md).

El [CI del candidato 9ab5014](https://github.com/MauricioPerera/KDD/actions/runs/41252212507)
verifica 141 contratos y dos pasadas de 1771 casos por sistema, sin fallos,
errores ni omisiones de fixture; conserva 10 SKIP Ubuntu y 9 Windows.

## Autoridad y compatibilidad

La persona revisora declara `oracle_reviews` en la politica JSON antes de
implementar. Cada entrada es un requisito, no un diagnostico opcional del
runner. No se permite vaciar la lista, reemplazarla desde el checkout,
omitir un caso ni convertir soporte ausente en PASS. Para proyectos nuevos
que requieren esta garantia, la politica debe incluir todos los contratos
de implementacion pertinentes; la persona revisora comprueba esa cobertura.
El runner informa exactamente las entradas ejecutadas, sin extender su
garantia a contratos no declarados.

Las politicas antiguas sin el campo conservan su comportamiento y declaran
`oracle assurance not requested`. Esto es compatibilidad limitada, no una
certificacion retrospectiva. Migrarlas exige otro baseline humano; no se
reescribe historia ni se agregan requisitos a una politica ya aprobada.

El auditor `audit_seals` conserva su API y su modo advisory. La revision
requerida lo utiliza, pero no lo agrega a GATE_SPECS ni a los 19 gates.
Los cinco modulos del bundle historico de tareas siguen siendo cinco.

## Esquema de una entrada requerida

```json
{
  "contract": "knowledge/contracts/app.md",
  "risk": "Rechazar la aceptacion indebida de otro entero",
  "structural": "python-ast",
  "timeout": 5,
  "mutants": [
    {
      "id": "accepts-two",
      "source": "quality/mutants/accepts-two.py",
      "expected_tests": ["tests.test_app.TestApp.test_value"]
    }
  ]
}
```

Las claves son exactas. Riesgo e IDs son strings no vacios; IDs unicos por
entrada; `expected_tests` no vacio; timeout entero 1..3600; rutas relativas
exactas dentro del proyecto, sin alias. Contrato, oraculo y fuentes mutantes
son archivos regulares protegidos. Los helpers ejecutables importados por
el oraculo tambien deben estar protegidos: su inventario completo se revisa
humanamente, el runner no deduce todas las dependencias dinamicas.

Soporte inicial: estructura AST de tests Python e invocacion unittest del
oraculo exacto. La estructura comprueba presencia, parseo, funciones de test,
aserciones no triviales segun las reglas existentes y referencia al target.
No demuestra pertinencia semantica. Otra estructura/lenguaje/runner requeridos
sin soporte producen ORACLE_UNSUPPORTED. No se afirma un AST TypeScript.

La politica protege tambien scripts/mutation_audit.py, scripts/audit_seals.py,
scripts/validate_contracts.py y scripts/process_tree.py. Se extraen de objetos
Git aprobados a un bundle externo para la revision. No se importa un auditor
alterado del checkout ni se amplia el bundle historico de tareas.

## Experimento y clasificacion

1. Validar esquema, contrato completo, sellos, modos y proteccion de entradas.
2. Comprobar estructura requerida antes de ejecutar el primer oraculo.
3. Ejecutar controles original y copia sin mutar en temporales externos.
   Ambos deben ejecutar pruebas reconocidas y pasar; cero pruebas no basta.
4. Copiar los mismos inputs y reemplazar solo el target por cada fuente exacta
   aprobada. No generar sustitutos para evitar un caso dificil.
5. DETECTED requiere las aserciones esperadas, sin errores de ejecucion ni
   fallos ajenos al inventario esperado. Pruebas ejecutadas y exitosas son
   SURVIVED. Error, timeout, cero pruebas o fallo de otra causa son INCONCLUSIVE.
   Solo un experimento completo con todos DETECTED permite aprobar.
6. Repetir cada revision en las dos pasadas y recomprobar integridad/perimetro
   despues de cada una, incluso cuando falla. Los checks ordinarios de esa
   pasada solo empiezan despues de sus revisiones requeridas exitosas.

ORACLE_REVIEW conserva JSON con iteracion, SHA aprobado, riesgo, hash del
contrato y metodo/findings estructurales. Cada mutante conserva fuente real,
hashes de target/oraculo/mutante, comando, exit, timeout, stdout/stderr,
hash de salida, casos fallidos y motivo de clasificacion. El auditor automatico
anterior recibe la misma mejora de atribucion y datos; conserva sus operadores
y SKIP advisory. La revision requerida nunca acepta un SKIP como deteccion.

Los hashes de fuente normalizan LF; los campos raw identifican tambien los
bytes originales. El hash de salida usa el stdout/stderr capturado como texto
UTF-8. Las copias y fuentes se recomprueban durante el experimento; los targets
revisados deben conservar sus bytes tras los checks y entre ambas pasadas.

Los procesos usan la contencion existente; no son un sandbox. Se bloquea
la aprobacion ante efectos observados sobre archivos protegidos, sin prometer
rollback de efectos arbitrarios de un oraculo hostil. El runner, Git, ejecutor
y seleccion de referencias siguen dentro de la base de confianza externa.

## Revision humana y evaluacion independiente

El codigo exige lo aprobado y conserva los hechos. La persona revisora decide
si el riesgo es adecuado, si las fuentes representan defectos pertinentes,
si los casos esperados los distinguen y si el inventario protegido es completo.
Una etiqueta o el nombre de un test no demuestra esas decisiones.

Las contramuestras del baseline son casos conocidos para regresion. No son un
conjunto independiente ni una medida de generalizacion. Mantener aparte un
conjunto de evaluacion seleccionado por una persona o evaluador que no haya
disenado estos casos ni la implementacion; registrar su procedencia y resultados
por separado. Si no existe esa evaluacion, declarar su ausencia. Este baseline
no acredita haberla realizado ni permite contar casos conocidos como holdout.

PARAR y presentar otra propuesta si se necesita otra fuente, otro oraculo,
mas presupuesto o cambiar workflows. El permiso propuesto de produccion se
limita a scripts/mutation_audit.py y scripts/verify_quality.py.
