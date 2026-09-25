#!/usr/bin/env python3
"""
Analyze October 2025 results to build probability calibration curve

This script compares model scores to actual win rates to:
1. Identify which score ranges predict which win probabilities
2. Build calibration bins for value betting
3. Validate model accuracy across score ranges
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.parsers.pdf_parser import parse_pdf_file
from src.data_loaders.statistics_loader import StatisticsLoader
from src.analyzers.fts_analyzer import FTSAnalyzer
from src.analyzers import racing_statistics as stats
import json
from typing import Dict, List
from pathlib import Path
import pdfplumber
import re

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
    """Convert PDF horse data to model input format (matches optimizer format)"""
    from datetime import datetime

    days_since_last = 999
    if horse.last_race_date:
        try:
            last_race = datetime.strptime(horse.last_race_date, '%Y-%m-%d')
            race_date = datetime.strptime(race.date, '%Y-%m-%d')
            days_since_last = (race_date - last_race).days
        except:
            pass

    # Get stats (no track_code parameter - optimizer doesn't use it)
    trainer_stats = stats_loader.get_trainer_stats(horse.trainer_name)
    jockey_stats = stats_loader.get_jockey_stats(horse.jockey_name)

    # FTS check (matches optimizer format)
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


def predict_race(horses_data, race, weights):
    """Generate predictions for a race (matches optimizer format)"""
    predictions = []

    for horse_data in horses_data:
        # Build race_data to match optimizer format
        race_data = {
            'date': race.date,
            'distance': race.distance_text,
            'surface': race.surface_description.lower(),
            'track_condition': race.track_condition,
            'purse': race.purse if race.purse > 0 else 50000,
            'field_size': len(horses_data),
            'avg_beyer': 70,
        }

        score_dict = stats.calculate_comprehensive_score(horse_data, race_data)

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
    print(' SCORE CALIBRATION ANALYSIS - OCTOBER 2025')
    print('='*80)
    print()

    # Initialize loaders
    stats_loader = StatisticsLoader(
        jockey_file='data/stats/jockey_statistics_comprehensive.json',
        trainer_file='data/stats/trainer_statistics_comprehensive.json'
    )

    fts_analyzer = FTSAnalyzer(
        trainer_stats_file='data/stats/fts_trainer_statistics.json',
        sire_stats_file='data/stats/fts_sire_statistics.json'
    )

    # Load optimized weights
    weights_path = 'output/optimized_weights_october_2025.json'
    with open(weights_path, 'r') as f:
        weights = json.load(f)

    print(f'✓ Loaded optimized weights')
    print()

    # Collect all predictions with outcomes
    all_predictions = []
    total_races = 0

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
            for horse in pp_race.horses:
                horse_dict = convert_horse_to_model_format(
                    horse, pp_race, stats_loader, fts_analyzer
                )
                horses_data.append(horse_dict)

            # Generate predictions
            predictions = predict_race(horses_data, pp_race, weights)

            # Mark winner
            winner_pgm = matching_result['winner_pgm']
            for pred in predictions:
                pred['won'] = (str(pred['program_number']) == str(winner_pgm))
                pred['race_id'] = f"{pp_date}_R{race_num}"
                all_predictions.append(pred)

    print(f'Collected {len(all_predictions)} horse predictions from {total_races} races')
    print()

    # Analyze by score bins
    print('='*80)
    print(' CALIBRATION ANALYSIS BY SCORE RANGE')
    print('='*80)
    print()

    score_bins = [
        (90, 100, 'Elite (90-100)'),
        (85, 90, 'Excellent (85-90)'),
        (80, 85, 'Very Good (80-85)'),
        (75, 80, 'Good (75-80)'),
        (70, 75, 'Above Average (70-75)'),
        (65, 70, 'Average (65-70)'),
        (60, 65, 'Below Average (60-65)'),
        (50, 60, 'Poor (50-60)'),
        (0, 50, 'Very Poor (0-50)'),
    ]

    calibration_data = {}

    for low, high, label in score_bins:
        horses_in_bin = [p for p in all_predictions if low <= p['score'] < high]

        if len(horses_in_bin) > 0:
            wins = sum(1 for p in horses_in_bin if p['won'])
            win_rate = wins / len(horses_in_bin)
            implied_probability = win_rate
            fair_odds = (1 / win_rate) - 1 if win_rate > 0 else 999

            calibration_data[label] = {
                'score_range': (low, high),
                'count': len(horses_in_bin),
                'wins': wins,
                'win_rate': win_rate,
                'implied_probability': implied_probability,
                'fair_odds': fair_odds
            }

            print(f'{label:25s}: {len(horses_in_bin):3d} horses, {wins:2d} wins, {win_rate*100:5.1f}% win rate, Fair odds: {fair_odds:5.2f}-1')

    print()

    # Analyze by rank
    print('='*80)
    print(' CALIBRATION ANALYSIS BY RANK')
    print('='*80)
    print()

    rank_bins = [
        (1, 1, 'Top Pick'),
        (2, 2, '2nd Choice'),
        (3, 3, '3rd Choice'),
        (4, 5, '4th-5th Choice'),
        (6, 10, '6th-10th Choice'),
    ]

    rank_calibration = {}

    for low, high, label in rank_bins:
        horses_in_bin = [p for p in all_predictions if low <= p['rank'] <= high]

        if len(horses_in_bin) > 0:
            wins = sum(1 for p in horses_in_bin if p['won'])
            win_rate = wins / len(horses_in_bin)
            implied_probability = win_rate
            fair_odds = (1 / win_rate) - 1 if win_rate > 0 else 999

            rank_calibration[label] = {
                'rank_range': (low, high),
                'count': len(horses_in_bin),
                'wins': wins,
                'win_rate': win_rate,
                'implied_probability': implied_probability,
                'fair_odds': fair_odds
            }

            print(f'{label:20s}: {len(horses_in_bin):3d} horses, {wins:2d} wins, {win_rate*100:5.1f}% win rate, Fair odds: {fair_odds:5.2f}-1')

    print()

    # Save calibration data
    output_data = {
        'score_calibration': calibration_data,
        'rank_calibration': rank_calibration,
        'total_predictions': len(all_predictions),
        'total_races': total_races,
        'dataset': 'October 2025 Keeneland'
    }

    output_file = 'output/probability_calibration.json'
    with open(output_file, 'w') as f:
        json.dump(output_data, f, indent=2)

    print(f'✓ Saved calibration data to: {output_file}')
    print()

    # Summary
    print('='*80)
    print(' KEY INSIGHTS FOR VALUE BETTING')
    print('='*80)
    print()

    top_pick_data = rank_calibration.get('Top Pick', {})
    if top_pick_data:
        print(f"Top Pick Win Rate: {top_pick_data['win_rate']*100:.1f}%")
        print(f"Top Pick Fair Odds: {top_pick_data['fair_odds']:.2f}-1")
        print(f"  → Any morning line > {top_pick_data['fair_odds']:.1f}-1 is VALUE!")
        print()

    print("Score-to-Probability Map:")
    for label, data in calibration_data.items():
        if data['count'] > 5:  # Only show bins with enough samples
            print(f"  {label}: {data['win_rate']*100:.1f}% win rate → {data['fair_odds']:.1f}-1 fair odds")

    print()


if __name__ == '__main__':
    main()
