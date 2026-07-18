---
type: 'Concept'
title: 'Guia humana: como supervisar y verificar lo que hizo un agente'
description: 'Checklist para el humano (no el agente-PM) que revisa un PR producido con KDD: que mirar, en que orden, y las senales de alarma concretas de un veredicto verde que no significa lo que deberia.'
tags: ['ccdd', 'okf', 'supervision', 'reference']
---

# Guia humana de supervision

`metodologia-ejecucion.md` y `validacion.md` estan escritos para el agente
que orquesta (el "PM"). Este nodo es para la persona humana que revisa un
PR o un merge producido bajo KDD sin haber leido todo el proceso interno —
que mirar, en que orden, y por que.

## El checklist de 5 minutos

1. **¿El CI esta verde?** `.github/workflows/validate.yml` corre TODOS los
   gates de Nivel 1 + `test_command` de cada contrato + la suite completa
   2 veces (anti-flaky), en `ubuntu-latest` y `windows-latest`. Si el
   check de GitHub esta verde, la base estructural ya esta verificada
   mecanicamente — no hace falta re-verificarla a mano.
2. **¿El contrato tiene `tests_sha256`?** Abri `knowledge/contracts/<task>.md`
   del PR. Si el campo `tests_sha256` cambio en el diff, es una señal
   normal (oraculo re-sellado) SOLO si tambien cambio el archivo de
   `tests` correspondiente en el mismo diff. Si `tests_sha256` cambio
   pero el archivo de tests NO esta en el diff — o viceversa — es una
   bandera roja: alguien reescribio el oraculo sin que el hash lo capture,
   o alguien cambio el hash sin cambiar el test (ambos casos, el gate
   `validate_contracts.py` deberia haberlo bloqueado; si el PR paso CI
   igual, revisa manualmente antes de mergear).
3. **¿El diff se queda dentro de `touch_only`?** El campo `touch_only` del
   contrato declara que archivos puede tocar la tarea. Compara contra los
   archivos del PR: `git diff --name-only <base>...<head>`. Si hay
   archivos fuera de esa lista, preguntate por que — puede ser legitimo
   (el PM agrega archivos fuera del perimetro del dev, eso es normal) pero
   si TODO el diff excede el perimetro declarado, el contrato esta mal
   descripto o la tarea se salio de scope.
4. **¿Hay evidencia de verificacion, no solo de intento?** Busca en el PR
   o en `docs/reports/CONTRACT-NN-REPORT.md` (si aplica) los comandos
   REALES corridos y su salida — no una descripcion en prosa de "lo probe
   y anda". `metodologia-ejecucion.md` llama a esto "verificar por
   artefacto"; como humano, aplica el mismo criterio: si no ves un
   comando + su output, no esta verificado.
5. **¿El `intent` del contrato describe lo que el codigo realmente hace?**
   Esta es la unica revision que NINGUN gate mecanico puede hacer por vos:
   que el contrato pedia lo correcto para el problema real. Los gates
   verifican que el codigo cumple EL CONTRATO, no que el contrato sea la
   decision correcta de producto/arquitectura. Esa lectura de intent
   sigue siendo trabajo humano.
6. **¿Dudas de la FUERZA del oraculo, no solo de su integridad?** El sello
   `tests_sha256` certifica que el oraculo no se reescribio, no que sepa
   hacer fallar al target. Corre `python scripts/audit_seals.py` para
   detectar oraculos que no pueden fallar (sin asserts reales, sin
   funciones de test, sin referenciar al target — 6 reglas `WEAK_*`); es
   advisory (sin `--strict` siempre exit 0). Juzgar la calidad semantica
   de un assert existente sigue siendo juicio humano (mutation testing),
   fuera del alcance del auditor.

## Que NO hace falta que revises a mano

Si el CI esta verde, esto YA esta verificado mecanicamente — no lo
reproduzcas a mano salvo sospecha concreta:
- Que el frontmatter del contrato este bien formado (`validate_contracts.py`).
- Que el `test_command` declarado realmente pase (`validate_test_commands.py`).
- Que no haya secretos con forma de credencial conocida en `src/`
  (`scan_secrets.py`).
- Que los nodos OKF esten enlazados y sin roturas (`validate_okf.py`).
- Que el `tests_sha256` coincida con el archivo de tests actual.

## Senales de alarma concretas

- Un PR grande que toca `knowledge/contracts/*.md` Y su `tests/` Y su
  `target` en el mismo commit, sin reporte ni evidencia — no hay forma de
  saber si el oraculo se escribio antes o despues del codigo (la garantia
  central de KDD, "quien define exito no es quien implementa", depende de
  ESE orden, y el orden no queda en el diff final).
- Un `intent` vago o que mezcla dos tareas ("hacer X y tambien mejorar Y")
  — la regla `tc-intent-atomic` deberia haberlo bloqueado en el gate, pero
  si paso, es señal de que el contrato no fue escrito con cuidado.
- Un `forbids` vacio o ausente en un contrato nuevo — `validate_contracts.py`
  lo marca WARNING, no ERROR (no bloquea el merge). Si ves esto en un PR,
  pregunta por que se omitio.

## Ver tambien

- [validacion.md](./validacion.md) — que verifica cada gate, en detalle.
- [metodologia-ejecucion.md](./metodologia-ejecucion.md) — el proceso
  completo desde la perspectiva del agente-PM que delega.
- [glosario.md](./glosario.md) — vocabulario usado en este checklist.
