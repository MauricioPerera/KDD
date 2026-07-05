"""Validación de registro de usuario contra la tabla `users`.

Contrato: knowledge/contracts/validate-user-record.md
Modelo:   knowledge/data_models/users_table.md

Función pura (stdlib, `re`): sin IO, sin red, sin subprocess. Devuelve una lista
de violaciones legibles (vacía si el registro es válido). Acumula TODAS las
violaciones y nunca lanza ante dicts con valores de tipos arbitrarios.
"""

import re

# Restricción de dominio exacta del modelo: [a-z0-9_]{3,50}.
_USERNAME_RE = re.compile(r"[a-z0-9_]{3,50}\Z")

_EMAIL_MAX_LEN = 255
_PASSWORD_HASH_LEN = 60
_DISPLAY_NAME_MAX_LEN = 100


def validate_user_record(record: dict) -> list:
    """Valida `record` contra los campos y restricciones de la tabla users.

    Devuelve una lista de strings, uno por violación (vacía si es válido).
    Cada mensaje nombra el campo afectado. Determinista, pura, stdlib.
    """
    violations = []

    _check_email(record, violations)
    _check_username(record, violations)
    _check_password_hash(record, violations)
    _check_display_name(record, violations)

    return violations


def _check_email(record, violations):
    email = record.get("email")
    # Obligatorio y string: ausente o no-string -> una sola violación.
    if not isinstance(email, str):
        violations.append("email: obligatorio y debe ser string")
        return
    if len(email) > _EMAIL_MAX_LEN:
        violations.append("email: excede 255 caracteres")
        return
    # RFC 5322 básica: una @, parte local no vacía, dominio con punto, sin espacios.
    if " " in email or email.count("@") != 1:
        violations.append("email: formato inválido")
        return
    local, domain = email.split("@", 1)
    if not local or "." not in domain:
        violations.append("email: formato inválido")
        return


def _check_username(record, violations):
    username = record.get("username")
    if not isinstance(username, str):
        violations.append("username: obligatorio y debe ser string")
        return
    if _USERNAME_RE.match(username) is None:
        violations.append("username: debe coincidir con [a-z0-9_]{3,50}")
        return


def _check_password_hash(record, violations):
    password_hash = record.get("password_hash")
    if not isinstance(password_hash, str):
        violations.append("password_hash: obligatorio y debe ser string")
        return
    if len(password_hash) != _PASSWORD_HASH_LEN:
        violations.append("password_hash: debe tener exactamente 60 caracteres")
        return


def _check_display_name(record, violations):
    # Opcional: ausente o None es válido.
    display_name = record.get("display_name")
    if display_name is None:
        return
    if not isinstance(display_name, str):
        violations.append("display_name: debe ser string")
        return
    if len(display_name) > _DISPLAY_NAME_MAX_LEN:
        violations.append("display_name: excede 100 caracteres")
        return