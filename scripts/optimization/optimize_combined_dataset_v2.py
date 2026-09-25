#!/usr/bin/env python3
"""
Combined Dataset Weight Optimizer (2023 + 2025 Keeneland) - Fast Version

Loads existing prediction results from:
- 2023 Keeneland backtest (output/2023_keeneland_validation_report.json)
- 2025 October validation (output/october_validation_report.json)

Re-optimizes weights by adjusting component scores and re-ranking horses.
Much faster than re-running full prediction pipeline.

Multi-objective: Win rate + Top-3 rate + Exacta rate
"""

import sys
sys.path.insert(0, '.')

import json
import numpy as np
from datetime import datetime
from typing import List, Dict, Tuple
from scipy.optimize import differential_evolution
from sklearn.model_selection import train_test_split


def load_existing_results() -> Tuple[List[Dict], List[Dict]]:
    """
    Load existing prediction results from both datasets

    Returns:
        (data_2023, data_2025) - lists of race result dicts with predictions
    """
    print("\n" + "="*80)
    print(" LOADING EXISTING PREDICTION RESULTS")
    print("="*80)

    # Load 2023 results - these already have top_5_picks with component scores
    with open('output/2023_keeneland_validation_report.json', 'r') as f:
        report_2023 = json.load(f)
    data_2023 = report_2023['detailed_results']
    print(f"  ✓ 2023: {len(data_2023)} races loaded")

    # Load 2025 results and merge with prediction files
    with open('output/october_validation_report.json', 'r') as f:
        report_2025 = json.load(f)

    # Load all 2025 prediction files
    # Map ISO dates (from validation report) to prediction filenames
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

    # Build lookup: (date, race_number) -> predictions
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
            data_2025.append(comp)

    print(f"  ✓ 2025: {len(data_2025)} races loaded with predictions")

    total = len(data_2023) + len(data_2025)
    print(f"\n  Total: {total} races")
    print("="*80)

    return data_2023, data_2025


def combine_and_split_data(data_2023: List[Dict], data_2025: List[Dict], train_split: float = 0.7):
    """
    Combine datasets and split into train/validation

    Returns:
        (train_data, val_data)
    """
    # Combine
    combined = data_2023 + data_2025

    # Shuffle and split
    train_data, val_data = train_test_split(
        combined,
        train_size=train_split,
        random_state=42
    )

    print(f"\nDataset split:")
    print(f"  Training:   {len(train_data)} races ({train_split*100:.0f}%)")
    print(f"  Validation: {len(val_data)} races ({(1-train_split)*100:.0f}%)")

    # Show distribution
    train_2023 = sum(1 for r in train_data if 'race_number' in r and isinstance(r['race_number'], int) and r['race_number'] >= 1)
    val_2023 = sum(1 for r in val_data if 'race_number' in r and isinstance(r['race_number'], int) and r['race_number'] >= 1)

    print(f"\n  Train: {train_2023} from 2023, {len(train_data) - train_2023} from 2025")
    print(f"  Val:   {val_2023} from 2023, {len(val_data) - val_2023} from 2025")

    return train_data, val_data


def rescore_prediction(pred: Dict, weights: Dict) -> float:
    """
    Re-calculate final score using new weights

    Predictions contain component scores, so we can re-weight them
    """
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


def evaluate_weights(weights_dict: Dict, dataset: List[Dict]) -> Dict[str, float]:
    """
    Evaluate weights on dataset by re-ranking predictions

    Returns metrics: win_rate, top3_rate, top5_rate
    """
    wins = 0
    top3 = 0
    top5 = 0
    total_races = len(dataset)

    for race_result in dataset:
        # Get predictions for this race
        # Check for 2023 format (has top_5_picks)
        if 'top_5_picks' in race_result:
            predictions = race_result['top_5_picks']
            winner_pgm = str(race_result['winner_pgm'])  # Convert to string for comparison
        # Check for 2025 format (has predicted_top_5 and actual_winner_pgm)
        elif 'predicted_top_5' in race_result:
            predictions = race_result['predicted_top_5']
            winner_pgm = str(race_result['actual_winner_pgm'])
        else:
            continue  # Skip if no predictions

        # Re-score and re-rank predictions with new weights
        rescored = []
        for pred in predictions:
            new_score = rescore_prediction(pred, weights_dict)
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

        # Check top-5
        top5_picks = [p['program_number'] for p in rescored[:5]]
        if winner_pgm in top5_picks:
            top5 += 1

    return {
        'win_rate': wins / total_races if total_races > 0 else 0,
        'top3_rate': top3 / total_races if total_races > 0 else 0,
        'top5_rate': top5 / total_races if total_races > 0 else 0,
    }


