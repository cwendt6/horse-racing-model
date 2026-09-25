#!/usr/bin/env python3
"""
Optimize Weights for Generalization Across Time Periods

Key improvements:
1. Stratified split - ensures both 2023 and 2025 in train/val
2. Gap minimization objective - reduces overfitting
3. Proper dataset tracking
"""

import sys
sys.path.insert(0, '.')

import json
import numpy as np
from typing import List, Dict, Tuple
from scipy.optimize import differential_evolution
from sklearn.model_selection import train_test_split


def load_datasets() -> Tuple[List[Dict], List[Dict]]:
    """Load 2023 and 2025 datasets with predictions"""

    print("\n" + "="*80)
    print(" LOADING DATASETS")
    print("="*80)

    # Load 2023 data
    with open('output/2023_keeneland_validation_report.json', 'r') as f:
        report_2023 = json.load(f)
    data_2023 = report_2023['detailed_results']

    # Add dataset label
    for race in data_2023:
        race['dataset'] = '2023'

    print(f"  ✓ 2023: {len(data_2023)} races loaded")

    # Load 2025 data with predictions
    with open('output/october_validation_report.json', 'r') as f:
        report_2025 = json.load(f)

    # Map ISO dates to prediction filenames
    date_to_file = {
        '2025-10-03': 'output/predictions_10-3-25.json',
        '2025-10-05': 'output/predictions_10-5-25.json',
        '2025-10-08': 'output/predictions_10-8-25.json',
        '2025-10-09': 'output/predictions_10-9-25.json',
        '2025-10-10': 'output/predictions_10-10-25.json',
        '2025-10-11': 'output/predictions_10-11-25.json',
        '2025-10-12': 'output/predictions_10-12-25.json',
        '2025-10-15': 'output/predictions_10-15-25.json',
        '2025-10-16': 'output/predictions_10-16-25.json',
        '2025-10-17': 'output/predictions_10-17-25.json',
        '2025-10-18': 'output/predictions_10-18-25.json',
        '2025-10-19': 'output/predictions_10-19-25.json',
    }

    # Build lookup
    predictions_lookup = {}
    for iso_date, file_path in date_to_file.items():
        try:
            with open(file_path, 'r') as f:
                pred_data = json.load(f)
            for race in pred_data['races']:
                key = (iso_date, race['race_number'])
                predictions_lookup[key] = race['predictions']
        except FileNotFoundError:
            print(f"  ⚠️  Prediction file not found: {file_path}")

    # Merge predictions into 2025 comparisons
    data_2025 = []
    for comp in report_2025['comparisons']:
        key = (comp['date'], comp['race_number'])
        if key in predictions_lookup:
            comp['predicted_top_5'] = predictions_lookup[key]
            comp['dataset'] = '2025'
            data_2025.append(comp)

    print(f"  ✓ 2025: {len(data_2025)} races loaded with predictions")

    total = len(data_2023) + len(data_2025)
    print(f"\n  Total: {total} races")
    print("="*80)

    return data_2023, data_2025


def stratified_split(data_2023: List[Dict], data_2025: List[Dict],
                      train_split: float = 0.7, random_state: int = 42) -> Tuple[List[Dict], List[Dict]]:
    """
    Stratified split ensuring both datasets represented in train and validation

    Returns:
        (train_data, val_data)
    """
    # Split each dataset separately
    train_2023, val_2023 = train_test_split(
        data_2023,
        train_size=train_split,
        random_state=random_state
    )

    train_2025, val_2025 = train_test_split(
        data_2025,
        train_size=train_split,
        random_state=random_state
    )

    # Combine
    train_data = train_2023 + train_2025
    val_data = val_2023 + val_2025

    print(f"\nStratified split (seed={random_state}):")
    print(f"  Training:   {len(train_data)} races ({len(train_2023)} from 2023, {len(train_2025)} from 2025)")
    print(f"  Validation: {len(val_data)} races ({len(val_2023)} from 2023, {len(val_2025)} from 2025)")

    return train_data, val_data


