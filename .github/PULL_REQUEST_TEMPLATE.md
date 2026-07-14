<!-- Referencia completa: knowledge/validacion.md y knowledge/supervision-humana.md -->

## Que hace este PR

<1-3 lineas: que problema cierra, no como.>

## Contrato(s) relacionado(s)

<link a knowledge/contracts/<task>.md, o "N/A" si es un cambio que no
sigue el flujo de task contract (ej. un fix de doc).>

## Evidencia de verificacion

<Comando real corrido + resultado. No alcanza con "lo probe y anda" — ver
"Verificar por artefacto" en knowledge/supervision-humana.md.>

- [ ] `python scripts/validate_contracts.py knowledge/contracts` — 0 errores.
- [ ] `python -m unittest discover -s tests -p "test_*.py"` — verde.
- [ ] Si el PR toca un contrato: `tests_sha256` re-sellado (si el oraculo cambio) y el archivo de tests esta en este mismo diff.
- [ ] Si el PR fue producido por un agente: diff dentro de `touch_only` del contrato (o justificado si lo excede).

## Checklist antes de pedir review

- [ ] CI verde en ambos legs (`ubuntu-latest` + `windows-latest`).
- [ ] `CHANGELOG.md` actualizado si el cambio es notable (ver `validate_changelog.py`).
- [ ] Sin secretos: `python scripts/scan_secrets.py src` limpio.
