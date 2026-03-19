# pyright: reportUnknownMemberType = false, reportExplicitAny = false, reportAny = false, reportIndexIssue = false, reportUnknownVariableType = false

from typing import cast, override

from ollama import Message

from enmeshed_bootstrapping.connector_sdk import ConnectorSDK
from enmeshed_bootstrapping.ollama_client import OllamaClient
from enmeshed_bootstrapping.webhook_server import WebhookServer

from . import IAgent

_SYS_PROMPT = "Du bist ein ulkiger Quatschkopfagent. Antworte ulkig auf die Nutzeremail (bestehend aus Titel und Inhalt)."


class AutoResponder(IAgent):
    _connector: ConnectorSDK
    _ollama_client: OllamaClient
    _webhook_server: WebhookServer

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
        pass

    @override
    def serve_forever(self) -> None:
        self._webhook_server.serve_forever()

    def handle_mail(
        self,
        sender_addr: str,
        title: str,
        body: str,
    ) -> dict[str, object]:
        messages = [
            Message(role="system", content=_SYS_PROMPT),
            Message(role="user", content=f"Titel: {title}\nInhalt: {body}"),
        ]
        response = self._ollama_client.chat(messages=messages)
        reply = response["message"]["content"]
        self._connector.post_mail_message(
            sender_addr,
            f"re: {title}",
            reply,
        )
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
