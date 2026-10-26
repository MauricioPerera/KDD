---
type: 'Architecture'
title: 'SDK MCP fijado y verificacion real en CI'
description: 'Ejecutar las ocho pruebas de protocolo en un entorno aislado y rechazar SDK ausente, incompatible o pruebas omitidas.'
tags: ['mcp', 'ci', 'quality']
---

# Alcance y version

El [objetivo OP-4](operational-closure.md) verifica las ocho pruebas existentes
de [MCP](mcp-server.md) con SDK real, mediante streams en memoria. No acredita
el transporte stdio. El perfil base sin SDK conserva su aplicabilidad opcional.

La [linea 1.x sigue mantenida](https://github.com/modelcontextprotocol/python-sdk/tree/v1.x).
Se fija [mcp 1.30.0](https://pypi.org/project/mcp/1.30.0/), que conserva las APIs
del adaptador. La version 2 cambia esas APIs; no se instala implicitamente.
Un diagnostico con el mismo commit 1ca4cb9 ejecuta los ocho casos sin SKIP,
errores ni fallos en Windows/Python 3.11.15 y Ubuntu/Python 3.11.17, con SDK
genuino fuera del checkout. Esto demuestra compatibilidad; aun falta cablear CI.

# Entorno y dependencias

Crear el venv bajo RUNNER_TEMP, fuera del checkout, sin paquetes del sistema.
Los locks por plataforma fijan todas las versiones y hashes obtenidos de las
instalaciones reales. Instalar con --only-binary=:all: y --require-hashes desde
PyPI. No instalar el SDK en el Python base que ejecuta los gates y las dos suites.

KDD nativo exige este perfil dentro de los dos jobs validate ya requeridos.
Un caller reusable puede activarlo explicitamente; su default es false.
El SDK no se convierte en requisito de cada producto Python inicializado.
quality/product.json conserva sus comprobaciones obligatorias y dos pasadas.

# Criterio de aprobacion

El [verificador](contracts/mcp-sdk-ci.md) precarga el SDK genuino antes de
incorporar rutas del proyecto y exige su version fijada y origen externo.
Comprueba el manifiesto y el hash LF del archivo de ocho oraculos antes de
ejecutarlos. No aceptar un paquete del candidato como SDK ni datos de reporte
como sustituto de ejecutar el protocolo.

Un resultado valido contiene los ocho IDs exactos, esperados y ejecutados,
una sola vez, sin errores de discovery, fallos, errores ni SKIP. Cero casos,
SDK ausente/incompatible o evidencia reutilizada fallan. Los reportes son
nuevos por invocacion y distinguen el commit contextual cuando existe Git.
El CLI puede exigir el commit exacto del checkout en CI. Un fixture local
sin Git puede verificar protocolo sin atribuirse un commit o un run de CI.

La suite base sigue mostrando sus ocho SKIP cuando no instala SDK. Ese perfil
no aprueba el adaptador. El check requerido de CI usa el venv y debe ejecutar
los ocho casos reales sin SKIP, ademas de las dos pasadas generales completas.

# Operacion

Consultar tools/mcp-sdk/pins.json y el lock de la plataforma antes de preparar
un entorno. Los hashes evitan resolver versiones nuevas durante una misma
revision. Actualizar SDK, locks u oraculos requiere otro baseline revisado;
las excepciones sobre archivos de CI protegidos requieren autorizacion concreta.