def objective_function(weights_array: np.ndarray, train_data: List[Dict]) -> float:
    """
    Multi-objective function:
    - 50% Win rate
    - 50% Top-3 rate

    Lower is better for differential_evolution (so we negate)
    """
    # Convert array to dict
    weights_dict = {
        'speed': weights_array[0],
        'form': weights_array[1],
        'class_rating': weights_array[2],
        'pace': weights_array[3],
        'recency': weights_array[4],
        'progression': weights_array[5],
        'jockey': weights_array[6],
        'trainer': weights_array[7],
        'post': weights_array[8],
        'jt_combo_scale': weights_array[9],
        'distance_surface_scale': weights_array[10],
        'equipment_scale': weights_array[11],
        'trip_notes_scale': weights_array[12],
        'workout_scale': weights_array[13],
        'trainer_pattern_scale': weights_array[14],
    }

    # Evaluate
    metrics = evaluate_weights(weights_dict, train_data)

    # Combined score
    combined = 0.5 * metrics['win_rate'] + 0.5 * metrics['top3_rate']

    # Return negative (minimization)
    return -combined


def optimize_weights(train_data: List[Dict], val_data: List[Dict], max_iterations: int = 100):
    """Run optimization"""

    print("\n" + "="*80)
    print(" RUNNING WEIGHT OPTIMIZATION")
    print("="*80)
    print(f"  Max iterations: {max_iterations}")
    print(f"  Objective: 50% Win + 50% Top-3")
    print("="*80)

    # Define bounds
    bounds = [
        (0.01, 0.40),  # speed
        (0.01, 0.40),  # form
        (0.01, 0.40),  # class_rating
        (0.01, 0.40),  # pace
        (0.01, 0.40),  # recency
        (0.01, 0.40),  # progression
        (0.01, 0.40),  # jockey
        (0.01, 0.40),  # trainer
        (0.01, 0.40),  # post
        (0.2, 2.5),    # jt_combo_scale
        (0.2, 2.5),    # distance_surface_scale
        (0.2, 2.5),    # equipment_scale
        (0.2, 2.5),    # trip_notes_scale
        (0.2, 2.5),    # workout_scale
        (0.2, 2.5),    # trainer_pattern_scale
    ]

    # Run optimization
    result = differential_evolution(
        lambda w: objective_function(w, train_data),
        bounds=bounds,
        maxiter=max_iterations,
        popsize=15,
        seed=42,
        workers=1,
        updating='deferred',
        disp=True
    )

    # Extract best weights
    best_weights_dict = {
        'speed': float(result.x[0]),
        'form': float(result.x[1]),
        'class_rating': float(result.x[2]),
        'pace': float(result.x[3]),
        'recency': float(result.x[4]),
        'progression': float(result.x[5]),
        'jockey': float(result.x[6]),
        'trainer': float(result.x[7]),
        'post': float(result.x[8]),
        'jt_combo_scale': float(result.x[9]),
        'distance_surface_scale': float(result.x[10]),
        'equipment_scale': float(result.x[11]),
        'trip_notes_scale': float(result.x[12]),
        'workout_scale': float(result.x[13]),
        'trainer_pattern_scale': float(result.x[14]),
    }

    # Evaluate on train and validation
    print("\n" + "="*80)
    print(" FINAL EVALUATION")
    print("="*80)

    train_metrics = evaluate_weights(best_weights_dict, train_data)
    val_metrics = evaluate_weights(best_weights_dict, val_data)

    print("\nTRAINING SET:")
    print(f"  Win Rate:   {train_metrics['win_rate']*100:.1f}%")
    print(f"  Top-3 Rate: {train_metrics['top3_rate']*100:.1f}%")
    print(f"  Top-5 Rate: {train_metrics['top5_rate']*100:.1f}%")

    print("\nVALIDATION SET:")
    print(f"  Win Rate:   {val_metrics['win_rate']*100:.1f}%")
    print(f"  Top-3 Rate: {val_metrics['top3_rate']*100:.1f}%")
    print(f"  Top-5 Rate: {val_metrics['top5_rate']*100:.1f}%")

    # Load baseline weights for comparison
    with open('config/optimized_weights.json', 'r') as f:
        baseline = json.load(f)

    baseline_dict = {
        'speed': baseline['speed'],
        'form': baseline['form'],
        'class_rating': baseline.get('class_rating', baseline.get('class', 0.2)),
        'pace': baseline['pace'],
        'recency': baseline['recency'],
        'progression': baseline['progression'],
        'jockey': baseline['jockey'],
        'trainer': baseline['trainer'],
        'post': baseline['post'],
        'jt_combo_scale': baseline['jt_combo_scale'],
        'distance_surface_scale': baseline['distance_surface_scale'],
        'equipment_scale': baseline['equipment_scale'],
        'trip_notes_scale': baseline['trip_notes_scale'],
        'workout_scale': baseline['workout_scale'],
        'trainer_pattern_scale': baseline['trainer_pattern_scale'],
    }

    baseline_train = evaluate_weights(baseline_dict, train_data)
    baseline_val = evaluate_weights(baseline_dict, val_data)

    print("\n" + "="*80)
    print(" COMPARISON TO BASELINE")
    print("="*80)
    print(f"\nBASELINE (Oct 2025 only):")
    print(f"  Train: Win {baseline_train['win_rate']*100:.1f}%, Top-3 {baseline_train['top3_rate']*100:.1f}%")
    print(f"  Val:   Win {baseline_val['win_rate']*100:.1f}%, Top-3 {baseline_val['top3_rate']*100:.1f}%")

    print(f"\nNEW WEIGHTS (2023+2025 combined):")
    print(f"  Train: Win {train_metrics['win_rate']*100:.1f}%, Top-3 {train_metrics['top3_rate']*100:.1f}%")
    print(f"  Val:   Win {val_metrics['win_rate']*100:.1f}%, Top-3 {val_metrics['top3_rate']*100:.1f}%")

    print(f"\nIMPROVEMENT:")
    print(f"  Train: Win {(train_metrics['win_rate'] - baseline_train['win_rate'])*100:+.1f}%, Top-3 {(train_metrics['top3_rate'] - baseline_train['top3_rate'])*100:+.1f}%")
    print(f"  Val:   Win {(val_metrics['win_rate'] - baseline_val['win_rate'])*100:+.1f}%, Top-3 {(val_metrics['top3_rate'] - baseline_val['top3_rate'])*100:+.1f}%")

    print("="*80)

    return best_weights_dict, {
        'train': train_metrics,
        'val': val_metrics,
        'baseline_train': baseline_train,
        'baseline_val': baseline_val,
    }


