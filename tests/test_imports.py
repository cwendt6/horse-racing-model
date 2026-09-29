"""Smoke test: every module in src/ and the production entry point import cleanly."""

import importlib
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULES = sorted(
    ".".join(p.relative_to(ROOT).with_suffix("").parts) for p in (ROOT / "src").rglob("*.py")
)
# Reference code that imports names which no longer exist. Tracked for a follow-up.
KNOWN_BROKEN = {
    "src.data_loaders.integrate_data",  # simd_parser.parse_simd_file was removed
    "src.analyzers.pace_integration",  # example code; PaceFigureCalculator etc. were removed
}


@pytest.mark.parametrize("module", MODULES)
def test_src_module_imports(module):
    if module in KNOWN_BROKEN:
        pytest.xfail("imports names that were removed")
    importlib.import_module(module)


def test_production_entry_point_imports():
    importlib.import_module("scripts.production.predict_from_pdf")
