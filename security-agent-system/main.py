"""CLI entrypoint shim for backward compatibility."""
from apps.cli.main import cli

if __name__ == "__main__":
    cli()
