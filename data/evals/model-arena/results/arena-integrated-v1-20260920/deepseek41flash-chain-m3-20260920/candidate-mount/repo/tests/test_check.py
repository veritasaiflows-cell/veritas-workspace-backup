"""Visible test for the protected audit script. Do not modify."""
import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _load_check():
    spec = importlib.util.spec_from_file_location("check", REPO / "tools" / "check.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["check"] = module
    spec.loader.exec_module(module)
    return module


def test_check_script_passes():
    assert _load_check().main() == 0
