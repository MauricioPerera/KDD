# SPRINT-03 — Aplicar autoridad antes de efectos locales

Estado: closed (verificado localmente). Usuario autoriza con "adelante" la prueba propuesta de autoridad.
Una tarea activa: local-authority. Coordinador/implementador/revisor: asistente,
sin revision independiente ni agentes LLM adicionales.

Resultado: ejecutar una operacion autorizada y demostrar que peticiones prohibidas,
incluidas las de un handle delegado, no crean ni modifican archivos.
Perimetro: nuevo ejecutor/catalogo de politicas, oraculo, modelo, contrato, demo y enlaces.

## Presupuesto y parada

Tokens/coste unknown. Limite operativo: una implementacion y dos correcciones sin
evidencia nueva; reserva de verificacion: pruebas focales, efectos reales y regresion.
Parar si requiere shell arbitraria, instalar sandbox, cambiar politica del host,
acceder a produccion o publicar GitHub. No ampliar esos permisos silenciosamente.

## Criterios de aceptación

- [x] `python -m unittest tests.test_authority_executor` pasa casos permitidos,
  rechazos sin efectos, proteccion de oraculos y cuota compartida entre hijos.
- [x] `python -m examples.authority.demo` produce evidencia de permiso y rechazo.
- [x] `python scripts/preflight.py` sin fallos: 18 PASS, 1 SKIP (seguridad opcional ausente).
- [x] `python -m unittest discover -s tests`: 826 tests, OK.

## Cierre

20 pruebas focales, sin skips; demo verifica hashes sin cambios tras tres rechazos.
Auditoria de sellos: 41 contratos, 0 hallazgos. Evidencia local en
`.agents/logs/local-authority-REPORT.md`. Sin push, PR ni CI remoto en este sprint.
Perfil deliberadamente limitado a operaciones internas y creacion de
archivos; no sandbox para codigo arbitrario ni prueba con LLM subagente real.
