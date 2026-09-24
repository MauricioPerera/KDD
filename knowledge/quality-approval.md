---
type: 'Concept'
title: 'Aprobacion integrada de calidad'
description: 'Integrar oraculos congelados, perimetro real y evidencia adversarial en la aprobacion de proyectos.'
tags: ['quality', 'ccdd', 'verification']
---

# Aprobación integrada de calidad

El objetivo de KDD es aportar garantías verificables de calidad, no prometer velocidad ni ausencia universal de defectos. Un sello demuestra integridad del oráculo; no demuestra su fuerza. Un validador disponible que el comando de aprobación no ejecuta no protege la entrega.

Este protocolo complementa la [validación de la plantilla](validacion.md) con un punto de aprobación específico de cada proyecto. Lo implementa [verify-quality](contracts/verify-quality.md). No reemplaza los validadores existentes ni cambia el conteo de sus 18 gates. El proyecto declara qué comandos los integran junto con sus pruebas.

## Flujo de aprobación

1. El PM define requisitos y oráculos antes de implementar. Cada garantía debe tener comprobación o una limitación declarada.
2. El PM redacta una política JSON que distingue archivos protegidos, implementación y artefactos del PM; declara comandos funcionales, adversariales y de interfaz cuando corresponda.
3. El revisor aprueba y registra un commit que contiene política y oráculos. El implementador no elige ni actualiza esa referencia.
4. Se implementa dentro del perímetro. El comando obligatorio de aprobación para ese proyecto es `python scripts/verify_quality.py --policy quality.json --approved-ref <commit-aprobado>`.
5. El verificador lee la política desde Git, compara los archivos protegidos, calcula el perímetro real y ejecuta todos los comandos dos veces. Recomprueba archivos y perímetro al terminar.
6. Los cambios de oráculo necesitan otra revisión y baseline explícito. No se resellan para encubrir un fallo. Conservar la evidencia anterior permite evaluar si aumentó la fuerza del oráculo.

## Política

- `protected`: oráculos, contratos, dependencias de pruebas y configuración que deben conservarse. Incluir helpers importados por las pruebas y cualquier archivo cuya edición permita falsearlas. La política se protege automáticamente.
- `implementation`: rutas exactas de producción autorizadas.
- `pm`: rutas exactas de documentación y reportes autorizadas. No usar un permiso genérico para todo el repositorio.
- `required_kinds`: al menos `functional` y `adversarial`; añadir `ui` si hay interfaz. Añadir otras categorías según riesgos del proyecto.
- `checks`: objetos con `name`, `kind`, `argv` (lista de argumentos sin shell) y `timeout` en segundos. Se requieren comandos para todas las categorías declaradas.

Los permisos son rutas exactas, no glob. La lista real incluye cambios staged, unstaged, commits posteriores al aprobado y archivos nuevos no ignorados. Los archivos ignorados como bases locales no se incorporan automáticamente al perímetro; un oráculo protegido se verifica aunque esté ignorado. No situar código ejecutable o helpers críticos fuera del inventario de confianza.

Para hacer visible la frontera antes de aprobar, genera un manifiesto de solo lectura
con `python scripts/quality_baseline.py --policy quality.json --approved-ref <SHA>`.
El comando rechaza `HEAD`, extrae la política y calcula hashes de todos los archivos
`protected` desde ese commit. Guarda su salida como evidencia de revisión y pasa el
mismo SHA explícito a `verify_quality.py`; el manifiesto no sustituye la aprobación
humana ni crea commits.

Ejemplo adaptable: [política y guía](../examples/quality-approval/README.md). No se debe usar HEAD automáticamente como referencia aprobada: hacerlo después de implementar borraría la frontera de revisión.

## Pruebas adversariales y de interfaz

Además de casos correctos, introducir defectos deliberados en copias aisladas. Para cada mutación registrar cambio exacto, test que la rechaza, salida y timeout. Clasificar: detectada por el oráculo pertinente, superviviente, equivalente o inconclusa. Un fallo por conexión o entorno no cuenta como detección de otro defecto.

Las pruebas de interfaz deben comprobar comportamiento: valores mostrados, texto del usuario, cancelación/confirmación y acciones realizadas. DOM simulado, navegador real, accesibilidad y revisión visual proporcionan evidencias distintas; no presentarlas como intercambiables. La categoría `ui` no permite deducir automáticamente cuál se ejecutó.

Mantener un conjunto de evaluación independiente no utilizado para diseñar las pruebas. Rechazar el conjunto conocido tras reforzarlo mide regresión, no generalización. Registrar falsos rechazos y repetir casos inconclusos conservando ambos intentos.

## Base de confianza y límites

Los comandos provienen de una política aprobada pero ejecutan código del proyecto: no hay sandbox. El runner, Git y la selección del commit requieren control externo. Un actor capaz de sustituir el runner puede imprimir PASS. En CI, usar un runner previamente revisado y fijado; las protecciones de rama/revisión deben configurarse fuera de este script.

Declarar un comando como adversarial o UI no prueba que lo sea. La revisión humana y las mutaciones evalúan la calidad del oráculo. No se calcula cobertura ni complejidad automáticamente: incorporar herramientas apropiadas a checks cuando sean requisitos, manteniendo la distinción de budget declarativo descrita en validacion.md.

## Evidencia que motivó este protocolo

En el experimento local del gestor de gastos, el oráculo inicial detectó 7 de 12 mutaciones manuales. Tras reforzarlo, rechazó las 12 conocidas y la regresión de identidad; también se comprobó bloqueo de archivos no autorizados y pruebas alteradas. Esto motivó integración obligatoria del perímetro y de pruebas complementarias. No representa una medición universal de KDD ni acredita proyectos que no ejecuten estos controles. Los resultados detallados pertenecen al repositorio del experimento, no se enlazan como archivos inexistentes en la plantilla.
