---
type: 'Data Model'
title: 'Autoridad aplicada por un ejecutor local'
description: 'Politica versionada, operaciones cerradas y delegacion restringida para un ejecutor confiable.'
tags: ['authority', 'executor', 'security', 'delegacion']
---

# Autoridad local v1

Este piloto complementa [las garantias de KDD](../verification-guarantees.md).
El coordinador confiable crea el ejecutor con raiz y politica aprobadas. El agente
solo entrega solicitudes de datos; no puede cambiar la politica mediante la solicitud.
No es un sandbox de Python ni del sistema operativo: quien tenga terminal, codigo
arbitrario o acceso directo al filesystem puede evitar esta interfaz. Para proteger
un agente real hay que retirarle esos canales y alojar el ejecutor fuera de su proceso.

## Politica

Objeto estricto con `version: 1`, `authority`, `touch_only`, `protected_paths`, `limits`.
`authority` requiere listas `read`, `write`, `execute`; execute solo admite sha256 y
validate_json. `limits` requiere enteros positivos `max_operations` y `max_bytes`.
No se aceptan claves desconocidas, capacidades sin implementacion ni flags decorativos.

Patrones read/write/touch_only/protected_paths: ruta exacta, prefijo/** o **.
Se usan rutas relativas POSIX normalizadas; no absolutas, segmentos vacios, . o ..,
backslash, dos puntos, NUL, glob parcial, nombres de dispositivo Windows ni segmentos
terminados en punto/espacio. En Windows el matching ignora mayusculas. No se soportan
todos los patrones fnmatch de contratos existentes: este piloto no los migra ni
reinterpreta. El propietario debe suministrar un subconjunto compatible aprobado.

Permiso de escritura requiere authority.write Y touch_only de cada ancestro.
protected_paths de cualquier ancestro siempre impide escribir, aunque otro permiso
coincida. Leer oraculos exige permiso de lectura. El coordinador debe incluir los
oraculos y otros artefactos inmutables en protected_paths antes de entregar el ambito.
La politica se copia a estructura inmutable; cambiar el dict original no la cambia.

## Operaciones

- `read_file`: op y path; devuelve texto UTF-8 dentro de max_bytes.
- `write_file`: op, path y text; crea exclusivamente un archivo nuevo. No crea padres
  ni reemplaza, borra o modifica archivos existentes. Apertura exclusiva evita pisarlos.
- `run_command`: op, path y command; sha256 y validate_json son implementaciones
  internas de solo lectura. Requieren permiso execute especifico Y read sobre el path.
  No se invoca shell, subprocess, scripts del proyecto, imports desde la raiz ni red.

No hay argumentos libres, scripts, variables de entorno ni rutas de ejecutables.
Validar JSON devuelve valid true/false, sin ejecutar contenido. SHA256 usa bytes crudos.
Archivos grandes se rechazan; resultados/errores no incluyen contenido en el audit.

Antes del IO, validar solicitud, permiso, protecciones, presupuesto y confinamiento.
Rutas con symlinks/junctions/reparse points se rechazan; archivos existentes con varios
hardlinks se rechazan. La raiz no puede cambiarse por una solicitud. Se exige filesystem
sin cambios externos concurrentes: las comprobaciones de ruta no eliminan todas las
carreras TOCTOU de un proceso hostil. No es aislamiento frente a otro proceso.
Se rechazan archivos especiales antes de abrirlos. Un fallo de IO durante una
escritura autorizada puede dejar un archivo parcial; no hay transacciones ni rollback.

Demostracion autocontenida: `python -m examples.authority.demo`. Usa un directorio
temporal, verifica hashes antes/despues de los rechazos y lo elimina al terminar.

## Delegacion y cuotas

`executor.delegate(child_policy)` entrega un nuevo handle. Cada permiso hijo debe ser
subconjunto del padre; si intenta ampliarlo, PermissionError y ningun handle concedido.
Los limites hijos no superan los del padre. Las protecciones del padre no se eliminan.
Las operaciones se comprueban contra toda la cadena y comparten contador raiz y lock;
tambien respetan cuota propia y ancestros. Crear nuevos hijos no reinicia la cuota raiz.
Pruebas usan handles delegados, no subagentes LLM reales ni identidades autenticadas.

max_operations cuenta solicitudes que pasan permisos estaticos y son admitidas a
procesamiento, incluso si despues fallan por IO o ruta insegura. Rechazos estaticos
no consumen cuota. max_bytes limita bytes leidos/escritos por operacion. Cuotas
persisten solo durante la vida del ejecutor en un proceso; reiniciarlo crea otra sesion.
Son limites de operaciones/bytes, no de tokens ni dinero.

## Resultado y escalamiento

Cada solicitud retorna ok, code, data si corresponde y escalation si requiere revisar
autoridad, operacion no soportada, presupuesto u overwrite. escalation es una peticion
de decision, nunca una ampliacion efectiva. No acepta approved=true desde el agente.
INVALID_REQUEST e IO_ERROR no conceden permisos ni exponen excepciones con contenido.

audit_log es una copia de eventos con secuencia, ambito, operacion, ruta, codigo y ok;
sin texto de archivos, payloads, stacktraces o secretos. Es evidencia en memoria, no
registro firmado ni durable. El host debe recogerlo fuera del control del agente.

CLI: `python -m src.authority_executor --root DIR --policy POLICY --requests REQUESTS`.
Policy y requests son archivos JSON suministrados por el host; requests contiene una
lista. Policy debe estar fuera de root. `--delegate CHILD_POLICY` repetible crea una
cadena antes de ejecutar solicitudes. JSON en stdout, exit 0 si todas ok, 1 si alguna
rechazada/fallida, 2 si configuracion/entrada ilegible o delegacion invalida. La lectura
inicial de archivos de control pertenece al host, no a permisos del agente.

No esta integrado en KDD-Board, el planificador ni el runner de tests. Un contrato
admitido no se ejecuta automaticamente. No ejecuta programas arbitrarios ni pretende
controlar sus efectos transitivos; eso requiere otro perfil y aislamiento efectivo.
