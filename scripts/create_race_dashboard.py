"""
Create Race Dashboard from Prediction Results
Generates interactive visualizations for race predictions
"""

import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import os
from datetime import datetime

from src.data_loaders.integrate_data import load_enhanced_races
from src.core.backtesting_framework import RacingBacktest
from src.analyzers.pace_analyzer import PaceAnalyzer
from src.visualization.race_dashboard import create_race_visualization


def create_dashboard_for_race(race, scoring_weights=None):
    """
    Create dashboard for a single race

    Args:
        race: Race object with enhanced data
        scoring_weights: Optional custom scoring weights

    Returns:
        predictions: List of prediction dictionaries
    """
    # Default weights (can be overridden)
    if scoring_weights is None:
        scoring_weights = {
            'speed': 0.30,
            'form': 0.20,
            'class': 0.15,
            'pace': 0.15,
            'jockey': 0.10,
            'trainer': 0.10,
        }

    # Import scoring module
    from src.analyzers import racing_statistics as stats

    # Build race data dict
    race_data = {
        'distance': race.distance_text,
        'surface': race.surface.lower() if race.surface else 'dirt',
        'purse': race.purse,
        'field_size': len(race.horses),
        'pace_scenario': 'moderate',
        'avg_beyer': 70,
    }

    # Calculate average Beyer if available
    import numpy as np
    beyers = [h.speed_rating for h in race.horses if h.speed_rating and h.speed_rating > 0]
    if beyers:
        race_data['avg_beyer'] = np.mean(beyers)

    # Score horses in the race
    horse_scores = []
    for horse in race.horses:
        # Build horse data dict
        if hasattr(horse, '_has_enhanced_data') and horse._has_enhanced_data:
            horse_data = {
                'name': horse.name,
                'program_number': horse.program_number,
                'post': horse.post_position,
                'ml_odds': horse.morning_line_odds,
                'age': horse.age,
                'sex': horse.sex,
                'best_beyer': horse._enhanced_best_beyer,
                'last_beyer': horse._enhanced_last_beyer,
                'running_style': horse._enhanced_running_style,
                'career_earnings': horse._enhanced_career_earnings,
                'career_starts': horse._enhanced_career_starts,
                'jockey_win_pct': horse._enhanced_jockey_win_pct,
                'trainer_win_pct': horse._enhanced_trainer_win_pct,
                'jockey_name': getattr(horse, '_enhanced_jockey_name', ''),
                'trainer_name': getattr(horse, '_enhanced_trainer_name', ''),
                'fts_multiplier': getattr(horse, '_fts_multiplier', 1.0),
                'is_fts': getattr(horse, '_is_fts', False),
                'fts_explanation': getattr(horse, '_fts_explanation', ''),
            }
        else:
            horse_data = {
                'name': horse.name,
                'program_number': horse.program_number,
                'post': horse.post_position,
                'ml_odds': horse.morning_line_odds,
                'age': horse.age,
                'sex': horse.sex,
                'best_beyer': horse.speed_rating if horse.speed_rating else 50,
                'last_beyer': horse.speed_rating if horse.speed_rating else 50,
                'running_style': 'P',
                'career_earnings': 100000,
                'career_starts': 10,
                'jockey_win_pct': 0.15,
                'trainer_win_pct': '15%',
                'jockey_name': '',
                'trainer_name': '',
                'fts_multiplier': 1.0,
                'is_fts': False,
                'fts_explanation': '',
            }

        # Calculate score
        score = stats.calculate_comprehensive_score(horse_data, race_data)
        horse_scores.append({
            'horse': horse,
            'horse_data': horse_data,
            'score': score.total,
            'factor_scores': {
                'speed': score.speed,
                'form': score.form,
                'class': score.class_rating,
                'pace': score.pace,
                'jockey': score.jockey,
                'trainer': score.trainer,
            }
        })

    # Analyze pace scenario
    pace_analyzer = PaceAnalyzer()
    horses_for_pace = []
    for horse in race.horses:
        if hasattr(horse, '_enhanced_running_style'):
            horses_for_pace.append({
                'name': horse.name,
                'running_style': horse._enhanced_running_style
            })

    distance_furlongs = race.distance / 220.0 if race.distance else 6.0
    pace_scenario_obj = pace_analyzer.analyze_pace(
        horses_for_pace,
        distance_furlongs,
        race.surface
    )

    # Apply FTS and pace multipliers
    adjusted_scores = []
    for h in horse_scores:
        base_score = h['score']

        # Apply FTS multiplier
        fts_multiplier = h['horse_data'].get('fts_multiplier', 1.0)
        score_after_fts = base_score * fts_multiplier

        # Apply pace multiplier
        running_style = h['horse_data'].get('running_style', 'P')
        horse_name = h['horse_data'].get('name', '')
        pace_multiplier, pace_explanation = pace_analyzer.calculate_pace_multiplier(
            horse_name, running_style, pace_scenario_obj
        )
        final_score = score_after_fts * pace_multiplier

        h['final_score'] = final_score
        h['pace_multiplier'] = pace_multiplier
        h['pace_explanation'] = pace_explanation
        adjusted_scores.append(h)

    # Normalize to probabilities
    total_score = sum(h['final_score'] for h in adjusted_scores)
    if total_score == 0:
        total_score = 1.0

    for h in adjusted_scores:
        h['win_probability'] = h['final_score'] / total_score

    # Sort by probability and assign ranks
    adjusted_scores.sort(key=lambda x: x['win_probability'], reverse=True)
    for rank, h in enumerate(adjusted_scores, 1):
        h['rank'] = rank

    # Create prediction dictionaries for dashboard
    predictions = []
    for h in adjusted_scores:
        pred = {
            'rank': h['rank'],
            'program_number': h['horse_data'].get('program_number', '?'),
            'horse_name': h['horse_data'].get('name', 'Unknown'),
            'win_probability': h['win_probability'],
            'model_odds': (1 / h['win_probability']) if h['win_probability'] > 0 else 99.0,
            'morning_line_odds': h['horse_data'].get('morning_line_odds', 5.0),
            'jockey_name': h['horse_data'].get('jockey_name', ''),
            'trainer_name': h['horse_data'].get('trainer_name', ''),
            'speed_figure': h['factor_scores'].get('speed', 0),
            'is_fts': h['horse_data'].get('is_fts', False),
            'running_style': h['horse_data'].get('running_style', 'P'),
            'pace_advantage': h.get('pace_explanation', ''),
            'factor_scores': h['factor_scores'],
        }
        predictions.append(pred)

    # Convert pace scenario object to dict
    pace_scenario_dict = {
        'scenario_type': pace_scenario_obj.scenario_type,
        'early_speed_count': pace_scenario_obj.early_speed_count,
        'advantage_horses': [p['program_number'] for p in predictions
                            if 'Advantage' in p.get('pace_advantage', '')],
    }

    return predictions, pace_scenario_dict


