---
type: 'Concept'
title: 'Patrón de estructura para paneles de administración'
description: 'Convención de estructura (sidebar por entidad, rutas separadas para auth/recuperación/verificación, listados sin ID crudo) para paneles admin generados por agentes de IA, con la tendencia natural del LLM a apilar todo en una vista.'
tags: ['ux', 'patron', 'panel-admin', 'reference']
version: 'alpha'
---

# Patrón de estructura para paneles admin

## Problema que resuelve

Los agentes de codificación, al generar un panel de administración, tienden a concentrar
toda la información de una entidad (listado, filtros, detalle, acciones) en una única
página densa. Es funcional para el propio agente iterando, pero para un humano resulta
abrumador de escanear y entender. El mismo sesgo aparece en autenticación (login/registro
en una sola vista con tabs) y en flujos con espera externa (recuperación de contraseña,
verificación de email) que el agente suele colapsar en un solo formulario.

## Regla de estructura: panel principal

1. **Navegación lateral (sidebar) por entidad.** Cada entidad de negocio tiene su propio
   ítem en el sidebar. El sidebar no debe "estorbar": debe poder colapsarse y no competir
   visualmente con el contenido.

2. **Subdivisión por etapa del CRUD, no todo en una pantalla.** Dentro de cada entidad,
   las etapas se navegan como subitems o rutas separadas, no como secciones apiladas en
   la misma vista: Listado (Read, con filtros) / Crear / Editar (puede compartir vista
   con Crear si el formulario es idéntico) / Eliminar-Desactivar (acción en línea desde
   el listado, no una pantalla aparte).

3. **El listado es una tabla de filas clickeables, no una lista de texto con el ID
   crudo.** Cada fila muestra únicamente los campos mínimos que permiten identificar el
   registro a simple vista (nombre, estado, fecha — nunca el UUID/ID como dato visible).
   **Toda la fila** es un link a la vista de detalle/edición, no solo el nombre — un
   click en cualquier celda de la fila navega igual. El ID solo vive en la URL de
   destino, nunca como texto que el usuario tenga que leer o copiar. Acciones puntuales
   (desactivar, eliminar) van en una columna de acciones al final de la fila, sin que su
   click dispare la navegación a detalle.

4. **Cada vista responde a una sola pregunta.** El listado responde "¿qué hay?". El
   formulario de edición responde "¿cómo cambio este ítem?". Ninguna vista intenta
   responder ambas.

5. **Ubicación como memoria.** El usuario debe poder recordar "esto vive en
   Entidad → Subitem" sin depender de escanear la pantalla completa. Rutas predecibles
   (`/entidad/listado`, `/entidad/crear`, `/entidad/:id/editar`) en vez de vistas
   monolíticas con estado condicional.

**Trade-off aceptado:** más clics que una vista única, a cambio de menor carga cognitiva
por pantalla — prioridad correcta cuando el consumidor final es un humano, no otro agente.

Patrón de referencia visual: navegación tipo WordPress/Laravel Nova/Django admin —
sidebar fijo o colapsable a la izquierda, contenido principal a la derecha, breadcrumb o
título de sección arriba indicando entidad + subitem actual.

## Regla de estructura: autenticación

1. **Login y registro son rutas distintas, no una vista con estado** (`/login`,
   `/registro`), cada una con un único formulario, un único objetivo y un único botón de
   acción primario.
2. **Un solo link cruzado, no un toggle** ("¿No tenés cuenta? Registrate"). Nada de tabs
   ni segmented control que impliquen "la misma pantalla con dos modos".
3. **El formulario no compite con nada más** — sin sidebar, sin secciones adicionales
   que empujen el formulario fuera del viewport inicial.
4. **Estados de error inline**, no un resumen genérico arriba del formulario.
5. **Recuperación de contraseña es una tercera ruta** (`/recuperar-password`), no un
   campo condicional dentro del login.

**Trade-off aceptado:** navegación extra para quien se equivoca de formulario, a cambio
de que cada vista quede enfocada en una sola tarea.

## Regla de estructura: recuperación de contraseña

Cuatro pasos, cada uno su propia vista, nunca colapsados en una:

1. `/recuperar-password` — un único campo (email), un único botón. Nada de contraseña
   nueva acá.
2. Pantalla de confirmación de envío — "Si el email existe, enviamos un link" (no
   confirmar ni negar si el email existe, por seguridad; no reemplazar por un toast que
   desaparece).
3. `/reset-password?token=...` — contraseña nueva + confirmación, sin pedir el email de
   nuevo. Token inválido/expirado → vista específica con acción para volver a pedir el
   link, no un error genérico.
4. Pantalla de éxito — confirma el cambio, un único link a `/login`. Sin login automático
   silencioso: el usuario se re-autentica conscientemente.

**Trade-off aceptado:** más pantallas que un formulario todo-en-uno, pero cada una
comunica en qué punto del proceso está el usuario — crítico en un flujo con espera
externa (el email) donde la ansiedad de "¿funcionó?" es alta.

## Regla de estructura: verificación de email

1. **Vista dedicada post-registro** (`/verificar-email`), no el dashboard directo.
   Mensaje simple + acción "Reenviar email" con cooldown visible.
2. **El link del email resuelve en su propia ruta de confirmación**
   (`/verificar-email/confirmar?token=...`) con resultado claro: éxito o error con
   acción para reenviar. No confirmar en silencio y redirigir sin feedback.
3. **Mientras no está verificado, no bloquear con modal** — banner discreto si el
   producto permite navegar sin verificar; si exige verificación, la ruta protegida
   redirige a `/verificar-email` en vez de un modal encima de la app.
4. **Una sola acción por vista** — la vista de "reenviar" no mezcla campos de perfil ni
   otra tarea.

**Trade-off aceptado:** un paso extra en el onboarding, contra el patrón de banner-modal
ambiguo que dificulta saber si la cuenta ya está verificada.

## Tokens visuales (placeholder — reemplazar por proyecto)

Los valores de color/tipografía/spacing de este patrón son genéricos, no están basados en
una marca existente, y **deben** reemplazarse por la paleta real de cada proyecto antes de
usarse en producción — la estructura (secciones anteriores) es la parte prescriptiva; los
tokens son solo un punto de partida.

## Validado en la práctica

Aplicado a un proyecto real construido con KDD ([caso real de Capa 3](./casos-reales.md#dos-dominios-de-capa-3-que-nunca-se-hablan-convergen-en-el-mismo-riesgo-verificar)).
Dos lecciones de esa aplicación real, no anticipadas por este documento:

- **La regla "toda la fila es un link" se implementó a medias en el primer intento** —
  solo el nombre navegaba, el resto de la fila no. Se detectó con un click real en una
  celda no-nombre (`element.click()` + chequear el cambio de ruta), no leyendo el código.
- **Verificar que el layout de un sidebar colapsable "no deja hueco" exige medir
  geometría real** (`getBoundingClientRect`), no la propiedad CSS declarada
  (`getComputedStyle` de `margin`) — un elemento puede tener `transform` aplicado sin
  `position: fixed`, y seguir reservando su espacio en el layout aunque esté
  visualmente fuera de pantalla. La disciplina general de verificar con evidencia
  ejecutada en vez de leer el código está en la
  [Metodología de ejecución](./metodologia-ejecucion.md).
