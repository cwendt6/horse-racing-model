"""
Analyze Prediction Errors and Suggest Weight Adjustments
Identifies where the model makes mistakes and recommends improvements
"""

import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import json
import os
from glob import glob
from typing import Dict, List, Tuple
from datetime import datetime
from collections import defaultdict
import numpy as np

from src.parsers.equibase_parser import parse_equibase_files


def load_predictions(predictions_file: str) -> Dict:
    """Load predictions from JSON file"""
    with open(predictions_file, 'r') as f:
        return json.load(f)


def match_prediction_to_result(prediction: Dict, results: List) -> Dict:
    """Match a prediction to its corresponding result"""
    for result_race in results:
        if (result_race.track_code == prediction['track_code'] and
            result_race.race_number == prediction['race_number'] and
            result_race.date == prediction['date']):
            return result_race
    return None


def analyze_error_patterns(predictions: List[Dict], results: List) -> Dict:
    """
    Analyze patterns in prediction errors

    Returns detailed error analysis including:
    - Errors by race type
    - Errors by distance
    - Errors by surface
    - Errors by field size
    - Errors by pace scenario
    - Which factor scores were misleading
    """
    error_patterns = {
        'by_race_type': defaultdict(lambda: {'total': 0, 'correct': 0, 'wrong': 0}),
        'by_distance': defaultdict(lambda: {'total': 0, 'correct': 0, 'wrong': 0}),
        'by_surface': defaultdict(lambda: {'total': 0, 'correct': 0, 'wrong': 0}),
        'by_field_size': defaultdict(lambda: {'total': 0, 'correct': 0, 'wrong': 0}),
        'by_pace_scenario': defaultdict(lambda: {'total': 0, 'correct': 0, 'wrong': 0}),
        'by_purse_level': defaultdict(lambda: {'total': 0, 'correct': 0, 'wrong': 0}),
        'fts_performance': {'total': 0, 'correct': 0, 'wrong': 0},
        'non_fts_performance': {'total': 0, 'correct': 0, 'wrong': 0},
        'misses': [],  # Store details of wrong predictions
        'big_upsets': [],  # Longshots that won
    }

    for pred in predictions:
        result_race = match_prediction_to_result(pred, results)
        if not result_race:
            continue

        # Get winner
        winner = next((h for h in result_race.horses if h.final_position == 1), None)
        if not winner:
            continue

        # Get our top pick
        top_pick = pred['top_pick']
        if not top_pick:
            continue

        # Check if correct
        is_correct = (top_pick['program_number'] == winner.program_number)

        # Update error patterns
        race_type = pred.get('race_type', 'Unknown')
        distance = pred.get('distance', 'Unknown')
        surface = pred.get('surface', 'Unknown')
        field_size = pred.get('field_size', 0)
        pace_scenario = pred.get('pace_scenario', 'Unknown')
        purse = pred.get('purse', 0)

        # Categorize by race type
        error_patterns['by_race_type'][race_type]['total'] += 1
        if is_correct:
            error_patterns['by_race_type'][race_type]['correct'] += 1
        else:
            error_patterns['by_race_type'][race_type]['wrong'] += 1

        # Categorize by distance
        error_patterns['by_distance'][distance]['total'] += 1
        if is_correct:
            error_patterns['by_distance'][distance]['correct'] += 1
        else:
            error_patterns['by_distance'][distance]['wrong'] += 1

        # Categorize by surface
        error_patterns['by_surface'][surface]['total'] += 1
        if is_correct:
            error_patterns['by_surface'][surface]['correct'] += 1
        else:
            error_patterns['by_surface'][surface]['wrong'] += 1

        # Categorize by field size
        size_category = 'Small (≤7)' if field_size <= 7 else 'Medium (8-10)' if field_size <= 10 else 'Large (11+)'
        error_patterns['by_field_size'][size_category]['total'] += 1
        if is_correct:
            error_patterns['by_field_size'][size_category]['correct'] += 1
        else:
            error_patterns['by_field_size'][size_category]['wrong'] += 1

        # Categorize by pace scenario
        error_patterns['by_pace_scenario'][pace_scenario]['total'] += 1
        if is_correct:
            error_patterns['by_pace_scenario'][pace_scenario]['correct'] += 1
        else:
            error_patterns['by_pace_scenario'][pace_scenario]['wrong'] += 1

        # Categorize by purse level
        purse_category = 'Low (<$30k)' if purse < 30000 else 'Medium ($30k-$100k)' if purse < 100000 else 'High ($100k+)'
        error_patterns['by_purse_level'][purse_category]['total'] += 1
        if is_correct:
            error_patterns['by_purse_level'][purse_category]['correct'] += 1
        else:
            error_patterns['by_purse_level'][purse_category]['wrong'] += 1

        # Track FTS performance
        if top_pick.get('is_fts', False):
            error_patterns['fts_performance']['total'] += 1
            if is_correct:
                error_patterns['fts_performance']['correct'] += 1
            else:
                error_patterns['fts_performance']['wrong'] += 1
        else:
            error_patterns['non_fts_performance']['total'] += 1
            if is_correct:
                error_patterns['non_fts_performance']['correct'] += 1
            else:
                error_patterns['non_fts_performance']['wrong'] += 1

        # Store misses for detailed analysis
        if not is_correct:
            # Find where winner was ranked
            winner_rank = None
            winner_pred = None
            for p in pred['predictions']:
                if p['program_number'] == winner.program_number:
                    winner_rank = p['rank']
                    winner_pred = p
                    break

            error_patterns['misses'].append({
                'track': pred['track_code'],
                'race': pred['race_number'],
                'date': pred['date'],
                'race_type': race_type,
                'distance': distance,
                'surface': surface,
                'our_pick': {
                    'number': top_pick['program_number'],
                    'name': top_pick['horse_name'],
                    'probability': top_pick['win_probability'],
                    'actual_finish': next((h.final_position for h in result_race.horses
                                          if h.program_number == top_pick['program_number']), None),
                },
                'actual_winner': {
                    'number': winner.program_number,
                    'name': winner.name,
                    'our_rank': winner_rank,
                    'our_probability': winner_pred['win_probability'] if winner_pred else 0,
                    'payoff': winner.win_payoff if hasattr(winner, 'win_payoff') else None,
                }
            })

        # Track big upsets (longshots that won)
        if is_correct and top_pick.get('win_probability', 0) < 0.10:
            error_patterns['big_upsets'].append({
                'track': pred['track_code'],
                'race': pred['race_number'],
                'date': pred['date'],
                'winner': {
                    'number': winner.program_number,
                    'name': winner.name,
                    'our_probability': top_pick['win_probability'],
                    'payoff': winner.win_payoff if hasattr(winner, 'win_payoff') else None,
                }
            })

    return error_patterns