def main():
    """Generate dashboards for sample races"""
    print("\n" + "="*80)
    print(" RACE DASHBOARD GENERATOR")
    print("="*80)

    # Load enhanced races
    print("\nLoading enhanced race data...")
    races, stats = load_enhanced_races(
        tch_dir='data/raw/Equibase Dataset/2023 Result Charts',
        simd_dir='data/raw/Equibase Dataset/2023 PPs',
        jockey_stats_file='data/stats/jockey_statistics_comprehensive.json',
        trainer_stats_file='data/stats/trainer_statistics_comprehensive.json',
        fts_trainer_stats_file='data/stats/fts_trainer_statistics.json',
        fts_sire_stats_file='data/stats/fts_sire_statistics.json'
    )

    print(f"\n✓ Loaded {len(races)} races")

    # Create output directory
    os.makedirs('output/dashboards', exist_ok=True)

    # Generate dashboards for first 3 races as examples
    print("\nGenerating sample dashboards...")
    for i, race in enumerate(races[:3], 1):
        print(f"\n  Creating dashboard for race {i}...")

        # Generate predictions
        predictions, pace_scenario = create_dashboard_for_race(race)

        # Create output filename
        race_date = race.date.replace('/', '-') if hasattr(race, 'date') and race.date else 'unknown'
        track_code = race.track_code if hasattr(race, 'track_code') else 'UNK'
        output_file = f"output/dashboards/{track_code}_R{race.race_number}_{race_date}_dashboard.png"

        # Generate dashboard
        try:
            create_race_visualization(race, predictions, pace_scenario, output_file)
            print(f"  ✓ Dashboard saved: {output_file}")
        except Exception as e:
            print(f"  ✗ Error creating dashboard: {e}")

    print("\n" + "="*80)
    print(" DASHBOARD GENERATION COMPLETE")
    print("="*80)
    print(f"\nDashboards saved to: output/dashboards/")
    print("\nTo create a dashboard for a specific race, use:")
    print("  from scripts.create_race_dashboard import create_dashboard_for_race")
    print("  predictions, pace = create_dashboard_for_race(race)")
    print()


if __name__ == '__main__':
    main()
