#!/usr/bin/env python3
"""rule_hints.py - Receta de arreglo accionable por cada rule-id de los gates KDD.

Por que existe: los validadores dicen QUE fallo ("clave requerida ausente: type"),
no QUE HACER. Un humano lo deduce leyendo el nodo OKF correspondiente; un agente
efimero, que llega en frio y no tiene ese contexto, itera a ciegas. Este modulo es
el mapa rule-id -> receta, el analogo de `tools/rule-hints.js` del proyecto hermano
game-protocol, donde cada hallazgo del linter viaja con su arreglo.

Contrato de un hint:
  - dice QUE HACER, no repite el error (el mensaje del finding ya lo da);
  - nombra el archivo, la clave o el comando concreto cuando aplica;
  - cabe en 1-3 lineas; si hace falta mas, enlaza al nodo OKF canonico.

Uso como dato:      from rule_hints import hint_for; hint_for('FM_TESTS_FROZEN')
Uso como CLI:       python scripts/rule_hints.py FM_TESTS_FROZEN
                    python scripts/rule_hints.py --all
                    python scripts/rule_hints.py --json
Exit codes: 0=OK, 2=input (codigo desconocido o flag no reconocido).

Determinista: stdlib pura, sin red, sin LLM (misma regla que el resto de gates).
"""
import json
import sys

# Fallback: ninguna regla se queda sin orientacion, aunque sea generica. Mismo
# criterio que el FALLBACK_HINT de game-protocol: es preferible apuntar al nodo
# canonico que devolver vacio.
FALLBACK_HINT = (
    "Sin receta especifica para este codigo. Lee el nodo canonico de validacion "
    "(knowledge/validacion.md) y el docstring del validador que lo emitio; si el "
    "codigo es nuevo, agregale su hint en scripts/rule_hints.py (el gate de "
    "cobertura lo exige)."
)