def rescore_prediction(pred: Dict, weights: Dict) -> float:
    """Re-calculate final score using new weights"""
    # Get component scores
    speed = pred.get('speed_score', 0)
    form = pred.get('form_score', 0)
    class_rating = pred.get('class_score', 0)
    pace = pred.get('pace_score', 0)
    recency = pred.get('recency_score', 0)
    progression = pred.get('progression_score', 0)
    jockey = pred.get('jockey_score', 0)
    trainer = pred.get('trainer_score', 0)
    post = pred.get('post_score', 0)

    # Get bonuses
    jt_bonus = pred.get('jt_combo_bonus', 0)
    ds_bonus = pred.get('ds_bonus', 0)
    equip_bonus = pred.get('equip_bonus', 0)
    trip_bonus = pred.get('trip_bonus', 0)
    workout_bonus = pred.get('workout_bonus', 0)
    trainer_pattern_bonus = pred.get('trainer_bonus', 0)

    # Calculate base score
    base_score = (
        weights['speed'] * speed +
        weights['form'] * form +
        weights['class_rating'] * class_rating +
        weights['pace'] * pace +
        weights['recency'] * recency +
        weights['progression'] * progression +
        weights['jockey'] * jockey +
        weights['trainer'] * trainer +
        weights['post'] * post
    )

    # Add scaled bonuses
    bonus_score = (
        jt_bonus * weights['jt_combo_scale'] +
        ds_bonus * weights['distance_surface_scale'] +
        equip_bonus * weights['equipment_scale'] +
        trip_bonus * weights['trip_notes_scale'] +
        workout_bonus * weights['workout_scale'] +
        trainer_pattern_bonus * weights['trainer_pattern_scale']
    )

    return base_score + bonus_score


def evaluate_dataset(data: List[Dict], weights: Dict) -> Dict[str, float]:
    """Evaluate weights on a dataset"""
    wins = 0
    top3 = 0
    total = len(data)

    for race_result in data:
        # Get predictions
        if 'top_5_picks' in race_result:  # 2023 format
            predictions = race_result['top_5_picks']
            winner_pgm = str(race_result['winner_pgm'])
        elif 'predicted_top_5' in race_result:  # 2025 format
            predictions = race_result['predicted_top_5']
            winner_pgm = str(race_result['actual_winner_pgm'])
        else:
            continue

        # Re-score and re-rank
        rescored = []
        for pred in predictions:
            new_score = rescore_prediction(pred, weights)
            rescored.append({
                'program_number': str(pred.get('program_number', pred.get('pgm', ''))),
                'score': new_score
            })

        # Sort by new score
        rescored.sort(key=lambda x: x['score'], reverse=True)

        # Check win
        if rescored[0]['program_number'] == winner_pgm:
            wins += 1

        # Check top-3
        top3_picks = [p['program_number'] for p in rescored[:3]]
        if winner_pgm in top3_picks:
            top3 += 1

    return {
        'win_rate': wins / total if total > 0 else 0,
        'top3_rate': top3 / total if total > 0 else 0,
        'wins': wins,
        'top3': top3,
        'total': total
    }


def evaluate_by_dataset(data: List[Dict], weights: Dict) -> Tuple[Dict, Dict]:
    """Evaluate weights separately for 2023 and 2025 subsets"""
    data_2023 = [r for r in data if r.get('dataset') == '2023']
    data_2025 = [r for r in data if r.get('dataset') == '2025']

    results_2023 = evaluate_dataset(data_2023, weights)
    results_2025 = evaluate_dataset(data_2025, weights)

    return results_2023, results_2025


def objective_function(params, train_data, baseline_weights):
    """
    Objective function for optimization

    PRIMARY GOAL: Minimize gap between 2023 and 2025 performance
    SECONDARY GOAL: Maintain reasonable overall performance
    """
    # Unpack parameters
    weights = {
        'speed': params[0],
        'form': params[1],
        'class_rating': params[2],
        'pace': params[3],
        'recency': params[4],
        'progression': params[5],
        'jockey': params[6],
        'trainer': params[7],
        'post': params[8],
        'jt_combo_scale': params[9],
        'distance_surface_scale': params[10],
        'equipment_scale': params[11],
        'trip_notes_scale': params[12],
        'workout_scale': params[13],
        'trainer_pattern_scale': params[14],
    }

    # Evaluate on both datasets separately
    results_2023, results_2025 = evaluate_by_dataset(train_data, weights)

    # Calculate performance gap (absolute difference)
    win_gap = abs(results_2023['win_rate'] - results_2025['win_rate'])
    top3_gap = abs(results_2023['top3_rate'] - results_2025['top3_rate'])

    # Calculate minimum performance (we don't want to sacrifice too much)
    min_win = min(results_2023['win_rate'], results_2025['win_rate'])
    min_top3 = min(results_2023['top3_rate'], results_2025['top3_rate'])

    # Combined objective:
    # 1. Minimize gap (weight 0.6)
    # 2. Maximize minimum performance (weight 0.4)
    gap_penalty = 0.5 * win_gap + 0.5 * top3_gap
    performance_reward = 0.5 * min_win + 0.5 * min_top3

    # Minimize gap, maximize min performance
    # (Negate performance to convert maximization to minimization)
    objective = 0.6 * gap_penalty - 0.4 * performance_reward

    return objective


