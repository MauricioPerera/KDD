---
type: 'Architecture'
title: 'Compilacion de Pages antes de fusionar'
description: 'Ejecutar el build real en los PR nativos, separado del despliegue y con regresion de imports en procesos nuevos.'
tags: ['ci', 'pages', 'integration']
---

# Frontera y flujo

El despliegue posterior al PR124 detecto un error que la suite no observaba:
Pages carga scripts.mcp_gate_dispatch como paquete, mientras las pruebas de
dispatch lo cargaban desde scripts/. PR125 corrigio esa compatibilidad.
La [compilacion](contracts/pages-build.md) debe verificarse tambien antes de
fusionar, conforme al [contrato de PR](contracts/pages-pr-build.md).

En cada job validate de la matriz Ubuntu/Windows se instalan las dependencias
de site/package-lock.json y se ejecuta la CLI real de site/build.py. Ambas
operaciones preceden al gate de comandos y las dos suites largas. Se reutilizan
Python3.11, Node24 y los pins existentes; no se agrega un job ni una tercera
pasada. El conjunto de [19 gates](validacion.md) permanece intacto.

La condicion explicita de ambos pasos es pull_request, repositorio
MauricioPerera/KDD y !inputs.reusable_execution. Los consumidores externos y
las llamadas reutilizables por defecto omiten esos pasos; un PR nativo no
puede omitirlos porque falten archivos de site/. No se infiere aplicabilidad
por nombre de directorio ni se requiere npm en la suite Python.

# Artefacto local y publicacion

El destino esta fuera del checkout, bajo RUNNER_TEMP, e incluye run ID,
intento y SO. Debe estar ausente. La URL de evidencia corresponde al run del
PR actual: sirve como procedencia de ese build y no afirma que el run ya haya
terminado. La compilacion ejecuta memory/publish, publish --check y validacion
strict bajo /KDD/, segun [Pages](contracts/pages-build.md).

El job conserva contents:read y actions:read. No obtiene secretos de despliegue,
permisos pages/id-token write ni environment github-pages. No configura,
sube ni despliega el artefacto del PR. El workflow deploy-pages conserva su
trigger workflow_run tras push exitoso de main y reconstruye el mismo SHA;
no reutiliza un artefacto generado por codigo de un PR.

Los comandos del PR son codigo candidato sin sandbox, como las pruebas ya
existentes. Esta separacion no promete aislamiento frente a control del SO.
Las [referencias aprobadas](quality-approval.md) y los controles remotos solo
cambian mediante revision explicita; este cambio no autoriza excepciones.

# Oraculos y aceptacion

El oraculo nuevo comprueba el cableado del workflow y crea fixtures pequenos
copiando los helpers reales. Un interprete aislado importa el dispatcher como
paquete desde la raiz, sin scripts/ en sys.path, y ejecuta lint_ascii real con
un archivo sano y otro invalido. El modo CLI y un cwd ajeno son controles
positivos adicionales. No se usa el cache de imports del proceso de tests.

Una copia con el dispatcher anterior a PR125 debe hacer fallar la integracion
de paquete, conservando el control CLI. Se distinguen fallos del oraculo de
errores de entorno. El build real se ejecuta ademas localmente y en los pasos
del PR, con las dependencias fijadas; un mock del publisher no lo acredita.
Se conservan los 1170 IDs anteriores, sus aserciones y skips de aplicabilidad.
No se modifican el runtime confiable ni los oraculos previos.

Contratos y pruebas primero, sello y baseline revisado antes de modificar el
workflow. La fase roja inicial corresponde a los pasos ausentes del PR; la
importacion corregida en PR125 ya debe pasar. La evidencia y los controles
de mutacion se registran en .agents/logs/pages-pr-build-REPORT.md.
