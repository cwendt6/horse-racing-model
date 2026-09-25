"""
Quick script to show betting recommendations
"""

import json
import sys
from pathlib import Path


def show_plays(predictions_file: str):
    """Show recommended plays from predictions"""

    with open(predictions_file, 'r') as f:
        data = json.load(f)

    print("\n" + "🏇"*35)
    print("BETTING RECOMMENDATIONS")
    print("🏇"*35 + "\n")

    for race_data in data.get('races', []):
        race_num = race_data['race_number']

        # Get top horses (not scratched)
        predictions = [p for p in race_data['predictions'] if not p.get('is_scratched')]
        predictions.sort(key=lambda p: p.get('probability', p.get('win_probability', 0)), reverse=True)

        # Get overlays
        overlays = [p for p in predictions if p.get('is_overlay')]

        if not overlays and not predictions:
            continue

        print(f"RACE {race_num}")
        print("─" * 60)

        if overlays:
            print("\n🎯 OVERLAYS (Value Bets):")
            for pred in overlays:
                overlay_pct = pred.get('overlay_percentage', 0)
                print(f"  #{pred['program_number']} {pred['name']}")
                print(f"    Win bet at {pred['live_odds']:.1f}-1 (Fair: {pred['fair_odds']:.1f}-1, +{overlay_pct:.0f}% overlay)")

        print("\n📊 Top Picks:")
        for i, pred in enumerate(predictions[:3], 1):
            ml_odds = pred.get('ml_odds', pred.get('morning_line_odds', 'N/A'))
            live_odds = pred.get('live_odds')
            if live_odds:
                odds_info = f"{live_odds:.1f}-1"
            else:
                odds_info = f"ML: {ml_odds}"
            print(f"  {i}. #{pred['program_number']} {pred['name']:20s} ({odds_info})")

        print("\n💰 Suggested Plays:")
        if overlays:
            print(f"  Win: #{overlays[0]['program_number']} ({overlays[0]['name']})")
        if len(predictions) >= 2:
            print(f"  Exacta: {predictions[0]['program_number']}-{predictions[1]['program_number']}")
            print(f"  Exacta: {predictions[1]['program_number']}-{predictions[0]['program_number']}")
        if len(predictions) >= 3:
            print(f"  Trifecta: {predictions[0]['program_number']}/{predictions[1]['program_number']},{predictions[2]['program_number']}")

        print()

    print("🏇"*35 + "\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python show_plays.py <predictions_file>")
        print("Example: python show_plays.py predictions/oct25_updated.json")
        sys.exit(1)

    show_plays(sys.argv[1])
