---
type: 'Data Model'
title: 'Tabla users'
description: 'Modelo de la tabla users: campos, tipos y restricciones para la app de ejemplo.'
tags: ['data-model', 'users', 'example']
---

# Data Model: `users`

Almacena las cuentas de usuario de la app de ejemplo. Relacionado con la arquitectura general definida en [Arquitectura general](../architecture/overview.md). La especificación de formato de este nodo está en [OKF-SPEC](../OKF-SPEC.md).

## Campos

| Columna      | Tipo          | Nulo | Default       | Restricciones / Notas                                  |
|--------------|---------------|------|---------------|--------------------------------------------------------|
| `id`         | BIGINT        | no   | autoincrement | PK. Identificador único.                               |
| `email`      | VARCHAR(255)  | no   | —             | UNIQUE, formato email válido.                          |
| `username`   | VARCHAR(50)   | no   | —             | UNIQUE, `[a-z0-9_]{3,50}`.                             |
| `password_hash` | CHAR(60)   | no   | —             | Hash bcrypt. Nunca se almacena texto plano.            |
| `display_name` | VARCHAR(100) | sí  | NULL          | Nombre para mostrar.                                   |
| `created_at` | TIMESTAMP     | no   | now()         | UTC.                                                   |
| `updated_at` | TIMESTAMP     | no   | now()         | UTC, se actualiza en cada modificación.                |
| `is_active`  | BOOLEAN       | no   | TRUE          | Soft-delete / desactivación de cuenta.                 |

## Claves e índices

- **PK:** `users(id)`
- **UNIQUE:** `users(email)`, `users(username)`
- **ÍNDICE:** `users(is_active)`, `users(created_at)`

## Invariantes

- `email` y `username` son únicos a nivel de tabla.
- `password_hash` nunca se serializa en respuestas de API ni se loguea.
- `created_at` es inmutable tras la inserción.

## Restricciones de dominio

- `username`: 3–50 caracteres, solo `[a-z0-9_]`.
- `email`: debe pasar validación RFC 5322 básica.
- `is_active = FALSE` equivale a desactivación (no borrado físico).