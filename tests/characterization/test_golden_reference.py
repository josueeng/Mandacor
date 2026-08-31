from __future__ import annotations

import hashlib

from conftest import GOLDEN_PATH, ORIGINAL_PATH


EXPECTED_SHA256 = "a74672dbde168962bac4d5640d2c0edb2a08fe8e20ad7b01c0062e5a242d15ba"


def _sha256(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_original_and_golden_have_same_hash():
    assert _sha256(ORIGINAL_PATH) == EXPECTED_SHA256
    assert _sha256(GOLDEN_PATH) == EXPECTED_SHA256


def test_original_and_golden_are_byte_identical():
    assert ORIGINAL_PATH.read_bytes() == GOLDEN_PATH.read_bytes()

