"""AI employees — one shared runtime (runtime.py) and the employees built on it.

Importing the package registers every T3 approval handler, so an approval
can always be carried out whichever route imports it first.
"""

from platform_core.ai_employees import collections, procurement, receptionist  # noqa: F401
from platform_core.ai_employees.runtime import AIRuntime

__all__ = ["AIRuntime"]