HINTS = {

    # -- validate_contracts.py: el gate obligatorio del task contract ------------
    # Lo emiten validate_contracts, validate_perimeter y validate_skills: el hint sirve
    # para los tres (mismo sintoma, mismo arreglo).
    'FM_PARSE':
        "El front-matter YAML no se pudo leer. Revisa que el archivo abra y cierre con "
        "'---' en lineas propias y que la indentacion sea de espacios (nunca tabs).",
    'FM_TESTS_FROZEN':
        "Falta o no coincide 'tests_sha256', el sello del oraculo congelado. Calculalo con "
        "'python scripts/validate_contracts.py --hash <ruta/al/archivo/de/tests>' y pegalo en "
        "el front-matter. Si cambio a proposito, re-sella: el diff del hash hace visible el "
        "cambio del oraculo en review.",
    'FM_TOUCH_ONLY':
        "'touch_only' debe ser una lista no vacia de rutas (strings no vacios). Es el "
        "perimetro de la tarea: fuera de esas rutas el implementador no puede escribir.",
    'FM_TOUCH_TARGET':
        "El 'target' no esta cubierto por ningun patron de 'touch_only': el implementador no "
        "podria escribir el archivo que debe implementar. Agrega el target (o un patron que "
        "lo cubra) a touch_only.",
    'FM_TOUCH_TESTS':
        "El archivo de tests SI esta cubierto por 'touch_only', asi que el implementador "
        "podria editar su propio oraculo. Quitalo de touch_only: quien implementa nunca "
        "define el exito (Capa 0 de la metodologia).",
    'FM_BUDGET_KEY':
        "Una subclave de 'budget' no es de las que el gate de Nivel 2 LEE, asi que ese tope "
        "no se aplicaria: el gate cae a su config firmada y el budget queda decorativo. Usa "
        "exactamente 'cyclomatic_max', 'nesting_max', 'lines_max' o 'params_max' (el mensaje "
        "del error nombra el reemplazo si era un alias historico).",
    'FM_BUDGET_VALUE':
        "Una subclave de 'budget' no tiene un entero positivo. Un tope solo es comparable si "
        "es un numero: escribi 'cyclomatic_max: 8', sin comillas ni texto.",

    # -- validate_okf.py: estructura de los nodos de conocimiento ---------------
    'FM_KEY':
        "Falta una clave obligatoria del front-matter OKF, o esta vacia. Un nodo necesita "
        "'type', 'title', 'description' y 'tags'. El formato normativo esta en "
        "knowledge/OKF-SPEC.md.",
    'TYPE':
        "El 'type' del nodo no es uno de los reconocidos: Task Contract, Data Model, "
        "Architecture o Concept. Elegi el que corresponda; el tipo es lo que dice como leer el "
        "nodo, no una etiqueta libre.",
    'TAGS':
        "'tags' debe ser una lista NO vacia de strings en minuscula. Un tag vacio, en "
        "mayusculas o fuera de lista rompe la indexacion por tema.",
    'INDEX':
        "Falta (o no se pudo leer) knowledge/index.md, que es la raiz de alcanzabilidad de la "
        "base de conocimiento. Sin index no hay forma de saber que nodos son alcanzables: "
        "crealo y enlaza desde ahi los nodos de primer nivel.",
    'LINK':
        "Hay un enlace roto o que apunta a algo que no es un nodo. Un enlace debe resolver a un "
        "archivo .md existente (o a una carpeta): corrige la ruta, que es relativa al archivo "
        "que la contiene, o crea el nodo destino.",
    'ORPHAN':
        "El nodo existe pero no es alcanzable desde index.md: nadie lo enlaza, asi que en la "
        "practica no forma parte de la base. Enlazalo desde el nodo que corresponda, o borralo "
        "si quedo muerto.",

    # -- validate_specs.py: contratos de ejecucion a nivel proyecto -------------
    'SEC_CRITERIOS':
        "Al spec le falta la seccion obligatoria '## Criterios de aceptacion'. Sin criterios "
        "verificables no hay forma de cerrar el contrato: agregalos como lista de condiciones "
        "comprobables, no como intenciones.",
    'SEC_RESTRICCIONES':
        "Al spec le falta la seccion obligatoria '## Restricciones'. Declara ahi el perimetro "
        "y lo que queda explicitamente fuera de alcance.",
    'TOCAR_SOLO':
        "El contrato esta abierto pero sus Restricciones no declaran 'Tocar SOLO'. Enumera los "
        "archivos o directorios que la tarea puede modificar, para que el perimetro sea "
        "auditable al cerrar.",
    'ABORTAR':
        "Falta el bullet 'ABORTAR SI' en Restricciones, o quedo con un placeholder <...> sin "
        "rellenar. Declara la condicion concreta que obliga a parar y reportar en vez de "
        "seguir: sin ella, un agente empuja hasta romper algo.",

    # -- validate_perimeter.py: lo que realmente se toco vs lo declarado --------
    'TOUCH_ONLY_MISSING':
        "El contrato no declara un 'touch_only' usable (ausente, vacio o con items no-string). "
        "Sin perimetro declarado no se puede auditar que cambio de verdad.",
    'OUT_OF_PERIMETER':
        "Se modifico un archivo fuera del perimetro 'touch_only' del contrato. O revierte ese "
        "cambio, o amplia touch_only DE FORMA EXPLICITA en el contrato (y explicalo en el "
        "reporte): ensanchar el perimetro en silencio invalida la auditoria.",
    'TESTS_TOUCHED':
        "Cambio el archivo de tests, que es el oraculo congelado. Revierte el cambio; si el "
        "oraculo estaba mal, corrigelo como decision explicita, re-sella 'tests_sha256' y "
        "dejalo escrito en el reporte.",

    # -- validate_rules.py: rule contracts (reglas de negocio como datos) -------
    'JSON':
        "El rule-set no es JSON parseable, o no es un objeto en la raiz. Un rule-set se carga "
        "con json.load y nunca se ejecuta: si no parsea, no hay reglas que aplicar. Revisa "
        "comas sobrantes y comillas.",
    'GOLDEN_FORMA':
        "El golden set debe ser un objeto (dict) con los casos ya decididos. Revisa "
        "knowledge/rule-contract-spec.md para la forma exacta.",
    'GOLDEN_FROZEN':
        "El sello del golden no coincide (o el archivo no se puede leer). Re-sella con "
        "'python scripts/validate_contracts.py --hash <ruta/al/golden>' y actualiza "
        "'golden.sha256'. Si el cambio de reglas es legitimo, el diff del sello es "
        "justamente lo que debe verse en review.",
    'CODE_ONLY':
        "Toda regla marcada 'code_only' necesita su razon escrita. Esa razon ES la frontera "
        "dato/logica del dominio: di por que no se puede expresar declarativamente y donde se "
        "valida en su lugar (que task contract la cubre).",
    'FAMILIA':
        "El rule-set trae una clave que no es una familia conocida: casi siempre es un typo. Se "
        "rechaza a proposito, porque una clave mal escrita degradaria en silencio a regla "
        "ignorada. Las familias validas estan en knowledge/rule-contract-spec.md.",
    'REPRO':
        "El motor no reproduce el golden: para ese caso, las violaciones que calcula no son las "
        "que el golden declara. O el rule-set ya no dice lo que decia, o el golden quedo "
        "desactualizado. Compara el 'expected' con el 'actual' del mensaje y corrige el que "
        "este mal; despues re-sella el golden.",

    # -- validate_skills.py: activos de skills de agente ------------------------
    'DIR_MISSING':
        "El directorio de skills no existe. Es una capa opcional: si el proyecto no publica "
        "skills, ignoralo (el gate sale INFO); si deberia existir, crealo con una skill por "
        "subdirectorio.",
    'SKILL_MISSING':
        "El directorio de la skill no tiene 'SKILL.md'. Cada skill es un directorio con ese "
        "archivo dentro; el nombre del directorio es el nombre de la skill.",
    'FM_NAME':
        "Falta 'name' en el front-matter de la skill (o no es un string no vacio).",
    'FM_NAME_KEBAB':
        "'name' debe ser kebab-case: minusculas, numeros y guiones (mi-skill), sin espacios, "
        "mayusculas ni guiones bajos.",
    'FM_NAME_DIR':
        "El 'name' del front-matter no coincide con el nombre del directorio. Renombra uno de "
        "los dos para que sean identicos: la resolucion de skills asume esa equivalencia.",
    'FM_DESC':
        "Falta 'description' en el front-matter de la skill (o no es un string no vacio). Es "
        "el texto por el que un agente decide si la skill aplica a su tarea.",
    'FM_DESC_LEN':
        "'description' debe medir entre 50 y 1024 caracteres. Muy corta no permite decidir si "
        "la skill aplica; muy larga gasta contexto en cada arranque.",
    'BODY_EMPTY':
        "La SKILL.md tiene front-matter pero el cuerpo esta vacio. El cuerpo son las "
        "instrucciones que el agente va a seguir: sin el, la skill no hace nada.",
    'LINK_BROKEN':
        "Hay un enlace a un archivo que no existe. Corrige la ruta (es relativa al archivo que "
        "la contiene) o crea el destino.",
    'NAME_DUP':
        "Dos skills declaran el mismo 'name'. Los nombres son la clave de resolucion: "
        "renombra una, porque cual de las dos gana no esta definido.",

    # -- validate_changelog.py: coherencia CHANGELOG <-> reportes ---------------
    'CHANGELOG_MISSING':
        "No existe CHANGELOG.md. Es informativo si el proyecto aun no lleva changelog; si "
        "deberia existir, crealo con una entrada por contrato cerrado.",
    'REPORTS_MISSING':
        "No existe el directorio de reportes. Informativo si el proyecto todavia no cerro "
        "ningun contrato de ejecucion.",
    'ENTRY_MISSING':
        "Hay un reporte de contrato sin su entrada en el CHANGELOG. Agrega la entrada: el "
        "changelog es el indice legible de lo que se cerro, y el reporte su evidencia.",
    'REPORT_MISSING':
        "Hay una entrada en el CHANGELOG sin su reporte. O escribe el reporte que la respalda, "
        "o quita la entrada: una entrada sin evidencia es una afirmacion sin verificar.",
    'ENTRY_DUP':
        "El mismo contrato aparece dos veces en el CHANGELOG. Deja una sola entrada.",
    'LINK_MISSING':
        "La entrada del CHANGELOG no enlaza a su reporte. Agrega el link relativo para que se "
        "pueda ir de la afirmacion a su evidencia en un clic.",

    # -- validate_attestation.py: envelope de atestacion de un reporte ----------
    'ENVELOPE_MISSING':
        "El reporte no tiene envelope de atestacion (o no se pudo leer). Es el bloque que ata "
        "el reporte al contrato y a su ejecucion; los reportes anteriores al gate no lo llevan "
        "y por eso salen como WARNING, no como error.",
    'MISSING_KEY':
        "Al envelope de atestacion le falta una clave obligatoria (o esta vacia). Completala: "
        "sin ella el reporte no es verificable.",
    'TASK_MISMATCH':
        "El 'task' del envelope no coincide con el nombre del archivo del reporte. Renombra el "
        "archivo o corrige el campo: la correspondencia es la que permite localizar el "
        "contrato.",
    # Lo emiten validate_attestation (falta el task contract del reporte) y
    # validate_diagrams (falta el .diagram-contract.json del .mmd).
    'CONTRACT_MISSING':
        "Falta el contrato al que el artefacto dice responder. En un reporte: el envelope "
        "apunta a un task contract que no existe en knowledge/contracts/ (corrige 'task' o "
        "recupera el contrato; un reporte sin contrato no atestigua nada). En un diagrama: "
        "falta el .diagram-contract.json junto al .mmd.",
    'CONTRACT_HASH_MISMATCH':
        "El 'contract_sha256' no coincide con el contrato real: el contrato cambio despues de "
        "ejecutarse la tarea. Re-ejecuta contra el contrato vigente, o re-sella si el cambio "
        "fue posterior e irrelevante y lo justificas en el reporte.",
    'OUTPUT_HASH_MISMATCH':
        "El 'output_sha256' no coincide con el cuerpo del reporte: el reporte se edito despues "
        "de sellarlo. Re-sella el envelope tras terminar de escribirlo.",
    'EXIT_CODE_INVALID':
        "'exit_code' debe ser un entero literal (0, 1, ...), no un string ni una expresion.",
    'EXIT_CODE_NONZERO':
        "El envelope declara un exit_code distinto de 0: la ejecucion que se atestigua fallo. "
        "Arregla la causa y vuelve a ejecutar; no se cierra un contrato con evidencia en rojo.",

    # -- scan_secrets.py: credenciales en el codigo -----------------------------
    'AWS_KEY':
        "Hay un Access Key ID de AWS (AKIA...) en el codigo. Quitalo del archivo Y "
        "ROTALO: una vez commiteado hay que considerarlo comprometido, aunque borres la linea. "
        "Usa variables de entorno o un gestor de secretos.",
    'GITHUB_TOKEN':
        "Hay un token de GitHub (ghp_/gho_/ghu_/ghs_/ghr_) en el codigo. Revocalo en GitHub y "
        "reemplazalo por una variable de entorno; borrarlo del archivo no lo invalida.",
    'SLACK_TOKEN':
        "Hay un token de Slack (xox...) en el codigo. Revocalo en el workspace y muevelo a una "
        "variable de entorno.",
    'GOOGLE_API_KEY':
        "Hay una API key de Google (AIza...) en el codigo. Revocala en la consola de GCP y "
        "usala desde el entorno, con restricciones de uso.",
    'STRIPE_KEY':
        "Hay una clave LIVE de Stripe (sk_live_/pk_live_) en el codigo. Rotala en el dashboard "
        "de inmediato: una sk_live permite mover dinero real.",
    'PRIVATE_KEY_BLOCK':
        "Hay un bloque de clave privada (-----BEGIN ... PRIVATE KEY-----) en el repo. Sacalo, "
        "genera un par nuevo y trata el anterior como comprometido.",

    # -- audit_seals.py: oraculos que no pueden fallar (advisory) ---------------
    'WEAK_TESTS_MISSING':
        "El contrato declara un archivo de tests que no existe. El sello esta protegiendo un "
        "oraculo inexistente: escribi los tests antes de delegar.",
    'WEAK_TESTS_EMPTY':
        "El archivo de tests esta vacio. Un oraculo vacio pasa siempre: no verifica nada.",
    'WEAK_TESTS_UNPARSEABLE':
        "El archivo de tests no se pudo parsear, asi que no se puede auditar su fuerza. "
        "Arregla la sintaxis.",
    'WEAK_NO_TEST_FUNCTIONS':
        "El archivo de tests no define ninguna funcion de test. Sin casos, el sello congela un "
        "oraculo que no ejerce nada.",
    'WEAK_NO_ASSERTS':
        "Los tests no tienen asserts: se ejecutan pero no comprueban nada, asi que no pueden "
        "fallar. Agrega aserciones sobre el resultado esperado.",
    'WEAK_TARGET_UNREFERENCED':
        "Los tests no referencian al target del contrato: probablemente no lo estan ejercitando. "
        "Importalo y llamalo, o corrige el 'target'.",

    'SECRETS_NO_FILES_SCANNED':
        "El escaner de secretos no miro NI UN archivo en ese directorio: tiene archivos, pero "
        "ninguno con una extension de DEFAULT_EXTENSIONS. No es que no haya secretos, es que "
        "no se busco. Pasa la extension de tu lenguaje al script, o apunta el gate al "
        "directorio correcto.",

    # -- audit_forbids.py: forbids declarado vs realmente impedido --------------
    'FORBID_UNVERIFIED':
        "Esa capacidad de 'forbids' no tiene verificador mecanico para el lenguaje del target, "
        "asi que sigue siendo declarativa. No es un error: es el auditor diciendote que parte "
        "de tu 'forbids' es garantia y que parte es intencion.",
    'FORBID_UNSAFE_PRESENT':
        "El contrato declara 'forbids: unsafe' pero el target USA unsafe y el crate no lo "
        "deniega. Saca el unsafe, o si el proyecto lo necesita, quita la prohibicion del "
        "contrato: declarar algo que no se cumple es peor que no declararlo.",
    'FORBID_UNSAFE_UNENFORCED':
        "Declaras 'forbids: unsafe' pero nada lo impide a nivel compilador: hoy el target no lo "
        "usa, y manana si. Agrega 'unsafe_code = \"deny\"' bajo [lints.rust] del Cargo.toml, o "
        "'#![forbid(unsafe_code)]' en la raiz del crate: eso cubre el crate entero, no un archivo.",

    # -- validate_commit_message.py: convencion de mensajes ---------------------
    'CONFIG_MISSING':
        "No se encontro la configuracion de la convencion de commits. Crea el JSON de "
        "convencion (ver examples/git/commit-convention.json) o pasa su ruta al validador.",
    'CONFIG_INVALID':
        "La configuracion de la convencion de commits no es JSON valido o le faltan claves. "
        "Revisala contra el ejemplo del repo.",
    'MESSAGE_FILE_MISSING':
        "No se encontro el archivo con el mensaje de commit a validar. En un hook suele ser "
        "'.git/COMMIT_EDITMSG'.",
    'HEADER_MALFORMED':
        "El header no sigue la gramatica 'tipo(scope)?!?: descripcion'. Ejemplo valido: "
        "'fix(parser): corrige el sello'. Sin dos puntos o sin tipo, no matchea.",
    'TYPE_UNKNOWN':
        "El tipo del commit no esta en la lista permitida por la convencion. Usa uno de los "
        "declarados en el JSON de configuracion (feat, fix, docs, ...).",
    'SCOPE_REQUIRED':
        "La convencion exige scope y el header no lo trae. Escribe 'tipo(scope): ...' con el "
        "area que tocas.",
    'SUBJECT_TOO_LONG':
        "El header excede el maximo de caracteres configurado. Acortalo y mueve el detalle al "
        "cuerpo del mensaje, despues de una linea en blanco.",
    'SUBJECT_TRAILING_PERIOD':
        "Quita el punto final de la descripcion del header (es una convencion de estilo, no "
        "una frase).",
    'BLANK_LINE_MISSING':
        "Falta una linea en blanco entre el header y el cuerpo del mensaje. Sin ella, las "
        "herramientas de git leen todo como un unico titulo.",

    # -- validate_ux_page.py: UX/accesibilidad mecanica (capa opcional) ---------
    'HTML_UNCLOSED':
        "Hay una etiqueta de cierre sin su apertura. Revisa el anidamiento del HTML alrededor "
        "de la etiqueta que reporta el mensaje.",
    'ID_UNRESOLVED':
        "Se referencia un id que no existe en la pagina (href='#x', for='x', aria-*). Corrige "
        "la referencia o agrega el elemento con ese id: un ancla rota rompe la navegacion por "
        "teclado y por lector de pantalla.",
    'CONTRAST_LOW':
        "El contraste entre texto y fondo queda por debajo del minimo legible. Oscurece el "
        "texto o aclara el fondo hasta 4.5:1 (3:1 para texto grande), que es el umbral WCAG AA.",
    'CONTRAST_DATA_INVALID':
        "El bloque '#ux-contrast-pairs' no es JSON valido. Es la lista de pares "
        "texto/fondo que el gate debe medir; sin JSON valido no puede comprobar ninguno.",
    'MOTION_UNGUARDED':
        "Hay animacion CSS sin la guarda '@media (prefers-reduced-motion: reduce)'. Envuelve la "
        "animacion para respetar a quien pidio menos movimiento por accesibilidad "
        "(mareo, migrana, epilepsia vestibular).",
    'I18N_MISSING':
        "Falta una clave de traduccion en uno de los idiomas. Agregala al bloque i18n: si no, "
        "ese idioma muestra la clave cruda o queda en blanco.",
    'I18N_DATA_MISSING':
        "La pagina usa atributos 'data-i18n' pero no existe el bloque "
        "'<script id=\"i18n-data\">' con las traducciones. Agregalo.",
    'I18N_DATA_INVALID':
        "El bloque '#i18n-data' no es JSON valido, asi que ninguna traduccion se aplica. "
        "Revisa comas y comillas.",

    # -- validate_diagrams.py: contratos de diagrama Mermaid (capa opcional) ----
    # PATH_MISSING y FILE_ERROR los emiten tanto validate_diagrams como validate_ux_page:
    # el hint cubre ambas capas (las dos son opcionales).
    'PATH_MISSING':
        "La ruta declarada no existe (el .mmd de un contrato de diagrama, o el directorio de "
        "paginas UX). Corrige la ruta o agrega el archivo. Ambas capas son opcionales: si el "
        "proyecto no usa esa capa, el gate sale INFO y podes ignorarlo.",
    'FILE_ERROR':
        "No se pudo leer el archivo (diagrama o pagina UX). Revisa permisos y codificacion "
        "(se espera UTF-8).",
    'CONTRACT_INVALID':
        "El contrato del diagrama no es JSON valido o no cumple su forma. Revisa "
        "knowledge/diagram-contract-spec.md.",
    'DIAGRAM_TYPE_MISMATCH':
        "El 'diagram_type' del contrato no coincide con el del archivo .mmd. Uno de los dos "
        "esta desactualizado.",
    'DIAGRAM_TYPE_UNSUPPORTED':
        "Este gate pure-Python cubre flowchart/gantt/pie/journey. Para los otros 16 tipos usa "
        "el proyecto hermano mermaid-gate, que corre el parser real de mermaid.",
    'MIN_NODES':
        "El flowchart tiene menos nodos que el minimo del contrato. O el diagrama quedo "
        "incompleto, o el minimo ya no refleja el alcance: ajusta el que este mal.",
    'MAX_NODES':
        "El flowchart supera el maximo de nodos del contrato. Divide el diagrama o sube el "
        "limite de forma explicita: el tope existe para que siga siendo legible.",
    'MISSING_NODE':
        "Falta un nodo que el contrato declara obligatorio. Agregalo al .mmd con ese id exacto.",
    'MISSING_EDGE':
        "Falta una conexion que el contrato exige entre dos nodos. Agrega la flecha "
        "'origen --> destino' (con su label si el contrato lo pide).",
    'NODE_LABEL_MISMATCH':
        "El nodo existe pero su etiqueta no es la que el contrato declara. Iguala el texto: la "
        "etiqueta es parte del contrato, no decoracion.",
    'MIN_TASKS':
        "El gantt tiene menos tareas que el minimo declarado.",
    'MAX_TASKS':
        "El gantt supera el maximo de tareas declarado. Divide el diagrama o ajusta el limite.",
    'MISSING_TASK':
        "Falta una tarea que el contrato declara obligatoria en el gantt.",
    'MISSING_SECTION':
        "Falta una seccion obligatoria del gantt. Agregala con 'section <nombre>'.",
    'TASK_SECTION_MISMATCH':
        "La tarea esta en una seccion distinta a la que declara el contrato. Muevela.",
    'TASK_START_MISMATCH':
        "La fecha de inicio de la tarea no coincide con la del contrato. Iguala la fecha o "
        "actualiza el contrato si la planificacion cambio de verdad.",
    'TASK_END_MISMATCH':
        "La fecha de fin (o la duracion) de la tarea no coincide con la del contrato.",
    'MIN_SLICES':
        "El grafico de torta tiene menos porciones que el minimo declarado.",
    'MAX_SLICES':
        "El grafico de torta supera el maximo de porciones. Agrupa las menores en 'otros' o "
        "sube el limite.",
    'MISSING_SLICE':
        "Falta una porcion que el contrato declara obligatoria, con esa etiqueta exacta.",
    'SLICE_VALUE_MISMATCH':
        "El valor de la porcion no coincide con el del contrato. Actualiza el dato o el "
        "contrato, pero que digan lo mismo.",
    'MISSING_ACTOR':
        "Falta un actor que el contrato exige en el journey.",
    'TASK_MISSING_PERSON':
        "La tarea del journey no incluye a una persona que el contrato exige. Agregala tras el "
        "score, separada por comas.",
    'TASK_SCORE_MISMATCH':
        "El score de la tarea del journey no coincide con el declarado en el contrato.",
}


