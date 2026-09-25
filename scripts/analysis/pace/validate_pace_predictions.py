#!/usr/bin/env python3
"""
Pace Prediction Validation
Compares predicted pace scenarios and fractional times vs actual race results
"""

import sys
import os
import re
import json
from pathlib import Path
from datetime import datetime

project_root = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, project_root)

import pdfplumber

from scripts.predict_from_pdf import predict_race, load_optimized_weights
from src.parsers.hybrid_parser_v3 import parse_pdf_hybrid_v3
from src.data_loaders.statistics_loader import StatisticsLoader
from src.analyzers.fts_analyzer import FTSAnalyzer
from src.analyzers.pace_analyzer import PaceAnalyzer
from src.analyzers.pace_analyzer_enhanced import EnhancedPaceAnalyzer
from src.analyzers.track_bias_detector import TrackBiasDetector
from src.analyzers.jockey_trainer_analyzer import JockeyTrainerAnalyzer
from src.analyzers.distance_surface_analyzer import DistanceSurfaceAnalyzer


def extract_actual_race_data(results_pdf_path):
    """Extract actual fractional times and running positions from results PDF"""
    race_data = {}

    with pdfplumber.open(results_pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue

            # Look for race headers
            race_pattern = r'KEENELAND.*?October\d+,2025.*?Race(\d+)'
            race_match = re.search(race_pattern, text)
            if not race_match:
                continue

            race_num = int(race_match.group(1))

            # Extract fractional times
            # Format: "FractionalTimes:23.54 47.54 1:12.38 1:38.06 FinalTime:1:44.80"
            frac_pattern = r'FractionalTimes:([\d\.:]+)\s+([\d\.:]+)\s+([\d\.:]+)\s+([\d\.:]+)\s+FinalTime:([\d\.:]+)'
            frac_match = re.search(frac_pattern, text)

            actual_fractions = []
            final_time = None

            if frac_match:
                # Parse fractional times
                quarter = frac_match.group(1)
                half = frac_match.group(2)
                six_f = frac_match.group(3)
                mile = frac_match.group(4)
                final = frac_match.group(5)

                actual_fractions = [quarter, half, six_f, mile]
                final_time = final

            # Extract running positions from Past Performance Running Line Preview
            # Format: "10 CriticalThreat 9 21/2 21/2 11 11/2 1Neck"
            horse_positions = {}
            lines = text.split('\n')
            in_pp_preview = False

            for line in lines:
                if 'PastPerformanceRunningLinePreview' in line:
                    in_pp_preview = True
                    continue

                if in_pp_preview and 'Trainers:' in line:
                    break

                if in_pp_preview and line.strip():
                    # Parse: "Pgm HorseName Start 1/4 1/2 3/4 Str Fin"
                    match = re.search(r'^\s*(\d+)\s+([A-Z][a-zA-Z]+(?:[A-Z][a-z]+)?)\s+(\d+)\s+(.+)', line)
                    if match:
                        pgm = match.group(1)
                        horse_name = match.group(2)
                        start_pos = match.group(3)
                        positions_str = match.group(4).strip()

                        # Extract positions (handle fractions like "21/2")
                        # Pattern: capture position numbers with optional fractions
                        pos_pattern = r'(\d+)(?:[¸º¹»¼½¾¿£¡¬«­®¯°±²³´µ¶·/\d]*)'
                        positions = re.findall(pos_pattern, positions_str)

                        if len(positions) >= 5:  # Should have 1/4, 1/2, 3/4, Str, Fin
                            horse_positions[horse_name] = {
                                'pgm': pgm,
                                'start': start_pos,
                                'quarter': positions[0],
                                'half': positions[1],
                                'six_f': positions[2],
                                'stretch': positions[3],
                                'finish': positions[4]
                            }

            if actual_fractions or horse_positions:
                race_data[race_num] = {
                    'fractional_times': actual_fractions,
                    'final_time': final_time,
                    'horse_positions': horse_positions
                }

    return race_data


def parse_time_to_seconds(time_str):
    """Convert time string to seconds (e.g., '1:44.80' -> 104.80)"""
    if ':' in time_str:
        parts = time_str.split(':')
        if len(parts) == 2:
            minutes = int(parts[0])
            seconds = float(parts[1])
            return minutes * 60 + seconds
    return float(time_str)


def analyze_pace_accuracy(date_str, pp_path, results_path, predictions_data):
    """Compare predicted pace vs actual race dynamics"""

    print(f"\n{'='*80}")
    print(f" PACE VALIDATION - {date_str}")
    print(f"{'='*80}\n")

    if not os.path.exists(results_path):
        print(f"⚠️ Results not found")
        return None

    # Extract actual race data
    actual_data = extract_actual_race_data(results_path)

    if not actual_data:
        print(f"⚠️ Could not extract race data from results")
        return None

    validation_results = []

    for race_num, actual in actual_data.items():
        # Find matching prediction
        pred_race = next((r for r in predictions_data if r['race'] == race_num), None)

        if not pred_race:
            continue

        print(f"\n{'─'*80}")
        print(f"RACE {race_num}")
        print(f"{'─'*80}")

        # Compare pace scenario
        predicted_scenario = pred_race.get('pace_scenario', 'Unknown')
        print(f"\nPredicted Pace Scenario: {predicted_scenario}")

        # Analyze actual running positions
        positions = actual['horse_positions']

        if positions:
            # Count horses by position at each call
            early_leaders = []  # Horses in top 3 at quarter
            closers = []  # Horses who improved 3+ positions from start to finish
            burners = []  # Horses who faded 3+ positions from early to finish

            for horse_name, pos_data in positions.items():
                try:
                    start_pos = int(pos_data['start'])
                    quarter_pos = int(pos_data['quarter'])
                    finish_pos = int(pos_data['finish'])

                    # Early leaders
                    if quarter_pos <= 3:
                        early_leaders.append(horse_name)

                    # Closers (improved)
                    if start_pos - finish_pos >= 3:
                        closers.append((horse_name, start_pos, finish_pos))

                    # Burners (faded)
                    if finish_pos - quarter_pos >= 3:
                        burners.append((horse_name, quarter_pos, finish_pos))

                except ValueError:
                    continue

            print(f"\nActual Pace Dynamics:")
            print(f"  Early leaders (1-3 at 1/4): {len(early_leaders)} horses")
            if early_leaders:
                print(f"    {', '.join(early_leaders[:5])}")

            if closers:
                print(f"\n  Closers (improved 3+ positions):")
                for horse, start, finish in closers[:3]:
                    print(f"    {horse}: {start} → {finish}")

            if burners:
                print(f"\n  ⚠️  Burners (faded 3+ positions from early pace):")
                for horse, early, finish in burners[:3]:
                    print(f"    {horse}: {early} at 1/4 → {finish} finish (ran out of gas)")

            # Validate pace scenario prediction
            pace_validation = ""
            if predicted_scenario == "SPEED_DUEL" and len(early_leaders) >= 3:
                pace_validation = "✅ CORRECT: Speed duel materialized"
            elif predicted_scenario == "LONE_SPEED" and len(early_leaders) <= 1:
                pace_validation = "✅ CORRECT: Lone speed scenario"
            elif predicted_scenario == "HONEST_PACE" and 2 <= len(early_leaders) <= 3:
                pace_validation = "✅ CORRECT: Honest pace"
            elif predicted_scenario == "NO_SPEED" and len(closers) >= 2:
                pace_validation = "✅ CORRECT: Closers had advantage"
            else:
                pace_validation = "⚠️ MISMATCH: Actual dynamics differed"

            print(f"\n{pace_validation}")

        # Compare fractional times (if available)
        actual_fractions = actual.get('fractional_times', [])
        if actual_fractions and len(actual_fractions) >= 2:
            print(f"\nActual Fractional Times:")
            print(f"  Quarter: {actual_fractions[0]}")
            print(f"  Half: {actual_fractions[1]}")
            if len(actual_fractions) >= 3:
                print(f"  Six furlongs: {actual_fractions[2]}")

            # TODO: Compare to predicted fractions once we store them
            # For now, just show actual times

        validation_results.append({
            'race': race_num,
            'predicted_scenario': predicted_scenario,
            'early_leaders_count': len(early_leaders),
            'closers_count': len(closers),
            'burners_count': len(burners),
            'pace_validation': pace_validation,
            'actual_fractions': actual_fractions,
            'final_time': actual.get('final_time')
        })

    return validation_results


def main():
    """Run pace validation for October 2025"""

    print("\n" + "="*80)
    print(" PACE PREDICTION VALIDATION - OCTOBER 2025")
    print("="*80)

    # Load backtest results (contains our predictions)
    backtest_file = 'output/october_2025_backtest_results.json'
    if not os.path.exists(backtest_file):
        print(f"❌ Backtest results not found: {backtest_file}")
        return

    with open(backtest_file, 'r') as f:
        backtest_data = json.load(f)

    predictions = backtest_data['detailed_results']

    # Analyze specific dates
    dates = ['10-18-25', '10-19-25']  # Start with these two

    all_validations = []

    for date in dates:
        pp_path = f"Keeneland October PPs/{date}-kee-ppspdf.pdf"
        results_path_str = date.replace('-', '')
        results_path = f"data/Results Files/KEE{results_path_str}USA.pdf"

        # Group predictions by date
        date_predictions = [p for p in predictions if p['date'] == date]

        validation = analyze_pace_accuracy(date, pp_path, results_path, date_predictions)

        if validation:
            all_validations.extend(validation)

    # Summary statistics
    print(f"\n{'='*80}")
    print(" SUMMARY")
    print(f"{'='*80}\n")

    if all_validations:
        correct = sum(1 for v in all_validations if '✅' in v['pace_validation'])
        total = len(all_validations)

        print(f"Races analyzed: {total}")
        print(f"Pace scenarios correct: {correct}/{total} = {correct/total*100:.1f}%")

        # Average early pace pressure
        avg_early_leaders = sum(v['early_leaders_count'] for v in all_validations) / len(all_validations)
        print(f"\nAverage early leaders (top 3 at 1/4): {avg_early_leaders:.1f}")

        print(f"\nClosers won: {sum(1 for v in all_validations if v['closers_count'] > 0)}/{total} races")
        print(f"Burners (horses that faded): {sum(v['burners_count'] for v in all_validations)} horses total")

    # Save results
    output_file = 'output/pace_validation_results.json'
    with open(output_file, 'w') as f:
        json.dump({
            'date_analyzed': datetime.now().isoformat(),
            'races_validated': len(all_validations),
            'validations': all_validations
        }, f, indent=2)

    print(f"\n✓ Detailed validation saved to: {output_file}")
    print()


if __name__ == '__main__':
    main()
