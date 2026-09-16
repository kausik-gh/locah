"""Permission identifier parity and authorization unit tests."""

import re
from pathlib import Path

from platform_core.permissions import ALL_PERMISSIONS, TEMPLATES


def test_all_permissions_are_dotted_identifiers() -> None:
    for perm in ALL_PERMISSIONS:
        assert "." in perm
        assert perm == perm.lower()
        assert " " not in perm
        assert "-" not in perm.split(".")[0]


def test_primary_owner_permissions_include_core() -> None:
    assert "business.read" in ALL_PERMISSIONS
    assert "team.invite" in ALL_PERMISSIONS
    assert "modules.enable" in ALL_PERMISSIONS
    assert "commercial.read" in ALL_PERMISSIONS


def test_manager_delegation_ceiling_logic() -> None:
    manager_perms = frozenset({"orders.read", "orders.update_status"})
    requested = {"orders.read", "orders.create"}
    excess = requested - manager_perms
    assert "orders.create" in excess


def test_builtin_templates_reference_valid_permissions() -> None:
    for template_id, perms in TEMPLATES.items():
        assert template_id.startswith("tmpl_")
        for perm in perms:
            assert perm in ALL_PERMISSIONS, f"{template_id} references unknown {perm}"


def test_python_permissions_match_typescript_registry() -> None:
    ts_path = (
        Path(__file__).resolve().parents[3] / "packages" / "permissions" / "src" / "identifiers.ts"
    )
    ts_content = ts_path.read_text(encoding="utf-8")
    ts_perms = set(re.findall(r"'([a-z][a-z0-9_.]+)'", ts_content))
    ts_perms = {p for p in ts_perms if "." in p and p.count(".") == 1}
    assert ts_perms == set(ALL_PERMISSIONS)
