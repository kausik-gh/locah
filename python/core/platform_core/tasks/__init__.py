"""Tasks contracts other modules may call without importing task internals."""

from platform_core.tasks.compliance_hook import create_task_for_compliance_due

__all__ = ["create_task_for_compliance_due"]
