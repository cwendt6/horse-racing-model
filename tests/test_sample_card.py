"""The synthetic demo card loads and runs through the full prediction pipeline."""

import subprocess
import sys
from pathlib import Path

from src.data_loaders.sample_card import load_card

ROOT = Path(__file__).resolve().parents[1]


def test_sample_card_loads():
    races = load_card()
    assert len(races) == 1
    race = races[0]
    assert race.track_name == "Sample Downs"
    assert len(race.horses) == 8
    assert all(len(h.past_performances) == 4 for h in race.horses)


def test_sample_prediction_runs_end_to_end(tmp_path):
    # Run from a temp dir so relative paths the model may write to stay out of the repo.
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "production" / "predict_from_pdf.py"), "--sample"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr[-2000:]
    assert "TOP 5 PREDICTIONS" in result.stdout
    assert "PREDICTION COMPLETE" in result.stdout
