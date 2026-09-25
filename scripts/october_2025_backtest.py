#!/usr/bin/env python3
"""
October 2025 Full Backtest with Longshot Detection
====================================================
Runs predictions on all October 2025 Keeneland races and validates against actual results.
Includes pace analysis and longshot detection.
"""

import sys
import os
import re
import json
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, project_root)

# Import the main prediction function from predict_from_pdf
from scripts.predict_from_pdf import predict_race, load_optimized_weights

# Import parsers and analyzers
from src.parsers.hybrid_parser_v3 import parse_pdf_hybrid_v3
from src.data_loaders.statistics_loader import StatisticsLoader
from src.analyzers.fts_analyzer import FTSAnalyzer
from src.analyzers.pace_analyzer import PaceAnalyzer

import pdfplumber

# Race dates with both PPs and Results
RACE_DATES = [
    '10-03-25',
    '10-05-25',  # Skip 10-04 (results only, no PPs)
    '10-08-25',
    '10-09-25',
    '10-10-25',
    '10-11-25',
    '10-12-25',
    '10-15-25',
    '10-16-25',
    '10-17-25',
    '10-18-25',
    '10-19-25',
]

def extract_winners_from_results_pdf(results_pdf_path):
    """Extract winner information from Equibase results PDF including ML odds."""
    winners = []

    with pdfplumber.open(results_pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue

            # Look for race headers: "KEENELAND-OctoberXX,2025-RaceN" (no spaces!)
            race_pattern = r'KEENELAND.*?October\d+,2025.*?Race(\d+)'
            race_match = re.search(race_pattern, text)
            if not race_match:
                continue

            race_num = int(race_match.group(1))

            # Extract winner line: "Winner: Horse Name, ..."
            winner_pattern = r'Winner:\s+([^,]+),'
            winner_match = re.search(winner_pattern, text)
            if winner_match:
                horse_name = winner_match.group(1).strip()
            else:
                continue

            # Extract pgm number and ML odds from results table
            # Pattern: Pgm number appears early in the results table
            pgm_pattern = r'Pgm\s+Horse.*?\n(\d+)\s+' + re.escape(horse_name)
            pgm_match = re.search(pgm_pattern, text, re.IGNORECASE)

            if pgm_match:
                pgm_num = pgm_match.group(1)
            else:
                # Try alternative: look in Past Performance Running Line Preview
                preview_pattern = r'(\d+)\s+' + re.escape(horse_name) + r'\s+\d+\s+\d'
                preview_match = re.search(preview_pattern, text)
                if preview_match:
                    pgm_num = preview_match.group(1)
                else:
                    pgm_num = '?'

            # Extract ML odds from finish line
            # Pattern: "Pgm Horse Name ... Fin Odds"
            # Look for winner's line in results table
            ml_odds = None
            for line in text.split('\n'):
                # Match: "PgmNum HorseName ... 1 OddsValue"
                if horse_name in line and re.search(r'\s1\s+[\d\.]+\s*$', line):
                    # Extract the last number (odds)
                    odds_match = re.search(r'\s1\s+([\d\.]+)\s*$', line)
                    if odds_match:
                        try:
                            ml_odds = float(odds_match.group(1))
                        except ValueError:
                            pass
                    break

            winners.append({
                'race': race_num,
                'pgm': pgm_num,
                'name': horse_name,
                'ml_odds': ml_odds
            })

    return winners


def run_predictions_for_date(pp_pdf_path, stats_loader, fts_analyzer, pace_analyzer, enhanced_pace_analyzer, track_bias_detector, jockey_trainer_analyzer, distance_surface_analyzer, weights):
    """Run predictions on a single PP PDF."""
    try:
        # Parse PDF
        races = parse_pdf_hybrid_v3(pp_pdf_path, debug=False)

        all_predictions = []

        for race in races:
            # Run prediction using the main predict_race function
            result = predict_race(
                race, stats_loader, fts_analyzer, pace_analyzer, enhanced_pace_analyzer,
                track_bias_detector, jockey_trainer_analyzer, distance_surface_analyzer, weights
            )

            # Unpack result - predict_race returns (predictions, pace_scenario, value_bets)
            if isinstance(result, tuple):
                predictions, pace_scenario, value_bets = result
            else:
                # Newer version returns dict
                predictions = result['predictions']
                pace_scenario = result.get('pace_scenario')
                value_bets = result.get('value_bets', [])

            if not predictions:
                continue

            # Extract top 5 for backtest
            top_5 = []
            for pred in predictions[:5]:
                top_5.append({
                    'pgm': pred['program_number'],
                    'name': pred['name'],  # Use 'name' not 'horse_name'
                    'prob': pred.get('probability', pred.get('win_probability', 0.0)),  # Handle both keys
                    'running_style': pred['running_style']
                })

            # Get pace scenario info (handle both object and string formats)
            if hasattr(pace_scenario, 'scenario_type'):
                pace_scenario_str = pace_scenario.scenario_type
                pace_advantage = pace_scenario.advantage_horses
            else:
                pace_scenario_str = str(pace_scenario) if pace_scenario else "Unknown"
                pace_advantage = []

            all_predictions.append({
                'race': race.race_number,
                'distance': race.distance_text,
                'surface': race.surface_description,
                'pace_scenario': pace_scenario_str,
                'pace_advantage_horses': pace_advantage,
                'top_5': top_5
            })

        return all_predictions

    except Exception as e:
        print(f"  ❌ ERROR parsing {pp_pdf_path}: {e}")
        import traceback
        traceback.print_exc()
        return []


def main():
    """Run full October 2025 backtest."""

    print()
    print("="*80)
    print(" OCTOBER 2025 FULL BACKTEST")
    print("="*80)
    print()

    # Load stats, analyzers, and weights (only once)
    print("📚 Loading statistics databases...")
    stats_loader = StatisticsLoader(
        jockey_file='data/stats/jockey_statistics_comprehensive.json',
        trainer_file='data/stats/trainer_statistics_comprehensive.json'
    )

    print("🔧 Initializing analyzers...")
    fts_analyzer = FTSAnalyzer(
        trainer_stats_file='data/stats/fts_trainer_statistics.json',
        sire_stats_file='data/stats/fts_sire_statistics.json'
    )
    pace_analyzer = PaceAnalyzer()

    # NEW: Enhanced pace analyzer
    from src.analyzers.pace_analyzer_enhanced import EnhancedPaceAnalyzer
    enhanced_pace_analyzer = EnhancedPaceAnalyzer(
        track_variants_file='data/track_variants.json'
    )

    # NEW: Track bias detector
    from src.analyzers.track_bias_detector import TrackBiasDetector
    track_bias_detector = TrackBiasDetector()

    # NEW: Jockey-trainer analyzer
    from src.analyzers.jockey_trainer_analyzer import JockeyTrainerAnalyzer
    jockey_trainer_analyzer = JockeyTrainerAnalyzer()

    # NEW: Distance/surface analyzer
    from src.analyzers.distance_surface_analyzer import DistanceSurfaceAnalyzer
    distance_surface_analyzer = DistanceSurfaceAnalyzer()

    print("⚖️  Loading optimized weights...")
    weights = load_optimized_weights('dirt')

    all_results = []

    for date in RACE_DATES:
        print(f"\n📅 Processing {date}...")

        # Paths
        pp_path = f"Keeneland October PPs/{date}-kee-ppspdf.pdf"
        results_path_str = date.replace('-', '')  # "10-03-25" → "100325"
        results_path = f"data/Results Files/KEE{results_path_str}USA.pdf"

        # Check files exist
        if not os.path.exists(pp_path):
            print(f"  ⚠️  Missing PP file: {pp_path}")
            continue

        if not os.path.exists(results_path):
            print(f"  ⚠️  Missing results file: {results_path}")
            continue

        # Extract actual winners
        print(f"  📊 Extracting winners from {results_path}...")
        winners = extract_winners_from_results_pdf(results_path)
        print(f"  ✓ Found {len(winners)} races with winners")

        # Run predictions
        print(f"  🔮 Running predictions on {pp_path}...")
        predictions = run_predictions_for_date(
            pp_path, stats_loader, fts_analyzer, pace_analyzer, enhanced_pace_analyzer,
            track_bias_detector, jockey_trainer_analyzer, distance_surface_analyzer, weights
        )
        print(f"  ✓ Generated predictions for {len(predictions)} races")

        # Match predictions to winners
        for winner in winners:
            race_num = winner['race']

            # Find matching prediction
            pred = next((p for p in predictions if p['race'] == race_num), None)

            if not pred:
                print(f"  ⚠️  No prediction for Race {race_num}")
                continue

            # Check if winner is in our top 5
            top_pick = pred['top_5'][0] if pred['top_5'] else None
            top_3_pgms = [h['pgm'] for h in pred['top_5'][:3]]
            top_5_pgms = [h['pgm'] for h in pred['top_5'][:5]]

            winner_pgm = winner['pgm']

            win_hit = (top_pick and top_pick['pgm'] == winner_pgm)
            top3_hit = winner_pgm in top_3_pgms
            top5_hit = winner_pgm in top_5_pgms

            # Pace analysis validation
            pace_correct = False
            if pred['pace_advantage_horses']:
                # Check if winner was in pace advantage list
                for adv_horse in pred['pace_advantage_horses']:
                    if winner['name'].lower() in adv_horse.lower():
                        pace_correct = True
                        break

            # Longshot detection
            ml_odds = winner.get('ml_odds')
            is_longshot = (ml_odds is not None and ml_odds >= 10.0)
            longshot_detected = (is_longshot and top5_hit)

            all_results.append({
                'date': date,
                'race': race_num,
                'winner_pgm': winner_pgm,
                'winner_name': winner['name'],
                'winner_ml_odds': ml_odds,
                'is_longshot': is_longshot,
                'longshot_detected': longshot_detected,
                'top_pick_pgm': top_pick['pgm'] if top_pick else '?',
                'top_pick_name': top_pick['name'] if top_pick else '?',
                'win_hit': win_hit,
                'top3_hit': top3_hit,
                'top5_hit': top5_hit,
                'pace_scenario': pred['pace_scenario'],
                'pace_correct': pace_correct,
                'top_5': pred['top_5']
            })

    # Calculate aggregate statistics
    print()
    print("="*80)
    print(" AGGREGATE RESULTS")
    print("="*80)
    print()

    total_races = len(all_results)
    win_hits = sum(1 for r in all_results if r['win_hit'])
    top3_hits = sum(1 for r in all_results if r['top3_hit'])
    top5_hits = sum(1 for r in all_results if r['top5_hit'])
    pace_correct = sum(1 for r in all_results if r['pace_correct'])

    # Longshot statistics
    longshot_wins = sum(1 for r in all_results if r['is_longshot'])
    longshots_detected = sum(1 for r in all_results if r['longshot_detected'])

    print(f"Total Races: {total_races}")
    print()
    print(f"Win Rate (Top Pick): {win_hits}/{total_races} = {win_hits/total_races*100:.1f}%")
    print(f"Top-3 Hit Rate:      {top3_hits}/{total_races} = {top3_hits/total_races*100:.1f}%")
    print(f"Top-5 Hit Rate:      {top5_hits}/{total_races} = {top5_hits/total_races*100:.1f}%")
    print()
    print(f"Pace Analysis Accuracy: {pace_correct}/{total_races} = {pace_correct/total_races*100:.1f}%")
    print()
    print(f"Longshot Wins (10-1+):  {longshot_wins}/{total_races} = {longshot_wins/total_races*100:.1f}%")
    print(f"Longshots Detected:     {longshots_detected}/{longshot_wins} = {longshots_detected/longshot_wins*100:.1f}%" if longshot_wins > 0 else "Longshots Detected:     N/A (no longshot wins)")
    print()

    # Pace scenario breakdown
    print("="*80)
    print(" PACE ANALYSIS BREAKDOWN")
    print("="*80)
    print()

    pace_scenarios = {}
    for result in all_results:
        scenario = result['pace_scenario']
        if scenario not in pace_scenarios:
            pace_scenarios[scenario] = {'total': 0, 'correct': 0}

        pace_scenarios[scenario]['total'] += 1
        if result['pace_correct']:
            pace_scenarios[scenario]['correct'] += 1

    for scenario, stats in sorted(pace_scenarios.items()):
        total = stats['total']
        correct = stats['correct']
        pct = correct / total * 100 if total > 0 else 0
        print(f"{scenario:20s}: {correct:2d}/{total:2d} = {pct:5.1f}%")

    # Save detailed results
    output_file = 'output/october_2025_backtest_results.json'
    os.makedirs('output', exist_ok=True)
    with open(output_file, 'w') as f:
        json.dump({
            'summary': {
                'total_races': total_races,
                'win_rate': f"{win_hits/total_races*100:.1f}%",
                'top3_rate': f"{top3_hits/total_races*100:.1f}%",
                'top5_rate': f"{top5_hits/total_races*100:.1f}%",
                'pace_accuracy': f"{pace_correct/total_races*100:.1f}%",
                'longshot_win_rate': f"{longshot_wins/total_races*100:.1f}%",
                'longshot_detection_rate': f"{longshots_detected/longshot_wins*100:.1f}%" if longshot_wins > 0 else "N/A"
            },
            'pace_scenarios': pace_scenarios,
            'detailed_results': all_results
        }, f, indent=2)

    print()
    print(f"✓ Detailed results saved to: {output_file}")
    print()

    # Print race-by-race for review
    print("="*80)
    print(" RACE-BY-RACE RESULTS")
    print("="*80)
    print()

    for result in all_results:
        status = "✅ WIN" if result['win_hit'] else ("📊 TOP-3" if result['top3_hit'] else ("🔶 TOP-5" if result['top5_hit'] else "❌ MISS"))
        pace_status = "✓" if result['pace_correct'] else "✗"

        # Longshot indicator
        longshot_indicator = ""
        if result['is_longshot']:
            odds_str = f"{result['winner_ml_odds']:.2f}" if result['winner_ml_odds'] else "???"
            if result['longshot_detected']:
                longshot_indicator = f" 🎯 LONGSHOT ({odds_str}-1) DETECTED!"
            else:
                longshot_indicator = f" 💥 LONGSHOT ({odds_str}-1) MISSED"

        print(f"{result['date']} R{result['race']:2d}: {status}{longshot_indicator}")
        print(f"  Winner: #{result['winner_pgm']:>2} {result['winner_name']}")
        print(f"  Our Pick: #{result['top_pick_pgm']:>2} {result['top_pick_name']}")
        print(f"  Pace: {result['pace_scenario']} [{pace_status}]")
        print()

    print("="*80)
    print(" BACKTEST COMPLETE")
    print("="*80)


if __name__ == '__main__':
    main()
