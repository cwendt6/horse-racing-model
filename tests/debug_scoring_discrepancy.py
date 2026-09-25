import os
"""
Debug script to find why optimizer gets 30% and calibration gets 17%
"""
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.parsers.pdf_parser import parse_pdf_file
from src.data_loaders.statistics_loader import StatisticsLoader
from src.analyzers.fts_analyzer import FTSAnalyzer
from src.analyzers import racing_statistics as stats
import json
import pdfplumber
import re

# Import fixed functions from calibration script
from scripts.analyze_score_calibration import (
    parse_results_pdf,
    convert_horse_to_model_format,
    predict_race
)

# Load optimized weights
with open('output/optimized_weights_october_2025.json', 'r') as f:
    weights = json.load(f)

# Initialize loaders
stats_loader = StatisticsLoader(
    jockey_file='data/stats/jockey_statistics_comprehensive.json',
    trainer_file='data/stats/trainer_statistics_comprehensive.json'
)

fts_analyzer = FTSAnalyzer(
    trainer_stats_file='data/stats/fts_trainer_statistics.json',
    sire_stats_file='data/stats/fts_sire_statistics.json'
)

def score_optimizer_way(horse, race, stats_loader, fts_analyzer, weights):
    """Score using optimizer method"""
    # Get jockey/trainer stats
    jockey_stats = stats_loader.get_jockey_stats(horse.jockey_name)
    trainer_stats = stats_loader.get_trainer_stats(horse.trainer_name)

    # Check FTS
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

    # Post position
    try:
        post_position = int(horse.program_number)
    except (ValueError, TypeError):
        post_position = 5

    # Days since last race
    days_since_last = 999
    if horse.last_race_date and race.date:
        try:
            race_date = datetime.strptime(race.date, '%Y-%m-%d')
            last_race = datetime.strptime(horse.last_race_date, '%Y-%m-%d')
            days_since_last = (race_date - last_race).days
        except:
            pass

    # Build horse_data (optimizer way)
    horse_data = {
        'name': horse.name,
        'program_number': horse.program_number,
        'jockey_name': horse.jockey_name,
        'trainer_name': horse.trainer_name,
        'best_beyer': horse.best_speed_figure if horse.best_speed_figure > 0 else 70,
        'last_beyer': horse.last_speed_figure if horse.last_speed_figure > 0 else 70,
        'avg_beyer': horse.avg_speed_figure if horse.avg_speed_figure > 0 else 70,
        'career_starts': horse.career_starts if horse.career_starts > 0 else 10,
        'career_wins': horse.career_wins,
        'career_earnings': horse.career_earnings if horse.career_earnings > 0 else 50000,
        'recent_finishes': recent_finishes,
        'days_since_last_race': days_since_last,
        'past_performances': horse.past_performances if horse.past_performances else [],
        'jockey_win_pct': jockey_stats.win_percentage / 100.0 if jockey_stats else 0.15,
        'trainer_win_pct': trainer_stats.win_percentage / 100.0 if trainer_stats else 0.15,
        'running_style': horse.running_style,
        'is_fts': fts_data['is_fts'],
        'fts_advantage': fts_data['advantage'],
    }

    # Build race_data (optimizer way)
    race_data = {
        'date': race.date,
        'distance': race.distance_text,
        'surface': race.surface_description.lower(),
        'track_condition': race.track_condition,
        'purse': race.purse if race.purse > 0 else 50000,
        'field_size': len(race.horses),
        'avg_beyer': 70,
    }

    # Calculate score
    score_obj = stats.calculate_comprehensive_score(horse_data, race_data)

    final_score = (
        score_obj.speed * weights['speed'] +
        score_obj.form * weights['form'] +
        score_obj.class_rating * weights['class'] +
        score_obj.pace * weights['pace'] +
        score_obj.recency * weights['recency'] +
        score_obj.progression * weights['progression'] +
        score_obj.jockey * weights['jockey'] +
        score_obj.trainer * weights['trainer'] +
        score_obj.post * weights['post']
    )

    return final_score

def score_calibration_way(horse, race, stats_loader, fts_analyzer, weights):
    """Score using fixed calibration method"""
    # Use the fixed convert function
    horse_data = convert_horse_to_model_format(horse, race, stats_loader, fts_analyzer)

    # Build race_data the same way
    race_data = {
        'date': race.date,
        'distance': race.distance_text,
        'surface': race.surface_description.lower(),
        'track_condition': race.track_condition,
        'purse': race.purse if race.purse > 0 else 50000,
        'field_size': len(race.horses),
        'avg_beyer': 70,
    }

    score_obj = stats.calculate_comprehensive_score(horse_data, race_data)

    final_score = (
        score_obj.speed * weights['speed'] +
        score_obj.form * weights['form'] +
        score_obj.class_rating * weights['class'] +
        score_obj.pace * weights['pace'] +
        score_obj.recency * weights['recency'] +
        score_obj.progression * weights['progression'] +
        score_obj.jockey * weights['jockey'] +
        score_obj.trainer * weights['trainer'] +
        score_obj.post * weights['post']
    )

    return final_score

# Test on Race 1 of October 3
pp_path = 'Keeneland October PPs/10-3-25-kee-ppspdf.pdf'
results_path = 'data/Results Files/KEE100325USA.pdf'

pp_races = parse_pdf_file(pp_path, debug=False)
actual_results = parse_results_pdf(results_path)

race = pp_races[0]  # Race 1
winner_pgm = [r for r in actual_results if r['race_number'] == 1][0]['winner_pgm']

print("DEBUGGING SCORING DISCREPANCY")
print("="*80)
print(f"Race 1 - Oct 3, 2025")
print(f"Actual winner: #{winner_pgm}")
print()

# Score all horses both ways
optimizer_predictions = []
calibration_predictions = []

for horse in race.horses:
    opt_score = score_optimizer_way(horse, race, stats_loader, fts_analyzer, weights)
    cal_score = score_calibration_way(horse, race, stats_loader, fts_analyzer, weights)

    optimizer_predictions.append({
        'program_number': horse.program_number,
        'name': horse.name,
        'score': opt_score
    })

    calibration_predictions.append({
        'program_number': horse.program_number,
        'name': horse.name,
        'score': cal_score
    })

# Sort both
optimizer_predictions.sort(key=lambda x: x['score'], reverse=True)
calibration_predictions.sort(key=lambda x: x['score'], reverse=True)

print("OPTIMIZER METHOD:")
print(f"  Top pick: #{optimizer_predictions[0]['program_number']} {optimizer_predictions[0]['name']}")
print(f"  Match: {'✓ WIN' if optimizer_predictions[0]['program_number'] == winner_pgm else '✗ MISS'}")
print()

print("CALIBRATION METHOD:")
print(f"  Top pick: #{calibration_predictions[0]['program_number']} {calibration_predictions[0]['name']}")
print(f"  Match: {'✓ WIN' if calibration_predictions[0]['program_number'] == winner_pgm else '✗ MISS'}")
print()

# Show top 5 from each
print("OPTIMIZER TOP 5:")
for i, p in enumerate(optimizer_predictions[:5], 1):
    marker = " ← WINNER" if p['program_number'] == winner_pgm else ""
    print(f"  {i}. #{p['program_number']:2s} {p['name']:30s} {p['score']:6.2f}{marker}")

print()
print("CALIBRATION TOP 5:")
for i, p in enumerate(calibration_predictions[:5], 1):
    marker = " ← WINNER" if p['program_number'] == winner_pgm else ""
    print(f"  {i}. #{p['program_number']:2s} {p['name']:30s} {p['score']:6.2f}{marker}")
