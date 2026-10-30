---
type: 'Architecture'
title: 'Comandos exclusivos para integraciones que crean otra suite'
description: 'Evitar que init-project compita con otros comandos mientras conserva su suite real y el limite de 600 segundos.'
tags: ['ci', 'performance', 'windows']
---

# Evidencia y alcance

El [objetivo OP-3](operational-closure.md) requiere conservar cobertura,
Ubuntu/Windows y dos pasadas. En el commit 1ca4cb9, runtime 9a8a619 y 100
contratos, el lote nativo de Windows con cuatro workers tardo 978.250 s:
99 contratos pasaron e init-project agoto sus 600 s. Repetir el mismo arbol
con Git Bash, mismas versiones y configuracion comprobada, tardo 987.531 s
y reprodujo el mismo timeout de 600 s. El cambio de lanzador no lo resuelve.

El codigo y una muestra real de procesos muestran que ese comando inicia
otra suite de cuatro workers mientras el lote exterior ejecuta otros tres
comandos. La propuesta evita esa competencia. Los segundos anteriores son
mediciones locales, no tiempos intercambiables con un runner de GitHub.
La mejora se medira con los mismos limites y conservando los intentos fallidos.

# Politica explicita

exclusive_commands es una secuencia de test_command exactos, sin normalizar
espacios, comillas ni argumentos. Debe estar vacia por defecto. Rechazar tipos
invalidos, duplicados y comandos inexistentes antes de arrancar procesos.

Ejecutar primero los representantes exclusivos, uno por uno y sin otros
comandos del lote activos. Despues ejecutar los restantes con el pool acotado
existente. Es exclusion entre comandos del lote, no un sandbox ni un limite
universal de procesos descendientes de codigo arbitrario.

Con deduplicacion, un comando compartido se ejecuta una vez y conserva todos
sus contratos, scopes, stdout, fallos y shared_from. Sin deduplicacion, cada
contrato conserva su ejecucion. La salida sigue el orden original del
inventario, aunque la politica explicita cambie el orden de ejecucion.
Un fallo o timeout exclusivo no omite los comandos restantes.

# Integracion

El [contrato](contracts/ci-contract-resources.md) agrega
--exclusive-commands-json al runner confiable y al CLI del gate. El workflow
reutilizable recibe exclusive_contract_commands con default '[]'. Solo KDD
nativo en Windows selecciona por defecto el comando exacto de init-project; Ubuntu
conserva el pool paralelo. Los callers
conservan su perfil serial salvo configuracion explicita.

El timeout sigue siendo 600 s. No cambiar el oraculo de init-project ni su
suite anidada, omitir contratos, convertir el timeout anterior en PASS o
fusionar resultados de lotes distintos. Conservar Ubuntu/Windows, los seis
archivos del bundle, los cinco checks requeridos y las dos suites completas.
La nueva referencia del runtime requiere revision humana antes de publicarse.

# Medicion de cierre

Registrar tiempos del lote y de init-project antes/despues, head, runtime,
versiones y contexto de ejecucion. El comando real debe terminar dentro de
600 s, con todos sus asserts y su suite post-apply. Verificar el lote completo,
dos pasadas de todos los IDs y el CI del head exacto. Distinguir la mejora de
ese caso del tiempo del job completo; reportar ambos aunque difieran.
