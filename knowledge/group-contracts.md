---
type: 'Concept'
title: 'Contratos de grupo KDD'
description: 'Composicion opt-in de contratos atomicos y pruebas de integracion bajo una referencia revisada.'
tags: ['ccdd', 'groups', 'integration']
---

# Contratos de grupo

Un grupo compone contratos de tarea y otros grupos. La verificacion sigue
siendo explicita: `python scripts/group_contracts.py <grupo> --repo-root <repo>
--approved-ref <commit> --timeout <segundos>`. Un grupo no implica por si solo
que el Nivel 2 de CCDD, una politica de producto o el CI hayan sido ejecutados.

## Formato

Cada grupo es un nodo OKF `type: 'Group Contract'` y declara `kind: group`. Dentro
de `knowledge/` vive en `knowledge/groups/`, separado de los contratos atomicos
de `knowledge/contracts/`. Conserva
los metadatos OKF habituales y agrega estas claves en frontmatter, usando listas
inline del dialecto de [contratos](validacion.md):

```yaml
kind: group
children: ['knowledge/contracts/a.md', 'knowledge/groups/sub.md']
integration_tests: ['tests/test_group_integration.py']
integration_argv: ['python', 'tests/test_group_integration.py']
protected: ['tests/group_helper.py']
```

Las rutas son relativas a la raiz del repo. `children` e `integration_tests`
son listas no vacias. `protected` es lista explicita, posiblemente vacia, de
helpers y configuracion adicionales necesarios para confiar en la prueba.
Cada prueba de integracion debe aparecer como argumento exacto en argv; esto
no demuestra por si mismo que el comando la ejecute ni la calidad del oraculo.
La persona revisora protege todas las dependencias necesarias, o usa tambien
la [aprobacion de calidad](quality-approval.md). No hay shell ni sandbox.

## Semantica

- La referencia es un SHA completo de commit del formato nativo del repositorio,
  explicito, existente y revisado. HEAD, ramas y referencias abreviadas no se
  aceptan. La herramienta no afirma quien aprobo el commit.
- Antes de ejecutar, se recorre y valida el grafo entero: grupos, hijos atomicos,
  sellos de estos y rutas protegidas deben existir como archivos normales dentro
  del repo y coincidir con los blobs del commit y el indice. El indice coincide
  en bytes; archivos UTF-8 del directorio de trabajo se comparan normalizando
  CRLF/CR a LF como el sello KDD, y los no UTF-8 se comparan por bytes. Se rechazan
  ciclos, listas duplicadas, rutas escapadas o enlaces simbolicos en cualquier
  componente, archivos ausentes y referencias ambiguas. No se siguen enlaces.
- Cada contrato atomico ejecuta su `test_command` real desde la raiz mediante
  el ejecutor KDD existente; los grupos ejecutan `integration_argv` sin shell.
  Una referencia compartida se valida y ejecuta una sola vez; el orden es
  profundidad primero y orden de declaracion. Un fallo impide ejecutar padres.
- Timeout positivo y finito por comando. Excepciones, fallo, timeout y salida
  invalida producen veredicto distinto de PASS. `python` se resuelve al mismo
  interprete del ejecutor; el resto de argumentos no se reinterpretan.
- Se comprueba nuevamente el conjunto protegido al terminar cada comando y al
  finalizar. Un cambio invalida PASS, incluido el indice; no se promete detectar
  una alteracion revertida entre controles ni dependencias que no se enumeren.
- La salida JSON declara `approved_ref`, `ok`, `verdict`, `stage` y `executed`,
  lista ordenada de rutas de hijos y grupos cuyos comandos se lanzaron realmente.
  `ok` solo es true para `verdict: PASS` y exit 0. Fallos de pruebas producen
  `verdict: FAIL`, `stage: atomic` o `stage: integration` y exit 1. Un timeout
  produce `verdict: TIMEOUT` y exit 2. Formato, integridad y referencia
  invalidos producen `verdict: INVALID` y exit 2; alteraciones detectadas
  despues de un comando usan `stage: inputs-changed`.

El CLI ejecuta codigo del proyecto con permisos del operador. Contrato, runners,
interprete, PATH y referencia deben pertenecer a la frontera confiable del
despliegue; el SHA no es una firma de identidad. El Nivel 2 nativo sigue siendo
opt-in y no se afirma al ejecutar este comando de composicion.

El formato deliberadamente usa rutas relativas a la raiz y argv explicito: los
grupos CCDD antiguos con rutas relativas al contrato o `integration_test_command`
requieren una conversion revisada; no se importan silenciosamente.
