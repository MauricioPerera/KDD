# KDD explicado sin tecnicismos

## ¿Qué problema resuelve?

Cuando una persona le pide a un agente de inteligencia artificial que haga un
cambio, el resultado puede parecer correcto y aun así incumplir una regla
importante. KDD agrega una forma de comprobar el trabajo antes de aceptarlo.

Piensa en KDD como una carpeta de proyecto con cuatro piezas:

1. **La explicación:** qué significa el proyecto y qué decisiones debe respetar.
2. **El encargo:** qué cambio se pide y qué archivos puede tocar.
3. **El comprobante:** una prueba que dice qué significa “funciona”.
4. **La revisión automática:** programas que comprueban las reglas sin tener que
   confiar en la opinión del agente.

## ¿Cómo se usa?

Una tarea típica sigue este camino:

1. Se escribe el resultado esperado en un contrato.
2. Se prepara una prueba antes de programar.
3. Se sella la prueba con una huella digital para saber si alguien la cambió.
4. El agente implementa solo dentro del perímetro permitido.
5. KDD ejecuta las comprobaciones y conserva la evidencia.
6. Una persona decide si el resultado es adecuado para el producto.

La automatización comprueba que se respetaron las reglas. La persona sigue
decidiendo si esas reglas representan la necesidad real del negocio.

## ¿Qué significa el resultado?

- **PASS:** esa comprobación terminó correctamente.
- **FAIL:** hay algo que debe corregirse; no significa automáticamente que todo
  el proyecto esté mal.
- **SKIP:** esa comprobación es opcional o no aplica al proyecto.
- **TIMEOUT:** la comprobación no terminó a tiempo; no debe contarse como éxito.
- **DETECTED:** una prueba detectó un defecto introducido deliberadamente.
- **SURVIVED:** un defecto de prueba pasó sin ser detectado; el oráculo necesita
  fortalecerse.
- **INCONCLUSIVE:** la prueba no permitió decidir, por ejemplo por timeout.

KDD mantiene estas categorías separadas para no convertir un fallo esperado de
una prueba negativa en un fallo real del proyecto.

## ¿Qué no promete KDD?

KDD no garantiza que el producto sea útil, seguro o correcto en todos los casos.
Garantiza algo más concreto: que las reglas declaradas, las pruebas y los
resultados de los validadores pueden revisarse y repetirse.

Un resultado verde no reemplaza una conversación con usuarios, una revisión de
seguridad ni una decisión de producto.

## Por dónde empezar

Para un proyecto nuevo se puede empezar con el perfil mínimo:

```text
python scripts/run_profile.py --profile minimal
```

Después se puede pasar a `standard` y finalmente a `strict` cuando el proyecto
necesite más controles. La guía técnica de cada perfil está en
[`knowledge/adoption-profiles.md`](../knowledge/adoption-profiles.md).
