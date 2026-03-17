#!/usr/bin/env -S uv run --script

from typing import TypedDict

import click

from enmeshed_bootstrapping import dev_app
from enmeshed_bootstrapping.c2_server import C2Server
from enmeshed_bootstrapping.connector_sdk import ConnectorSDK
from enmeshed_bootstrapping.flows import bootstrap


class LocalAccountDTO(TypedDict):
    id: str
    address: str
    name: str


@click.group()
def cli():
    pass


@cli.command()
def build_app():
    """Compile app.j"""
    dev_app.build()


@cli.command()
@click.option("--device", default=None, help="ADB device serial")
def install_app(device: str | None):
    """Uninstall old app, then install APK via adb."""
    dev_app.uninstall(device_serial=device)
    dev_app.install(device_serial=device)


@cli.command()
@click.option("--device", default=None, help="ADB device serial")
def start(device: str | None = None):
    """Run bootstrap flow."""
    c2 = C2Server()
    connector = ConnectorSDK()
    bootstrap.bootstrap(c2, connector, device_serial=device)


if __name__ == "__main__":
    cli()
