"""Epic 1 AC: external SDKs may be imported ONLY inside backend/providers/.

A router/service importing stripe/paramiko/supabase/resend/docker directly defeats
local-first (docs/ARCHITECTURE.md §3) — fail the build if it happens.
"""

from __future__ import annotations

import ast
import pathlib

BACKEND = pathlib.Path(__file__).resolve().parents[1]
FORBIDDEN = {"stripe", "paramiko", "supabase", "resend", "docker"}


def _modules_importing_forbidden() -> dict[str, set[str]]:
    offenders: dict[str, set[str]] = {}
    for py in BACKEND.rglob("*.py"):
        rel = py.relative_to(BACKEND)
        parts = rel.parts
        if parts[0] in {"providers", "tests"}:
            continue
        tree = ast.parse(py.read_text(), filename=str(py))
        hits: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                hits |= {a.name.split(".")[0] for a in node.names} & FORBIDDEN
            elif isinstance(node, ast.ImportFrom) and node.module:
                if node.module.split(".")[0] in FORBIDDEN:
                    hits.add(node.module.split(".")[0])
        if hits:
            offenders[str(rel)] = hits
    return offenders


def test_no_forbidden_imports_outside_providers():
    offenders = _modules_importing_forbidden()
    assert not offenders, (
        f"External SDKs imported outside providers/: {offenders}. "
        "Route these through a provider interface (backend/providers/base.py)."
    )
