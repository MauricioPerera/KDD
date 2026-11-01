---
type: 'Architecture'
title: 'Aprobaciones externas aisladas por arbol de Git'
description: 'Seleccionar referencias revisadas sin que la aprobacion de una propuesta desconfigure main u otra propuesta.'
tags: ['ci', 'quality', 'security']
---

# Problema y alcance

El [objetivo operativo OP-2](operational-closure.md) corrige la interferencia
de una sola KDD_APPROVED_BASELINE_REF global. Antes de integrar PR134, main
3acca373 pasaba contra 5efc4992 y fallaba contra el nuevo baseline 034c9f3,
aunque los dos habian sido revisados para estados diferentes. La aprobacion
del PR no debe retirar la aprobacion utilizable para ese main.

Se conserva la [revision humana](quality-approval.md) y la
[comparacion de contratos y oraculos](contracts/validate-baseline.md).
El identificador del arbol selecciona un registro externo; no aprueba por si
solo el codigo candidato ni reemplaza la comprobacion de archivos protegidos.

# Registro versionado como datos

KDD_APPROVAL_REGISTRY es una variable de Actions configurada fuera del PR:

```json
{
  "schema_version": 1,
  "trees": {
    "<SHA_COMPLETO_DEL_ARBOL_GIT>": {
      "baseline_ref": "<COMMIT_APROBADO_DE_CONTRATOS_Y_ORACULOS>",
      "quality_ref": "<COMMIT_APROBADO_DE_CALIDAD_CUANDO_APLIQUE>"
    }
  }
}
```

Las claves y referencias son SHA completos de 40 o 64 hexadecimales. Las
referencias seleccionadas deben existir como commits en el repositorio; quality_ref es
opcional si no se requiere calidad de producto. No son alias HEAD ni nombres
de ramas. Rechazar claves duplicadas, colisiones al normalizar mayusculas,
campos desconocidos, versiones no soportadas y entradas incompletas.

El limite local del JSON es 48000 bytes UTF-8, conservador respecto al
[limite de 48 KB de GitHub](https://docs.github.com/en/actions/reference/workflows-and-actions/variables).
El registro se amplía conservando entradas previas; no se sustituye todo el
mapa para aprobar otro PR. El selector no escribe variables ni el repositorio.
Una entrada no seleccionada se valida como datos, sin exigir que sus commits
ya esten disponibles en este checkout. Registrar antes de publicar un PR no
debe romper el CI de otro contexto por objetos que aun no fueron fetchados.

# Seleccion y confianza

El [selector](contracts/approval-registry.md) resuelve el commit candidato y
su arbol real mediante Git, sin ejecutar archivos candidatos. Un merge con
los mismos bytes y modos que su propuesta obtiene la misma entrada por arbol.
Si main avanza con un arbol diferente, su aprobacion requiere otra entrada;
no se buscan coincidencias aproximadas ni aprobaciones de ancestros.

Cada valor baseline_ref conserva el commit elegido por la persona revisora.
Registrar un nuevo arbol con ese valor no autoriza modificar los oraculos:
el [guard](contracts/trusted-pr-gate.md) vuelve a comparar sus bytes. Por si
sola, esa entrada tampoco autoriza cambios a workflows o validadores protegidos.

El modo nativo exige una entrada exacta para el arbol. Si falta, falla incluso
si sigue definida una variable global antigua. Un workflow reutilizable o
una invocacion administrativa puede proporcionar referencias explicitas
completas sin registro; no se permite mezclar ambos modos. La salida indica
commit, arbol, baseline, referencia de calidad y origen de la seleccion.

El workflow [de integracion](contracts/approval-routing.md) selecciona antes
de ejecutar contratos, producto o suites. Con registro, las referencias de
contratos y de calidad salen de la misma entrada. No hay fallback silencioso
a variables globales ni a HEAD. La ausencia de quality_ref falla cuando se
exige quality/product.json; el bootstrap mantiene esa exigencia.

# Revision independiente de infraestructura

El guard con [revision exacta](contracts/trusted-ci-change-review.md) acepta,
ademas del registro de baseline, JSON en la variable administrativa externa
`KDD_TRUSTED_CHANGE_REVIEW`. No toma esa aprobacion del checkout ni del PR:
la administracion de la variable es parte de la raiz de confianza. Sin ella
mantiene el rechazo anterior. Se revisan base, arbol candidato y conjunto
completo de rutas protegidas con modos y OIDs Git anteriores y posteriores:

```json
{"schema_version":1,"base_commit":"SHA_BASE","candidate_tree":"OID_ARBOL",
 "files":[{"path":".github/workflows/validate.yml",
           "before":{"mode":"100644","oid":"OID_ANTERIOR"},
           "after":{"mode":"100644","oid":"OID_NUEVO"}}]}
```

`before` o `after` es null en altas o bajas. La revision requiere OIDs completos
exactos, archivos regulares y ningun campo o ruta adicional. Un cambio de base,
arbol, modo, contenido o conjunto de rutas exige una nueva revision. No
sustituye la aprobacion de contratos y oraculos ni autentica criptograficamente
la identidad del revisor. La version antigua del guard bloquea la primera
instalacion de esta capacidad; requiere una excepcion puntual autorizada.

# Guard y migracion

pull_request_target sigue ejecutando codigo de main y leyendo la propuesta
como objetos Git. El selector y su nombre importable pertenecen a la raiz
protegida. Un archivo de aprobaciones incluido en el PR no es autoridad.

Durante la migracion, mantener el baseline global antiguo que usa main y
preparar el registro externo con las entradas del main actual y la propuesta.
El guard antiguo seguira bloqueando los cambios de workflow/validador. Solo
una excepcion especifica autorizada permite integrar ese cambio; restaurar
el control y verificar CI y Pages de main despues. Este protocolo no concede
esa excepcion ni registra referencias remotas automaticamente.

Despues de migrar, publicar una propuesta exige registrar su arbol real y
los SHA revisados antes de lanzar su CI. Si cambia el arbol al actualizar la
rama, se agrega otra entrada con el mismo baseline solo si los oraculos
siguen intactos y ese baseline permanece aprobado para el trabajo.

Identificar el candidato con git rev-parse HEAD y su clave con
git rev-parse 'HEAD^{tree}'. Estos comandos describen el contexto; no eligen
el baseline. Usar en baseline_ref y quality_ref los SHA entregados por la
persona revisora. Conservar el mapa existente al agregar entradas.
Antes de publicar, el CLI permite comprobar la seleccion sin escribir Git
ni variables remotas:

```text
python scripts/approval_registry.py --repo-root . --candidate-ref HEAD
```

El JSON se obtiene de KDD_APPROVAL_REGISTRY. Un caller reusable proporciona
approval_registry o los inputs explicitos completos; las variables globales
antiguas no sustituyen esos inputs. Los repositorios con workflows anteriores
conservan su comportamiento hasta migrar su copia o referencia del workflow.

# Criterios verificables

- Main y dos propuestas con oraculos distintos se validan independientemente.
- Un merge sin cambios de arbol conserva su seleccion; otro arbol no hereda
  una aprobacion por compartir padres o por escribir un JSON dentro del PR.
- Una referencia equivocada seleccionada desde el registro falla en la
  comparacion real de contratos/oraculos; el selector no fabrica aprobaciones.
- La calidad del proyecto nuevo se ejecuta con su referencia correspondiente,
  sin SKIP, y una referencia ausente o manipulada falla antes de los checks.
- Los inputs explicitos del workflow reutilizable siguen disponibles con
  SHA completo y quedan identificados como modo explicito en la evidencia.
