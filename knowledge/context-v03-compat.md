---
type: 'Architecture'
title: 'Compatibilidad de contratos de contexto CCDD v0.3'
description: 'Adaptador explicito de contratos de contexto YAML, ensamblado y comparacion conservadora.'
tags: ['ccdd', 'context', 'compatibility']
---

# Compatibilidad CCDD v0.3

Este perfil independiente permite utilizar contratos `context.yaml` v0.3 de
Antigravity sin modificar el [ensamblador KDD](contracts/assemble-context.md).
No consulta ni copia automaticamente proyectos del usuario. El formato y los
checks de KDD existentes no cambian; la compatibilidad es opt-in.

## Interfaz y frontera

```text
python scripts/context_v03.py lint <contract-dir>
python scripts/context_v03.py assemble <contract-dir> --inputs <inputs.json>
python scripts/context_v03.py diff <baseline-dir> <candidate-dir>
```

Las tres operaciones devuelven un objeto JSON en stdout. `status: PASS` usa
exit 0; contrato, entrada o dependencia invalida usa `INVALID` y exit 2;
guardrail o regresion detectada usa `BLOCKED` y exit 3. Ningun error emite
payload ni incluye valores de entradas, secretos o contenido de slots en el
diagnostico. Las respuestas validas incluyen `governance_verified: false`:
este perfil no verifica identidad ni firmas de quorum. El ensamblado exitoso
devuelve `payload`, `payload_sha256`,
`tokens_used`, `tokens_available` y `guardrails` como lista de objetos con `id`
y `passed`; por ello su
stdout puede contener datos sensibles y debe tratarse como el contexto mismo.
Lint y diff son de solo lectura. No se escribe `last-assembly.json` ni se
ejecutan proveedores dinamicos: `inputs.json` aporta los valores por ID de
slot. El llamador controla el contrato, las entradas y ambos directorios del
diff; la comparacion no acredita que la referencia haya sido aprobada. Para
aprobar y proteger archivos usar [calidad](quality-approval.md).

## Formato aceptado

- Solo `ccdd_version: '0.3'`, UTF-8, YAML seguro sin claves duplicadas,
  aliases ni tags arbitrarios. Campos y tipos no soportados fallan cerrados;
  no se descartan opciones de seguridad silenciosamente.
- Slots unicos, prioridad entera, presupuestos validos, fuentes `static`,
  `dynamic` o `runtime` y modos `none`, `truncate` o `summarize`. Un proveedor
  dinamico es solo un identificador; no se importa ni invoca codigo.
- Las rutas estaticas y de esquemas son relativas al directorio del contrato,
  no pueden escapar ni atravesar enlaces simbolicos o puntos de reanalisis.
  Los estaticos con `sign: true` requieren `expected-hashes.json` coincidente;
  hashes SHA-256 comprueban contenido, no identidad ni firma humana.
- Prioridad para asignar presupuesto; orden declarado para presentar slots.
  Los pisos y slots `none` son obligatorios: si no caben, se bloquea. Los dos
  modos de compactacion recortan de manera determinista; no hacen resumen LLM.
  Se conserva la heuristica del runner original de 1 token por 4 caracteres.
- Guardrails soportados: `regex_deny`, `reference_check` de IDs de slots y
  `json_schema` Draft 2020-12 sobre el slot indicado. `abort` bloquea; `warn`
  informa sin afirmar que paso; `reroute` u opciones no implementadas fallan
  cerradas. Esquemas invalidos y referencias remotas o locales `$ref` y
  `$dynamicRef` se rechazan; no se hace red ni resolucion externa. `format` es
  anotacion, no una validacion afirmada por este perfil.
- `inputs.json` debe ser un objeto con cadenas para cada slot no estatico;
  claves faltantes, duplicadas, adicionales o tipos distintos se rechazan.
  El esquema valida el texto del slot despues de la compactacion; JSON invalido
  o truncado no puede resultar PASS. Regex se aplica al contexto ensamblado.

## Comparacion conservadora

`diff` valida ambos contratos e integridades, compara slots, presupuesto,
contenido estatico, guardrails y schemas. No permite remover slots o guardrails,
reducir la capacidad disponible, el quorum o el piso de un slot critico, degradar
su prioridad o permitir su compactacion, debilitar `on_fail`, ni cambiar de forma
no revisable tipo, patron, objetivo o esquema de un guardrail. Cambios de
proveedor, fuente u orden de slots existentes tambien bloquean. Un slot dinamico
nuevo o existente no puede ascender a la zona de slots criticos. Agregar un
slot critico estatico o cambiar el contenido estatico firmado bloquea como
`REVIEW_REQUIRED`: este perfil no verifica Ed25519, y una atestacion presente
no se trata como valida. Ninguna salida afirma que el quorum se haya cumplido.
El registro de revisores y sus atestaciones no se convierten ni validan; cambios
en ellos bloquean. Aumentar quorum o agregar un guardrail no debilita el perfil
por si mismo y puede pasar si no hay otra regresion.

El diff es conservador, no prueba equivalencia semantica ni reemplaza revision
humana. Directorios base confiables y permisos de escritura son responsabilidad
del operador. Las validaciones antes/despues detectan alteraciones persistentes,
no una alteracion revertida entre lecturas ni carreras de procesos externos.

## Dependencias y CI

PyYAML y jsonschema (con dependencias) se fijan con hashes en
`tools/context-v03/requirements.txt`, perfil binario Windows AMD64 y Linux
x86_64 con Python 3.10+. La instalacion es explicita; si faltan dependencias,
el CLI falla, nunca devuelve PASS ni descarga paquetes. El workflow de plantilla
instala el lock antes de los comandos de contratos y las dos pasadas en ambos
sistemas; la inicializacion de proyectos conserva ese paso. El resto de gates,
la matriz Ubuntu/Windows y el ensamblador stdlib actual permanecen intactos.