def calculate_win_rates_by_category(error_patterns: Dict) -> Dict:
    """Calculate win rates for each category"""
    win_rates = {}

    for category_name, category_data in error_patterns.items():
        if category_name in ['misses', 'big_upsets', 'fts_performance', 'non_fts_performance']:
            continue

        win_rates[category_name] = {}
        for subcategory, stats in category_data.items():
            if stats['total'] > 0:
                win_rate = stats['correct'] / stats['total']
                win_rates[category_name][subcategory] = {
                    'win_rate': win_rate,
                    'total_races': stats['total'],
                    'correct': stats['correct'],
                    'wrong': stats['wrong'],
                }

    return win_rates


def identify_weak_areas(win_rates: Dict, threshold: float = 0.15) -> List[Dict]:
    """
    Identify areas where model performs below threshold

    Args:
        win_rates: Win rates by category
        threshold: Minimum acceptable win rate (default 15%)

    Returns:
        List of weak areas with details
    """
    weak_areas = []

    for category, subcategories in win_rates.items():
        for subcategory, stats in subcategories.items():
            if stats['win_rate'] < threshold and stats['total_races'] >= 10:
                weak_areas.append({
                    'category': category,
                    'subcategory': subcategory,
                    'win_rate': stats['win_rate'],
                    'total_races': stats['total_races'],
                    'deficit': threshold - stats['win_rate'],
                })

    # Sort by deficit (worst first)
    weak_areas.sort(key=lambda x: x['deficit'], reverse=True)

    return weak_areas


