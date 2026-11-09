---
type: 'Concept'
title: 'Remediacion de objetos aprobados, manifiesto y reinicio de Board'
description: 'Contratos y criterios de cierre para los tres defectos reproducidos en main 71630f0.'
tags: ['quality', 'baseline', 'board', 'integration']
---

# Alcance definido antes de implementar

La auditoría de `71630f0` reprodujo los tres defectos en Windows y Ubuntu.
Las garantías se definieron antes de implementar y se congelaron en el
baseline aprobado `ee0d4e614dff81e09e971edbf727b7a3c0a31948`.
Aplicar la [aprobacion](quality-approval.md) y la
[revision proporcional del candidato](baseline-risk-review.md) antes de adoptar
el commit de contratos y oraculos.

## QBR-1: identidad de objetos aprobados

El mismo OID aprobado debe seleccionar sus objetos originales. Un replacement
de commit o blob, la variable GIT_REPLACE_REF_BASE o un reemplazo creado durante
un check no pueden sustituir politica, oraculos, helper confiable o perimetro.
La [lectura de calidad](contracts/quality-approved-objects.md) debe cubrir las
invocaciones generales y batch de Git y la preparacion del manifiesto.
Los lectores no borran ni reescriben refs de reemplazo para lograrlo.

El control positivo aprueba un producto correcto. El producto incorrecto y los
oraculos debilitados se rechazan antes y despues de instalar el replacement;
el helper no revisado nunca se importa. Un check que confirma un archivo fuera
del perimetro no puede ocultarlo sustituyendo el commit aprobado.

## QBR-2: reinicio de Board legacy

El [ciclo de reinicio](contracts/board-secret-restart.md) inicializa el vault
antes de que TaskStore pueda consultar credenciales. Un requisito secreto
persistido no convierte almacenamiento valido en un error de formato.
Los controles recorren HTTP autenticado, cierre y un proceso Node nuevo:
credencial vigente, credencial retirada y migracion del vault antiguo.
Se conserva la [aislacion del vault](contracts/board-vault-isolation.md).

## QBR-3: identidad del manifiesto

El [hash del manifiesto](contracts/quality-manifest-bytes.md) identifica los
bytes del blob Git aprobado, sin normalizar CR, LF, CRLF, NUL o UTF-8.
Esto incluye policy_sha256 y cada protected.sha256. La forma JSON y las firmas
historicas se mantienen; cambia deliberadamente el hash cuando los bytes
aprobados contienen CR. La comparacion de texto normalizado de verify_quality
conserva su semantica: comparar oraculos y describir la identidad de un blob
son operaciones diferentes.

El fixture previo de quality-baseline escribe `frozen\n` como bytes explicitos,
conservando el hash esperado, sus dos metodos y sus aserciones. Evita que la
traduccion de write_text de Windows convierta esa entrada conocida en CRLF.
Los casos nuevos cubren tambien binarios sin NUL y politicas JSON con CRLF.

## Perimetro y cierre

El cambio de producción se limitó a `scripts/verify_quality.py`,
`scripts/quality_baseline.py` y `tools/kdd-board/src/server.ts`.
Las guías de calidad y Board documentan las garantías de cada componente.

Antes de implementar se exigieron: contratos validos, sellos exactos, fase roja equivalente
en Windows/Ubuntu y copias inicializadas, inventario anterior conservado,
revision del candidato exacto y aprobacion humana del baseline. El primer candidato
se conservo bloqueado al faltar la sustitucion independiente de la politica;
el segundo agrega ese control y fue revisado antes de aprobarse.
El cierre exige los 19 gates y comandos de contratos aplicables, dos pasadas completas
por sistema, IDs previos conservados, integraciones nuevas reales y controles
de mutacion pertinentes. Las pruebas Node de Board pueden omitirse unicamente
en la copia Python inicializada que no incluye sus dependencias; en la plantilla
deben ejecutarse y fallar si faltan esas dependencias.

## Resultado integrado

El PR #171 integró las tres correcciones en `e9689aa` con sus commits
originales. El guard verificó la revisión externa exacta del cambio en
`verify_quality.py` y el CI comprobó la selección del baseline aprobado.
[PR #171](https://github.com/MauricioPerera/KDD/pull/171) ·
[CI de main](https://github.com/MauricioPerera/KDD/actions/runs/42535919312)

La regresión del SHA integrado pasó en Ubuntu y Windows. El corte vigente
reúne los inventarios, la verificación de Pages y los resultados de
rendimiento y complejidad. [Estado verificable de KDD](estado-actual-kdd.md)
