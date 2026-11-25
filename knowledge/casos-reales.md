---
type: 'Concept'
title: 'Casos reales de la metodología'
description: 'Incidentes verificados en producción que motivaron reglas de la metodología de ejecución; evidencia separada del proceso normativo.'
tags: ['metodologia', 'casos', 'evidencia']
---

# Casos reales

Evidencia que motivó reglas de la [metodología de ejecución](./metodologia-ejecucion.md). El proceso normativo vive allá; aquí solo los incidentes, para que la narrativa no cargue el contexto de cada delegación. Cada caso lleva el ancla que la metodología enlaza.

Los relatos completos y su evidencia se conservan en el [archivo historico](../docs/reports/ARCHIVO-CASOS-REALES.md). Este índice conserva las anclas de los 101 casos. Busca el mismo encabezado en el archivo para leer su evidencia.

## entorno-afirmado (PLAN / RECON)

## crear-sobre-existente (PLAN / RECON)

## hecho-sin-intencion (SPEC / red-team de la definición de hecho)

## verificar-antes-de-limpiar (VERIFICAR)

## replace-silencioso-en-docs (CERRAR / documentación)

## colision-de-entregables (SPEC)

## tension-de-diseno-en-la-spec (SPEC)

## formato-persistente-sin-contrato-de-upgrade (SPEC / CIERRE)

## contrato-bilateral-mitad-arreglado (VERIFICAR)

## persiste-de-auditor-refutado (VERIFICAR)

## check-que-fallo-no-es-check (VERIFICAR)

## alcance-real-de-un-gate-no-es-el-prometido (VERIFICAR)

## auditoria-de-artefacto-sin-motor-vivo (CIERRE)

## ronda-de-confirmacion (CIERRE)

## infra-huerfana-es-evidencia (CIERRE)

## no-verificado-acumulado (VERIFICAR)

## credencial-efimera-a-delegados (DELEGAR)

## clase-cazada-a-clausula-de-spec (SPEC)

## contrato-documentado-cambia-junto (SPEC / VERIFICAR)

## investigacion-bloqueada-necesita-arnes (DELEGAR)

## limite-declarado-es-el-siguiente-objetivo-de-auditoria (VERIFICAR)

## propiedad-atipica-en-compilador-generico (SPEC)

## artefacto-real-encuentra-gaps-que-la-clasificacion-abstracta-no (PLAN)

## rescate-hibrido-por-cuota (DELEGAR / recuperación)

## demo-por-el-camino-documentado (VERIFICAR)

## nota-de-upgrade-no-ejecutada (SPEC / VERIFICAR)

## excepcion-unica-declarada (SPEC)

## contrato-exige-superficie-no-expuesta (SPEC)

## destino-no-idempotente-se-limpia-antes-de-cada-corrida (DELEGAR / VERIFICAR)

## fixture-persistente-se-aisla-de-la-suite-default (SPEC / VERIFICAR)

## powershell-no-soporta-redireccion-de-stdin (DELEGAR)

## claim-de-cobertura-se-verifica-leyendo-el-artefacto-entero-no-su-encabezado (VERIFICAR)

## fixture-existente-se-extiende-con-alias-de-entorno-no-se-bifurca (SPEC)

## middleware-de-permiso-no-se-reusa-entre-header-y-cookie (SPEC)

## escritura-atada-al-secreto-rompe-la-gestion-por-id (SPEC)

## colision-de-campo-con-struct-embebido-en-vista-compartida (VERIFICAR)

## go-run-en-windows-deja-binario-huerfano (VERIFICAR)

## infra-existente-se-inspecciona-antes-de-decidir-arquitectura-de-deploy (PLAN)

## cache-immutable-sin-version-sirve-stale-tras-redeploy (VERIFICAR)

## verificacion-de-ui-por-geometria-no-por-status-http (VERIFICAR)

## aplicar-esquema-todo-o-nada-rompe-el-primer-cambio-incremental-tras-deploy (VERIFICAR)

## metadata-de-esquema-cacheada-se-reescribe-completa-tras-un-apply-parcial (VERIFICAR)

## verificar-migracion-de-esquema-contra-copia-real-antes-de-tocar-produccion (VERIFICAR / CIERRE)

## modelo-de-referencia-externo-no-se-traduce-a-ciegas-cuando-el-proyecto-ya-eligio-otro (SPEC)

## agregar-permiso-nuevo-se-justifica-por-ausencia-semantica-no-por-conveniencia (SPEC)

## verificar-un-deploy-con-lecturas-no-prueba-que-el-sistema-funcione (VERIFICAR / CIERRE)

## capacidad-de-configuracion-sin-via-de-escritura-en-el-producto (SPEC)

## invariante-que-se-puede-olvidar-se-vuelve-imposible-o-ruidosa (SPEC)

## reproducir-lo-que-el-cliente-real-envia-no-lo-que-uno-cree-que-envia (VERIFICAR)

## capacidad-que-puede-revocarse-a-si-misma-necesita-guarda-sobre-el-estado-resultante (SPEC)

## una-bateria-de-casos-sobre-estado-compartido-se-contamina-a-si-misma (VERIFICAR)

## migracion-manual-debe-invalidar-la-cache-que-el-sistema-prefiere (VERIFICAR / CIERRE)

## orden-de-un-deploy-con-migracion-minimiza-la-ventana-de-caida (CIERRE)

## una-leccion-que-reincide-pide-un-artefacto-operativo-no-mas-documentacion (CIERRE)

## una-limitacion-de-una-dependencia-propia-se-arregla-en-la-dependencia (DEFINIR / PLAN)

