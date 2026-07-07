---
type: 'Concept'
title: 'Upgrade de la plantilla: infra vs proyecto'
description: 'Guía para traer mejoras del template KDD a un proyecto instanciado: qué es infraestructura sobreescribible desde upstream y qué es propiedad del proyecto.'
tags: ['upgrade', 'versionado', 'template', 'infra', 'procedimiento']
---

# Upgrade de la plantilla: infraestructura vs. proyecto

## Infraestructura sobreescribible desde upstream

Estos artefactos forman parte del tooling y las convenciones del template. Al upgrade de una nueva versión de la plantilla, **se pueden y deben ser sobrescritos** para traer mejoras, correcciones de seguridad y nuevas características:

- **Validadores y herramientas:** `scripts/validate_contracts.py`, `scripts/validate_okf.py`, `scripts/validate_specs.py`, `scripts/export_gate_contract.py`, `scripts/assemble_context.py`, `scripts/init_project.py`, `scripts/lint_ascii.py`
- **Configuración de contexto:** `ccdd/context.json`
- **Reglas de agentes:** `.agents/AGENTS.md`
- **Documentación de metodología:** `knowledge/OKF-SPEC.md`, `knowledge/metodologia-ejecucion.md`, `knowledge/validacion.md`
- **Contratos de infraestructura:** `knowledge/contracts/` (excepto los propios del proyecto — ver abajo)
- **Tests de infraestructura:** Tests que validan la plantilla misma (p. ej. `tests/test_agents_rules.py`, tests que validan `validate_contracts.py`, `init_project.py`, etc.). Véase `tests/test_init_project.py` línea 14-20 (constante `INTACTABLES_KDD`) para la lista autorizada.
- **Configuración de CI:** `.github/workflows/validate.yml`

**Origen de la verdad:** La estructura y contenido se especifican en `specs/CONTRACT-0{1..13}-*.md` y sus reportes correspondientes en `docs/reports/`.

## Propiedad del proyecto

Estos artefactos **pertenecen al proyecto** instanciado y **no deben ser sobrescritos** salvo con plena consciencia:

- **Código de la aplicación:** `src/` (excepto ejemplos que `init_project --apply` borra al inicial)
- **Tests propios:** `tests/test_*.py` que tu proyecto agrega (salvo los nombrados en `INTACTABLES_KDD`)
- **Contratos propios:** Contratos CCDD redactados para tareas de tu proyecto (en `knowledge/contracts/`)
- **Base de conocimiento OKF:** `knowledge/*.md` que tu proyecto crea (modelos de datos, arquitectura, conceptos, decisiones — excepto los nodos que `init_project` borra)
- **Especificaciones propias:** `specs/` que tu proyecto añade (contratos de ejecución para tu contexto)

## Procedimiento manual de upgrade (4-5 pasos)

### 1. Bajar el release upstream

```bash
# Descarga la nueva versión de la plantilla
git clone --branch v1.1.0 https://github.com/tu-org/kdd-template.git kdd-upstream
```

O si tu plantilla está en un monorepo/rama:

```bash
git fetch origin v1.1.0
git show origin/v1.1.0:scripts/validate_contracts.py > /tmp/validate_contracts_new.py
```

### 2. Comparar la infraestructura

Revisa línea por línea qué cambió en cada archivo de infra. Herramientas útiles:

```bash
# Compara scripts
diff -u scripts/validate_contracts.py /tmp/validate_contracts_new.py

# O visual, en tu editor favorito
# Busca cambios en lógica, no en comentarios (los comentarios pueden cambiar sin impacto)
```

**Casos típicos:**
- Nuevas features en un validador: aceptar el cambio.
- Cambios en mensajes de error: aceptar.
- Cambios en `budget` o `complexity` en `ccdd/context.json`: **necesario upgrade** si tu proyecto usa el ensamblador.
- Nuevas reglas en `.agents/AGENTS.md`: revisar si aplican a tu contexto; si no, argumentar al PM.

### 3. Sobreescribir infraestructura

Reemplaza los archivos de infra con los de upstream. **No intentes mergear manualmente.**

```bash
# Ejemplo: reemplazar validadores
cp /tmp/validate_contracts_new.py scripts/validate_contracts.py
cp /tmp/validate_okf_new.py scripts/validate_okf.py
# ... etc para cada archivo de infra
```

### 4. Re-correr los gates

Después del upgrade, **re-valida todo localmente:**

```bash
# Valida contratos
python scripts/validate_contracts.py knowledge/contracts

# Valida OKF
python scripts/validate_okf.py knowledge

# Valida specs (si existen)
python scripts/validate_specs.py specs

# Corre la suite de tests
python -m unittest discover -s tests -p "test_*.py"
```

**Resultado esperado:** Todo exit 0, suite OK. Si algo falla:
- **Error en validación:** el upgrade rompió algo en tu proyecto o en la infra. Revisa el mensaje; posible candidato a un issue en el upstream.
- **Error en tests:** tu suite necesita actualización (p. ej. si la API de un validador cambió). Actualiza los tests propios.

### 5. Resella los hashes si cambian tests de infraestructura

Si cualquier `tests/test_*.py` que fue modificado por el upgrade tiene un `tests_sha256` en su contrato, recalcula:

```bash
# Helper: imprime el nuevo hash
python scripts/validate_contracts.py --hash tests/test_agents_rules.py

# Actualiza el frontmatter en knowledge/contracts/agents-context-rule.md
# Reemplaza la clave tests_sha256 con el valor nuevo
```

## Advertencia: upgrade no es merge ciego

El upgrade de infra NO es un merge automático ni ciego. **Después de sobreescribir, validá**:

1. Corre los gates (paso 4 arriba).
2. Si el validador de contratos falla: **PARAR**, investigá qué cambió.
3. Si los tests fallan: **PARAR**, evaluá si es una ruptura de API en la infra o un bug en tu código.
4. Nunca hagas push/merge hasta que gates estén en verde.

**Escalada:** Si un cambio de upstream es mayor (p. ej. nueva sintaxis de contratos, cambio de metodología), considera abrir un issue en el upstream antes de mergear.

---

**Referencia:**
- Instanciación inicial: `scripts/init_project.py` (manifest en línea 37-44)
- Tests intocables: `tests/test_init_project.py` (constante `INTACTABLES_KDD`, línea 14-20)
- Versión actual de la plantilla: `CHANGELOG.md`
