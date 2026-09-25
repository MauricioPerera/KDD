---
type: 'Concept'
title: 'Garantias verificables y limites de confianza'
description: 'Alcance real del tablero, referencia aprobada, evidencia de seguridad y migracion.'
tags: ['security', 'ccdd', 'reference']
---

# Garantias de verificacion

Complementa la [validacion](./validacion.md) y la [supervision humana](./supervision-humana.md). Un proceso exitoso, un test reconocido y una decision correcta de producto son propiedades distintas.

## Tablero local

Requiere Node 24 o posterior y Python. El lanzador imprime una URL autenticada con token en el fragmento; abrir esa URL, no solo el puerto. El navegador guarda el token en sessionStorage y elimina el fragmento. El servidor escucha exclusivamente en 127.0.0.1, exige Bearer en las APIs y rechaza origenes ajenos. Quien tenga el token puede ejecutar los comandos de los contratos locales; debe ser un operador de confianza. No es un sandbox ni un servicio multiusuario.

HTTP y MCP comparten el mismo ejecutor. Este valida el contrato con el parser Python canonico y toma de el test_command, target y tests; no ejecuta el comando arbitrario recibido al crear una tarea. Resuelve rutas reales dentro del proyecto y conserva cwd, comando y hashes SHA-256 del contrato, target y oraculo. Rechaza evidencia si esos archivos cambian durante la ejecucion o antes de cerrar/generar un reporte. Cambiar comando o contrato invalida la evidencia; nuevos requisitos humanos tambien la invalidan.

La evidencia cubre esos tres archivos. No cubre automaticamente dependencias transitivas, servicios externos, herramientas ni toda la revision del proyecto. La salida del runner reconoce totales de Node TAP/spec y unittest; una salida no reconocida conserva cero tests y no habilita done. Un proceso puede terminar correctamente sin ejecutar tests. El codigo hostil puede falsificar salida: estos controles presuponen un ejecutor y oraculo confiables.

## Vault

El archivo .env.local del proyecto guarda valores en texto. Se inyectan solo al subproceso; no se exportan globalmente desde el flujo HTTP/MCP. Se redactan coincidencias exactas de valores conocidos en stdout/stderr antes de devolver o almacenar la salida. Esto no protege valores codificados, fragmentados o enviados por red. El codigo ejecutado y quien pueda leer el archivo pueden obtener los secretos. Para acceso ciego real se necesita un proxy de operaciones delimitadas con credenciales fuera del proceso controlado por el agente.

## Referencia aprobada

El hash tests_sha256 detecta diferencias respecto al contrato actual. El perfil
`standard` y el CI de pull requests comparan todos los contratos y sus oráculos
con una referencia aprobada, incluidas altas y bajas. Para revisar una tarea:

```sh
python scripts/validate_baseline.py knowledge/contracts/mi-tarea.md --approved-ref COMMIT_APROBADO
```

La referencia es obligatoria, sin default HEAD en `standard`/`strict`. Se
comparan contrato y archivo tests declarado en el contrato aprobado,
normalizando LF. La herramienta no modifica ni re-sella archivos. El commit
aprobado debe existir localmente; en CI se usa checkout con historial completo.
El CI de pull requests y de `push` a `main` exige
`KDD_APPROVED_BASELINE_REF` como variable del repositorio o el input
`approved_baseline_ref` del workflow reutilizable; si faltan ambos, falla.
No usa el SHA de la rama base ni el commit que está validando como aprobación
automática. El workflow comprueba esa referencia antes de ejecutar los
`test_command` y la suite del PR. Usa `contents: read` y el checkout no
persiste credenciales.

En este repositorio, la protección de `main` exige además `trusted-pr-gate`.
Su workflow `pull_request_target` usa código de `main` y lee el merge propuesto
como objetos Git, sin ejecutar archivos del PR. Compara contratos y oráculos
con la referencia aprobada y rechaza cambios a workflows o validadores
protegidos, incluso si el PR intenta aprobarse con su propio SHA. Al clonar
la plantilla, la configuración de protección de GitHub no se hereda: hay que
exigir este check explícitamente para obtener esa garantía. La herramienta
no autentica por sí sola la aprobación humana; quien administra la variable
y la protección de rama sigue siendo parte de la raíz de confianza.

## Evidencia de seguridad

El validador exige un manifest previamente sellado y reutiliza el verificador vendorizado en modo solo lectura para comprobar schemas, coverage, referencias y hashes antes de evaluar reglas. Nunca llama al paso que escribe o repara el sello.

```sh
python scripts/validate_security_findings.py security/scan --required
```

Sin --required, ausencia conserva exit 0 por compatibilidad y preflight muestra SKIP, fuera del numerador PASS. Con --required, ausencia bloquea. La comprobacion de integridad no autentica al productor ni prueba que el escaneo corresponda al HEAD actual; esa vinculacion debe imponerla el pipeline que produce y aprueba la evidencia. Otros dominios de Capa 3 conservan sus politicas existentes.

## Migracion

- Estado del tablero: antes tools/kdd-board/data/tasks.json; ahora .kdd-board/tasks.json dentro del proyecto seleccionado. Con el tablero detenido, copiar el archivo antiguo al destino si se desea conservar las tareas; no sobrescribir un destino existente sin reconciliar. La migracion no es automatica porque el estado anterior era compartido entre proyectos.
- Evidencia antigua sin hashes no habilita done. Re-enlazar el contrato y ejecutar los tests para obtener evidencia nueva; los reportes previos permanecen como historial.
- Reportes nuevos se guardan en .agents/logs del proyecto con ID de tarea en el nombre, evitando colisiones por titulo. Los logs locales siguen sin sustituir un artefacto durable de CI.
- Un findings.json aislado que antes pasaba ahora se rechaza: proporcionar el paquete de scan completo y previamente sellado.

## Optimizacion y riesgo

La ejecucion compartida elimina divergencias entre canales; las regresiones del tablero se ejecutan en un job independiente. Antes de agregar cache o seleccion incremental de gates, medir su costo y definir dependencias: saltarse un gate sin conocer sus entradas puede volver a producir falsos verdes. No se habilita cache de evidencia ni se reduce la suite completa en esta revision.