## una-trampa-reincidente-se-convierte-en-criterio-de-aceptacion (SPEC / VERIFICAR)

## una-capa-de-compatibilidad-documenta-la-divergencia-no-la-fuerza (SPEC)

## publicar-una-version-no-es-tagearla-sino-verificarla-como-consumidor (CIERRE)

## una-capacidad-destructiva-se-verifica-en-produccion-con-una-operacion-que-es-su-propio-inverso (VERIFICAR / CIERRE)

## una-verificacion-que-necesita-identidad-se-emite-una-efimera-no-se-pide-la-del-humano (CIERRE)

## el-desvio-que-tuviste-que-improvisar-siguiendo-un-runbook-es-el-bug-del-runbook (CIERRE)

## antes-de-escribir-un-artefacto-operativo-busca-si-ya-existe-y-envejecio (CIERRE)

## una-promesa-heredada-de-un-componente-se-verifica-al-nivel-del-sistema (DEFINIR / VERIFICAR)

## un-test-de-comparacion-cuyos-datos-no-pueden-diferir-no-prueba-nada (VERIFICAR)

## el-acoplamiento-que-ningun-compilador-atrapa-es-el-que-hay-que-buscar-a-mano (VERIFICAR)

## la-instruccion-del-orquestador-es-una-hipotesis-y-el-implementador-debe-medirla (DELEGAR)

## una-capacidad-opcional-puede-imponer-un-requisito-de-infraestructura-obligatorio (DEFINIR / CIERRE)

## verificar-las-dos-mitades-por-separado-no-verifica-la-composicion (VERIFICAR)

## una-capacidad-que-nunca-operaste-solo-se-entiende-ensayandola (VERIFICAR / CIERRE)

## el-titulo-con-que-anotaste-un-hueco-es-una-hipotesis-no-una-especificacion (DEFINIR)

## el-valor-por-defecto-de-una-capacidad-nueva-debe-ser-el-statu-quo (SPEC)

## una-medicion-hecha-en-otra-topologia-mide-la-topologia-no-el-sistema (VERIFICAR)

## la-misma-clasificacion-de-errores-necesita-polaridad-opuesta-segun-la-capa (SPEC)

## una-confirmacion-util-exige-un-dato-que-solo-se-obtiene-preguntando (SPEC)

## invertir-una-decision-de-alcance-exige-registrar-que-la-estas-invirtiendo (DEFINIR)

## una-capacidad-nueva-puede-tener-un-precio-y-conviene-cotizarlo-antes-de-construir (DEFINIR)

## un-orden-implicito-que-nadie-valida-es-una-bomba-de-tiempo-en-el-export (SPEC / VERIFICAR)

## un-hueco-conocido-se-deja-asertado-para-que-una-prueba-obligue-a-cerrarlo (VERIFICAR / CIERRE)

## las-sondas-de-verificacion-tambien-dejan-estado (VERIFICAR)

## un-aislamiento-que-depende-de-la-higiene-compartida-no-es-aislamiento (SPEC / VERIFICAR)

## una-prueba-que-depende-de-una-variable-no-documentada-nunca-corre (VERIFICAR / CIERRE)

## una-punta-anotada-como-comodidad-se-mide-antes-de-dimensionarla (DEFINIR / SPEC)

## una-verificacion-que-pasa-con-el-artefacto-viejo-no-verifica-el-despliegue (VERIFICAR)

## seguir-un-runbook-de-memoria-es-no-seguirlo (VERIFICAR / CIERRE)

## declarar-un-residuo-no-lo-registra (CIERRE)

## instalar-en-limpio-siguiendo-solo-el-manual-encuentra-lo-que-el-autor-ya-no-ve (VERIFICAR / CIERRE)

## un-gate-con-un-limite-que-el-sistema-supero-no-puede-dar-verde (VERIFICAR)

## corregir-una-promesa-exige-barrer-todas-las-superficies-donde-se-la-dijo (CIERRE)

## leer-por-fuera-de-la-capa-de-portabilidad-reintroduce-la-divergencia-que-la-capa-elimina (SPEC)

## una-novedad-puede-reabrir-un-defecto-cerrado-por-un-camino-nuevo (VERIFICAR / CIERRE)

## una-capa-de-portabilidad-que-delega-la-semantica-al-motor-no-porta (SPEC / DEFINIR)

## bajo-un-regimen-sin-alter-una-tabla-nueva-llega-sola-y-una-columna-nueva-no (SPEC)

## una-medicion-correcta-no-autoriza-la-generalizacion-que-la-acompana (VERIFICAR / DELEGAR)

## donde-pones-el-rechazo-decide-si-rompes-la-escritura-o-tambien-la-lectura (SPEC)

## una-regla-que-se-evalua-al-escribir-es-mas-grave-que-una-que-se-evalua-al-leer (DEFINIR / SPEC)

## la-verificacion-la-elige-lo-que-el-cambio-gobierna-no-el-tamano-del-diff (VERIFICAR)

## una-comparacion-entre-sistemas-debe-comparar-solo-la-propiedad-bajo-prueba (VERIFICAR)

## cobertura-parcial-honesta-vale-mas-que-completa-falsa (VERIFICAR / CIERRE)

## dos-dominios-de-capa-3-que-nunca-se-hablan-convergen-en-el-mismo-riesgo (VERIFICAR)

## un-hallazgo-arreglado-en-el-codigo-sigue-abierto-si-el-artefacto-no-se-resella (CIERRE / VERIFICAR)

## el-fix-obvio-de-un-hallazgo-de-capa-3-puede-romper-en-silencio-lo-que-arregla (VERIFICAR)
