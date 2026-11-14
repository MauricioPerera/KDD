---
type: 'Concept'
title: 'Margen estable del post-init en Windows'
description: 'Reducir el coste real manteniendo toda la suite inicializada y evidencias de tiempo completas.'
tags: ['ci', 'windows', 'performance', 'bootstrap']
---

# Objetivo

El comando completo de [init-project](contracts/init-project.md) debe completar
en menos de 480 segundos en tres workflows completos y consecutivos del mismo
head final. Se mantienen los 600 segundos operativos, Ubuntu/Windows y las dos
pasadas generales. Un fallo interrumpe la secuencia de aceptacion y se conserva
en la evidencia; repetir hasta obtener un PASS no acredita estabilidad.

## Evidencia de partida

El arbol de `827c1f3a72881468861f15935226940d6f8744f0` agoto 600 segundos en
Windows y paso en una repeticion con 597,395 segundos de unittest para init.
El job completo Windows tardo 48:52. Esa ejecucion acredita funcionalidad,
no un margen estable ni una reduccion del tiempo total.

En diagnosticos locales secuenciales con Python 3.11.15 y Git 2.54 nativo,
el comando instrumentado tardo 439,174 segundos con cuatro workers, 339,656
con seis y 297,281 con ocho. Los tres conservaron los mismos 1.969 IDs y
104 SKIP de la copia inicializada. El perfil directo es diagnostico, no una
muestra del comando estandar en GitHub ni una promesa de equivalencia entre
hosts. CI ya selecciona Git nativo; ese ajuste no es una optimizacion nueva.

Una comprobacion real de aliases del fixture `test_task_committed_artifacts`
resolvio la raiz 4.362 veces: `_key` acumulo 1,145 segundos en una ejecucion
instrumentada de 8,424 segundos. La propuesta de [identidad de raiz](contracts/task-root-identity.md)
reduce ese coste sin adelantar lecturas Git ni cachear refs o resultados nuevos.

## Cambios propuestos en la medicion de partida

El [ensayo de concurrencia](contracts/postinit-windows-concurrency.md)
define el perfil que se medira en el siguiente candidato.

- [Identidad fisica de la raiz](contracts/task-root-identity.md): clave de
  cache por directorio real, observada de nuevo en cada consulta, con fallback
  compatible cuando el sistema no ofrece una identidad util.
- [Perfil post-apply](contracts/init-post-apply-profile.md): ocho workers solo
  en el post-init Windows; cuatro en Ubuntu. Las dos suites ordinarias
  mantienen sus perfiles. El resultado debe medirse de forma completa.
- [Duracion del comando en CI](contracts/postinit-command-timing.md): publicar
  los datos existentes del runtime revisado, sin inferir el tiempo de init
  del paso que ejecuta todos los contratos ni de stdout del producto.

## Seguimiento del PR 186

- [Lectura agrupada de inventarios](contracts/task-oracle-inventory-batch.md).
- [Prioridad de los modulos rezagados](contracts/postinit-multi-oracle-priority.md).
## Verificacion y limites

Conservar los metodos y aserciones anteriores, sus IDs y los SKIP aplicables.
Las pruebas nuevas se contabilizan aparte; los inventarios de la plantilla y
de la copia inicializada se comparan cada uno contra su propia referencia.
Mantener el presupuesto seguro de 62 procesos y los controles de `git replace`,
modos, objetos corruptos, aliases y aislamiento entre repositorios.

La [politica de calidad](quality-approval.md) exige revisar los nuevos contratos
y oraculos antes de adoptar los cambios. Cualquier cambio de runtime requiere
otra revision especifica; no modificar protecciones ni fusionar el PR como
parte de esta optimizacion. Medir tambien el resto del job y el workflow para
no desplazar el coste y atribuirle una mejora inexistente.
