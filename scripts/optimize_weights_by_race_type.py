#!/usr/bin/env python3
"""
Optimize Weights by Race Type

Creates specialized weight sets for:
1. Maiden races - Emphasize trainer/pedigree over class
2. Claiming races - Emphasize recency/pace over class
3. Allowance races - Balanced approach with class emphasis
4. Stakes races - Emphasize class and speed over other factors

Each race type will have its own optimized weights to improve accuracy.
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
from datetime import datetime
import pdfplumber
import re
from itertools import product

# October 2025 race dates (using 6 for training, 6 for validation)
TRAIN_DATES = [
    ('10-3-25', 'KEE100325USA.pdf'),
    ('10-5-25', 'KEE100525USA.pdf'),
    ('10-9-25', 'KEE100925USA.pdf'),
    ('10-11-25', 'KEE101125USA.pdf'),
    ('10-15-25', 'KEE101525USA.pdf'),
    ('10-17-25', 'KEE101725USA.pdf'),
]

VALIDATION_DATES = [
    ('10-8-25', 'KEE100825USA.pdf'),
    ('10-10-25', 'KEE101025USA.pdf'),
    ('10-12-25', 'KEE101225USA.pdf'),
    ('10-16-25', 'KEE101625USA.pdf'),
    ('10-18-25', 'KEE101825USA.pdf'),
    ('10-19-25', 'KEE101925USA.pdf'),
]


def classify_race_type(race) -> str:
    """Classify race by type"""
    race_name = race.race_name.lower() if hasattr(race, 'race_name') else ''
    race_type = race.race_type.lower() if hasattr(race, 'race_type') else ''

    if 'maiden' in race_name or 'maiden' in race_type:
        return 'maiden'
    if 'claiming' in race_name or 'claiming' in race_type or 'clm' in race_type:
        return 'claiming'
    if 'stakes' in race_name or 'stakes' in race_type or race.purse > 150000:
        return 'stakes'
    return 'allowance'


def parse_results_pdf(results_pdf_path: str) -> List[Dict]:
    """Parse results PDF to get actual winners"""
    results = []

    with pdfplumber.open(results_pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            lines = text.split('\n')

            current_race = None

            for i, line in enumerate(lines):
                if 'KEENELAND' in line and 'Race' in line:
                    race_match = re.search(r'Race(\d+)', line)
                    if race_match:
                        current_race = int(race_match.group(1))
                        continue

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

    trainer_stats = stats_loader.get_trainer_stats(horse.trainer_name)
    jockey_stats = stats_loader.get_jockey_stats(horse.jockey_name)

    fts_data = {'is_fts': horse.career_starts == 0, 'advantage': 0.0}
    if fts_data['is_fts']:
        fts_multiplier, _ = fts_analyzer.calculate_fts_multiplier(
            trainer_name=horse.trainer_name,
            sire_name=horse.sire_name
        )
        fts_data['advantage'] = fts_multiplier - 1.0

    recent_finishes = []
    if horse.past_performances:
        recent_finishes = [pp['finish'] for pp in horse.past_performances[:5] if 'finish' in pp]

    return {
        'name': horse.name,
        'program_number': horse.program_number,
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


def predict_race(horses_data, race, weights, bias_detector):
    """Generate predictions for a race"""
    predictions = []

    for horse_data in horses_data:
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

        # Apply track bias
        apply_track_biases_to_scores(score_dict, horse_data, race_data, bias_detector)

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

    predictions.sort(key=lambda x: x['score'], reverse=True)

    for i, pred in enumerate(predictions, 1):
        pred['rank'] = i

    return predictions


def evaluate_weights(weights, race_type, dates, stats_loader, fts_analyzer, bias_detector):
    """Evaluate a weight set on given dates for a specific race type"""
    total_races = 0
    correct_picks = 0

    for pp_date, results_file in dates:
        pp_path = f'Keeneland October PPs/{pp_date}-kee-ppspdf.pdf'
        results_path = f'data/Results Files/{results_file}'

        try:
            pp_races = parse_pdf_file(pp_path, debug=False)
            actual_results = parse_results_pdf(results_path)
        except FileNotFoundError:
            continue

        for pp_race in pp_races:
            # Filter by race type
            if classify_race_type(pp_race) != race_type:
                continue

            race_num = pp_race.race_number
            total_races += 1

            matching_result = None
            for result in actual_results:
                if result['race_number'] == race_num:
                    matching_result = result
                    break

            if not matching_result:
                continue

            horses_data = []
            for horse in pp_race.horses:
                horse_dict = convert_horse_to_model_format(
                    horse, pp_race, stats_loader, fts_analyzer
                )
                horses_data.append(horse_dict)

            if len(horses_data) == 0:
                continue

            predictions = predict_race(horses_data, pp_race, weights, bias_detector)

            winner_pgm = matching_result['winner_pgm']
            if predictions and str(predictions[0]['program_number']) == str(winner_pgm):
                correct_picks += 1

    win_rate = correct_picks / total_races if total_races > 0 else 0.0
    return win_rate, correct_picks, total_races


def generate_weight_candidates_for_race_type(race_type):
    """
    Generate weight candidates optimized for each race type

    Based on analysis:
    - Maiden: High trainer/jockey, low class
    - Claiming: High recency/pace, low class
    - Allowance: Balanced, moderate class
    - Stakes: High class/speed, moderate recency
    """
    if race_type == 'maiden':
        # Maiden: Trainer/jockey matter more, class doesn't exist yet
        speed_range = [0.20, 0.25]
        form_range = [0.12, 0.15]
        class_range = [0.05, 0.08]  # Low - no class history
        pace_range = [0.12, 0.15]
        recency_range = [0.15, 0.18]
        progression_range = [0.04, 0.06]
        jockey_range = [0.08, 0.12]  # Higher
        trainer_range = [0.08, 0.12]  # Higher
        post_range = [0.04, 0.06]

    elif race_type == 'claiming':
        # Claiming: Recency/pace matter, class less important
        speed_range = [0.18, 0.22]
        form_range = [0.12, 0.15]
        class_range = [0.06, 0.10]  # Lower
        pace_range = [0.15, 0.18]  # Higher
        recency_range = [0.16, 0.20]  # Higher
        progression_range = [0.04, 0.06]
        jockey_range = [0.05, 0.08]
        trainer_range = [0.05, 0.08]
        post_range = [0.04, 0.06]

    elif race_type == 'stakes':
        # Stakes: Class/speed matter most
        speed_range = [0.24, 0.28]  # Higher
        form_range = [0.14, 0.17]
        class_range = [0.14, 0.18]  # Higher
        pace_range = [0.12, 0.15]
        recency_range = [0.12, 0.15]
        progression_range = [0.04, 0.06]
        jockey_range = [0.05, 0.08]
        trainer_range = [0.05, 0.08]
        post_range = [0.04, 0.06]

    else:  # allowance
        # Allowance: Balanced, standard weights
        speed_range = [0.22, 0.26]
        form_range = [0.13, 0.16]
        class_range = [0.10, 0.14]
        pace_range = [0.13, 0.16]
        recency_range = [0.12, 0.15]
        progression_range = [0.04, 0.06]
        jockey_range = [0.05, 0.08]
        trainer_range = [0.05, 0.08]
        post_range = [0.04, 0.06]

    # Generate limited set of candidates (2 values per factor = 512 total)
    candidates = []

    for speed in speed_range:
        for form in form_range:
            for class_w in class_range:
                for pace in pace_range:
                    for recency in recency_range:
                        for progression in progression_range:
                            for jockey in jockey_range:
                                for trainer in trainer_range:
                                    for post in post_range:
                                        total = speed + form + class_w + pace + recency + progression + jockey + trainer + post

                                        # Normalize to sum to 1.0
                                        weights = {
                                            'speed': speed / total,
                                            'form': form / total,
                                            'class': class_w / total,
                                            'pace': pace / total,
                                            'recency': recency / total,
                                            'progression': progression / total,
                                            'jockey': jockey / total,
                                            'trainer': trainer / total,
                                            'post': post / total
                                        }

                                        candidates.append(weights)

    return candidates


def main():
    print('='*80)
    print(' WEIGHT OPTIMIZATION BY RACE TYPE')
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

    bias_detector = TrackBiasDetector(
        bias_data_file='output/track_bias_analysis_october_2025.json'
    )

    print('✓ Components initialized')
    print()

    # Optimize weights for each race type
    race_types = ['maiden', 'claiming', 'allowance', 'stakes']
    optimized_weights = {}

    for race_type in race_types:
        print('='*80)
        print(f' OPTIMIZING WEIGHTS FOR {race_type.upper()} RACES')
        print('='*80)
        print()

        # Generate candidates
        candidates = generate_weight_candidates_for_race_type(race_type)
        print(f'Generated {len(candidates)} weight candidates for {race_type} races')
        print()

        best_weights = None
        best_train_rate = 0.0
        best_val_rate = 0.0

        print(f'Testing candidates (this may take a few minutes)...')
        print()

        for i, weights in enumerate(candidates):
            if (i + 1) % 50 == 0:
                print(f'  Tested {i+1}/{len(candidates)} candidates... (best so far: {best_train_rate*100:.1f}%)')

            # Evaluate on training set
            train_rate, train_correct, train_total = evaluate_weights(
                weights, race_type, TRAIN_DATES, stats_loader, fts_analyzer, bias_detector
            )

            if train_rate > best_train_rate:
                # Validate on validation set
                val_rate, val_correct, val_total = evaluate_weights(
                    weights, race_type, VALIDATION_DATES, stats_loader, fts_analyzer, bias_detector
                )

                best_train_rate = train_rate
                best_val_rate = val_rate
                best_weights = weights

        print()
        print(f'✓ Best weights for {race_type}:')
        print(f'  Training: {best_train_rate*100:.1f}%')
        print(f'  Validation: {best_val_rate*100:.1f}%')
        print()

        for factor, weight in sorted(best_weights.items(), key=lambda x: x[1], reverse=True):
            print(f'  {factor:12s}: {weight:.4f} ({weight*100:5.1f}%)')

        print()

        optimized_weights[race_type] = best_weights

    # Save optimized weights
    output_file = 'output/optimized_weights_by_race_type.json'
    with open(output_file, 'w') as f:
        json.dump(optimized_weights, f, indent=2)

    print('='*80)
    print(' OPTIMIZATION COMPLETE')
    print('='*80)
    print()
    print(f'✓ Saved specialized weights to: {output_file}')
    print()

    # Summary
    print('SUMMARY:')
    print('-'*80)
    for race_type in race_types:
        weights = optimized_weights[race_type]
        top_factors = sorted(weights.items(), key=lambda x: x[1], reverse=True)[:3]
        print(f'{race_type.title():12s}: {", ".join(f[0] for f in top_factors)} (top 3)')

    print()


if __name__ == '__main__':
    main()
