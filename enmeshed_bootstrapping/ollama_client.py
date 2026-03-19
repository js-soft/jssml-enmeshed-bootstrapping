# pyright: reportUnknownMemberType = false, reportAny = false, reportExplicitAny = false

from collections.abc import Callable, Mapping, Sequence
from typing import Any

import ollama
from ollama import ChatResponse, Message, Tool


class OllamaClient:
    """Ollama wrapper with fixed model and think settings."""
    _model: str
    _think: bool
    _client: ollama.Client

    def __init__(
        self,
        model: str,
        think: bool,
        ollama_host: str | None = None,
    ) -> None:
        self._model = model
        self._think = think
        self._client = ollama.Client(host=ollama_host)

    def chat(
        self,
        messages: Sequence[Mapping[str, Any] | Message] | None = None,
        *,
        tools: Sequence[Mapping[str, Any] | Tool | Callable[..., Any]] | None = None,
    ) -> ChatResponse:
        return self._client.chat(
            model=self._model,
            messages=messages,
            tools=tools,
            think=self._think,
        )