def optimize_weights(train_data: List[Dict], baseline_weights: Dict,
                     max_iterations: int = 100) -> Dict:
    """
    Optimize weights using differential evolution

    Returns optimized weights dict
    """
    print("\n" + "="*80)
    print(" RUNNING OPTIMIZATION")
    print("="*80)
    print(f"  Objective: Minimize gap between 2023 and 2025 performance")
    print(f"  Max iterations: {max_iterations}")
    print(f"  Algorithm: Differential Evolution")

    # Define parameter bounds
    # Component weights: 0.01 to 0.40
    component_bounds = [(0.01, 0.40)] * 9

    # Bonus scales: 0.2 to 2.5
    bonus_bounds = [(0.2, 2.5)] * 6

    bounds = component_bounds + bonus_bounds

    # Run optimization
    result = differential_evolution(
        objective_function,
        bounds,
        args=(train_data, baseline_weights),
        maxiter=max_iterations,
        seed=42,
        workers=1,
        updating='deferred',
        polish=True
    )

    # Extract optimized weights
    optimized_weights = {
        'speed': result.x[0],
        'form': result.x[1],
        'class_rating': result.x[2],
        'pace': result.x[3],
        'recency': result.x[4],
        'progression': result.x[5],
        'jockey': result.x[6],
        'trainer': result.x[7],
        'post': result.x[8],
        'jt_combo_scale': result.x[9],
        'distance_surface_scale': result.x[10],
        'equipment_scale': result.x[11],
        'trip_notes_scale': result.x[12],
        'workout_scale': result.x[13],
        'trainer_pattern_scale': result.x[14],
    }

    print(f"\n  ✅ Optimization complete!")
    print(f"  Final objective value: {result.fun:.4f}")

    return optimized_weights


