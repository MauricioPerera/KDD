# CONTRACT-23 — Contrato editorial — REPORT

Fecha: 2026-07-08
Spec: `specs/CONTRACT-23-editorial.md`

## Resumen ejecutivo

| Criterio | Veredicto | Evidencia |
|---|---|---|
| Oráculo del checker (19) | ✅ verde sin modificarlo (sello `60d534ee...`) | corrida PM |
| Adversarial (borrador realista del PM) | ✅ artículo conforme de ~1.500 palabras con links markdown → `[]`; borrador con em-dash + "Robusto" + tabla + URL cruda → 4 violaciones exactas nombrando `body` | fixtures del PM con tabla de estilo real |
| Gate de rule contracts | ✅ 4/4 dominios intactos | corrida PM |
| Validadores + lint | ✅ exit 0 (16 contratos, 30 nodos, 23 specs) | corrida PM |
| Suite `unittest` | ✅ verde 2× (**279 tests**) | corridas PM |
| Post-init neutral | ✅ los 4 artefactos al MANIFEST | `test_init_project` en suite |
| CI | ✅ ambas patas en success | run del push de cierre |

## Qué demuestra (contratos más allá de la "lógica")

Las reglas editoriales de un artículo — largo, estructura, léxico prohibido, formato —
que normalmente viven en prosa interpretada por humanos o LLMs, convertidas en gate
determinista pre-publicación. La tabla de estilo entra por argumento: el checker sirve
para cualquier editorial, no hardcodea una newsletter.

**El diseño honesto es el punto**:
- Las **definiciones exactas** quedaron congeladas en el oráculo (qué es palabra, párrafo,
  URL cruda, tabla) — sin eso, cada implementador decide distinto y el gate no es gate.
- Las **fronteras de juicio** (calidad del hook, tono, humor) quedaron FUERA por contrato:
  territorio de juez auditado o humano. "Párrafos en pantalla" se aproxima por palabras
  con la aproximación declarada.
- **Cuarta clase de frontera de la vertiente**: propiedades de texto (length/matches). Las
  familias declarativas operan sobre valores, no sobre strings — el dominio entero va como
  task contract (forma C16), y solo se agregarían familias de texto si otro dominio repite
  la clase (doctrina evidencia-primero).

## Verificación final del PM (independiente del dev)

- Oráculo 19/19; adversarial con estilo realista (arriba); gate 4/4; lint exit 0.
- Suite 2× consecutivas 279/279; perímetro limpio (solo `src/validate_article.py`);
  sin re-delegaciones.
- Reporte del dev (evidencia local, gitignorada): `.agents/logs/C23-REPORT.md`.

## Pendientes / ítems de seguimiento

Ninguno. Con C23 el catálogo de ejemplos cubre: finanzas, fronteras, workflows, ruteo y
editorial — cinco respuestas distintas a "¿qué se puede contratar?".
