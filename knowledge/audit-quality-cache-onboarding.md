---
type: 'Architecture'
title: 'Correcciones de calidad, cache Git y configuracion de arranque'
description: 'Cerrar el P1 y dos P2 de main b041a67 con contratos previos y reproducciones reales.'
tags: ['quality', 'git', 'bootstrap', 'integration']
---

# Alcance y evidencia inicial

Base: main b041a67429e124951cc6098a5548f18dbf4208b6. El
[CI de ese merge](https://github.com/MauricioPerera/KDD/actions/runs/40416165179)
paso Ubuntu/Windows y dos pasadas con 1444 IDs por sistema. Los defectos
se reprodujeron con Git y procesos reales sin modificar ese main.

La [aprobacion humana](quality-approval.md) se conserva. Este protocolo no
registra variables, autoriza publicaciones ni modifica protecciones. Los
[limites verificables](verification-guarantees.md) siguen vigentes.

# P1: ciclo de vida de los checks de producto

El [contrato de contencion](contracts/quality-process-lifecycle.md) extiende
[verify-quality](contracts/verify-quality.md). Un check que termina, falla o
agota su timeout debe devolver solo despues de contener y esperar los
descendientes propios observados, antes de comprobar integridad otra vez.
Mantener argv sin shell, cwd, entorno, salida, timeout por check y dos rondas.
No confundir contencion con sandbox o aislamiento frente a codigo hostil.

El runner reutiliza process_tree.py desde el MISMO commit aprobado que la
politica. Leer el blob regular scripts/process_tree.py de ese commit y cargarlo
desde un temporal externo al checkout. No importarlo del candidato, resolver
otro baseline, consultar HEAD como fallback ni depender de un helper vecino
al runner aislado. La API del backend y sus seis archivos aprobados no cambian.
Mantener su gracia compartida de cinco segundos y los limites POSIX/Windows.

Un helper aprobado ausente, con modo Git 120000, directorio o objeto invalido
rechaza antes de ejecutar checks. Se admiten archivos regulares 100644/100755.
Un baseline historico sin ese helper necesita otra referencia revisada para
usar el runner nuevo; los runners historicos fijados conservan su semantica.

La carga se integra en el batch de objetos existente mas una comprobacion
de modo. Preservar el control previo de treinta procesos Git del oraculo de
batching. El temporal se mantiene durante los checks y se libera al terminar.
Un error de contencion/espera/lectura nunca acredita PASS.

Las integraciones nuevas cubren hijos y nietos con readiness real, salida
exitosa, no cero, timeout, vecinos independientes y escritura posterior a la
devolucion. Cubren el runner extraido solo, helpers alterados del checkout,
modos Git y referencias ausentes sin mocks de procesos ni respuestas de Git.
La referencia de cada fixture es sintetica; no aprueba un proyecto real.

Los fixtures antiguos test_verify_quality.py y test_quality_workflow.py
agregan el helper a su repositorio de pruebas y permiten que scripts/ ya exista.
No cambia ningun metodo ni asercion anterior. Esa adaptacion y el sello de
verify-quality requieren revision explicita del baseline propuesto.

# P2: referencias moviles en todos los lectores Git

El [contrato de lectores](contracts/git-reader-ref-cache.md) completa la
[politica de coste](task-history-read-cost.md). commit_sha, blobs, paths y
_committed_paths deben resolver de nuevo las referencias moviles durante una
operacion, incluso nombres hexadecimales de la longitud de otro formato Git.
La cache solo reutiliza valores asociados a OIDs completos del formato nativo.

Mantener aislamiento por raiz fisica/repositorio, descarte al terminar o
salir con excepcion, orden de resultados y rechazo de blobs/rutas invalidos.
No cachear fallos ni comprobaciones positivas de modo bajo un alias mutable.
Conservar la cache de ancestros ya corregida y la auditoria completa.
Git decide que nombres identifica como objetos; no inventar SHA a partir de
su forma. SHA-1 y SHA-256 se prueban con repositorios reales.

Conservar los presupuestos anteriores: doce nodos usan como maximo cinco
procesos Git y el piloto de historial no supera 380. No introducir cache de
evidencia ni persistencia entre operaciones. Las pruebas usan Trace2 real.

# P2: una configuracion de onboarding coherente

El [contrato de guia](contracts/approval-onboarding-consistency.md) alinea
las tres traducciones del README y los nodos canonicos validacion y
verification-guarantees con el [registro externo](approval-registry.md).
La configuracion nativa usa KDD_APPROVAL_REGISTRY con el arbol exacto y los
SHA revisados. Las dos variables antiguas son resultados de la seleccion,
no una alternativa global de configuracion. Los callers reutilizables
conservan inputs explicitos, sin mezclar ambos modos ni elegir HEAD aprobado.

Enlazar el protocolo en cada entrada de inicio y conservar las instrucciones
de politica propia, revision humana, calidad obligatoria y dos rondas. La guia
generada ya describe el registro y debe seguir coherente. Los documentos
fechados historicos conservan su revision; no se reescribe su evidencia.

Las pruebas crean producto, politica y Git propios, ejecutan el bootstrap
cuando la fuente es la plantilla y consumen los cuerpos Python reales del
workflow resultante. Una fuente ya inicializada no se inicializa otra vez;
los mismos controles de seleccion y calidad siguen ejecutandose, aunque la
fuente ya inicializada no conserve .git. El fixture enumera esa fuente fisica
y crea Git solo para su propio producto; una regresion ejecuta los seis casos
de integracion desde una copia sin repositorio de origen. No hay SKIP de
infraestructura. El registro correcto selecciona y ejecuta los checks reales
dos veces; solo variables antiguas, registro ausente, arbol desconocido
o calidad sin referencia fallan antes de esos checks.

# Secuencia y cierre

1. Congelar contratos, oraculos nuevos y adaptacion minima de fixtures.
2. Registrar fase roja en Windows/Ubuntu y comprobar controles independientes.
3. Presentar SHA y hashes para revision humana antes de implementar.
4. Implementar solo verify_quality.py y task_git.py y actualizar documentacion.
5. Pasar 19 gates, contratos/sellos, Board, SDK y dos suites completas por SO.
   Conservar los 1444 IDs y las aserciones anteriores; agregar los casos nuevos.
6. Una publicacion o cambio de referencia remota necesita su autorizacion
   correspondiente. Workflows, runtime de seis archivos y protecciones no
   cambian en esta correccion.

El cierre exige procesos terminados, lecturas frescas y configuracion utilizable;
un test que falla por entorno o readiness no cuenta como fase roja del defecto.
