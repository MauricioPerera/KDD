---
type: 'Architecture'
title: 'Contencion de mutaciones, aprobaciones canonicas y coste de fixtures'
description: 'Contratos previos para dos P1 y dos P2 auditados en main 12c0f45, con medicion remota del CI.'
tags: ['quality', 'security', 'ci', 'integration']
---

# Alcance

Base: 12c0f452f4912d4f5a1c5bcc51ff63615c77cdea. Aplicar la
[aprobacion humana](quality-approval.md) antes de adoptar los nuevos oraculos.
Contratos: [target contenido](contracts/mutation-target-boundary.md),
[identidad del registro](contracts/approval-ref-identity.md),
[comillas portables](contracts/mutation-command-quoting.md) y
[preparacion de fixtures](contracts/fixture-preparation-cost.md).

# Escritura de mutantes

El target es un archivo relativo exacto del proyecto. Rechazar absolutos,
drives, UNC, traversal y componentes enlazados/reparse antes de controles o
copias; rechazar tambien el target con varios hardlinks. No convertir una ruta insegura en SKIP. Comprobar tambien el destino
de escritura dentro de la copia. Mantener REJECT estructurado y CLI no cero
ante rechazo. La validacion de contratos rechaza target/tests no relativos
y escapados con findings legibles, antes de leer su contenido o sellos.
El original, su indice, referencias y canarios externos permanecen intactos.
Conservar controles original/copy, operadores, contencion y omisiones legitimas.
No se afirma sandbox frente a callbacks o escritores concurrentes.

# Identidad de aprobaciones

La forma hexadecimal no autentica un OID. Cada baseline_ref/quality_ref,
normalizado como permite el esquema, debe coincidir con el OID del commit
resuelto. Rechazar ramas hexadecimales, tags, arboles, objetos ausentes y
abreviaciones. Probar SHA-1/SHA-256, ambos campos y modos externo/explicito.
Conservar HEAD/FETCH_HEAD como contexto candidato, sin autoaprobacion.
No modificar el registro para validar entradas no seleccionadas; mantener
limites, duplicados, ausencia de efectos y errores APPROVAL_* existentes.

# Comillas

Tokenizar el test_command de forma coherente con el runner de contratos,
sin shell=True. Conservar paths Unicode/espacios, argumentos y fallos reales.
Un comando valido entrecomillado debe ejecutar el mismo oracle sellado y
mutantes que su equivalente sin comillas en Windows y Ubuntu.

# Metricas de CI

Antes: tres observaciones verdes con el mismo arbol fb04cdbf y 1517 IDs.
PR137 run 40463930600 intentos 1/2: Windows 1929/1818 s, Ubuntu 428/388 s.
Merge run 40519237116: Windows 1972 s, Ubuntu 428 s. Medianas: Windows
1929 s (32:09), Ubuntu 428 s (7:08). Se conserva cada muestra y su evento;
no se mezcla con revisiones anteriores de 1483 IDs. El merge observa 912 s
de contratos y 488/499 s en las dos suites Windows.

El perfil senala preparacion con PowerShell por junction en dos fixtures.
Proponer un helper de pruebas que cree junctions reales mediante API nativa
en Windows y symlinks reales en Ubuntu. No reemplazar el filesystem por mocks.
Tambien preparar en una escritura la configuracion local constante de los dos
constructores Git comunes, conservando identidad, autocrlf, firma y mantenimiento.
Git real valida y utiliza esos archivos; no hay repositorios o commits simulados.
Los cuatro oraculos anteriores conservan sus metodos y todas las aserciones.
El helper es parte del oraculo revisado, no un cambio del runner confiable.

Medir antes/despues el mismo lote de enlaces: tiempo, tipo de objeto,
canarios y procesos iniciados. El presupuesto es cero procesos auxiliares
para crear los enlaces y configurar los repos; medir los comandos Git init/add/
commit/rev-parse y el proceso que ejecuta el probe por separado.
El objetivo remoto es mediana Windows <=1832,55 s (5% por debajo de 1929),
con dos intentos completos verdes del mismo head posterior, cada uno <1929 s.
Reportar tambien Ubuntu, cola y suma de jobs, crecimiento del inventario y
variacion de runners. Este umbral observado no prueba causalidad exclusiva.
Si no se alcanza, mantener OP-3 abierto y continuar el perfilado sin relajar
oraculos, limites o cobertura. No cerrar el P2 por un microbenchmark.

Se conservan los 1517 IDs anteriores, 112 contratos previos, 19 gates,
Ubuntu/Windows y dos comandos de suite identicos y consecutivos. Los nuevos
IDs se incorporan al inventario; mantener SDK 8 sin SKIP y Board 53. Los
skips historicos se identifican por aplicabilidad y no se convierten en PASS.

# Orden y referencias

Contratos, integraciones reales, fase roja en ambos SO, inventario y commit
de baseline para revision humana. Los cambios de helpers de oraculos se
presentan completos con sus hashes y fase roja/controles, antes de adoptarlos.
Despues se implementan las tres correcciones de produccion y se ejecutan las
dos suites completas. El cambio de validate_contracts pertenece al bundle:
presentar por separado SHA y seis hashes finales antes de registrar runtime.

Publicar para medir requiere autorizacion. Conservar las siete entradas
externas anteriores al registrar el arbol final con su baseline revisado.
El selector es protegido por trusted-pr-gate: no hacer excepciones ni fusionar
sin autorizacion especifica posterior. No cambiar workflows, locks ni protecciones
en este alcance. Conservar evidencia de todos los intentos, incluidos fallos.
