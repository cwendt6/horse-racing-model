#!/usr/bin/env python3
"""
Track Bias Backtest - October 2025

Compares model performance with and without track bias adjustments
to validate that bias detection improves prediction accuracy.

Tests:
1. Baseline (no bias) - current performance
2. With bias adjustments - expected improvement
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.parsers.pdf_parser import parse_pdf_file
from src.data_loaders.statistics_loader import StatisticsLoader
from src.analyzers.fts_analyzer import FTSAnalyzer
from src.analyzers import racing_statistics as stats
from src.analyzers.track_bias_detector import TrackBiasDetector, apply_track_biases_to_scores
import json
from typing import Dict, List
from pathlib import Path
import pdfplumber
import re
from datetime import datetime

# October 2025 race dates
RACE_DATES = [
    ('10-3-25', 'KEE100325USA.pdf'),
    ('10-5-25', 'KEE100525USA.pdf'),
    ('10-8-25', 'KEE100825USA.pdf'),
    ('10-9-25', 'KEE100925USA.pdf'),
    ('10-10-25', 'KEE101025USA.pdf'),
    ('10-11-25', 'KEE101125USA.pdf'),
    ('10-12-25', 'KEE101225USA.pdf'),
    ('10-15-25', 'KEE101525USA.pdf'),
    ('10-16-25', 'KEE101625USA.pdf'),
    ('10-17-25', 'KEE101725USA.pdf'),
    ('10-18-25', 'KEE101825USA.pdf'),
    ('10-19-25', 'KEE101925USA.pdf'),
]


def parse_results_pdf(results_pdf_path: str) -> List[Dict]:
    """Parse results PDF to get actual winners"""
    results = []

    with pdfplumber.open(results_pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            lines = text.split('\n')

            current_race = None

            for i, line in enumerate(lines):
                # Look for race header
                if 'KEENELAND' in line and 'Race' in line:
                    race_match = re.search(r'Race(\d+)', line)
                    if race_match:
                        current_race = int(race_match.group(1))
                        continue

                # Look for winner (first finisher)
                if current_race and re.match(r'^\d{1,2}[A-Z][a-z]{2}\d{2}', line):
                    parts = line.split()
                    if len(parts) >= 3:
                        try:
                            winner_pgm = parts[1]
                            if winner_pgm.isdigit():
                                results.append({
                                    'race_number': current_race,
                                    'winner_pgm': winner_pgm
                                })
                                current_race = None
                        except (ValueError, IndexError):
                            continue

    return results


def convert_horse_to_model_format(horse, race, stats_loader, fts_analyzer):
    """Convert PDF horse data to model input format"""
    days_since_last = 999
    if horse.last_race_date:
        try:
            last_race = datetime.strptime(horse.last_race_date, '%Y-%m-%d')
            race_date = datetime.strptime(race.date, '%Y-%m-%d')
            days_since_last = (race_date - last_race).days
        except:
            pass

    # Get stats
    trainer_stats = stats_loader.get_trainer_stats(horse.trainer_name)
    jockey_stats = stats_loader.get_jockey_stats(horse.jockey_name)

    # FTS check
    fts_data = {'is_fts': horse.career_starts == 0, 'advantage': 0.0}
    if fts_data['is_fts']:
        fts_multiplier, _ = fts_analyzer.calculate_fts_multiplier(
            trainer_name=horse.trainer_name,
            sire_name=horse.sire_name
        )
        fts_data['advantage'] = fts_multiplier - 1.0

    # Recent finishes
    recent_finishes = []
    if horse.past_performances:
        recent_finishes = [pp['finish'] for pp in horse.past_performances[:5] if 'finish' in pp]

    return {
        'name': horse.name,
        'program_number': horse.program_number,
        'trainer_name': horse.trainer_name,
        'jockey_name': horse.jockey_name,
        'best_beyer': horse.best_speed_figure if horse.best_speed_figure > 0 else 70,
        'last_beyer': horse.last_speed_figure if horse.last_speed_figure > 0 else 70,
        'avg_beyer': horse.avg_speed_figure if horse.avg_speed_figure > 0 else 70,
        'career_starts': horse.career_starts if horse.career_starts > 0 else 10,
        'career_wins': horse.career_wins,
        'career_earnings': horse.career_earnings if horse.career_earnings > 0 else 50000,
        'recent_finishes': recent_finishes,
        'days_since_last_race': days_since_last,
        'running_style': horse.running_style,
        'past_performances': horse.past_performances if horse.past_performances else [],
        'jockey_win_pct': jockey_stats.win_percentage / 100.0 if jockey_stats else 0.15,
        'trainer_win_pct': trainer_stats.win_percentage / 100.0 if trainer_stats else 0.15,
        'is_fts': fts_data['is_fts'],
        'fts_advantage': fts_data['advantage'],
    }


def predict_race(horses_data, race, weights, bias_detector=None, apply_bias=False):
    """
    Generate predictions for a race

    Args:
        horses_data: List of horse data dicts
        race: Race object
        weights: Component weights dict
        bias_detector: TrackBiasDetector instance (optional)
        apply_bias: Whether to apply bias adjustments

    Returns:
        List of predictions sorted by score
    """
    predictions = []

    for horse_data in horses_data:
        # Build race_data
        race_data = {
            'date': race.date,
            'distance': race.distance_text,
            'surface': race.surface_description.lower(),
            'track_condition': race.track_condition,
            'purse': race.purse if race.purse > 0 else 50000,
            'field_size': len(horses_data),
            'avg_beyer': 70,
        }

        # Calculate base scores
        score_dict = stats.calculate_comprehensive_score(horse_data, race_data)

        # Apply track bias adjustments if requested
        if apply_bias and bias_detector:
            apply_track_biases_to_scores(score_dict, horse_data, race_data, bias_detector)

        # Combine with weights
        final_score = (
            score_dict.speed * weights['speed'] +
            score_dict.form * weights['form'] +
            score_dict.class_rating * weights['class'] +
            score_dict.pace * weights['pace'] +
            score_dict.recency * weights['recency'] +
            score_dict.progression * weights['progression'] +
            score_dict.jockey * weights['jockey'] +
            score_dict.trainer * weights['trainer'] +
            score_dict.post * weights['post']
        )

        predictions.append({
            'program_number': horse_data['program_number'],
            'name': horse_data['name'],
            'score': final_score,
        })

    # Sort by score descending
    predictions.sort(key=lambda x: x['score'], reverse=True)

    # Add ranks
    for i, pred in enumerate(predictions, 1):
        pred['rank'] = i

    return predictions


def main():
    print('='*80)
    print(' TRACK BIAS BACKTEST - OCTOBER 2025')
    print('='*80)
    print()
    print('Comparing model performance with and without track bias adjustments')
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

    # Initialize track bias detector
    bias_detector = TrackBiasDetector(
        bias_data_file='output/track_bias_analysis_october_2025.json'
    )

    # Load optimized weights
    weights_path = 'output/optimized_weights_october_2025.json'
    with open(weights_path, 'r') as f:
        weights = json.load(f)

    print('✓ Components initialized')
    print()

    # Show bias summary
    bias_detector.print_bias_report('KEE')
    print()

    # Track results for both approaches
    results_baseline = {'total_races': 0, 'top_pick_wins': 0, 'top3_hits': 0}
    results_with_bias = {'total_races': 0, 'top_pick_wins': 0, 'top3_hits': 0}

    # Track rank distributions
    baseline_winner_ranks = []
    bias_winner_ranks = []

    print('='*80)
    print(' RUNNING BACKTEST')
    print('='*80)
    print()

    for pp_date, results_file in RACE_DATES:
        pp_path = f'Keeneland October PPs/{pp_date}-kee-ppspdf.pdf'
        results_path = f'data/Results Files/{results_file}'

        try:
            pp_races = parse_pdf_file(pp_path, debug=False)
            actual_results = parse_results_pdf(results_path)
        except FileNotFoundError:
            continue

        for pp_race in pp_races:
            race_num = pp_race.race_number

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
            for horse in pp_race.horses:
                horse_dict = convert_horse_to_model_format(
                    horse, pp_race, stats_loader, fts_analyzer
                )
                horses_data.append(horse_dict)

            if len(horses_data) == 0:
                continue

            # Test 1: BASELINE (no bias)
            predictions_baseline = predict_race(
                horses_data, pp_race, weights,
                bias_detector=None, apply_bias=False
            )

            # Test 2: WITH BIAS
            predictions_with_bias = predict_race(
                horses_data, pp_race, weights,
                bias_detector=bias_detector, apply_bias=True
            )

            # Evaluate both
            winner_pgm = matching_result['winner_pgm']

            # Baseline results
            results_baseline['total_races'] += 1
            for rank, pred in enumerate(predictions_baseline, 1):
                if str(pred['program_number']) == str(winner_pgm):
                    baseline_winner_ranks.append(rank)
                    if rank == 1:
                        results_baseline['top_pick_wins'] += 1
                    if rank <= 3:
                        results_baseline['top3_hits'] += 1
                    break

            # With bias results
            results_with_bias['total_races'] += 1
            for rank, pred in enumerate(predictions_with_bias, 1):
                if str(pred['program_number']) == str(winner_pgm):
                    bias_winner_ranks.append(rank)
                    if rank == 1:
                        results_with_bias['top_pick_wins'] += 1
                    if rank <= 3:
                        results_with_bias['top3_hits'] += 1
                    break

    # Print results
    print('='*80)
    print(' BACKTEST RESULTS')
    print('='*80)
    print()
    print(f'Total Races Analyzed: {results_baseline["total_races"]}')
    print()

    print('BASELINE (No Bias Adjustments):')
    print('-'*80)
    baseline_win_rate = results_baseline['top_pick_wins'] / results_baseline['total_races']
    baseline_top3_rate = results_baseline['top3_hits'] / results_baseline['total_races']
    baseline_avg_rank = sum(baseline_winner_ranks) / len(baseline_winner_ranks) if baseline_winner_ranks else 999

    print(f"  Top Pick Wins:     {results_baseline['top_pick_wins']}/{results_baseline['total_races']} = {baseline_win_rate*100:.1f}%")
    print(f"  Top-3 Hit Rate:    {results_baseline['top3_hits']}/{results_baseline['total_races']} = {baseline_top3_rate*100:.1f}%")
    print(f"  Avg Winner Rank:   {baseline_avg_rank:.2f}")
    print()

    print('WITH TRACK BIAS ADJUSTMENTS:')
    print('-'*80)
    bias_win_rate = results_with_bias['top_pick_wins'] / results_with_bias['total_races']
    bias_top3_rate = results_with_bias['top3_hits'] / results_with_bias['total_races']
    bias_avg_rank = sum(bias_winner_ranks) / len(bias_winner_ranks) if bias_winner_ranks else 999

    print(f"  Top Pick Wins:     {results_with_bias['top_pick_wins']}/{results_with_bias['total_races']} = {bias_win_rate*100:.1f}%")
    print(f"  Top-3 Hit Rate:    {results_with_bias['top3_hits']}/{results_with_bias['total_races']} = {bias_top3_rate*100:.1f}%")
    print(f"  Avg Winner Rank:   {bias_avg_rank:.2f}")
    print()

    # Calculate improvement
    print('='*80)
    print(' IMPROVEMENT ANALYSIS')
    print('='*80)
    print()

    win_rate_improvement = (bias_win_rate - baseline_win_rate) * 100
    top3_improvement = (bias_top3_rate - baseline_top3_rate) * 100
    rank_improvement = baseline_avg_rank - bias_avg_rank

    if win_rate_improvement > 0:
        symbol = '✅'
        status = 'IMPROVED'
    elif win_rate_improvement < 0:
        symbol = '❌'
        status = 'DECLINED'
    else:
        symbol = '→'
        status = 'NO CHANGE'

    print(f"Top Pick Win Rate:  {win_rate_improvement:+.1f} percentage points {symbol}")
    print(f"Top-3 Hit Rate:     {top3_improvement:+.1f} percentage points")
    print(f"Avg Winner Rank:    {rank_improvement:+.2f} places better")
    print()

    if bias_win_rate > baseline_win_rate:
        print(f"✅ BIAS ADJUSTMENTS {status}")
        print(f"   Win rate improved from {baseline_win_rate*100:.1f}% to {bias_win_rate*100:.1f}%")
        print()

        # Estimate ROI improvement (assuming $2 win bets at avg 5-1 odds)
        baseline_roi = (baseline_win_rate * 10) - 2.0
        bias_roi = (bias_win_rate * 10) - 2.0
        roi_improvement = ((bias_roi - baseline_roi) / 2.0) * 100

        print(f"Estimated ROI Impact (at 5-1 avg odds):")
        print(f"  Baseline: ${baseline_roi:.2f}/race ({(baseline_roi/2.0)*100:+.1f}% ROI)")
        print(f"  With Bias: ${bias_roi:.2f}/race ({(bias_roi/2.0)*100:+.1f}% ROI)")
        print(f"  Improvement: {roi_improvement:+.1f} percentage points ROI")
    else:
        print(f"⚠️  BIAS ADJUSTMENTS {status}")
        print(f"   No improvement detected. Win rate: {baseline_win_rate*100:.1f}% → {bias_win_rate*100:.1f}%")
        print()
        print("Possible reasons:")
        print("  - Sample size may be too small")
        print("  - Bias multipliers may need calibration")
        print("  - Post/pace factors may already be well-weighted")

    print()

    # Save detailed results
    output_data = {
        'total_races': results_baseline['total_races'],
        'baseline': {
            'top_pick_wins': results_baseline['top_pick_wins'],
            'win_rate': baseline_win_rate,
            'top3_hits': results_baseline['top3_hits'],
            'top3_rate': baseline_top3_rate,
            'avg_winner_rank': baseline_avg_rank,
        },
        'with_bias': {
            'top_pick_wins': results_with_bias['top_pick_wins'],
            'win_rate': bias_win_rate,
            'top3_hits': results_with_bias['top3_hits'],
            'top3_rate': bias_top3_rate,
            'avg_winner_rank': bias_avg_rank,
        },
        'improvement': {
            'win_rate_points': win_rate_improvement,
            'top3_rate_points': top3_improvement,
            'rank_improvement': rank_improvement,
        }
    }

    output_file = 'output/track_bias_backtest_results.json'
    with open(output_file, 'w') as f:
        json.dump(output_data, f, indent=2)

    print(f'✓ Saved detailed results to: {output_file}')
    print()


if __name__ == '__main__':
    main()
