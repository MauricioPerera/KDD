"""Implementacion del contrato route-message (Contrato 21).

Funcion pura que decide la ruta de un mensaje segun su emisor
contra una tabla de ruteo.
"""


def route_message(message: dict, routing: dict) -> str:
    """Decide la ruta de `message` segun `routing`.

    routing = {"senders": {<email en minusculas>: <ruta>}, "default": <ruta>}

    Devuelve la ruta del emisor (normalizado a minusculas) si esta en senders;
    routing["default"] en cualquier otro caso. Pura, determinista, nunca lanza
    ante message malformado; asume routing bien formado (data model controlado,
    no entrada libre: si routing omite 'default' o 'senders' si lanza KeyError).
    """
    sender = message.get("sender")

    # Si no es string, ir a default
    if not isinstance(sender, str):
        return routing["default"]

    # Normalizar a minusculas y buscar en senders
    normalized_sender = sender.lower()
    if normalized_sender in routing["senders"]:
        return routing["senders"][normalized_sender]

    # Si no esta, devolver default
    return routing["default"]
