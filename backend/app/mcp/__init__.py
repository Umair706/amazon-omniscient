"""Omniscient MCP server package.

Defines the FastMCP instance, then imports the submodules that register tools,
prompts, and resources on it. Submodules import `mcp` from here, so this must
create it before importing them.
"""

from mcp.server.fastmcp import FastMCP

# Shown to the model by the client — how to actually use this server well.
_INSTRUCTIONS = """\
Omniscient is an Amazon FBA product-research engine you drive as tools. You do the
reasoning and write the plan; Omniscient supplies the data, computation, and memory.

Typical workflow:
1. discover_opportunities(seed, marketplace) to get candidate niches from a broad idea.
2. analyze_keyword(keyword, marketplace) on a promising candidate for a full analysis.
3. get_recommendation(id) to read the scored brief; get_niche_* for detail.
4. Save your output with save_plan so it persists across sessions.

Async jobs: discover_opportunities, analyze_keyword and reanalyze_niche return a
`job_id`. Call job_status(job_id) every few seconds until status is 'completed'
(or 'failed'), THEN read the result. Analysis can take several minutes when AI
steps run on a local model — keep polling, do not assume it failed.

Errors: a tool result that contains an `error` field means the call failed. Read
its `hint` and adjust your inputs; do not retry the same call blindly.

Honesty: respect FAIL verdicts (a hard filter failed — usually walk away). Treat
anything flagged in `data_gaps`/`risk_flags` as an assumption to verify, not a
fact. AU sales estimates are uncalibrated (rough). Read the omniscient://scoring-guide
resource before interpreting any score.
"""

mcp = FastMCP("omniscient", instructions=_INSTRUCTIONS)

# Import for side effects: each module registers its tools/prompts/resources.
from . import tools, prompts, resources  # noqa: E402,F401

__all__ = ["mcp"]
