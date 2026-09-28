"""Omniscient MCP server package.

Defines the FastMCP instance, then imports the submodules that register tools,
prompts, and resources on it. Submodules import `mcp` from here, so this must
create it before importing them.
"""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("omniscient")

# Import for side effects: each module registers its tools/prompts/resources.
from . import tools, prompts, resources  # noqa: E402,F401

__all__ = ["mcp"]
