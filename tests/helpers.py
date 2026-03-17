"""Shared test helpers for trailtraining tests.

Not a conftest so pytest does not auto-collect it; import explicitly where needed.
"""

from __future__ import annotations

import sys
from types import ModuleType
from typing import Any


def install_module(
    monkeypatch: Any,
    package: Any,
    full_name: str,
    attr_name: str,
    **attrs: Any,
) -> ModuleType:
    """Create a stub module, register it in sys.modules, and patch *package*.

    Replaces the private ``_install_module`` helper that was duplicated in
    ``test_commands_llm.py`` and ``test_commands_pipeline.py``.
    """
    module = ModuleType(full_name)
    for key, value in attrs.items():
        setattr(module, key, value)
    monkeypatch.setitem(sys.modules, full_name, module)
    monkeypatch.setattr(package, attr_name, module, raising=False)
    return module
