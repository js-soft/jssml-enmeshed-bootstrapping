#!/usr/bin/env -S uv run --script

from typing import TypedDict

import click
import ollama

from enmeshed_bootstrapping import dev_app
from enmeshed_bootstrapping.agents import auto_responder
from enmeshed_bootstrapping.c2_server import C2Server
from enmeshed_bootstrapping.connector_sdk import ConnectorSDK
from enmeshed_bootstrapping.flows import bootstrap
from enmeshed_bootstrapping.webhook_server import WebhookServer


class LocalAccountDTO(TypedDict):
    id: str
    address: str
    name: str


@click.group()
def cli():
    pass


@cli.command()
def build_app():
    """Compile app."""
    dev_app.build()


@cli.command()
@click.option("--device", default=None, help="ADB device serial")
def install_app(device: str | None):
    """Uninstall old app, then install APK via adb."""
    dev_app.uninstall(device_serial=device)
    dev_app.install(device_serial=device)


@cli.command()
@click.option("--device", default=None, help="ADB device serial")
def start_app(device: str | None = None):
    """Run bootstrap flow."""
    c2 = C2Server()
    connector = ConnectorSDK()
    bootstrap.bootstrap(c2, connector, device_serial=device)


@cli.command()
@click.argument("demo", type=click.Choice(["auto-respond"]))
@click.option("--device", default=None, help="ADB device serial")
def run(demo: str, device: str | None = None) -> None:
    """Run a particular demo."""
    match demo:
        case "auto-respond":
            c2 = C2Server()
            connector = ConnectorSDK()
            ollama_client = ollama.Client()

            click.echo("running bootstrap...")
            bootstrap.bootstrap(c2, connector, device_serial=device)

            click.echo("starting auto responder agent...")
            handlerfn = auto_responder.make_handlerfn(connector, ollama_client)
            webhook_srv = WebhookServer(handlerfn, hostname="0.0.0.0")
            webhook_srv.serve_forever()

        case _:
            raise ValueError(f"no such demo {demo}")


if __name__ == "__main__":
    cli()
