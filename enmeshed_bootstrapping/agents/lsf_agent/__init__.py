# pyright: reportUnknownMemberType = false, reportExplicitAny = false, reportAny = false, reportIndexIssue = false, reportUnknownVariableType = false

import json
from pathlib import Path
from typing import Literal, cast

import ollama

from enmeshed_bootstrapping.connector_sdk import ConnectorSDK
from enmeshed_bootstrapping.webhook_server import HandlerFn

_SYSTEM_PROMPT = """Du bist ein LSF-Agent innerhalb einer Universitätsverwaltungssoftware, der den Self-Service der Studenten unterstützt.

# Fähigkeiten

Du verfügst über folgende Tools:
- `durchsuche_studenten_daten`: Sucht Dokumente (Immatrikulationsbescheid, Notenspiegel) im LSF-Verzeichnis des Studierenden und gibt eine Dateireferenz zurück.
- `antworten`: Sendet eine Antwort an den Studierenden. Kann Dateireferenzen als Anhänge enthalten.

# Ablauf

1. Du erhältst eine Nachricht eines Studierenden (Betreff + Inhalt).
2. Analysiere das Anliegen. Nutze `durchsuche_studenten_daten`, um benötigte Dokumente zu beschaffen.
3. Stelle sicher, dass du alle nötigen Informationen gesammelt hast, bevor du antwortest. Rufe bei Bedarf mehrere Tools nacheinander auf.
4. Sobald du alle Informationen besitzt, beantworte die Anfrage abschließend mit dem `antworten`-Tool. Jede Konversation muss mit einem `antworten`-Aufruf enden.

# Einschränkungen

- Wenn kein Tool zum Anliegen passt oder du die Anfrage nicht bearbeiten kannst, nutze `antworten`, um höflich mitzuteilen, dass du die Anfrage nicht verarbeiten kannst.
- Erfinde keine Informationen. Nutze ausschließlich die Daten, die dir über Tools zur Verfügung stehen."""

# Usecases
# --------
# - Transcript schicken
# - aktuelle Imma
# - matrikelnummer veregessen
# - anmeldung Prüfung

# XXX: Dateien beim bootstrap hochladen


def make_handlerfn(
    connector: ConnectorSDK,
    ollama_client: ollama.Client,
) -> HandlerFn:
    def handlerfn(
        trigger: str,
        data: dict[str, object],
    ) -> dict[str, object]:
        if not trigger == "consumption.messageProcessed":
            return {}

        message = data["data"]["message"]
        if message["isOwn"]:
            return {}

        content = message["content"]
        if content["@type"] != "Mail":
            return {}

        sender_addr = cast(str, message["createdBy"])
        title = cast(str, content["subject"])
        body = cast(str, content["body"])

        messages = [
            {
                "role": "system",
                "content": _SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": f"Betreff: {title}\nInhalt: {body}",
            },
        ]
        while True:
            response: ollama.ChatResponse = ollama_client.chat(
                model="glm-4.7-flash:q4_K_M",
                messages=messages,
                tools=[durchsuche_studenten_daten, antworten],
                think=True,
            )

            messages.append(response.message.model_dump())
            if response.message.tool_calls:
                for call in response.message.tool_calls:
                    match call.function.name:
                        case "durchsuche_studenten_daten":
                            doc_type: Literal[
                                "Immatrikulationsbescheid", "Notenspiegel"
                            ] = call.function.arguments["typ"]
                            fileref = durchsuche_studenten_daten(doc_type)
                            messages.append(
                                {
                                    "role": "tool",
                                    "tool_name": call.function.name,
                                    "content": str(fileref),
                                }
                            )

                        case "antworten":
                            agent_response_title: str = call.function.arguments[
                                "betreff"
                            ]
                            agent_response_body: str = call.function.arguments["inhalt"]
                            agent_response_filerefs: list[str] = (
                                call.function.arguments["dateireferenzen"]
                            )
                            connector.post_message(
                                sender_addr,
                                title=agent_response_title,
                                body=agent_response_body,
                                attachments=agent_response_filerefs,
                            )
                            break  # exit agent loop
                        case _ as fnname:
                            raise ValueError(f"invalid function call {fnname}")
                else:
                    continue
                break
        msgs = json.dumps(messages, ensure_ascii=False, indent=2)
        _ = Path("messages.json").write_text(msgs)
        return {}

    return handlerfn


def durchsuche_studenten_daten(
    typ: Literal["Immatrikulationsbescheid", "Notenspiegel"],
) -> str | None:
    """Sucht im LSF-Verzeichnis des Studierenden nach Dokumenten. Gibt bei Auffinden einer Datei eine eindeutige Dateireferenz zurück, z.B. 'FILjfwatCXPoyqmmlnuX'. Dateireferenzen werden genutzt, um Dateien als Anhänge einer Nachricht zu versenden. Wenn keine Datei gefunden werden konnte, wird None zurückgegeben.

    typ: Art des gesuchten Dokuments - entweder "Immatrikulationsbescheid" oder "Notenspiegel"
    """

    match typ:
        case "Immatrikulationsbescheid":
            return "FILjfwatCXPoyqmmlnuX"
        case "Notenspiegel":
            return "FIL3OIwrYISq0xdf3Caj"


def antworten(
    betreff: str,
    inhalt: str,
    dateireferenzen: list[str] | None = None,
) -> None:
    """Beantwortet final die Anfrage des Studierenden und beendet das Gespräch. Rufe diese Funktion auf, wenn du dir sicher bist, alle Anliegen des Studierenden beantwortet zu haben.

    betreff: Betreffzeile der Antwort
    inhalt: Vollständiger Nachrichtentext der Antwort
    dateireferenzen: Liste von Dateireferenzen (z.B. ["FIL441idofj31", "FILdeadbeef13"]), deren Dateien als Anhänge verschickt werden sollen. None, wenn keine Anhänge benötigt werden.
    """
    pass
