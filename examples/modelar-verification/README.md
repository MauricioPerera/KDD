# Modelar: actuar y verificar el estado resultante

Ejemplo experimental de una prueba realizada en [Codex Modeling Studio](https://codex-modeling-studio.openai.chatgpt.site/). No es una integracion instalada, un gate obligatorio de KDD ni una prueba en vivo al ejecutar estos archivos.

## Prueba original

1. La escena inicial estaba vacia. Se crearon el cubo azul `m_1nfjt` y la esfera testigo `m_2pyka`.
2. Se consulto `get_studio_state` y se guardo [contract.json](contract.json), con el estado previo y el esperado, ANTES de la accion.
3. Se ejecuto `update_model` sobre el cubo: posicion `[0, 0.5, 0]` a `[1, 0.5, 0]`.
4. Una nueva llamada a `get_studio_state` produjo [observed.json](observed.json). No se utilizo el acuse de `update_model` como prueba de cumplimiento.
5. Una politica Lua ejecutada en el WASM experimental de Kite Lite comparo modelos completos, escena y camara con el resultado esperado. Resultado: los tres campos coinciden.

Se rechazaron tres controles negativos sobre copias de los datos: accion no realizada, posicion esperada incorrecta y cambio de color de la esfera. No fueron tres mutaciones adicionales en el sitio. Despues de la lectura se solicito un render para la galeria; sus pixeles no se inspeccionaron.

## Repetir la comprobacion de la evidencia

Requiere Node.js con ESM/`structuredClone` y los DOS artefactos del runtime experimental del POC: `kite_lite_wasm.js` y `kite_lite_wasm_bg.wasm`. El wrapper debe cargarse como ESM (por ejemplo, bajo un paquete con `"type": "module"`). **Los artefactos no se distribuyen en KDD: un clon de este repo por si solo no basta para ejecutar el replay.** No se instalan dependencias ni se descargan ejecutables automaticamente.

Desde la raiz de KDD, pasando las rutas reales de ambos archivos:

```sh
node examples/modelar-verification/verify.mjs /ruta/kite_lite_wasm.js /ruta/kite_lite_wasm_bg.wasm
```

El script exige los SHA256 de los artefactos exactos usados en la prueba antes de importarlos:

| Artefacto | SHA256 (bytes, sin normalizacion) |
| --- | --- |
| JS | `09073dfdbef457ccf237b6062d174c6ec896c8666eb21d0511522d552ce432ad` |
| WASM | `b68e6a5aff31b54a3d3378601f0ff261d79b797988b5e46d0840c64bbe6900a8` |

Salida comprobada:

```text
RECORDED READBACK REPLAY {"camera_match":true,"models_match":true,"passed":true,"scene_match":true}
PASS: 1 recorded readback replay + 3 negative fixture checks; Lua in real WASM. No persistence or pixel guarantee.
```

Una discrepancia, un archivo ausente, runtime distinto o argumento faltante termina con codigo no cero. Esta politica es fija, para estos datos conocidos; no es un validador general de esquemas ni un sandbox para Lua arbitrario.

## Repetir EN VIVO

Usar una escena de prueba autorizada y las herramientas del estudio. Obtener IDs reales, capturar el estado inicial, fijar el esperado antes de actuar, ejecutar el cambio y consultar el estado otra vez. Los IDs de este ejemplo no son reutilizables en otra sesion. Conservar las capturas originales: no reemplazar el esperado con el observado para conseguir un verde. No etiquetar el replay de estos fixtures como una nueva prueba en vivo.

## Frontera de confianza y relacion con KDD

La comparacion incluye el orden y todos los campos de los modelos, la escena y la camara. Excluye seleccion y metadatos. Usa igualdad exacta, sin tolerancia numerica. La captura de camara es anterior al render.

No prueba persistencia tras recargar, fidelidad visual, autenticidad criptografica de la captura ni veracidad del proveedor del estado. Los hashes identifican el runtime, no certifican su seguridad. Un agente con permiso para editar politica y evidencia puede falsificar el resultado si no hay una referencia externa confiable.

Para convertir el patron en aprobacion de cambios de un proyecto, seguir el [protocolo de aprobacion integrada](../../knowledge/quality-approval.md): captura fresca en el check, oraculos protegidos, referencia aprobada explicita y pruebas adversariales. Aqui solo se incorpora el caso y su replay; no se modifica el runner, el tablero, las reglas de aprobacion ni el conteo de gates.
