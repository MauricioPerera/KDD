---
type: 'Concept'
title: 'Calidad de producto desde el arranque'
description: 'Preparar el CI de cada proyecto para exigir su politica de producto y una referencia revisada.'
tags: ['bootstrap', 'quality', 'ci']
---

# Calidad de producto desde el arranque

El [inicializador](contracts/init-project.md) y el
[arranque guiado](contracts/bootstrap-project.md) adaptan el workflow de la
copia nueva. El repositorio plantilla conserva su configuracion opcional:
sus ejemplos no constituyen la aprobacion de un producto ajeno.

## Resultado de inicializar

El workflow generado usa quality/product.json por defecto, requiere quality
como evidencia y verifica su configuracion antes de los oraculos. Una
politica ausente, SHA incompleto, inexistente o no ancestral causa FAIL.
Ubuntu/Windows, los gates, la concurrencia y las dos suites se conservan.
La implementacion se rige por el [contrato de integracion](contracts/bootstrap-product-quality-ci.md).

El inicializador comprueba el formato de las regiones que adapta antes de
borrar ejemplos. Si faltan o son ambiguas, aborta sin escribir. Conserva una
politica propia existente y cualquier archivo fuera del manifiesto. Dry-run
solo anuncia la configuracion; no genera ni aprueba un producto.

## Preparacion del primer CI

1. Definir los contratos y oraculos propios antes de implementar.
2. Redactar quality/product.json segun [quality-approval](quality-approval.md)
   y el ejemplo adaptable en examples/quality-approval/README.md. Incluir
   comandos funcionales, adversariales y de interfaz cuando corresponda.
3. Inventariar rutas exactas. Proteger oraculos, helpers, contratos,
   scripts/verify_quality.py, scripts/approval_registry.py, el workflow generado
   y sus dependencias.
   No copiar rutas ni SHAs del experimento de demostracion.
4. Registrar todo lo necesario en un commit y someter ese SHA completo a
   revision humana. La politica y todos los protected deben existir en el
   objeto Git aprobado. El manifiesto de quality_baseline.py facilita su
   revision; no aprueba la referencia.
5. La persona revisora registra los commits aprobados en la variable externa
   KDD_APPROVAL_REGISTRY, bajo el arbol Git exacto del candidato. Seguir el
   [protocolo de aprobaciones aisladas](approval-registry.md); conservar las
   entradas de main y de otras propuestas. baseline_ref y quality_ref pueden
   coincidir cuando el commit revisado contiene ambos baselines.
   El selector publica KDD_APPROVED_BASELINE_REF y KDD_QUALITY_APPROVED_REF
   para los pasos siguientes; los globals antiguos no son fallback.
   El bootstrap no crea commits, variables, refs ni aprobaciones.

Hasta completar esa preparacion, el CI nuevo falla con un diagnostico; la
ausencia de calidad no se considera SKIP satisfactorio, incluso con el
perfil local minimal. Los perfiles de adopcion conservan sus comandos.

## Ejecucion y confianza

El paso quality extrae scripts/verify_quality.py desde el SHA aprobado a un
temporal externo al checkout, y lo aplica al arbol e indice actuales.
Comprueba integridad y perimetro y ejecuta los checks dos veces. El resumen
solo muestra PASS de quality cuando existe la politica y el paso termina
success. No se prueba una revision antigua ni se filtran archivos.

Los cuerpos generados se verifican con Git y procesos reales en copias
temporales, incluyendo un producto propio y mutaciones. Esa aprobacion
simulada del fixture no aprueba KDD ni un repositorio del usuario.
Las protecciones y revision externa del workflow siguen siendo parte de la
frontera de confianza descrita en quality-approval.
