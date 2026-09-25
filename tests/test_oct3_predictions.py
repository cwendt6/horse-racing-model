import os
#!/usr/bin/env python3
"""
Test October 3 Predictions vs Actual Results
Uses full prediction model with all factors and optimized weights
"""

import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import json
import re
from datetime import datetime

# Import PDF parsers
from src.parsers.pdf_parser import parse_pdf_file

# Import model components
from src.data_loaders.statistics_loader import StatisticsLoader
from src.analyzers.fts_analyzer import FTSAnalyzer
from src.analyzers.pace_analyzer import PaceAnalyzer
from src.analyzers import racing_statistics as stats

# Import the prediction functions from predict_from_pdf
from scripts.predict_from_pdf import (
    load_optimized_weights,
    convert_pdf_horse_to_model_format,
    predict_race
)


def parse_results_pdf(results_pdf_path):
    """Parse the results PDF to get actual finishing order"""
    import pdfplumber

    results = {}

    with pdfplumber.open(results_pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            lines = text.split('\n')

            current_race = None

            for line in lines:
                # Look for race headers: "KEENELAND-October3,2025-Race1"
                race_match = re.search(r'KEENELAND-\w+\d+,\d{4}-Race(\d+)', line)
                if race_match:
                    current_race = int(race_match.group(1))
                    results[current_race] = []
                    continue

                # Look for horse result lines
                # Format: "LastRaced Pgm HorseName(Jockey) Wgt..."
                # Example: "28Aug255KD7 4 IndyLabel(Saez,Luis) 122..."
                if current_race and re.match(r'^\d{1,2}\w{3}\d{2}', line):
                    # Extract program number (after date, before horse name)
                    parts = line.split()
                    if len(parts) >= 3:
                        # parts[0] = date like "28Aug255KD7"
                        # parts[1] = program number like "4"
                        # parts[2] = horse name with jockey like "IndyLabel(Saez,Luis)"
                        try:
                            pgm_num = parts[1].strip()
                            horse_info = parts[2]

                            # Extract horse name (before parenthesis)
                            if '(' in horse_info:
                                horse_name = horse_info.split('(')[0]
                            else:
                                horse_name = horse_info

                            # Position is order in which they appear
                            finish_position = len(results[current_race]) + 1

                            results[current_race].append({
                                'program_number': pgm_num,
                                'horse_name': horse_name,
                                'finish_position': finish_position
                            })
                        except (ValueError, IndexError):
                            pass

    return results


def compare_predictions_to_results(predictions, actual_results):
    """Compare model predictions to actual race results"""

    if not actual_results:
        return None

    # Find winner's program number
    winner = actual_results[0]
    winner_pgm = winner['program_number']

    # Find top 3 finishers
    top_3_pgms = [r['program_number'] for r in actual_results[:3]]

    # Check if our top pick won
    top_pick = predictions[0]
    top_pick_won = top_pick['program_number'] == winner_pgm

    # Check if our top pick finished in top 3
    top_pick_in_top3 = top_pick['program_number'] in top_3_pgms

    # Find where the actual winner ranked in our predictions
    winner_rank = None
    for i, pred in enumerate(predictions, 1):
        if pred['program_number'] == winner_pgm:
            winner_rank = i
            break

    # Count how many of top 3 finishers we predicted in our top 5
    top5_predictions = set(p['program_number'] for p in predictions[:5])
    top3_in_our_top5 = sum(1 for pgm in top_3_pgms if pgm in top5_predictions)

    return {
        'winner_pgm': winner_pgm,
        'winner_name': winner['horse_name'],
        'top_pick_won': top_pick_won,
        'top_pick_in_top3': top_pick_in_top3,
        'winner_rank_in_predictions': winner_rank,
        'top_3_in_our_top_5': top3_in_our_top5,
        'top_pick': top_pick
    }


def main():
    """Main comparison script"""

    pdf_path = 'Keeneland October PPs/10-3-25-kee-ppspdf.pdf'
    results_path = 'data/October 3 Results eqbPDFChartPlus .pdf'

    print(f"\n{'='*80}")
    print(f" OCTOBER 3 MODEL PERFORMANCE TEST")
    print(f" Full Prediction Model vs Actual Results")
    print(f"{'='*80}\n")

    # Load statistics
    print(f"Loading statistics and analyzers...")
    stats_loader = StatisticsLoader(
        jockey_file='data/stats/jockey_statistics_comprehensive.json',
        trainer_file='data/stats/trainer_statistics_comprehensive.json'
    )

    fts_analyzer = FTSAnalyzer(
        trainer_stats_file='data/stats/fts_trainer_statistics.json',
        sire_stats_file='data/stats/fts_sire_statistics.json'
    )

    pace_analyzer = PaceAnalyzer()
    print(f"✓ Statistics loaded\n")

    # Parse PDF
    print(f"Parsing PDF: {pdf_path}")
    races = parse_pdf_file(pdf_path, debug=False)
    print(f"✓ Found {len(races)} races\n")

    # Parse results
    print(f"Parsing results: {results_path}")
    actual_results = parse_results_pdf(results_path)
    print(f"✓ Found results for {len(actual_results)} races\n")

    # Track overall statistics
    total_races = 0
    winners_picked = 0
    top_picks_in_top3 = 0
    total_top3_captured = 0

    print(f"{'='*80}")
    print(f" RACE-BY-RACE COMPARISON")
    print(f"{'='*80}\n")

    for race in races:
        if race.race_number not in actual_results:
            continue

        total_races += 1

        # Load optimized weights for this surface
        weights = load_optimized_weights(race.surface_description)

        # Generate predictions using full model
        result = predict_race(race, stats_loader, fts_analyzer, pace_analyzer, weights)

        if not result:
            continue

        predictions, pace_scenario = result

        # Compare to actual results
        comparison = compare_predictions_to_results(predictions, actual_results[race.race_number])

        if not comparison:
            continue

        # Update statistics
        if comparison['top_pick_won']:
            winners_picked += 1

        if comparison['top_pick_in_top3']:
            top_picks_in_top3 += 1

        total_top3_captured += comparison['top_3_in_our_top_5']

        # Print race comparison
        print(f"\n{'─'*80}")
        print(f"RACE {race.race_number}")
        print(f"{'─'*80}")

        actual_winner = comparison['winner_name']
        actual_pgm = comparison['winner_pgm']

        top_pick = comparison['top_pick']

        print(f"\n  ACTUAL WINNER: #{actual_pgm} {actual_winner}")
        print(f"  OUR TOP PICK:  #{top_pick['program_number']} {top_pick['horse_name']}")
        print(f"                 {top_pick['win_probability']*100:.1f}% win prob, {top_pick['model_odds']:.1f} model odds")

        if comparison['top_pick_won']:
            print(f"  ✅ TOP PICK WON!")
        elif comparison['top_pick_in_top3']:
            print(f"  ⚠️  Top pick finished in top 3")
        else:
            print(f"  ❌ Top pick did not win")

        if comparison['winner_rank_in_predictions']:
            print(f"\n  Actual winner ranked #{comparison['winner_rank_in_predictions']} in our predictions")
        else:
            print(f"\n  Actual winner not in our top predictions")

        print(f"  Top 3 finishers we predicted in our top 5: {comparison['top_3_in_our_top_5']}/3")

    # Print overall statistics
    print(f"\n{'='*80}")
    print(f" OVERALL PERFORMANCE")
    print(f"{'='*80}\n")

    if total_races > 0:
        win_rate = (winners_picked / total_races) * 100
        top3_rate = (top_picks_in_top3 / total_races) * 100
        avg_top3_captured = total_top3_captured / total_races

        print(f"Races Analyzed: {total_races}")
        print(f"\nWin Performance:")
        print(f"  Winners Picked: {winners_picked}/{total_races} ({win_rate:.1f}%)")
        print(f"  Top Pick in Top 3: {top_picks_in_top3}/{total_races} ({top3_rate:.1f}%)")
        print(f"  Avg Top 3 Finishers in Our Top 5: {avg_top3_captured:.1f}/3")

        # ROI calculation (simplified - assumes $2 win bet on each top pick)
        # In reality we'd need actual win payoffs
        print(f"\nEstimated ROI:")
        print(f"  Flat $2 WIN bet on top pick each race:")
        print(f"    Total wagered: ${total_races * 2}")
        print(f"    Winners: {winners_picked}")
        print(f"    (Actual ROI requires win payoff data)")

        print(f"\n{'='*80}\n")
    else:
        print(f"No races matched between predictions and results\n")


if __name__ == '__main__':
    main()
