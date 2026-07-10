---
type: 'Architecture'
title: 'Arquitectura general'
description: 'Arquitectura mínima de la app de ejemplo: 4 componentes y sus relaciones.'
tags: ['architecture', 'overview', 'example']
---

# Arquitectura general (app de ejemplo)

Vista de alto nivel de una app web mínima de ejemplo. El formato de este nodo se define en [OKF-SPEC](../OKF-SPEC.md). Los datos de usuario persistidos por el API se modelan en [Tabla users](../data_models/users_table.md).

## Componentes

1. **Web Client** — SPA en el navegador. Renderiza UI y consume el API REST del App API. Sin acceso directo a la base de datos.
2. **App API** — servicio backend stateless (REST). Valida entradas, aplica reglas de negocio y lee/escribe contra la capa de persistencia. Punto único de acceso a datos.
3. **Auth Service** — módulo responsable de autenticación: emisión/verificación de tokens y hash de contraseñas (bcrypt). Es invocado por el App API.
4. **PostgreSQL** — base de datos relacional. Almacena usuarios (ver [Tabla users](../data_models/users_table.md)) y demás entidades.

## Relaciones

```text
Web Client --(HTTPS / REST)--> App API --(interno)--> Auth Service
App API --(SQL)--> PostgreSQL
```

- Web Client → App API: REST sobre HTTPS.
- App API → Auth Service: llamada interna (no expuesta a internet).
- App API → PostgreSQL: conexión SQL sobre red privada.

## Decisiones clave

- **Stateless en el backend:** el App API no guarda sesión; delega autenticación al Auth Service vía tokens.
- **Acceso a datos centralizado:** solo el App API habla con PostgreSQL. El Web Client nunca accede a la base directamente.
- **Soft-delete de usuarios:** las cuentas se desactivan (`is_active = FALSE`), no se borran físicamente.

## Límites de esta vista

No cubre despliegue, observabilidad ni escalado horizontal. Es una baseline para ejemplos; los detalles viven en nodos propios a medida se agreguen.