def suggest_weight_adjustments(error_patterns: Dict, win_rates: Dict,
                               current_weights: Dict) -> Dict:
    """
    Suggest weight adjustments based on error analysis

    Returns recommendations for weight changes
    """
    recommendations = {
        'summary': '',
        'weight_changes': [],
        'reasoning': [],
    }

    # Analyze if certain factors are consistently misleading
    # This requires looking at the misses and seeing patterns

    total_misses = len(error_patterns['misses'])
    if total_misses > 0:
        # Sample some misses to understand patterns
        sample_size = min(100, total_misses)
        sample_misses = error_patterns['misses'][:sample_size]

        # Check FTS performance
        fts_stats = error_patterns['fts_performance']
        non_fts_stats = error_patterns['non_fts_performance']

        if fts_stats['total'] > 0:
            fts_win_rate = fts_stats['correct'] / fts_stats['total']
            non_fts_win_rate = non_fts_stats['correct'] / non_fts_stats['total'] if non_fts_stats['total'] > 0 else 0

            if fts_win_rate < non_fts_win_rate * 0.7:  # FTS performing significantly worse
                recommendations['reasoning'].append(
                    f"FTS picks have {fts_win_rate:.1%} win rate vs {non_fts_win_rate:.1%} for non-FTS. "
                    f"Consider tightening FTS multipliers."
                )

        # Check pace scenario performance
        pace_rates = win_rates.get('by_pace_scenario', {})
        if pace_rates:
            pace_sorted = sorted(pace_rates.items(), key=lambda x: x[1]['win_rate'])
            worst_pace = pace_sorted[0] if pace_sorted else None
            best_pace = pace_sorted[-1] if pace_sorted else None

            if worst_pace and best_pace:
                if worst_pace[1]['total_races'] >= 20:
                    recommendations['reasoning'].append(
                        f"Pace scenario '{worst_pace[0]}' has only {worst_pace[1]['win_rate']:.1%} win rate "
                        f"vs {best_pace[1]['win_rate']:.1%} for '{best_pace[0]}'. "
                        f"Pace weight may need adjustment."
                    )

    # Generate weight recommendations
    recommendations['summary'] = f"Analyzed {total_misses} missed predictions to identify patterns."

    return recommendations


