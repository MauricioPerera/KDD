# Verificación completa y prueba en navegador

Fecha local: 2026-09-05 (America/Mexico_City). Rama: `fix/kdd-verification-hardening`.

## Resultado

Las pruebas automatizadas pasan. El navegador detectó un defecto adicional: el catálogo de contratos solo se cargaba al visitar Documentación y el selector de nueva tarea nunca se alimentaba. Se corrigió cargando el catálogo al iniciar y compartiéndolo entre vistas, sin solicitarlo en cada polling.

La regresión `tools/kdd-board/tests/catalog-startup.test.ts` se escribió y selló antes del arreglo: inicialmente falló porque no se solicitaba `/api/docs`; después pasó. Contrato: `knowledge/contracts/catalog-startup.md`.

## Pruebas automatizadas

- Suite Python: 751 tests aprobados en cada una de dos pasadas, 50.898 s y 47.185 s de runner.
- Tablero: 11 tests aprobados después del arreglo, incluyendo autenticación/origen HTTP, evidencia desactualizada, MCP, vault, conteos y arranque del catálogo.
- TypeScript: `npm --prefix tools/kdd-board run typecheck`, exit 0.
- JavaScript: `node --check tools/kdd-board/public/app.js`, exit 0.
- Preflight global: exit 0, 18 PASS y 1 SKIP por ausencia del scan opcional de seguridad. Se ejecutó antes del ajuste del catálogo; después se comprobó el nuevo contrato con preflight acotado: 3/3.
- Estado final: 37 contratos válidos; 73 nodos OKF válidos; auditor de sellos: 37 examinados, cero hallazgos.
- Higiene: nueve casos de `git check-ignore` con resultado esperado. `.env` y `.env.production` excluidos; plantillas de entorno, `.sln`, código y contratos visibles; cachés seleccionadas excluidas.
- Changelog y `git diff --check`: correctos. Aviso de normalización LF/CRLF de `.gitignore`, sin fallo de validación.

## Navegador real

Instancia temporal en loopback, proyecto fixture y token exclusivamente de prueba. Sin secretos reales ni cambios en tareas del proyecto del usuario.

1. URL autenticada: tablero visible y fragmento eliminado de la dirección.
2. Reproducción del selector vacío antes de visitar Documentación.
3. Tras el arreglo y recarga, el contrato aparece en el primer formulario de creación.
4. Crear «Prueba con contrato» y ejecutar desde el botón: salida TAP real, un test aprobado y comando del contrato visible.
5. Cambiar a Done y generar reporte: UI muestra Done, VERIFIED y ruta del reporte con ID de tarea.
6. Intentar cerrar otra tarea sin contrato/evidencia: rechazo visible; tras recargar continúa en Backlog.
7. Pestaña cerrada e instancia temporal detenida al concluir.

## Alcance

Windows, Python 3.14.6 y Node 24.16.0. No se ejecutó GitHub Actions ni Linux. Estos resultados no certifican todas las combinaciones posibles ni sustituyen un escaneo real de seguridad. Persisten las limitaciones de `knowledge/verification-guarantees.md`.

Logs: `.agents/logs/verification-2026-09-06/` (fecha UTC), gitignorados. El borrado de cachés rechazado anteriormente no se volvió a intentar.
