# Aprobar un proyecto con KDD

`policy.example.json` es un esquema ilustrativo: las rutas feature y sus pruebas no existen en esta plantilla. Adáptalo a archivos y comandos reales antes de congelarlo. No se ofrece un comando que apruebe placeholders.

1. Crear contrato y oráculos. Incluir sus helpers y configuración relevantes en protected.
2. Copiar/adaptar policy.example.json a quality.json en la raíz del proyecto. Especificar todos los gates relevantes en checks y las rutas exactas de implementación/PM. Si no hay interfaz, omitir ui con la justificación en el contrato.
3. Revisar y guardar política/oráculos en un commit ANTES de implementar. El revisor conserva ese SHA explícito.
4. Ejecutar `python scripts/verify_quality.py --policy quality.json --approved-ref <SHA-aprobado>` sobre el trabajo a aprobar. Opcional `--repo-root <ruta>`.

Requisitos del runner: Python estándar y Git. Los comandos del proyecto pueden necesitar Node u otras herramientas; si faltan, la aprobación falla. No se instalan dependencias automáticamente. Cada comando se ejecuta dos veces, sin shell; fallo, timeout, cambio de oráculo o salida del perímetro bloquean la aprobación.

Leer [protocolo, evidencia y límites](../../knowledge/quality-approval.md). El runner por sí solo no constituye aislamiento de código ni auditoría de seguridad.

## CI

El workflow validate.yml busca quality.json por defecto. Si existe, exige la variable de repositorio KDD_QUALITY_APPROVED_REF o el input quality_approved_ref del workflow reutilizable; sin referencia falla. Puede configurarse otra ruta mediante quality_policy_path. Si no hay política ni referencia, declara SKIP: la plantilla aún no aprueba la calidad de una aplicación.

El revisor debe mantener la referencia y el workflow/runner bajo revisión confiable; no obtener el SHA automáticamente del HEAD de la implementación. El checkout descarga el historial para poder resolver el commit. Los jobs existentes preparan Python y Node; otros runtimes de los checks necesitan preparación explícita en el proyecto.
