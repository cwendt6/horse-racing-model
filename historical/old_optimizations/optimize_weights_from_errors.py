"""
Optimize Weights Based on Full 2023 Results
Uses actual 2023 results to find optimal weights through grid search
"""

import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import json
import os
from datetime import datetime
from glob import glob

from src.data_loaders.integrate_data import load_enhanced_races
from src.core.weight_optimizer import WeightOptimizer


def main():
    """Run weight optimization on full 2023 dataset"""
    print("\n" + "="*80)
    print(" WEIGHT OPTIMIZATION - FULL 2023 DATASET")
    print("="*80)
    print(f"\nStarted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Load all 2023 data with results
    print("\nStep 1: Loading full 2023 dataset with results...")
    races, stats = load_enhanced_races(
        tch_dir='equibase 2023 data/2023 Result Charts',
        simd_dir='equibase 2023 data/2023 PPs',
        jockey_stats_file='data/stats/jockey_statistics_comprehensive.json',
        trainer_stats_file='data/stats/trainer_statistics_comprehensive.json',
        fts_trainer_stats_file='data/stats/fts_trainer_statistics.json',
        fts_sire_stats_file='data/stats/fts_sire_statistics.json'
    )

    print(f"\n✓ Data loaded successfully:")
    print(f"  Total races: {stats['total_races']}")
    print(f"  Total horses: {stats['total_horses']}")
    print(f"  Enhanced horses: {stats['enhanced_horses']} ({stats['enhanced_horses']/stats['total_horses']*100:.1f}%)")

    # Load current weights
    print("\nStep 2: Loading current weights...")
    try:
        with open('output/optimized_weights_2023_full.json', 'r') as f:
            current_weights = json.load(f)
        print("✓ Current weights loaded:")
        for factor, weight in current_weights.items():
            print(f"    {factor:10s}: {weight:.4f}")
    except:
        current_weights = None
        print("! No previous weights found, will start fresh")

    # Define optimization parameters
    print("\nStep 3: Setting up optimization...")
    print("\nOptimization Parameters:")
    print("  Metric: ROI (Return on Investment)")
    print("  Method: Grid Search")
    print("  Iterations: ~100-200 weight combinations")

    # Create optimizer
    optimizer = WeightOptimizer(races)

    # Test current weights first (if available)
    if current_weights:
        print("\nStep 4: Testing current weights...")
        from src.core.backtesting_framework import RacingBacktest
        bt = RacingBacktest(scoring_weights=current_weights)
        current_metrics = bt.run_backtest(races)

        print(f"\nCurrent Performance:")
        print(f"  Win Rate: {current_metrics.top_pick_win_rate:.2%}")
        print(f"  ROI: {current_metrics.win_bet_roi:+.2f}%")
        print(f"  Top 3 Accuracy: {current_metrics.top_3_accuracy:.2%}")
        print(f"  Exacta Hit Rate: {current_metrics.exacta_hit_rate:.2%}")

        baseline_roi = current_metrics.win_bet_roi
    else:
        baseline_roi = None

    # Run grid search
    print("\nStep 5: Running grid search optimization...")
    print("(This may take 30-60 minutes depending on dataset size)")

    param_grid = {
        'speed': [0.25, 0.27, 0.30, 0.32, 0.35, 0.38],
        'form': [0.18, 0.20, 0.22, 0.24, 0.26],
        'class': [0.14, 0.16, 0.18, 0.20, 0.22],
        'pace': [0.12, 0.14, 0.16, 0.18],
        'jockey': [0.06, 0.08, 0.10],
        'trainer': [0.06, 0.08, 0.10],
    }

    best_weights = optimizer.grid_search(param_grid, metric='roi')
    best_roi = optimizer.best_score

    print(f"\n✓ Optimization complete!")
    print(f"\nBest weights found:")
    for factor, weight in best_weights.items():
        change = ""
        if current_weights and factor in current_weights:
            diff = weight - current_weights[factor]
            change = f" ({diff:+.4f})"
        print(f"  {factor:10s}: {weight:.4f}{change}")

    print(f"\nBest ROI: {best_roi:+.2f}%")
    if baseline_roi:
        improvement = best_roi - baseline_roi
        print(f"Improvement: {improvement:+.2f}% vs current weights")

    # Test optimal weights
    print("\nStep 6: Testing optimal weights...")
    from src.core.backtesting_framework import RacingBacktest
    bt_optimal = RacingBacktest(scoring_weights=best_weights)
    optimal_metrics = bt_optimal.run_backtest(races)

    print(f"\nOptimal Performance:")
    print(f"  Win Rate: {optimal_metrics.top_pick_win_rate:.2%}")
    print(f"  ITM Rate: {(optimal_metrics.top_pick_wins + optimal_metrics.top_pick_places + optimal_metrics.top_pick_shows) / optimal_metrics.total_races:.2%}")
    print(f"  Top 3 Accuracy: {optimal_metrics.top_3_accuracy:.2%}")
    print(f"  Win ROI: {optimal_metrics.win_bet_roi:+.2f}%")
    print(f"  Exacta Hit Rate: {optimal_metrics.exacta_hit_rate:.2%}")
    print(f"  Brier Score: {optimal_metrics.brier_score:.4f}")

    # Save results
    print("\nStep 7: Saving results...")

    # Save new optimal weights
    weights_file = 'output/optimized_weights_2023_FULL_YEAR.json'
    with open(weights_file, 'w') as f:
        json.dump(best_weights, f, indent=2)
    print(f"✓ Optimal weights saved to: {weights_file}")

    # Save detailed report
    report = {
        'generated_at': datetime.now().isoformat(),
        'dataset': {
            'total_races': stats['total_races'],
            'total_horses': stats['total_horses'],
            'enhanced_horses': stats['enhanced_horses'],
            'coverage_pct': stats['enhanced_horses']/stats['total_horses']*100,
        },
        'previous_weights': current_weights,
        'optimal_weights': best_weights,
        'performance': {
            'win_rate': optimal_metrics.top_pick_win_rate,
            'itm_rate': (optimal_metrics.top_pick_wins + optimal_metrics.top_pick_places + optimal_metrics.top_pick_shows) / optimal_metrics.total_races,
            'top_3_accuracy': optimal_metrics.top_3_accuracy,
            'win_roi': optimal_metrics.win_bet_roi,
            'exacta_hit_rate': optimal_metrics.exacta_hit_rate,
            'brier_score': optimal_metrics.brier_score,
        },
        'improvement': {
            'roi_change': best_roi - baseline_roi if baseline_roi else None,
        },
        'optimization_method': 'Grid Search',
        'metric_optimized': 'ROI',
    }

    report_file = f'output/2023_predictions/weight_optimization_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)
    print(f"✓ Optimization report saved to: {report_file}")

    # Summary
    print("\n" + "="*80)
    print(" OPTIMIZATION SUMMARY")
    print("="*80)

    print(f"\nDataset: {stats['total_races']} races from full 2023 season")
    print(f"Coverage: {stats['enhanced_horses']/stats['total_horses']*100:.1f}%")

    print(f"\nOptimal Weights:")
    for factor, weight in best_weights.items():
        print(f"  {factor:10s}: {weight:.4f}")

    print(f"\nPerformance:")
    print(f"  Win Rate: {optimal_metrics.top_pick_win_rate:.2%}")
    print(f"  Win ROI: {optimal_metrics.win_bet_roi:+.2f}%")
    print(f"  Top 3 Accuracy: {optimal_metrics.top_3_accuracy:.2%}")

    if baseline_roi:
        print(f"\nImprovement over previous weights:")
        print(f"  ROI: {best_roi - baseline_roi:+.2f}%")

    print(f"\nRecommendation:")
    if baseline_roi and best_roi > baseline_roi:
        print(f"  ✅ USE NEW WEIGHTS - {best_roi - baseline_roi:+.2f}% ROI improvement")
    elif baseline_roi:
        print(f"  ⚠️  KEEP CURRENT WEIGHTS - No significant improvement")
    else:
        print(f"  ✅ USE THESE WEIGHTS - Optimized on full 2023 dataset")

    print(f"\n✓ Optimization complete!")
    print(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    print()


if __name__ == '__main__':
    main()
