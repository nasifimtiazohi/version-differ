#!/usr/bin/env python
"""Command-line interface."""
import click
from rich import traceback


@click.command()
@click.version_option(version="0.3.6", message=click.style("version-differ Version: 0.3.6"))
def main() -> None:
    """version-differ."""


if __name__ == "__main__":
    traceback.install()
    main(prog_name="version-differ")  # pragma: no cover
