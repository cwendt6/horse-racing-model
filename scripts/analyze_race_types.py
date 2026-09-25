#!/usr/bin/env python3
"""
Race Type Analysis - October 2025

Classifies races by type and analyzes factor importance for each:
1. Maiden races (horses with no wins)
2. Claiming races (horses for sale)
3. Allowance races (mid-level conditions)
4. Stakes races (high-class competition)
5. Turf vs Dirt
6. Sprint vs Route

Goal: Identify which factors matter most for each race type
to create specialized weight sets.
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
from collections import defaultdict
from datetime import datetime
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


def classify_race_type(race) -> str:
    """
    Classify race by type based on race name and conditions

    Returns one of:
        - 'maiden' - horses with no wins
        - 'claiming' - horses for sale
        - 'allowance' - mid-level conditions
        - 'stakes' - high-class competition
    """
    race_name = race.race_name.lower() if hasattr(race, 'race_name') else ''
    race_type = race.race_type.lower() if hasattr(race, 'race_type') else ''

    # Check for maiden
    if 'maiden' in race_name or 'maiden' in race_type:
        return 'maiden'

    # Check for claiming
    if 'claiming' in race_name or 'claiming' in race_type or 'clm' in race_type:
        return 'claiming'

    # Check for stakes
    if 'stakes' in race_name or 'stakes' in race_type or \
       'handicap' in race_name or 'cup' in race_name or \
       race.purse > 150000:  # High purse indicates stakes
        return 'stakes'

    # Default to allowance
    return 'allowance'


def classify_distance(distance_furlongs: float) -> str:
    """Classify race distance"""
    if distance_furlongs < 7.0:
        return 'sprint'
    elif distance_furlongs < 9.0:
        return 'mile'
    else:
        return 'route'


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


def main():
    print('='*80)
    print(' RACE TYPE ANALYSIS - OCTOBER 2025')
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

    print('✓ Components initialized')
    print()

    # Data structures for analysis
    race_type_stats = defaultdict(lambda: {
        'count': 0,
        'winners': [],
        'factor_correlations': defaultdict(list)
    })

    surface_stats = defaultdict(lambda: {'count': 0, 'winners': []})
    distance_stats = defaultdict(lambda: {'count': 0, 'winners': []})

    print('Loading and classifying races...')
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

            # Classify race
            race_type = classify_race_type(pp_race)
            surface = 'turf' if 'turf' in pp_race.surface_description.lower() else 'dirt'
            distance_furlongs = pp_race.distance / 100.0
            distance_class = classify_distance(distance_furlongs)

            # Find matching result
            matching_result = None
            for result in actual_results:
                if result['race_number'] == race_num:
                    matching_result = result
                    break

            if not matching_result:
                continue

            # Track race type
            race_type_stats[race_type]['count'] += 1
            surface_stats[surface]['count'] += 1
            distance_stats[distance_class]['count'] += 1

            # Convert horses to model format
            horses_data = []
            for horse in pp_race.horses:
                horse_dict = convert_horse_to_model_format(
                    horse, pp_race, stats_loader, fts_analyzer
                )
                horses_data.append(horse_dict)

            if len(horses_data) == 0:
                continue

            # Calculate scores for each horse
            winner_pgm = matching_result['winner_pgm']

            for horse_data in horses_data:
                # Build race_data
                race_data = {
                    'date': pp_race.date,
                    'distance': pp_race.distance_text,
                    'surface': pp_race.surface_description.lower(),
                    'track_condition': pp_race.track_condition,
                    'purse': pp_race.purse if pp_race.purse > 0 else 50000,
                    'field_size': len(horses_data),
                    'avg_beyer': 70,
                }

                # Calculate comprehensive scores
                score_dict = stats.calculate_comprehensive_score(horse_data, race_data)

                # Check if winner
                is_winner = (str(horse_data['program_number']) == str(winner_pgm))

                if is_winner:
                    # Store winner's scores
                    race_type_stats[race_type]['winners'].append({
                        'speed': score_dict.speed,
                        'form': score_dict.form,
                        'class': score_dict.class_rating,
                        'pace': score_dict.pace,
                        'recency': score_dict.recency,
                        'progression': score_dict.progression,
                        'jockey': score_dict.jockey,
                        'trainer': score_dict.trainer,
                        'post': score_dict.post
                    })

                    surface_stats[surface]['winners'].append(score_dict.speed)
                    distance_stats[distance_class]['winners'].append(score_dict.speed)

                # Track factor scores for correlation analysis
                race_type_stats[race_type]['factor_correlations']['speed'].append(
                    (score_dict.speed, is_winner)
                )
                race_type_stats[race_type]['factor_correlations']['class'].append(
                    (score_dict.class_rating, is_winner)
                )
                race_type_stats[race_type]['factor_correlations']['trainer'].append(
                    (score_dict.trainer, is_winner)
                )

    # Print race type distribution
    print('='*80)
    print(' RACE TYPE DISTRIBUTION')
    print('='*80)
    print()
    print(f"{'Type':<15} {'Count':<8} {'Percentage':<12}")
    print('-'*80)

    total_races = sum(stats['count'] for stats in race_type_stats.values())

    for race_type in sorted(race_type_stats.keys()):
        count = race_type_stats[race_type]['count']
        pct = count / total_races * 100 if total_races > 0 else 0
        print(f"{race_type.title():<15} {count:<8} {pct:>5.1f}%")

    print()

    # Print surface distribution
    print('='*80)
    print(' SURFACE DISTRIBUTION')
    print('='*80)
    print()

    for surface in sorted(surface_stats.keys()):
        count = surface_stats[surface]['count']
        pct = count / total_races * 100 if total_races > 0 else 0
        print(f"{surface.title():<15} {count:<8} {pct:>5.1f}%")

    print()

    # Print distance distribution
    print('='*80)
    print(' DISTANCE DISTRIBUTION')
    print('='*80)
    print()

    for distance in ['sprint', 'mile', 'route']:
        if distance in distance_stats:
            count = distance_stats[distance]['count']
            pct = count / total_races * 100 if total_races > 0 else 0
            print(f"{distance.title():<15} {count:<8} {pct:>5.1f}%")

    print()

    # Analyze winner characteristics by race type
    print('='*80)
    print(' WINNER CHARACTERISTICS BY RACE TYPE')
    print('='*80)
    print()

    for race_type in sorted(race_type_stats.keys()):
        winners = race_type_stats[race_type]['winners']

        if len(winners) == 0:
            continue

        print(f"{race_type.upper()} RACES ({len(winners)} winners):")
        print('-'*80)

        # Calculate average scores for winners
        avg_scores = {
            'speed': sum(w['speed'] for w in winners) / len(winners),
            'form': sum(w['form'] for w in winners) / len(winners),
            'class': sum(w['class'] for w in winners) / len(winners),
            'pace': sum(w['pace'] for w in winners) / len(winners),
            'recency': sum(w['recency'] for w in winners) / len(winners),
            'progression': sum(w['progression'] for w in winners) / len(winners),
            'jockey': sum(w['jockey'] for w in winners) / len(winners),
            'trainer': sum(w['trainer'] for w in winners) / len(winners),
            'post': sum(w['post'] for w in winners) / len(winners),
        }

        # Sort by importance
        sorted_factors = sorted(avg_scores.items(), key=lambda x: x[1], reverse=True)

        for factor, avg_score in sorted_factors:
            print(f"  {factor.title():12s}: {avg_score:5.1f}")

        print()

    # Save analysis results
    output_data = {
        'total_races': total_races,
        'race_type_distribution': {
            race_type: {
                'count': stats['count'],
                'percentage': stats['count'] / total_races * 100
            }
            for race_type, stats in race_type_stats.items()
        },
        'winner_characteristics': {
            race_type: {
                'sample_size': len(stats['winners']),
                'avg_scores': {
                    'speed': sum(w['speed'] for w in stats['winners']) / len(stats['winners']) if stats['winners'] else 0,
                    'form': sum(w['form'] for w in stats['winners']) / len(stats['winners']) if stats['winners'] else 0,
                    'class': sum(w['class'] for w in stats['winners']) / len(stats['winners']) if stats['winners'] else 0,
                    'pace': sum(w['pace'] for w in stats['winners']) / len(stats['winners']) if stats['winners'] else 0,
                    'recency': sum(w['recency'] for w in stats['winners']) / len(stats['winners']) if stats['winners'] else 0,
                    'progression': sum(w['progression'] for w in stats['winners']) / len(stats['winners']) if stats['winners'] else 0,
                    'jockey': sum(w['jockey'] for w in stats['winners']) / len(stats['winners']) if stats['winners'] else 0,
                    'trainer': sum(w['trainer'] for w in stats['winners']) / len(stats['winners']) if stats['winners'] else 0,
                    'post': sum(w['post'] for w in stats['winners']) / len(stats['winners']) if stats['winners'] else 0,
                }
            }
            for race_type, stats in race_type_stats.items()
        }
    }

    output_file = 'output/race_type_analysis_october_2025.json'
    with open(output_file, 'w') as f:
        json.dump(output_data, f, indent=2)

    print(f'✓ Saved analysis to: {output_file}')
    print()


if __name__ == '__main__':
    main()
