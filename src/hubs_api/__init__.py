"""hubs_api package.

Expose the CLI at package level: `from hubs_api import cli`.
"""
from .cli import cli  # re-export the click CLI group at package level

__all__ = ["cli"]
