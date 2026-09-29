"""The production entry point loads the tuned weights file, not the hard-coded fallback."""

import pytest

from scripts.production.predict_from_pdf import load_optimized_weights


@pytest.mark.parametrize("surface", ["dirt", "turf", "synthetic"])
def test_loads_production_weights(surface, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # must not depend on the working directory
    weights = load_optimized_weights(surface=surface)
    assert weights["trainer"] == pytest.approx(0.1822, abs=1e-4)
    assert "jt_combo_scale" in weights
