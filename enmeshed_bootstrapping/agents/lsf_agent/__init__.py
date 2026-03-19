# pyright: reportUnknownMemberType = false, reportExplicitAny = false, reportAny = false, reportIndexIssue = false, reportUnknownVariableType = false

import json
from pathlib import Path
from typing import Literal, cast, override

from ollama import Message

from enmeshed_bootstrapping.connector_sdk import ConnectorSDK
from enmeshed_bootstrapping.ollama_client import OllamaClient
from enmeshed_bootstrapping.webhook_server import WebhookServer

from .. import IAgent

_SCRIPT_DIR = Path(__file__).parent
_IMMA_PATH = _SCRIPT_DIR / "imma.pdf"
_TRANSCRIPT_PATH = _SCRIPT_DIR / "transcript.pdf"

_SYSTEM_PROMPT = """Du bist ein LSF-Agent innerhalb einer Universitätsverwaltungssoftware, der den Self-Service der Studenten unterstützt.

# Fähigkeiten

Du verfügst über folgende Tools:
- `durchsuche_studenten_daten`: Sucht Dokumente (Immatrikulationsbescheid, Notenspiegel) im LSF-Verzeichnis des Studierenden und gibt eine Dateireferenz zurück.
- `liste_besuchter_vorlesungen`: Liefert die Liste der Vorlesungen, für die der Studierende angemeldet ist.
- `pruefungsvorausetzungen_erfuellt`: Prüft, ob der Studierende die Voraussetzungen für die Prüfung einer bestimmten Vorlesung erfüllt.
- `anfrage_pruefungsanmeldung`: Verschickt eine Prüfungsanmeldungsanfrage an den Studierenden über einen separaten Kanal.
- `antworten`: Sendet eine Antwort an den Studierenden. Kann Dateireferenzen als Anhänge enthalten.

# Ablauf

1. Du erhältst eine Nachricht eines Studierenden (Betreff + Inhalt).
2. Analysiere das Anliegen. Nutze die verfügbaren Tools, um benötigte Informationen und Dokumente zu beschaffen.
3. Stelle sicher, dass du alle nötigen Informationen gesammelt hast, bevor du antwortest. Rufe bei Bedarf mehrere Tools nacheinander auf.
4. Sobald du alle Informationen besitzt, beantworte die Anfrage abschließend mit dem `antworten`-Tool. Jede Konversation muss mit einem `antworten`-Aufruf enden.

# Einschränkungen

- Wenn kein Tool zum Anliegen passt oder du die Anfrage nicht bearbeiten kannst, nutze `antworten`, um höflich mitzuteilen, dass du die Anfrage nicht verarbeiten kannst. Verweise in diesem Fall auf den telefonischen Support unter +49 (0) 6221 54-5454 oder per E-Mail an support@uni-heidelberg.de.
- Erfinde keine Informationen. Nutze ausschließlich die Daten, die dir über Tools zur Verfügung stehen.

# Formatierung

- Verwende kein Markdown oder andere Auszeichnungssprachen. Antworte ausschließlich in reinem Text, da die Nachrichten als Plain-Text angezeigt werden."""


