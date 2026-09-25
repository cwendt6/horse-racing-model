"""
Value Betting Strategy Backtest

Validates value betting approach on October 2025 Keeneland data:
1. Run predictions on all races
2. Identify value bets (ML > Fair Odds)
3. Calculate ROI for value betting strategy
4. Compare to baseline (betting all top picks)

Expected Improvement:
- Baseline: 25.7% win rate, betting all top picks
- Value Strategy: Higher win rate (30%+) on value picks, fewer races
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.parsers.pdf_parser import parse_pdf_file
from src.data_loaders.statistics_loader import StatisticsLoader
from src.analyzers.fts_analyzer import FTSAnalyzer
from src.analyzers import racing_statistics as stats
from src.betting.probability_calibrator import ProbabilityCalibrator
from src.betting.value_detector import ValueDetector
from scripts.analyze_score_calibration import (
    parse_results_pdf,
    convert_horse_to_model_format,
    predict_race
)
import json
from typing import Dict, List


# October 2025 race dates
RACE_DATES = [
    ('10-3-25-kee-ppspdf.pdf', 'KEE100325USA.pdf'),
    ('10-5-25-kee-ppspdf.pdf', 'KEE100525USA.pdf'),
    ('10-8-25-kee-ppspdf.pdf', 'KEE100825USA.pdf'),
    ('10-9-25-kee-ppspdf.pdf', 'KEE100925USA.pdf'),
    ('10-10-25-kee-ppspdf.pdf', 'KEE101025USA.pdf'),
    ('10-11-25-kee-ppspdf.pdf', 'KEE101125USA.pdf'),
    ('10-12-25-kee-ppspdf.pdf', 'KEE101225USA.pdf'),
    ('10-15-25-kee-ppspdf.pdf', 'KEE101525USA.pdf'),
    ('10-16-25-kee-ppspdf.pdf', 'KEE101625USA.pdf'),
    ('10-17-25-kee-ppspdf.pdf', 'KEE101725USA.pdf'),
    ('10-18-25-kee-ppspdf.pdf', 'KEE101825USA.pdf'),
    ('10-19-25-kee-ppspdf.pdf', 'KEE101925USA.pdf'),
]


def main():
    print('='*80)
    print(' VALUE BETTING STRATEGY BACKTEST - OCTOBER 2025')
    print('='*80)
    print()

    # Initialize components
    stats_loader = StatisticsLoader(
        jockey_file='data/stats/jockey_statistics_comprehensive.json',
        trainer_file='data/stats/trainer_statistics_comprehensive.json'
    )

    fts_analyzer = FTSAnalyzer(
        trainer_stats_file='data/stats/fts_trainer_statistics.json',
        sire_stats_file='data/stats/fts_sire_statistics.json'
    )

    calibrator = ProbabilityCalibrator()
    value_detector = ValueDetector(min_edge=0.15, min_probability=0.10)

    # Load optimized weights
    with open('output/optimized_weights_october_2025.json', 'r') as f:
        weights = json.load(f)

    print(f'✓ Loaded optimized weights')
    print(f'✓ Calibrator initialized: {calibrator.get_calibration_summary()["top_pick_win_rate"]*100:.1f}% top pick win rate')
    print(f'✓ Value detector: {value_detector.min_edge*100:.0f}% min edge, {value_detector.min_probability*100:.0f}% min probability')
    print()

    # Track results for different strategies
    strategies = {
        'all_top_picks': {'bets': 0, 'wins': 0, 'roi': 0.0},
        'value_only': {'bets': 0, 'wins': 0, 'roi': 0.0},
        'value_high_conf': {'bets': 0, 'wins': 0, 'roi': 0.0},
    }

    total_races = 0
    races_with_value = 0

    for pp_date, results_file in RACE_DATES:
        pp_path = f'Keeneland October PPs/{pp_date}'
        results_path = f'data/Results Files/{results_file}'

        try:
            pp_races = parse_pdf_file(pp_path, debug=False)
            actual_results = parse_results_pdf(results_path)
        except FileNotFoundError:
            continue

        for pp_race in pp_races:
            race_num = pp_race.race_number
            total_races += 1

            # Find matching result
            matching_result = None
            for result in actual_results:
                if result['race_number'] == race_num:
                    matching_result = result
                    break

            if not matching_result:
                continue

            # Convert horses to model format
            horses_data = []
            morning_line_map = {}
            for horse in pp_race.horses:
                horse_dict = convert_horse_to_model_format(
                    horse, pp_race, stats_loader, fts_analyzer
                )
                # Store morning line separately
                ml_odds = value_detector.parse_morning_line(horse.morning_line_odds)
                morning_line_map[horse.program_number] = ml_odds
                horses_data.append(horse_dict)

            # Generate predictions
            predictions = predict_race(horses_data, pp_race, weights)

            # Add morning line odds to predictions
            for pred in predictions:
                pred['morning_line_odds'] = morning_line_map.get(pred['program_number'], 6.0)

            # Calibrate probabilities
            predictions_calibrated = calibrator.calibrate_race_probabilities(predictions)

            # Detect value bets
            value_bets = value_detector.identify_value_bets(predictions_calibrated)
            value_bets_high_conf = [vb for vb in value_bets if vb.confidence == 'HIGH']

            if value_bets:
                races_with_value += 1

            # Get actual winner
            winner_pgm = matching_result['winner_pgm']

            # Strategy 1: Bet all top picks
            top_pick = predictions_calibrated[0]
            top_pick_won = (str(top_pick['program_number']) == str(winner_pgm))

            strategies['all_top_picks']['bets'] += 1
            if top_pick_won:
                strategies['all_top_picks']['wins'] += 1
                # Assume $2 bet, get back $2 * (odds + 1)
                payout = 2.0 * (top_pick['morning_line_odds'] + 1.0)
                strategies['all_top_picks']['roi'] += payout - 2.0
            else:
                strategies['all_top_picks']['roi'] -= 2.0

            # Strategy 2: Bet value picks only
            if value_bets:
                # Bet on all value horses in this race
                for vb in value_bets:
                    strategies['value_only']['bets'] += 1
                    vb_won = (str(vb.program_number) == str(winner_pgm))

                    if vb_won:
                        strategies['value_only']['wins'] += 1
                        payout = 2.0 * (vb.morning_line_odds + 1.0)
                        strategies['value_only']['roi'] += payout - 2.0
                    else:
                        strategies['value_only']['roi'] -= 2.0

            # Strategy 3: Bet high confidence value picks only
            if value_bets_high_conf:
                for vb in value_bets_high_conf:
                    strategies['value_high_conf']['bets'] += 1
                    vb_won = (str(vb.program_number) == str(winner_pgm))

                    if vb_won:
                        strategies['value_high_conf']['wins'] += 1
                        payout = 2.0 * (vb.morning_line_odds + 1.0)
                        strategies['value_high_conf']['roi'] += payout - 2.0
                    else:
                        strategies['value_high_conf']['roi'] -= 2.0

    # Print results
    print('='*80)
    print(' BACKTEST RESULTS')
    print('='*80)
    print()
    print(f'Total Races: {total_races}')
    print(f'Races with Value Opportunities: {races_with_value} ({races_with_value/total_races*100:.1f}%)')
    print()

    print('='*80)
    print(' STRATEGY COMPARISON')
    print('='*80)
    print()

    for strategy_name, results in strategies.items():
        if results['bets'] > 0:
            win_rate = results['wins'] / results['bets']
            roi_pct = (results['roi'] / (results['bets'] * 2.0)) * 100
            roi_per_race = results['roi'] / total_races if total_races > 0 else 0

            print(f"{strategy_name.upper().replace('_', ' ')}:")
            print(f"  Total Bets: {results['bets']}")
            print(f"  Wins: {results['wins']} ({win_rate*100:.1f}% win rate)")
            print(f"  Total Wagered: ${results['bets'] * 2.0:.2f}")
            print(f"  Total Return: ${results['bets'] * 2.0 + results['roi']:.2f}")
            print(f"  Net Profit/Loss: ${results['roi']:+.2f}")
            print(f"  ROI: {roi_pct:+.1f}%")
            print(f"  Profit per Race: ${roi_per_race:+.2f}")
            print()

    # Calculate improvement
    print('='*80)
    print(' VALUE BETTING IMPACT')
    print('='*80)
    print()

    baseline_roi = strategies['all_top_picks']['roi']
    value_roi = strategies['value_only']['roi']
    improvement = value_roi - baseline_roi

    print(f"Baseline Strategy (All Top Picks):")
    print(f"  Net: ${baseline_roi:+.2f}")
    print()
    print(f"Value Betting Strategy:")
    print(f"  Net: ${value_roi:+.2f}")
    print()
    print(f"Improvement: ${improvement:+.2f} ({(improvement/abs(baseline_roi)*100):+.1f}%)")
    print()

    if strategies['value_high_conf']['bets'] > 0:
        high_conf_roi = strategies['value_high_conf']['roi']
        print(f"High Confidence Value Only:")
        print(f"  Net: ${high_conf_roi:+.2f}")
        print(f"  vs Baseline: ${high_conf_roi - baseline_roi:+.2f}")
        print()

    # Recommendations
    print('='*80)
    print(' RECOMMENDATIONS')
    print('='*80)
    print()

    best_strategy = max(strategies.items(), key=lambda x: x[1]['roi'])
    print(f"Best Strategy: {best_strategy[0].upper().replace('_', ' ')}")
    print(f"  ROI: {(best_strategy[1]['roi'] / (best_strategy[1]['bets'] * 2.0) * 100):+.1f}%")
    print(f"  Avg Profit per Bet: ${best_strategy[1]['roi'] / best_strategy[1]['bets']:+.2f}")
    print()

    if strategies['value_only']['roi'] > strategies['all_top_picks']['roi']:
        print("✓ VALUE BETTING WORKS!")
        print("  Focus on value opportunities rather than betting all races")
        print(f"  Expect to bet ~{strategies['value_only']['bets']/total_races:.1f} horses per race")
    else:
        print("⚠ Value betting didn't improve ROI in this dataset")
        print("  May need to adjust min_edge or min_probability thresholds")

    print()

    # Save results
    output_file = 'output/value_betting_backtest_results.json'
    with open(output_file, 'w') as f:
        json.dump({
            'total_races': total_races,
            'races_with_value': races_with_value,
            'strategies': strategies,
            'best_strategy': best_strategy[0],
            'improvement_vs_baseline': improvement
        }, f, indent=2)

    print(f"✓ Saved results to: {output_file}")


if __name__ == '__main__':
    main()
