#!/usr/bin/env python3
"""Portable dbt console entry point (notably for Windows Store Python)."""
from dbt.cli.main import cli


if __name__ == "__main__":
    cli()
