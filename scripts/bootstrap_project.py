#!/usr/bin/env python3
# ascii-lint: skip-file  # user-facing Spanish onboarding text
"""Initialize a KDD project and generate a human-friendly start guide."""

import argparse
from pathlib import Path
import sys

from init_project import init_project


_PROFILES = {"minimal", "standard", "strict"}


def _start_here(name, profile):
    project = name or "tu proyecto"
    return """# Primeros pasos con KDD

Este proyecto ({project}) fue inicializado con el perfil `{profile}`.

## Qué hacer ahora

1. Lee `knowledge/index.md` para conocer las reglas del proyecto.
2. Crea un test que describa el resultado esperado.
3. Crea un contrato en `knowledge/contracts/` y sella su test.
4. Ejecuta el perfil elegido:

```text
python scripts/run_profile.py --profile {profile}
```

Para una tarea concreta, valida también su budget:

```text
python scripts/validate_budgets.py knowledge/contracts --repo-root . --contract <task>
```

KDD comprueba las reglas declaradas; una persona sigue revisando si esas reglas
representan la necesidad real del producto. Consulta `docs/KDD-PARA-PERSONAS.md`
si quieres una explicación sin tecnicismos.
""".format(project=project, profile=profile)


def bootstrap_project(repo_dir, apply, name, profile="standard"):
    if profile not in _PROFILES:
        raise ValueError("perfil desconocido: {} (use minimal, standard o strict)".format(profile))
    result = init_project(repo_dir, apply, name)
    start_here = _start_here(name, profile)
    if apply:
        path = Path(repo_dir).resolve() / "KDD-START-HERE.md"
        path.write_text(start_here, encoding="utf-8")
    return {**result, "profile": profile, "start_here": start_here,
            "start_file": "KDD-START-HERE.md", "applied": bool(apply)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--name")
    parser.add_argument("--profile", choices=sorted(_PROFILES), default="standard")
    parser.add_argument("--repo-dir", default=".")
    args = parser.parse_args(argv)
    try:
        result = bootstrap_project(args.repo_dir, args.apply, args.name, args.profile)
    except (ValueError, OSError) as error:
        print("ERROR: {}".format(error))
        return 2
    print("Perfil: {}".format(result["profile"]))
    print("Archivo de inicio: {}{}".format(result["start_file"],
          " (creado)" if args.apply else " (se creara con --apply)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
