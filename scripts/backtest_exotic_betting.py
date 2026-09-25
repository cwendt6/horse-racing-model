"""
Exotic Betting Strategy Backtest

Tests exacta and trifecta strategies on October 2025 Keeneland data.
Calculates actual hit rates to validate the exotic strategy.

Note: PDF results files may not contain exact exotic payoffs,
so we focus on hit rate validation. Actual payoffs would need
to be manually collected or obtained from other sources.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.parsers.pdf_parser import parse_pdf_file
from src.data_loaders.statistics_loader import StatisticsLoader
from src.analyzers.fts_analyzer import FTSAnalyzer
from src.betting.probability_calibrator import ProbabilityCalibrator
from src.betting.exotic_strategy import ExoticStrategy
from scripts.analyze_score_calibration import (
    parse_results_pdf,
    convert_horse_to_model_format,
    predict_race
)
import json
import pdfplumber
import re


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


def parse_top_finishers(results_pdf_path: str) -> list:
    """
    Parse top 3 finishers from results PDF

    Returns:
        List of dicts with race_number and finishers (top 3 program numbers)
    """
    results = []

    with pdfplumber.open(results_pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            lines = text.split('\n')

            current_race = None
            finishers = []

            for i, line in enumerate(lines):
                # Look for race header
                if 'KEENELAND' in line and 'Race' in line:
                    # Save previous race if complete
                    if current_race and len(finishers) >= 3:
                        results.append({
                            'race_number': current_race,
                            'finishers': finishers[:3]  # Top 3 only
                        })

                    race_match = re.search(r'Race(\d+)', line)
                    if race_match:
                        current_race = int(race_match.group(1))
                        finishers = []
                        continue

                # Look for finishers
                if current_race and re.match(r'^\d{1,2}[A-Z][a-z]{2}\d{2}', line):
                    parts = line.split()
                    if len(parts) >= 3:
                        try:
                            pgm_num = parts[1]
                            if pgm_num.isdigit():
                                finishers.append(pgm_num)
                        except (ValueError, IndexError):
                            continue

                # Stop collecting for this race after fractional times
                if 'FractionalTimes:' in line and current_race:
                    if len(finishers) >= 3:
                        results.append({
                            'race_number': current_race,
                            'finishers': finishers[:3]
                        })
                    current_race = None
                    finishers = []

    return results


def main():
    print('='*80)
    print(' EXOTIC BETTING STRATEGY BACKTEST - OCTOBER 2025')
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
    exotic_strategy = ExoticStrategy(base_bet=1.0)

    # Load weights
    with open('output/optimized_weights_october_2025.json', 'r') as f:
        weights = json.load(f)

    print('✓ Components initialized')
    print()

    # Track results
    total_races = 0
    exacta_attempts = {'2_box': 0, '3_box': 0, '4_box': 0}
    exacta_hits = {'2_box': 0, '3_box': 0, '4_box': 0}
    trifecta_attempts = {'3_box': 0, '4_box': 0, '5_box': 0}
    trifecta_hits = {'3_box': 0, '4_box': 0, '5_box': 0}

    for pp_date, results_file in RACE_DATES:
        pp_path = f'Keeneland October PPs/{pp_date}'
        results_path = f'data/Results Files/{results_file}'

        try:
            pp_races = parse_pdf_file(pp_path, debug=False)
            actual_results = parse_top_finishers(results_path)
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

            if not matching_result or len(matching_result['finishers']) < 3:
                continue

            # Get actual top 3 finishers
            actual_1st = matching_result['finishers'][0]
            actual_2nd = matching_result['finishers'][1]
            actual_3rd = matching_result['finishers'][2]

            # Convert horses to model format
            horses_data = []
            for horse in pp_race.horses:
                horse_dict = convert_horse_to_model_format(
                    horse, pp_race, stats_loader, fts_analyzer
                )
                horses_data.append(horse_dict)

            # Generate predictions
            predictions = predict_race(horses_data, pp_race, weights)
            predictions_calibrated = calibrator.calibrate_race_probabilities(predictions)

            # Get our top picks
            our_picks = [str(p['program_number']) for p in predictions_calibrated]

            # Test exacta strategies
            for num_picks in [2, 3, 4]:
                if len(our_picks) >= num_picks:
                    key = f'{num_picks}_box'
                    exacta_attempts[key] += 1

                    our_top_n = our_picks[:num_picks]

                    # Exacta hit: Top 2 finishers both in our picks (any order)
                    if actual_1st in our_top_n and actual_2nd in our_top_n:
                        exacta_hits[key] += 1

            # Test trifecta strategies
            for num_picks in [3, 4, 5]:
                if len(our_picks) >= num_picks:
                    key = f'{num_picks}_box'
                    trifecta_attempts[key] += 1

                    our_top_n = our_picks[:num_picks]

                    # Trifecta hit: Top 3 finishers all in our picks (any order)
                    if (actual_1st in our_top_n and
                        actual_2nd in our_top_n and
                        actual_3rd in our_top_n):
                        trifecta_hits[key] += 1

    # Print results
    print('='*80)
    print(' BACKTEST RESULTS')
    print('='*80)
    print()
    print(f'Total Races Analyzed: {total_races}')
    print()

    print('EXACTA BOX STRATEGIES:')
    print('-'*80)
    print(f"{'Strategy':<20} {'Attempts':<12} {'Hits':<8} {'Hit Rate':<12} {'Cost/Race':<12}")
    print('-'*80)

    for key in ['2_box', '3_box', '4_box']:
        if exacta_attempts[key] > 0:
            num_horses = int(key[0])
            cost_per_race = exotic_strategy.calculate_exacta_cost(num_horses, 'box')
            hit_rate = exacta_hits[key] / exacta_attempts[key]

            strategy_name = f'{num_horses}-Horse Box'
            print(f"{strategy_name:<20} {exacta_attempts[key]:<12} {exacta_hits[key]:<8} "
                  f"{hit_rate*100:>5.1f}%      ${cost_per_race:>6.2f}")

    print()
    print('TRIFECTA BOX STRATEGIES:')
    print('-'*80)
    print(f"{'Strategy':<20} {'Attempts':<12} {'Hits':<8} {'Hit Rate':<12} {'Cost/Race':<12}")
    print('-'*80)

    for key in ['3_box', '4_box', '5_box']:
        if trifecta_attempts[key] > 0:
            num_horses = int(key[0])
            cost_per_race = exotic_strategy.calculate_trifecta_cost(num_horses, 'box')
            hit_rate = trifecta_hits[key] / trifecta_attempts[key]

            strategy_name = f'{num_horses}-Horse Box'
            print(f"{strategy_name:<20} {trifecta_attempts[key]:<12} {trifecta_hits[key]:<8} "
                  f"{hit_rate*100:>5.1f}%      ${cost_per_race:>6.2f}")

    print()
    print('='*80)
    print(' KEY FINDINGS')
    print('='*80)
    print()

    # Best exacta strategy
    best_exacta_key = max(exacta_hits.keys(), key=lambda k: exacta_hits[k] / max(exacta_attempts[k], 1))
    best_exacta_rate = exacta_hits[best_exacta_key] / exacta_attempts[best_exacta_key]
    print(f"Best Exacta Strategy: {best_exacta_key.replace('_', ' ').title()}")
    print(f"  Hit Rate: {best_exacta_rate*100:.1f}%")
    print(f"  Hits: {exacta_hits[best_exacta_key]}/{exacta_attempts[best_exacta_key]}")
    print()

    # Best trifecta strategy
    best_trifecta_key = max(trifecta_hits.keys(), key=lambda k: trifecta_hits[k] / max(trifecta_attempts[k], 1))
    best_trifecta_rate = trifecta_hits[best_trifecta_key] / trifecta_attempts[best_trifecta_key]
    print(f"Best Trifecta Strategy: {best_trifecta_key.replace('_', ' ').title()}")
    print(f"  Hit Rate: {best_trifecta_rate*100:.1f}%")
    print(f"  Hits: {trifecta_hits[best_trifecta_key]}/{trifecta_attempts[best_trifecta_key]}")
    print()

    # Estimated ROI (using typical payoffs)
    print('='*80)
    print(' ESTIMATED ROI (Using Typical Payoffs)')
    print('='*80)
    print()
    print('NOTE: Actual exotic payoffs vary widely. These are conservative estimates.')
    print()

    # Exacta 3-box estimation
    if exacta_attempts['3_box'] > 0:
        exacta_3_rate = exacta_hits['3_box'] / exacta_attempts['3_box']
        exacta_3_cost = exotic_strategy.calculate_exacta_cost(3, 'box')
        # Conservative avg exacta with favorites: $40
        avg_exacta_payout = 40.0
        exacta_3_roi = ((exacta_3_rate * avg_exacta_payout) - exacta_3_cost) / exacta_3_cost * 100

        print(f"3-Horse Exacta Box:")
        print(f"  Cost: ${exacta_3_cost:.2f}/race")
        print(f"  Hit Rate: {exacta_3_rate*100:.1f}%")
        print(f"  Avg Payout (est): ${avg_exacta_payout:.2f}")
        print(f"  Expected ROI: {exacta_3_roi:+.1f}%")
        print()

    # Trifecta 4-box estimation
    if trifecta_attempts['4_box'] > 0:
        trifecta_4_rate = trifecta_hits['4_box'] / trifecta_attempts['4_box']
        trifecta_4_cost = exotic_strategy.calculate_trifecta_cost(4, 'box')
        # Conservative avg trifecta with favorites: $120
        avg_trifecta_payout = 120.0
        trifecta_4_roi = ((trifecta_4_rate * avg_trifecta_payout) - trifecta_4_cost) / trifecta_4_cost * 100

        print(f"4-Horse Trifecta Box:")
        print(f"  Cost: ${trifecta_4_cost:.2f}/race")
        print(f"  Hit Rate: {trifecta_4_rate*100:.1f}%")
        print(f"  Avg Payout (est): ${avg_trifecta_payout:.2f}")
        print(f"  Expected ROI: {trifecta_4_roi:+.1f}%")
        print()

    # Save results
    output_data = {
        'total_races': total_races,
        'exacta_strategies': {
            k: {
                'attempts': exacta_attempts[k],
                'hits': exacta_hits[k],
                'hit_rate': exacta_hits[k] / exacta_attempts[k] if exacta_attempts[k] > 0 else 0
            }
            for k in exacta_attempts.keys()
        },
        'trifecta_strategies': {
            k: {
                'attempts': trifecta_attempts[k],
                'hits': trifecta_hits[k],
                'hit_rate': trifecta_hits[k] / trifecta_attempts[k] if trifecta_attempts[k] > 0 else 0
            }
            for k in trifecta_attempts.keys()
        }
    }

    output_file = 'output/exotic_betting_backtest_results.json'
    with open(output_file, 'w') as f:
        json.dump(output_data, f, indent=2)

    print(f"✓ Saved results to: {output_file}")
    print()


if __name__ == '__main__':
    main()
