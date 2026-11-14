"""The four agents. Each takes the shared state and returns the fields it updates."""

from swe_agent.agents.localizer import Localizer
from swe_agent.agents.patcher import Patcher
from swe_agent.agents.planner import Planner
from swe_agent.agents.verifier import Verifier

__all__ = ["Planner", "Localizer", "Patcher", "Verifier"]
