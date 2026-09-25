#!/usr/bin/env python3
"""
Validate Combined Weights on 2023 and 2025 Datasets Separately

Tests both baseline (Oct 2025 only) and combined (2023+2025) weights
to measure generalization improvement.
"""

import sys
sys.path.insert(0, '.')

import json
from typing import List, Dict


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


def evaluate_dataset(data: List[Dict], weights: Dict, dataset_name: str) -> Dict:
    """Evaluate weights on a dataset"""
    wins = 0
    top3 = 0
    top5 = 0
    total = len(data)

    for race_result in data:
        # Get predictions for this race
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

        # Check top-5
        top5_picks = [p['program_number'] for p in rescored[:5]]
        if winner_pgm in top5_picks:
            top5 += 1

    return {
        'dataset': dataset_name,
        'total_races': total,
        'win_rate': wins / total if total > 0 else 0,
        'top3_rate': top3 / total if total > 0 else 0,
        'top5_rate': top5 / total if total > 0 else 0,
        'wins': wins,
        'top3': top3,
        'top5': top5
    }


def main():
    print("\n" + "="*80)
    print(" VALIDATING COMBINED WEIGHTS vs BASELINE")
    print(" Testing on 2023 and 2025 data separately")
    print("="*80)

    # Load baseline weights (Oct 2025 only)
    with open('config/optimized_weights.json', 'r') as f:
        baseline_weights = json.load(f)

    # Load combined weights (2023 + 2025)
    with open('config/weights_combined_optimized.json', 'r') as f:
        combined_weights = json.load(f)

    # Load 2023 data
    with open('output/2023_keeneland_validation_report.json', 'r') as f:
        report_2023 = json.load(f)
    data_2023 = report_2023['detailed_results']

    # Load 2025 data with predictions
    with open('output/october_validation_report.json', 'r') as f:
        report_2025 = json.load(f)

    # Load 2025 prediction files
    date_to_file = {
        '2025-10-10': 'output/predictions_10-10-25.json',
        '2025-10-11': 'output/predictions_10-11-25.json',
        '2025-10-12': 'output/predictions_10-12-25.json',
        '2025-10-16': 'output/predictions_10-16-25.json',
        '2025-10-17': 'output/predictions_10-17-25.json',
        '2025-10-18': 'output/predictions_10-18-25.json',
        '2025-10-19': 'output/predictions_10-19-25.json',
    }

    # Build lookup and merge
    predictions_lookup = {}
    for iso_date, file_path in date_to_file.items():
        try:
            with open(file_path, 'r') as f:
                pred_data = json.load(f)
            for race in pred_data['races']:
                key = (iso_date, race['race_number'])
                predictions_lookup[key] = race['predictions']
        except FileNotFoundError:
            pass

    data_2025 = []
    for comp in report_2025['comparisons']:
        key = (comp['date'], comp['race_number'])
        if key in predictions_lookup:
            comp['predicted_top_5'] = predictions_lookup[key]
            data_2025.append(comp)

    print(f"\n✓ Loaded {len(data_2023)} races from 2023")
    print(f"✓ Loaded {len(data_2025)} races from 2025")

    # Evaluate baseline weights
    print("\n" + "="*80)
    print(" BASELINE WEIGHTS (Oct 2025 only)")
    print("="*80)

    baseline_2023 = evaluate_dataset(data_2023, baseline_weights, "2023 Keeneland")
    baseline_2025 = evaluate_dataset(data_2025, baseline_weights, "2025 Keeneland")

    print(f"\n2023 Performance:")
    print(f"  Win:   {baseline_2023['wins']}/{baseline_2023['total_races']} = {baseline_2023['win_rate']*100:.1f}%")
    print(f"  Top-3: {baseline_2023['top3']}/{baseline_2023['total_races']} = {baseline_2023['top3_rate']*100:.1f}%")
    print(f"  Top-5: {baseline_2023['top5']}/{baseline_2023['total_races']} = {baseline_2023['top5_rate']*100:.1f}%")

    print(f"\n2025 Performance:")
    print(f"  Win:   {baseline_2025['wins']}/{baseline_2025['total_races']} = {baseline_2025['win_rate']*100:.1f}%")
    print(f"  Top-3: {baseline_2025['top3']}/{baseline_2025['total_races']} = {baseline_2025['top3_rate']*100:.1f}%")
    print(f"  Top-5: {baseline_2025['top5']}/{baseline_2025['total_races']} = {baseline_2025['top5_rate']*100:.1f}%")

    baseline_gap = {
        'win': (baseline_2025['win_rate'] - baseline_2023['win_rate']) * 100,
        'top3': (baseline_2025['top3_rate'] - baseline_2023['top3_rate']) * 100,
        'top5': (baseline_2025['top5_rate'] - baseline_2023['top5_rate']) * 100,
    }

    print(f"\nGap (2025 - 2023):")
    print(f"  Win gap:   {baseline_gap['win']:+.1f}%")
    print(f"  Top-3 gap: {baseline_gap['top3']:+.1f}%")
    print(f"  Top-5 gap: {baseline_gap['top5']:+.1f}%")

    # Evaluate combined weights
    print("\n" + "="*80)
    print(" COMBINED WEIGHTS (2023 + 2025)")
    print("="*80)

    combined_2023 = evaluate_dataset(data_2023, combined_weights, "2023 Keeneland")
    combined_2025 = evaluate_dataset(data_2025, combined_weights, "2025 Keeneland")

    print(f"\n2023 Performance:")
    print(f"  Win:   {combined_2023['wins']}/{combined_2023['total_races']} = {combined_2023['win_rate']*100:.1f}%")
    print(f"  Top-3: {combined_2023['top3']}/{combined_2023['total_races']} = {combined_2023['top3_rate']*100:.1f}%")
    print(f"  Top-5: {combined_2023['top5']}/{combined_2023['total_races']} = {combined_2023['top5_rate']*100:.1f}%")

    print(f"\n2025 Performance:")
    print(f"  Win:   {combined_2025['wins']}/{combined_2025['total_races']} = {combined_2025['win_rate']*100:.1f}%")
    print(f"  Top-3: {combined_2025['top3']}/{combined_2025['total_races']} = {combined_2025['top3_rate']*100:.1f}%")
    print(f"  Top-5: {combined_2025['top5']}/{combined_2025['total_races']} = {combined_2025['top5_rate']*100:.1f}%")

    combined_gap = {
        'win': (combined_2025['win_rate'] - combined_2023['win_rate']) * 100,
        'top3': (combined_2025['top3_rate'] - combined_2023['top3_rate']) * 100,
        'top5': (combined_2025['top5_rate'] - combined_2023['top5_rate']) * 100,
    }

    print(f"\nGap (2025 - 2023):")
    print(f"  Win gap:   {combined_gap['win']:+.1f}%")
    print(f"  Top-3 gap: {combined_gap['top3']:+.1f}%")
    print(f"  Top-5 gap: {combined_gap['top5']:+.1f}%")

    # Summary comparison
    print("\n" + "="*80)
    print(" GENERALIZATION IMPROVEMENT SUMMARY")
    print("="*80)

    print(f"\nGap Reduction (Absolute %, smaller is better):")
    win_improvement = abs(combined_gap['win']) - abs(baseline_gap['win'])
    top3_improvement = abs(combined_gap['top3']) - abs(baseline_gap['top3'])
    top5_improvement = abs(combined_gap['top5']) - abs(baseline_gap['top5'])

    print(f"  Win gap:   {abs(baseline_gap['win']):.1f}% → {abs(combined_gap['win']):.1f}% ({win_improvement:+.1f}% {'✓ IMPROVED' if win_improvement < 0 else '✗ WORSE'})")
    print(f"  Top-3 gap: {abs(baseline_gap['top3']):.1f}% → {abs(combined_gap['top3']):.1f}% ({top3_improvement:+.1f}% {'✓ IMPROVED' if top3_improvement < 0 else '✗ WORSE'})")
    print(f"  Top-5 gap: {abs(baseline_gap['top5']):.1f}% → {abs(combined_gap['top5']):.1f}% ({top5_improvement:+.1f}% {'✓ IMPROVED' if top5_improvement < 0 else '✗ WORSE'})")

    print(f"\nPerformance on 2023 (out-of-sample for baseline):")
    print(f"  Win:   {baseline_2023['win_rate']*100:.1f}% → {combined_2023['win_rate']*100:.1f}% ({(combined_2023['win_rate'] - baseline_2023['win_rate'])*100:+.1f}%)")
    print(f"  Top-3: {baseline_2023['top3_rate']*100:.1f}% → {combined_2023['top3_rate']*100:.1f}% ({(combined_2023['top3_rate'] - baseline_2023['top3_rate'])*100:+.1f}%)")

    print(f"\nPerformance on 2025 (in-sample for baseline):")
    print(f"  Win:   {baseline_2025['win_rate']*100:.1f}% → {combined_2025['win_rate']*100:.1f}% ({(combined_2025['win_rate'] - baseline_2025['win_rate'])*100:+.1f}%)")
    print(f"  Top-3: {baseline_2025['top3_rate']*100:.1f}% → {combined_2025['top3_rate']*100:.1f}% ({(combined_2025['top3_rate'] - baseline_2025['top3_rate'])*100:+.1f}%)")

    # Save report
    report = {
        'baseline_weights': baseline_weights,
        'combined_weights': combined_weights,
        'baseline_performance': {
            '2023': baseline_2023,
            '2025': baseline_2025,
            'gap': baseline_gap
        },
        'combined_performance': {
            '2023': combined_2023,
            '2025': combined_2025,
            'gap': combined_gap
        },
        'improvements': {
            'win_gap_change': win_improvement,
            'top3_gap_change': top3_improvement,
            'top5_gap_change': top5_improvement
        }
    }

    with open('output/weights_validation_report.json', 'w') as f:
        json.dump(report, f, indent=2)

    print("\n✅ Report saved to: output/weights_validation_report.json")
    print("="*80)


if __name__ == '__main__':
    main()