def main():
    print("\n" + "="*80)
    print(" GAP-MINIMIZING WEIGHT OPTIMIZATION")
    print(" Goal: Reduce overfitting, improve generalization")
    print("="*80)

    # Load baseline weights
    with open('config/optimized_weights.json', 'r') as f:
        baseline_weights = json.load(f)

    # Load datasets
    data_2023, data_2025 = load_datasets()

    # Stratified split
    train_data, val_data = stratified_split(data_2023, data_2025, train_split=0.7, random_state=42)

    # Evaluate baseline on training data
    print("\n" + "="*80)
    print(" BASELINE PERFORMANCE ON TRAINING DATA")
    print("="*80)

    train_2023_baseline, train_2025_baseline = evaluate_by_dataset(train_data, baseline_weights)

    print(f"\n  2023 subset: {train_2023_baseline['wins']}/{train_2023_baseline['total']} wins ({train_2023_baseline['win_rate']*100:.1f}%), "
          f"{train_2023_baseline['top3']}/{train_2023_baseline['total']} top-3 ({train_2023_baseline['top3_rate']*100:.1f}%)")
    print(f"  2025 subset: {train_2025_baseline['wins']}/{train_2025_baseline['total']} wins ({train_2025_baseline['win_rate']*100:.1f}%), "
          f"{train_2025_baseline['top3']}/{train_2025_baseline['total']} top-3 ({train_2025_baseline['top3_rate']*100:.1f}%)")

    baseline_gap = abs(train_2023_baseline['top3_rate'] - train_2025_baseline['top3_rate']) * 100
    print(f"\n  Baseline top-3 gap: {baseline_gap:.1f}%")

    # Run optimization
    optimized_weights = optimize_weights(train_data, baseline_weights, max_iterations=100)

    # Evaluate optimized weights on training data
    print("\n" + "="*80)
    print(" OPTIMIZED PERFORMANCE ON TRAINING DATA")
    print("="*80)

    train_2023_opt, train_2025_opt = evaluate_by_dataset(train_data, optimized_weights)

    print(f"\n  2023 subset: {train_2023_opt['wins']}/{train_2023_opt['total']} wins ({train_2023_opt['win_rate']*100:.1f}%), "
          f"{train_2023_opt['top3']}/{train_2023_opt['total']} top-3 ({train_2023_opt['top3_rate']*100:.1f}%)")
    print(f"  2025 subset: {train_2025_opt['wins']}/{train_2025_opt['total']} wins ({train_2025_opt['win_rate']*100:.1f}%), "
          f"{train_2025_opt['top3']}/{train_2025_opt['total']} top-3 ({train_2025_opt['top3_rate']*100:.1f}%)")

    optimized_gap = abs(train_2023_opt['top3_rate'] - train_2025_opt['top3_rate']) * 100
    print(f"\n  Optimized top-3 gap: {optimized_gap:.1f}%")
    print(f"  Gap reduction: {baseline_gap:.1f}% → {optimized_gap:.1f}% ({baseline_gap - optimized_gap:+.1f}%)")

    # Evaluate on validation data
    print("\n" + "="*80)
    print(" VALIDATION SET PERFORMANCE")
    print("="*80)

    val_2023_baseline, val_2025_baseline = evaluate_by_dataset(val_data, baseline_weights)
    val_2023_opt, val_2025_opt = evaluate_by_dataset(val_data, optimized_weights)

    print(f"\n  Baseline:")
    print(f"    2023: {val_2023_baseline['top3_rate']*100:.1f}% top-3")
    print(f"    2025: {val_2025_baseline['top3_rate']*100:.1f}% top-3")
    print(f"    Gap: {abs(val_2023_baseline['top3_rate'] - val_2025_baseline['top3_rate'])*100:.1f}%")

    print(f"\n  Optimized:")
    print(f"    2023: {val_2023_opt['top3_rate']*100:.1f}% top-3")
    print(f"    2025: {val_2025_opt['top3_rate']*100:.1f}% top-3")
    print(f"    Gap: {abs(val_2023_opt['top3_rate'] - val_2025_opt['top3_rate'])*100:.1f}%")

    # Save optimized weights
    output_file = 'config/weights_generalized.json'
    with open(output_file, 'w') as f:
        json.dump(optimized_weights, f, indent=2)

    print(f"\n✅ Optimized weights saved to: {output_file}")

    # Save detailed report
    report = {
        'optimization_date': str(np.datetime64('now')),
        'objective': 'minimize_gap_between_2023_and_2025',
        'dataset': {
            'total_races': len(data_2023) + len(data_2025),
            'train_races': len(train_data),
            'val_races': len(val_data),
            'train_2023': train_2023_baseline['total'],
            'train_2025': train_2025_baseline['total'],
            'val_2023': val_2023_baseline['total'],
            'val_2025': val_2025_baseline['total']
        },
        'weights': optimized_weights,
        'performance': {
            'train': {
                'baseline_2023': train_2023_baseline,
                'baseline_2025': train_2025_baseline,
                'optimized_2023': train_2023_opt,
                'optimized_2025': train_2025_opt,
                'baseline_gap': baseline_gap,
                'optimized_gap': optimized_gap
            },
            'val': {
                'baseline_2023': val_2023_baseline,
                'baseline_2025': val_2025_baseline,
                'optimized_2023': val_2023_opt,
                'optimized_2025': val_2025_opt,
                'baseline_gap': abs(val_2023_baseline['top3_rate'] - val_2025_baseline['top3_rate']) * 100,
                'optimized_gap': abs(val_2023_opt['top3_rate'] - val_2025_opt['top3_rate']) * 100
            }
        }
    }

    report_file = 'output/generalization_optimization_report.json'
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)

    print(f"✅ Detailed report saved to: {report_file}")
    print("="*80)


if __name__ == '__main__':
    main()
