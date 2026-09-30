"""Load a race card from JSON into the same objects the PDF parser returns.

Used by the demo (`predict_from_pdf.py --sample`) so the model runs without
licensed past-performance PDFs. See sample_data/sample_card.json.
"""

import json
from pathlib import Path
from typing import List

from src.parsers.pdf_parser import PDFHorse, PDFRace

SAMPLE_DIR = Path(__file__).resolve().parents[2] / "sample_data"
SAMPLE_CARD = SAMPLE_DIR / "sample_card.json"
SAMPLE_STATS = SAMPLE_DIR / "stats"


def load_card(path=SAMPLE_CARD) -> List[PDFRace]:
    data = json.loads(Path(path).read_text())
    races = []
    for r in data["races"]:
        horses = [PDFHorse(**h) for h in r["horses"]]
        race_fields = {k: v for k, v in r.items() if k != "horses"}
        races.append(PDFRace(**race_fields, horses=horses))
    return races
