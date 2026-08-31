from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ORIGINAL_PATH = PROJECT_ROOT / "conect_espectro.py"
GOLDEN_PATH = PROJECT_ROOT / "legacy" / "byk_reader_working.py"


@pytest.fixture(scope="session")
def golden_module():
    """Load the frozen module without changing its source or executing main()."""
    spec = importlib.util.spec_from_file_location("byk_reader_working", GOLDEN_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

