# KDD Pages

La fuente de [GitHub Pages](https://mauricioperera.github.io/KDD/) vive en
`main:site/`. El workflow `deploy-pages` se dispara solo después de que
`validate-contracts` termine correctamente para un `push` a `main`. Descarga
ese SHA exacto, construye el artifact y lo despliega en el entorno
`github-pages`, cuya política de ramas permite `main`.

## Construcción local

```sh
npm ci --prefix site --ignore-scripts --no-audit --no-fund
python -m unittest tests/test_pages_build.py
python site/build.py --output /tmp/kdd-pages-preview \
  --ci-run-url https://github.com/MauricioPerera/KDD/actions/runs/36196006067
```

El destino debe ser nuevo. El script copia únicamente fuentes públicas
rastreadas por Git, genera el índice de conocimiento y las skills, ejecuta
`publish --check` y valida estrictamente el bundle bajo `/KDD/`. El número de
reportes, gates y tests de la portada sale del mismo checkout. La URL de CI
apunta al run que aprobó ese SHA; los reportes antiguos se identifican como
históricos, no como cierres verificados por el gate de evidencia nuevo.

El `demo_seed` en `llms-skills.json` reproduce una firma demostrativa. No es
una credencial de identidad para producción. Si se requiere atribución
criptográfica del editor, configurar una clave privada fuera del repositorio.

Después de migrar la configuración de Pages a GitHub Actions, `gh-pages`
permanece únicamente como historial de la publicación manual anterior.
