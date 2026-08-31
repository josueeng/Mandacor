from __future__ import annotations

import os
import subprocess
import sys

import pytest

from conftest import GOLDEN_PATH, PROJECT_ROOT


@pytest.mark.instrument
def test_golden_reference_read_only_flow():
    if os.environ.get("MANDACOR_RUN_INSTRUMENT") != "1":
        pytest.skip("set MANDACOR_RUN_INSTRUMENT=1 for the read-only bench test")
    subprocess.run(
        [sys.executable, str(GOLDEN_PATH)],
        cwd=PROJECT_ROOT,
        check=True,
        timeout=45,
    )

