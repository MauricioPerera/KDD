# Trazabilidad de requisitos

Estado inicial: contratos y oraculos primero; las interfaces nuevas fallan
explicitamente hasta implementar el baseline revisado. La receta siguiente
define el flujo que la entrega debe verificar.

1. Copiar templates/PRODUCT-SPEC.md a knowledge/product-spec.md, completar
   el resultado y cada requisito, y enlazar el nodo desde knowledge/index.md.
2. Definir contratos y oraculos antes de implementar. Crear el manifiesto
   quality/traceability.json con los IDs de requisitos, contratos y tareas
   previstas. Las tareas se pueden declarar antes de crearlas.
3. Obtener una revision humana del commit que incluye esos artefactos.
4. Crear las tareas, ready con ese SHA aprobado, start, implementar en sus
   ramas, integrar conservando commits y finish con el coordinador canonico.
5. Consultar la revision confirmada y exigir verificacion completa al cerrar.

```text
python scripts/traceability.py --repo-root . --ref main --manifest quality/traceability.json
python scripts/traceability.py --repo-root . --ref main --manifest quality/traceability.json --format markdown
python scripts/traceability.py --repo-root . --ref main --manifest quality/traceability.json --require-verified
```

El manifiesto de esta carpeta documenta los requisitos del MVP con tasks
vacio. Su resultado esperado es pending, nunca una cobertura ya verificada.
Para examinar ese plan en la revision que lo incorpora:

```text
python scripts/traceability.py --ref HEAD --manifest examples/traceability/traceability.json
```

HEAD es la revision observada; no se usa como aprobacion automatica. La
evidencia proviene de approved_ref y verified_ref de cada tarea. Un target
cambiado despues del cierre se muestra stale; una tarea nueva aprobada debe
respaldar el requisito actualizado. Cambios locales sin commit no forman parte
del reporte. El alcance no incluye dependencias transitivas automaticamente.

## Check obligatorio de calidad

Conservar los checks funcionales, adversariales y de interfaz propios. Anadir
el kind traceability a required_kinds y este check en quality/product.json:

```json
{
  "name": "requirements-traceability",
  "kind": "traceability",
  "argv": ["python", "scripts/traceability.py", "--repo-root", ".", "--ref", "HEAD", "--manifest", "quality/traceability.json", "--require-verified"],
  "timeout": 120
}
```

Proteger tambien estas rutas exactas, ademas de los contratos y oraculos
propios que la politica ya debe proteger:

```text
knowledge/product-spec.md
quality/traceability.json
scripts/traceability.py
scripts/traceability_model.py
scripts/traceability_git.py
scripts/validate_tasks.py
scripts/task_git.py
scripts/task_model.py
scripts/task_evidence.py
scripts/validate_contracts.py
scripts/process_tree.py
```

Mantener generated_task_evidence para las tareas que generen cierres, como
define la politica de calidad existente. La politica y sus dependencias se
aprueban antes de implementar. El CI de producto ya ejecuta verify_quality:
este check corre dos veces junto con los otros, sin agregar un workflow ni
un gate global. Un proyecto sin manifiesto no tiene este check configurado;
si lo configura y falta el archivo, la invocacion falla en vez de emitir SKIP.

La prueba de integracion de CLI debe recorrer este flujo con Git y oraculo
reales, comprobar las dos ejecuciones y rechazar una evidencia desfasada.
