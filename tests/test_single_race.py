import os
#!/usr/bin/env python3
"""Test prediction on a single SIMD file"""

import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import json
from src.parsers.simd_parser import parse_simd_file
from src.data_loaders.statistics_loader import StatisticsLoader
from src.analyzers.fts_analyzer import FTSAnalyzer
from src.analyzers.pace_analyzer import PaceAnalyzer
from src.analyzers import racing_statistics as stats
import numpy as np

print("="*80)
print("SINGLE RACE TEST")
print("="*80)

# Load statistics
print("\n1. Loading statistics...")
stats_loader = StatisticsLoader(
    jockey_file='data/stats/jockey_statistics_comprehensive.json',
    trainer_file='data/stats/trainer_statistics_comprehensive.json'
)
print("✓ Statistics loaded")

# Load FTS analyzer
print("\n2. Loading FTS analyzer...")
fts_analyzer = FTSAnalyzer(
    trainer_stats_file='data/stats/fts_trainer_statistics.json',
    sire_stats_file='data/stats/fts_sire_statistics.json'
)
print("✓ FTS analyzer loaded")

# Initialize pace analyzer
pace_analyzer = PaceAnalyzer()

# Parse single SIMD file
print("\n3. Parsing SIMD file...")
test_file = 'equibase 2023 data/2023 PPs/SIMD20230101AQU_USA.xml'
simd_races = parse_simd_file(test_file)
print(f"✓ Found {len(simd_races)} races in file")

# Process first race
if simd_races and len(simd_races) > 0:
    simd_race = simd_races[0]
    print(f"\n4. Processing race: {simd_race.track_id} R{simd_race.race_number}")
    print(f"   Horses: {len(simd_race.horses)}")

    # Try to score first horse
    if simd_race.horses and len(simd_race.horses) > 0:
        horse = simd_race.horses[0]
        print(f"\n5. Scoring horse: {horse.name}")

        # Get stats
        jockey_stats_obj = stats_loader.get_jockey_stats(horse.jockey_name)
        trainer_stats_obj = stats_loader.get_trainer_stats(horse.trainer_name)

        print(f"   Jockey: {horse.jockey_name}")
        if jockey_stats_obj:
            print(f"     Win %: {jockey_stats_obj.win_percentage}%")

        print(f"   Trainer: {horse.trainer_name}")
        if trainer_stats_obj:
            print(f"     Win %: {trainer_stats_obj.win_percentage}%")

        # Build horse data
        horse_data = {
            'name': horse.name,
            'best_beyer': 70,
            'last_beyer': 70,
            'jockey_win_pct': jockey_stats_obj.win_percentage / 100.0 if jockey_stats_obj else 0.15,
            'trainer_win_pct': trainer_stats_obj.win_percentage / 100.0 if trainer_stats_obj else 0.15,
            'career_earnings': horse.total_earnings if hasattr(horse, 'total_earnings') else 100000,
            'career_starts': 10,
            'running_style': 'P',
        }

        race_data = {
            'distance': '6F',
            'surface': 'dirt',
            'purse': 50000,
            'field_size': len(simd_race.horses),
            'pace_scenario': 'moderate',
            'avg_beyer': 70,
        }

        print("\n6. Calculating score...")
        score = stats.calculate_comprehensive_score(horse_data, race_data)
        print(f"✓ Score calculated: {score.total:.2f}")
        print(f"   Speed: {score.speed:.2f}")
        print(f"   Form: {score.form:.2f}")
        print(f"   Class: {score.class_rating:.2f}")
        print(f"   Pace: {score.pace:.2f}")
        print(f"   Jockey: {score.jockey:.2f}")
        print(f"   Trainer: {score.trainer:.2f}")

print("\n" + "="*80)
print("TEST COMPLETE")
print("="*80)
