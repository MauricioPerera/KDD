---
type: 'Concept'
title: 'Piloto de KDD como complemento para un repositorio existente'
description: 'Adopción de KDD, release 1.1.0 y evidencia de la actualización a 1.2.0 en un proyecto existente.'
tags: ['kdd', 'adoption', 'plugin', 'validation', 'evidence']
---

# Piloto de KDD como complemento

El 10 de noviembre de 2026 se verificó que un repositorio Python existente puede adoptar un contrato KDD y validarlo con la misma revisión de KDD desde Codex, la terminal y GitHub Actions. El consumidor fue `MauricioPerera/delegate-codex-cli`, que ya tenía pruebas, historial y CI. El piloto quedó en la rama `codex/kdd-validator-pilot`, con un workflow adicional y la suite original intacta. [Base del consumidor](https://github.com/MauricioPerera/delegate-codex-cli/commit/ba90f5808639ebea5795139984b06d5aae38e99f) · [Árbol final del piloto](https://github.com/MauricioPerera/delegate-codex-cli/tree/b9518a9ddded49af4d0bbcf9142794c210555179)

## Diseño comprobado

Codex, la terminal y Actions usaron el mismo pin del validador. [Detalle](../docs/reports/ARCHIVO-PILOTO-KDD-COMPLEMENTO.md#diseño-comprobado)

## Evidencia

Codex, terminal y Actions concordaron en el SHA efectivo y el sello durante el
ensayo A → B → A, la regresión y su reversión.
[Commits, resultados y controles](../docs/reports/ARCHIVO-PILOTO-KDD-COMPLEMENTO.md#evidencia)

## KDD for Codex 1.1.0

La adopción reutilizable se verificó en un proyecto existente en Ubuntu y Windows.
El tag de instalación del complemento y el pin del validador se eligen por separado.
[Instalación y evidencia de la release](../docs/reports/ARCHIVO-PILOTO-KDD-COMPLEMENTO.md#kdd-for-codex-110)

## Piloto con política de calidad activa

La demo ejecutó dos pasadas de los cuatro checks de calidad y los 22 casos del
contrato en cada sistema, con la referencia de calidad del consumidor aprobada.
[SHA, comandos y evidencia](../docs/reports/ARCHIVO-PILOTO-KDD-COMPLEMENTO.md#piloto-con-política-de-calidad-activa)

## Actualización verificada de 1.1.0 a 1.2.0

Codex CLI, terminal y Actions verificaron el mismo pin en el consumidor de slugs durante la actualización y la reversión. [Detalle](../docs/reports/ARCHIVO-PILOTO-KDD-COMPLEMENTO.md#actualización-verificada-de-110-a-120)

## Piloto de revisión ODD y EGM

En un proyecto adoptado, `python -I .kdd/validate.py review` usa el pin de la
adopción aprobada. Codex y la terminal pueden inspeccionar el mismo candidato.
La ruta editorial exige un único commit elegible y confirmación después de
leer el diff y la política. Los cambios de garantías conservan el contrato, el
oráculo y la aprobación humana del baseline. El modo de revisión valida el
registro de lectores independientes y lo vincula al árbol exacto.
[Contrato de revisión](./contracts/plugin-odd-egm-review.md)

La validación aprobada del consumidor compara los IDs por contrato en cada
pasada. El comprobante distingue dos selecciones distintas con el mismo
conteo y exige evidencia fresca de ambas pasadas. La salida conserva los
conteos y añade `oracle_inventory`. [Contrato de identidad de casos](./contracts/adoption-oracle-pass-identity.md)

## Alcance del resultado

Para nuevas adopciones, la [guía de instalación](../tools/kdd-adoption/README.md)
describe cómo revisar el commit del consumidor, configurar el control de PR y
preparar Python. También documenta la actualización y reversión del pin y la
migración desde una referencia histórica de calidad.

La evidencia de 1.1.0 cubre una instalación y actualización comprobadas con
Codex CLI, y el caso de una política activa sobre el SHA del consumidor indicado.
El lanzador selecciona la etapa de calidad cuando el proyecto tiene una
política en `quality/product.json` o `quality.json`. La política de la demo
comprueba integridad, perímetro y los cuatro comandos indicados. El alcance
observado es la CLI de slugs y el contrato seleccionado.
[Contrato de adopción](./contracts/reusable-kdd-adoption.md)

En el piloto inicial, Codex se probó con el binario de la aplicación y el modo
de permisos de la sesión. El intento con aislamiento de escritura de Windows
falló al iniciar el proceso de shell. Ese consumidor solo acreditó el rechazo
cuando faltaba la referencia de calidad. La plantilla sigue siendo el punto
de partida documentado para proyectos nuevos. [Plantilla KDD](https://github.com/MauricioPerera/KDD)