def hint_for(rule_id):
    """Devuelve la receta de un rule-id (o el fallback generico si no la tiene)."""
    return HINTS.get(rule_id, FALLBACK_HINT)


def enrich(findings):
    """Agrega 'hint' a cada finding {file, level, rule, msg} sin mutar la entrada."""
    out = []
    for f in findings:
        item = dict(f)
        item['hint'] = hint_for(item.get('rule', ''))
        out.append(item)
    return out


def _usage():
    print("Usage: python scripts/rule_hints.py <RULE_ID> | --all | --json")
    print("Options:")
    print("  --all      Imprime todos los rule-ids con su receta")
    print("  --json     Vuelca el mapa completo como JSON")
    print("  --help     Show this help message")
    print("Exit codes: 0=OK, 2=input (codigo desconocido o flag no reconocido)")


def main(argv):
    args = list(argv)
    if not args or '--help' in args or '-h' in args:
        _usage()
        return 0 if args else 2
    if '--json' in args:
        print(json.dumps(HINTS, indent=2, ensure_ascii=True, sort_keys=True))
        return 0
    if '--all' in args:
        for code in sorted(HINTS):
            print("[{}]\n    {}\n".format(code, HINTS[code]))
        print("{} rule-ids con receta.".format(len(HINTS)))
        return 0
    unknown_flags = [a for a in args if a.startswith('-')]
    if unknown_flags:
        print("Error: flag desconocido: {}".format(', '.join(unknown_flags)), file=sys.stderr)
        _usage()
        return 2
    code = args[0]
    if code not in HINTS:
        print("Error: rule-id desconocido: {}".format(code), file=sys.stderr)
        print(FALLBACK_HINT, file=sys.stderr)
        return 2
    print(HINTS[code])
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