def main():
    """Main analysis function"""
    print("\n" + "="*80)
    print(" PREDICTION ERROR ANALYSIS & WEIGHT OPTIMIZATION")
    print("="*80)

    # Find prediction file
    pred_files = glob('output/2023_predictions/all_predictions_*.json')
    if not pred_files:
        print("\n✗ No prediction files found!")
        return

    pred_file = sorted(pred_files)[-1]
    print(f"\nUsing predictions: {pred_file}")

    # Load predictions
    print("\nStep 1: Loading predictions...")
    pred_data = load_predictions(pred_file)
    predictions = pred_data['predictions']
    print(f"✓ Loaded {len(predictions)} predictions")

    # Load results
    print("\nStep 2: Loading results...")
    results_dir = 'equibase 2023 data/2023 Result Charts'
    if not os.path.exists(results_dir):
        print(f"\n✗ Results directory not found: {results_dir}")
        return

    results = parse_equibase_files(results_dir)
    print(f"✓ Loaded {len(results)} result races")

    # Analyze error patterns
    print("\nStep 3: Analyzing error patterns...")
    error_patterns = analyze_error_patterns(predictions, results)
    print("✓ Error analysis complete")

    # Calculate win rates by category
    print("\nStep 4: Calculating win rates by category...")
    win_rates = calculate_win_rates_by_category(error_patterns)
    print("✓ Win rates calculated")

    # Identify weak areas
    print("\nStep 5: Identifying weak areas...")
    weak_areas = identify_weak_areas(win_rates, threshold=0.15)
    print(f"✓ Found {len(weak_areas)} weak areas")

    # Suggest weight adjustments
    print("\nStep 6: Generating recommendations...")
    current_weights = pred_data.get('weights_used', {})
    recommendations = suggest_weight_adjustments(error_patterns, win_rates, current_weights)
    print("✓ Recommendations generated")

    # Display results
    print("\n" + "="*80)
    print(" ERROR ANALYSIS REPORT")
    print("="*80)

    # Win rates by category
    print("\n📊 WIN RATES BY CATEGORY:")
    print("-" * 80)

    for category, subcategories in sorted(win_rates.items()):
        print(f"\n{category.replace('_', ' ').title()}:")
        for subcat, stats in sorted(subcategories.items(), key=lambda x: x[1]['win_rate'], reverse=True):
            print(f"  {subcat:30s}: {stats['win_rate']:6.1%}  ({stats['correct']}/{stats['total_races']} races)")

    # FTS Performance
    print("\n" + "-" * 80)
    print("\n🎯 FTS PERFORMANCE:")
    fts_stats = error_patterns['fts_performance']
    non_fts_stats = error_patterns['non_fts_performance']

    if fts_stats['total'] > 0:
        fts_rate = fts_stats['correct'] / fts_stats['total']
        print(f"  FTS Picks:     {fts_rate:6.1%}  ({fts_stats['correct']}/{fts_stats['total']} races)")

    if non_fts_stats['total'] > 0:
        non_fts_rate = non_fts_stats['correct'] / non_fts_stats['total']
        print(f"  Non-FTS Picks: {non_fts_rate:6.1%}  ({non_fts_stats['correct']}/{non_fts_stats['total']} races)")

    # Weak areas
    if weak_areas:
        print("\n" + "-" * 80)
        print("\n⚠️  WEAK AREAS (Below 15% Win Rate):")
        for area in weak_areas[:10]:  # Show top 10
            print(f"  {area['category'].replace('_', ' ').title()} - {area['subcategory']}:")
            print(f"    Win Rate: {area['win_rate']:.1%} ({area['total_races']} races)")
            print(f"    Deficit: {area['deficit']:.1%}\n")

    # Recommendations
    print("\n" + "-" * 80)
    print("\n💡 RECOMMENDATIONS:")
    print(f"\n{recommendations['summary']}\n")
    for reason in recommendations['reasoning']:
        print(f"  • {reason}\n")

    # Sample of biggest misses
    print("\n" + "-" * 80)
    print("\n❌ SAMPLE OF BIGGEST MISSES (Top 10):")
    sorted_misses = sorted(error_patterns['misses'],
                          key=lambda x: x['our_pick']['probability'], reverse=True)
    for i, miss in enumerate(sorted_misses[:10], 1):
        print(f"\n  {i}. {miss['track']} R{miss['race']} ({miss['date']}) - {miss['race_type']}")
        print(f"     Our Pick: #{miss['our_pick']['number']} {miss['our_pick']['name']} "
              f"({miss['our_pick']['probability']:.1%} prob)")
        print(f"     Finished: {miss['our_pick']['actual_finish']}")
        print(f"     Winner: #{miss['actual_winner']['number']} {miss['actual_winner']['name']} "
              f"(we had at rank {miss['actual_winner']['our_rank']})")

    # Save detailed report
    report = {
        'generated_at': datetime.now().isoformat(),
        'predictions_file': pred_file,
        'results_directory': results_dir,
        'error_patterns': {k: v for k, v in error_patterns.items() if k not in ['misses', 'big_upsets']},
        'win_rates': win_rates,
        'weak_areas': weak_areas,
        'recommendations': recommendations,
        'sample_misses': sorted_misses[:50],
        'big_upsets': error_patterns['big_upsets'][:20],
    }

    report_file = f'output/2023_predictions/error_analysis_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)

    print(f"\n✓ Detailed analysis saved to: {report_file}")
    print("\n" + "="*80)
    print()


if __name__ == '__main__':
    main()
