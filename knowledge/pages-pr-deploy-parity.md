---
type: 'Architecture'
title: 'Discovery de Pages en PR con dependencias del despliegue'
description: 'Reproducir el entorno Python de discovery del workflow de despliegue en un PR nativo.'
tags: ['ci', 'pages', 'discovery', 'integration']
---

# Paridad del discovery de Pages en PR

El [build de PR](pages-pr-validation.md) previo usa el interprete del job de
validacion, en el que pueden existir paquetes adicionales. El despliegue de
Pages prepara otro interprete. Una dependencia ausente en ese segundo entorno
puede pasar el preview y fallar despues de fusionar.

El PR nativo ejecuta ademas el discovery real de `site/ci_inventory.py` en un
venv Python nuevo, sin paquetes del sistema ni `PYTHONPATH`, en Ubuntu con el
mismo Python 3.11 del despliegue. Para evitar dos listas que diverjan, el
[ejecutor](contracts/pages-pr-deploy-environment.md) lee los pasos de instalacion
Python declarados antes del build en `.github/workflows/deploy-pages.yml` y
los ejecuta en orden en ese venv, sin shell. El
[cableado de CI](contracts/pages-pr-deploy-ci.md) ejecuta ese control antes del
preview existente; mantiene Ubuntu/Windows y las dos suites. El discovery no
es ejecucion de las pruebas ni una medicion de cobertura.

El analisis de instaladores admite solo pasos incondicionales y comandos
literales `python -m pip install` sin operadores de shell ni interpolaciones.
Una sintaxis de instalacion que no se pueda reproducir de forma fiel falla
cerrada, no se ignora. El checkout y las dependencias son codigo del PR que ya
se ejecuta en CI; un venv no es sandbox. El control se limita a dependencias
Python del discovery: no acredita igualdad del sistema operativo, red, servicios,
Node, permisos de despliegue ni artifacts del run posterior.

La lista exacta de IDs se obtiene del discovery del proyecto y se valida como
ordenada, unica y no vacia. Ausencia de paquetes, instalacion fallida, fixture
con import fallido, venv existente o configuracion no soportada devuelve fallo;
no se usa la salida parcial ni un fallback al interprete del job. El despliegue
sigue reconstruyendo desde su propio checkout y consumiendo solo el inventario
del CI de main, conforme al [protocolo](pages-ci-inventory.md).