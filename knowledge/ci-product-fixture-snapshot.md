---
type: 'Concept'
title: 'Instantaneas aisladas del producto de prueba de aprobaciones'
description: 'Reducir la preparacion Git repetida del fixture conservando fuentes frescas, proyectos independientes y calidad real.'
tags: ['ci', 'fixtures', 'git', 'integration']
---

## Evidencia y alcance

El primer [CI de f5b02c9](https://github.com/MauricioPerera/KDD/actions/runs/40600526980)
conservo Ubuntu y ambos jobs de Board verdes, pero Windows fallo en la primera
suite: git add . del producto de test_approval_routing excedio 60 s. Los 1586 IDs
se ejecutaron; hubo un error y la segunda pasada no corrio. No es una muestra
verde ni evidencia de ahorro. Se conservan logs y las mediciones anteriores.

El helper fresh_product vuelve a copiar la misma fuente, inicializar y hacer
staging completo para cada uno de tres casos. El [contrato](contracts/ci-product-fixture-snapshot.md)
propone una instantanea por clase de fixture y fuente inmutable; conserva las
nueve pruebas de routing, sus aserciones y los limites de 60/90/600 s.

## Protocolo del fixture

Enumerar fuentes visibles con Git cuando existe .git; en la copia inicializada
sin Git recorrer fuentes excluyendo .git, dependencias regenerables, bytecode
y .agents/logs. Identificar la fuente por ruta, nombres ordenados y SHA256 de
sus bytes, incluyendo archivos nuevos. No reutilizar solo por HEAD, mtime o tamano.

Preparar un producto completo una vez por identidad y clase; un cambio de
bytes/nombres/ruta invalida esa preparacion. Comprobar otra vez la identidad
antes de publicarla. Una fuente con manifiesto completo ejecuta el bootstrap
real; una ya inicializada no lo repite; un manifiesto parcial falla antes.

Cada llamada retorna un clon real nuevo, con directorio Git y objetos propios:
sin hardlinks ni alternates compartidos. Configurar mantenimiento sin detach
antes del checkout y conservar las referencias y la calidad real del producto.
La [documentacion de Git](https://git-scm.com/docs/git-clone) define --no-hardlinks
y --config para ese aislamiento. La instantanea no se usa entre clases, procesos
ni pasadas de la suite; no es una cache global del bootstrap.

## Verificacion

Conservar literalmente los nueve metodos de pruebas anteriores. El oraculo nuevo
usa proyectos minimos de control con scripts y workflow reales, Git real y
verify_quality real; no simula filesystem, subprocesses ni resultados. Comprueba
una preparacion/tres clones, aislamiento ante mutacion, calidad dos veces,
invalidacion por bytes con mismo nombre/mtime/tamano, cambio durante la preparacion
sin publicar la cache y rechazo de fuente parcial.
Los tres casos existentes de plantilla conservan sus tres SKIP exactos solo en
una copia ya inicializada. Los controles nuevos siguen activos en esa copia y
sin test_init_project.py. No se agregan SKIP a la suite de KDD.

El benchmark local del producto completo registra tres preparaciones antes y
una despues; su tiempo no demuestra ahorro remoto. La reduccion total conserva
el [criterio aprobado](ci-windows-suite-concurrency.md): dos intentos verdes del
mismo head, Windows <1929 s cada uno y mediana <=1832.55 s. No mezclar muestras.

## Aprobacion

Seguir [quality-approval](quality-approval.md): el helper pertenece a un oraculo
congelado y necesita otro baseline revisado antes de adoptarlo y registrarlo.
Conservar las nueve entradas externas actuales al publicar el nuevo arbol.
Runtime 57cb3e7, workflows, matriz, seis workers Windows/cuatro Ubuntu, contratos
cuatro, ambas pasadas, cobertura y protecciones permanecen intactos. No autoriza
fusion ni excepciones al guard.