class LSFAgent(IAgent):
    _connector: ConnectorSDK
    _ollama_client: OllamaClient
    _webhook_server: WebhookServer

    _imma_fileref: str = ""
    _transcript_rileref: str = ""

    def __init__(
        self,
        connector: ConnectorSDK,
        ollama_client: OllamaClient,
        webhook_server_hostname: str | None = None,
        webhook_server_port: int | None = None,
    ) -> None:
        self._connector = connector
        self._ollama_client = ollama_client
        self._webhook_server = WebhookServer(
            self.handle_webhook,
            hostname=webhook_server_hostname,
            port=webhook_server_port,
        )

    @override
    def init(self) -> None:
        resp = self._connector.post_own_file(
            title="Immatrikulationsbescheid",
            description="Aktueller Immatrikulationsbescheid",
            filename="imma.pdf",
            mimetype="application/pdf",
            data=_IMMA_PATH.read_bytes(),
        )
        self._imma_fileref = resp.result.id

        resp = self._connector.post_own_file(
            title="Notenspiegel",
            description="Aktueller Notespiele",
            filename="transcript.pdf",
            mimetype="application/pdf",
            data=_TRANSCRIPT_PATH.read_bytes(),
        )
        self._transcript_rileref = resp.result.id

    @override
    def serve_forever(self) -> None:
        self._webhook_server.serve_forever()

    def tool_search_student_records(
        self,
        typ: Literal["Immatrikulationsbescheid", "Notenspiegel"],
        student_nmshd_addr: str,  # pyright: ignore[reportUnusedParameter]
    ) -> str | None:
        match typ:
            case "Immatrikulationsbescheid":
                return self._imma_fileref
            case "Notenspiegel":
                return self._transcript_rileref

    def tool_request_exam_registration(
        self,
        course: str,
        student_nmshd_addr: str,
    ) -> None:
        request_items = [
            {
                "@type": "ConsentRequestItem",
                "mustBeAccepted": False,
                "consent": f"Ich trete hiermit verpflichtend zur Prüfung der Vorlesung '{course}' bei",
                "link": "https://www.uni-heidelberg.de/de/forschung",
            }
        ]
        resp = self._connector.post_requests_outgoing(
            payload={
                "content": {
                    "items": request_items,
                },
                "peer": student_nmshd_addr,
            }
        )
        request_id = resp.result.id

        msg_payload = {
            "recipients": [
                student_nmshd_addr,
            ],
            "content": {
                "@type": "Request",
                "id": request_id,
                "items": request_items,
            },
        }
        self._connector.post_message(msg_payload)

    def tool_check_exam_prerequisites(
        self,
        course: str,
        student_nmshd_addr: str,  # pyright: ignore[reportUnusedParameter]
    ) -> bool:
        return course in _VORLESUNGEN

    def tool_list_courses(
        self,
        student_nmshd_addr: str,  # pyright: ignore[reportUnusedParameter]
    ) -> list[str]:
        return _VORLESUNGEN

    def tool_send_mail(
        self,
        recipient_addr: str,
        title: str,
        body: str,
        attachments: list[str] | None = None,
    ) -> None:
        self._connector.post_mail_message(
            recipient_addr,
            title=title,
            body=body,
            attachments=attachments,
        )

    def handle_mail(
        self,
        sender_addr: str,
        title: str,
        body: str,
    ) -> dict[str, object]:
        messages: list[Message] = [
            Message(role="system", content=_SYSTEM_PROMPT),
            Message(role="user", content=f"Betreff: {title}\nInhalt: {body}"),
        ]
        while True:
            response = self._ollama_client.chat(
                messages=messages,
                tools=[
                    durchsuche_studenten_daten,
                    liste_besuchter_vorlesungen,
                    pruefungsvoraussetzungen_erfuellt,
                    anfrage_pruefungsanmeldung,
                    antworten,
                ],
            )

            messages.append(response.message)
            if response.message.tool_calls:
                for call in response.message.tool_calls:
                    match call.function.name:
                        case "durchsuche_studenten_daten":
                            doc_type: Literal[
                                "Immatrikulationsbescheid", "Notenspiegel"
                            ] = call.function.arguments["typ"]
                            fileref = self.tool_search_student_records(
                                doc_type,
                                sender_addr,
                            )
                            messages.append(
                                Message(
                                    role="tool",
                                    tool_name=call.function.name,
                                    content=fileref,
                                )
                            )
                        case "anfrage_pruefungsanmeldung":
                            vorlesung = call.function.arguments["vorlesung"]
                            result = self.tool_request_exam_registration(
                                vorlesung,
                                sender_addr,
                            )
                            messages.append(
                                Message(
                                    role="tool",
                                    tool_name=call.function.name,
                                    content=result,
                                )
                            )

                        case "pruefungsvoraussetzungen_erfuellt":
                            vorlesung = call.function.arguments["vorlesung"]
                            result = self.tool_check_exam_prerequisites(
                                vorlesung,
                                sender_addr,
                            )
                            messages.append(
                                Message(
                                    role="tool",
                                    tool_name=call.function.name,
                                    content=str(result),
                                )
                            )

                        case "liste_besuchter_vorlesungen":
                            courses = self.tool_list_courses(sender_addr)
                            messages.append(
                                Message(
                                    role="tool",
                                    tool_name=call.function.name,
                                    content=str(courses),
                                )
                            )

                        case "antworten":
                            agent_response = {
                                "title": call.function.arguments["betreff"],
                                "body": call.function.arguments["inhalt"],
                                "attachments": call.function.arguments[
                                    "dateireferenzen"
                                ],
                            }
                            result = self.tool_send_mail(
                                sender_addr,
                                **agent_response,
                            )
                            messages.append(
                                Message(
                                    role="tool",
                                    tool_name=call.function.name,
                                    content=str(result),
                                )
                            )
                            break  # exit agent loop
                        case _ as fnname:
                            raise ValueError(f"invalid function call {fnname}")
                else:
                    continue
                break

        # Debug - print conversation to file
        msgs = json.dumps(
            [m.model_dump() for m in messages], ensure_ascii=False, indent=2
        )
        _ = Path("messages.json").write_text(msgs)

        return {}

    @override
    def handle_webhook(
        self,
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

        return self.handle_mail(sender_addr, title, body)


def durchsuche_studenten_daten(
    typ: Literal["Immatrikulationsbescheid", "Notenspiegel"],  # pyright: ignore[reportUnusedParameter]
) -> str | None:
    """Sucht im LSF-Verzeichnis des Studierenden nach Dokumenten. Gibt bei Auffinden einer Datei eine eindeutige Dateireferenz zurück, z.B. 'FILjfwatCXPoyqmmlnuX'. Dateireferenzen werden genutzt, um Dateien als Anhänge einer Nachricht zu versenden. Wenn keine Datei gefunden werden konnte, wird None zurückgegeben.

    typ: Art des gesuchten Dokuments - entweder "Immatrikulationsbescheid" oder "Notenspiegel"
    """
    pass


def antworten(
    betreff: str,  # pyright: ignore[reportUnusedParameter]
    inhalt: str,  # pyright: ignore[reportUnusedParameter]
    dateireferenzen: list[str] | None = None,  # pyright: ignore[reportUnusedParameter]
) -> None:
    """Beantwortet final die Anfrage des Studierenden und beendet das Gespräch. Rufe diese Funktion auf, wenn du dir sicher bist, alle Anliegen des Studierenden beantwortet zu haben.

    betreff: Betreffzeile der Antwort
    inhalt: Vollständiger Nachrichtentext der Antwort
    dateireferenzen: Liste von Dateireferenzen (z.B. ["FIL441idofj31", "FILdeadbeef13"]), deren Dateien als Anhänge verschickt werden sollen. None, wenn keine Anhänge benötigt werden.
    """
    pass


_VORLESUNGEN = [
    "Experimentalphysik I",
    "Experimentalphysik II",
    "Computerlinguistik I",
    "Compilerbau",
    "Elektronik",
    "Einführung in die Wissenschaftsphilosophie",
]


def liste_besuchter_vorlesungen() -> list[str]:
    """Liefert die Liste der Vorlesungen, für die der Studierende angemeldet ist und eine Prüfung ablegen darf."""
    return _VORLESUNGEN


def pruefungsvoraussetzungen_erfuellt(
    vorlesung: str,  # pyright: ignore[reportUnusedParameter]
) -> bool:  # pyright: ignore[reportReturnType]
    """Prüft, ob der Studierende die Voraussetzungen erfüllt, um an der Prüfung einer bestimmten Vorlesung teilzunehmen.

    vorlesung: Name der Vorlesung, z.B. "Experimentalphysik I"
    """
    pass


def anfrage_pruefungsanmeldung(
    vorlesung: str,  # pyright: ignore[reportUnusedParameter]
) -> None:
    """Verschickt eine Anfrage zur Prüfungsanmeldung an den Studierenden. Die Anfrage wird über einen separaten Kanal außerhalb der Konversation zugestellt.

    vorlesung: Name der Vorlesung, für die die Prüfungsanmeldung angefragt werden soll
    """