def main():
    print("\n" + "="*80)
    print(" COMBINED DATASET WEIGHT OPTIMIZER (Fast Version)")
    print(" Re-optimizing on 2023 + 2025 Keeneland results")
    print("="*80)

    # Load existing results
    data_2023, data_2025 = load_existing_results()

    # Combine and split
    train_data, val_data = combine_and_split_data(data_2023, data_2025, train_split=0.7)

    # Optimize
    best_weights, metrics = optimize_weights(train_data, val_data, max_iterations=100)

    # Save new weights
    output_file = 'config/weights_combined_optimized.json'
    with open(output_file, 'w') as f:
        json.dump(best_weights, f, indent=2)

    print(f"\n✅ New weights saved to: {output_file}")

    # Save report
    report = {
        'optimization_date': datetime.now().isoformat(),
        'dataset': {
            'total_races': len(train_data) + len(val_data),
            'train_races': len(train_data),
            'val_races': len(val_data),
        },
        'weights': best_weights,
        'performance': {
            'train': {k: float(v) for k, v in metrics['train'].items()},
            'val': {k: float(v) for k, v in metrics['val'].items()},
            'baseline_train': {k: float(v) for k, v in metrics['baseline_train'].items()},
            'baseline_val': {k: float(v) for k, v in metrics['baseline_val'].items()},
        }
    }

    report_file = 'output/combined_optimization_report.json'
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)

    print(f"✅ Report saved to: {report_file}")
    print("\n" + "="*80)
    print(" OPTIMIZATION COMPLETE")
    print("="*80)

    return 0


if __name__ == '__main__':
    sys.exit(main())
