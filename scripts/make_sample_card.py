"""Generate sample_data/sample_card.json: a synthetic race card for the demo.

Every horse, jockey, trainer and sire is invented. Figures are drawn from a seeded
RNG so the file is reproducible. No licensed Equibase or Brisnet data is used.

    python scripts/make_sample_card.py
"""

import json
import random
from datetime import date, timedelta
from pathlib import Path

SAMPLE = Path(__file__).resolve().parents[1] / "sample_data"
OUT = SAMPLE / "sample_card.json"

HORSES = [
    ("1", "Paper Lantern", "Rowan Hale", "Mara Quill", "Lantern Bay", "5-2"),
    ("2", "Quiet Ledger", "Tess Ormond", "Idris Vane", "Double Entry", "6-1"),
    ("3", "Copper Mile", "Jude Farrow", "Mara Quill", "Iron Furlong", "4-1"),
    ("4", "Late Harvest", "Nico Brandt", "Ellis Thorne", "Autumn Rain", "8-1"),
    ("5", "Signal Fire", "Ada Kestrel", "Ruth Calder", "Beacon Hill", "3-1"),
    ("6", "Blue Ribbon Kid", "Cyrus Pell", "Idris Vane", "Prize Day", "12-1"),
    ("7", "Northbound", "Lena Voss", "Ellis Thorne", "Compass Rose", "10-1"),
    ("8", "Sandpiper Run", "Omar Reyes", "Ruth Calder", "Shoreline", "15-1"),
]
# (style, speed level) per horse: E=early, P=presser, S=stalker, C=closer
PROFILES = ["E", "P", "E", "C", "P", "S", "C", "S"]
SPEED = [88, 82, 86, 80, 90, 76, 79, 74]


def past_performances(rng, style, speed, race_day):
    pps = []
    day = race_day
    for _ in range(4):
        day -= timedelta(days=rng.randint(21, 42))
        early = {"E": 1, "P": 2, "S": 4, "C": 7}[style] + rng.randint(0, 1)
        finish = max(1, min(8, round(rng.gauss(4.5 - (speed - 80) / 4, 1.5))))
        q = round(22.0 + rng.uniform(0, 1.2), 2)
        h = round(q + 23.0 + rng.uniform(0, 1.0), 2)
        f = round(h + 24.5 + rng.uniform(0, 1.5), 2)
        pps.append(
            {
                "date": day.isoformat(),
                "track": "SMP",
                "distance": "6f",
                "surface": "Dirt",
                "fractional_times": [q, h, f],
                "early": (rng.randint(1, 8), early),
                "first_call": early,
                "second_call": max(1, early + rng.randint(-1, 1)),
                "stretch": max(1, finish + rng.randint(-1, 1)),
                "finish": finish,
                "finish_position": finish,
                "final_time": f,
                "speed_figure": speed + rng.randint(-6, 4),
            }
        )
    return pps


def main():
    rng = random.Random(7)
    race_day = date(2026, 10, 10)
    horses = []
    for (num, name, jockey, trainer, sire, ml), style, speed in zip(HORSES, PROFILES, SPEED):
        pps = past_performances(rng, style, speed, race_day)
        figs = [pp["speed_figure"] for pp in pps]
        starts = rng.randint(6, 14)
        wins = rng.randint(1, max(1, starts // 3))
        horses.append(
            {
                "program_number": num,
                "name": name,
                "jockey_name": jockey,
                "trainer_name": trainer,
                "morning_line_odds": ml,
                "weight": 122,
                "age": rng.randint(3, 5),
                "sex": rng.choice(["C", "G", "H"]),
                "best_speed_figure": max(figs),
                "last_speed_figure": figs[0],
                "avg_speed_figure": round(sum(figs) / len(figs)),
                "career_starts": starts,
                "career_wins": wins,
                "career_seconds": rng.randint(0, starts - wins),
                "career_thirds": rng.randint(0, 2),
                "career_earnings": float(rng.randint(40, 180) * 1000),
                "days_since_last_race": (race_day - date.fromisoformat(pps[0]["date"])).days,
                "last_race_date": pps[0]["date"],
                "last_race_finish": pps[0]["finish"],
                "sire_name": sire,
                "dam_name": "",
                "running_style": style,
                "style_confidence": 0.7,
                "past_performances": pps,
                "today_equipment": {"blinkers": rng.random() < 0.3, "lasix": True},
            }
        )
    card = {
        "note": "Synthetic demo card. All names and figures are invented.",
        "races": [
            {
                "track_code": "SMP",
                "track_name": "Sample Downs",
                "date": race_day.isoformat(),
                "race_number": 1,
                "distance": 600,
                "distance_text": "6 Furlongs",
                "surface": "D",
                "surface_description": "Dirt",
                "track_condition": "FT",
                "race_type": "ALW",
                "race_type_description": "Allowance",
                "purse": 80000.0,
                "horses": horses,
            }
        ],
    }
    OUT.write_text(json.dumps(card, indent=2) + "\n")
    print(f"wrote {OUT}")
    write_stats(rng)


def people_stats(rng, names):
    out = []
    for name in sorted(set(names)):
        starts = rng.randint(150, 600)
        wins = round(starts * rng.uniform(0.10, 0.24))
        itm = round(starts * rng.uniform(0.32, 0.50))
        out.append(
            {
                "name": name,
                "all_time_all_tracks": {
                    "starts": starts,
                    "wins": wins,
                    "win_percentage": round(100 * wins / starts, 1),
                    "itm_percentage": round(100 * itm / starts, 1),
                    "earnings": float(starts * rng.randint(3, 9) * 1000),
                },
            }
        )
    return out


def write_stats(rng):
    """Synthetic jockey/trainer stats in the StatisticsLoader format. FTS stats are empty
    because no horse on the card is a first-time starter."""
    stats = SAMPLE / "stats"
    stats.mkdir(exist_ok=True)
    files = {
        "jockey_statistics.json": {"jockeys": people_stats(rng, [h[2] for h in HORSES])},
        "trainer_statistics.json": {"trainers": people_stats(rng, [h[3] for h in HORSES])},
        "fts_trainer_statistics.json": {},
        "fts_sire_statistics.json": {},
    }
    for name, data in files.items():
        (stats / name).write_text(json.dumps(data, indent=2) + "\n")
    print(f"wrote {len(files)} stats files to {stats}")


if __name__ == "__main__":
    main()
