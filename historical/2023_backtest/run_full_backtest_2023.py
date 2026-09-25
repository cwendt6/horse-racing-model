import os
"""
Full 2023 Backtest with All Improvements
Tests model on complete 2023 dataset with FTS, Pace, and optimized weights
"""

import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import json
import numpy as np
from datetime import datetime

from src.data_loaders.integrate_data import load_enhanced_races
from src.core.backtesting_framework import RacingBacktest
from src.core.weight_optimizer import WeightOptimizer

print("\n" + "="*80)
print(" FULL 2023 BACKTEST - ALL IMPROVEMENTS")
print("="*80)
print(f"\nStarted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# Load all 2023 enhanced races with FTS and statistics
print("\n" + "-"*80)
print(" STEP 1: Loading Data")
print("-"*80)

races, stats = load_enhanced_races(
    tch_dir='data/raw/Equibase Dataset/2023 Result Charts',
    simd_dir='data/raw/Equibase Dataset/2023 PPs',
    jockey_stats_file='data/stats/jockey_statistics_comprehensive.json',
    trainer_stats_file='data/stats/trainer_statistics_comprehensive.json',
    fts_trainer_stats_file='data/stats/fts_trainer_statistics.json',
    fts_sire_stats_file='data/stats/fts_sire_statistics.json'
)

print(f"\nData loaded successfully:")
print(f"  Total races: {stats['total_races']}")
print(f"  Total horses: {stats['total_horses']}")
print(f"  Enhanced horses: {stats['enhanced_horses']} ({stats['enhanced_horses']/stats['total_horses']*100:.1f}%)")

# Test different weight configurations
print("\n" + "-"*80)
print(" STEP 2: Testing Weight Configurations")
print("-"*80)

weight_configurations = {
    'Baseline (Original)': {
        'speed': 0.30,
        'form': 0.20,
        'class': 0.15,
        'pace': 0.15,
        'jockey': 0.10,
        'trainer': 0.10,
    },
    'Speed Focused': {
        'speed': 0.40,
        'form': 0.20,
        'class': 0.15,
        'pace': 0.10,
        'jockey': 0.075,
        'trainer': 0.075,
    },
    'Class Focused': {
        'speed': 0.25,
        'form': 0.20,
        'class': 0.30,
        'pace': 0.15,
        'jockey': 0.05,
        'trainer': 0.05,
    },
    'Balanced': {
        'speed': 0.27,
        'form': 0.23,
        'class': 0.20,
        'pace': 0.15,
        'jockey': 0.08,
        'trainer': 0.07,
    },
}

results_summary = {}

for config_name, weights in weight_configurations.items():
    print(f"\nTesting: {config_name}")
    print(f"  Weights: {weights}")

    bt = RacingBacktest(scoring_weights=weights)
    metrics = bt.run_backtest(races)

    results_summary[config_name] = {
        'weights': weights,
        'win_rate': metrics.top_pick_win_rate,
        'itm_rate': (metrics.top_pick_wins + metrics.top_pick_places + metrics.top_pick_shows) / metrics.total_races,
        'top_3_accuracy': metrics.top_3_accuracy,
        'win_roi': metrics.win_bet_roi,
        'brier_score': metrics.brier_score,
    }

    print(f"  Win Rate: {metrics.top_pick_win_rate:.2%}")
    print(f"  ITM Rate: {results_summary[config_name]['itm_rate']:.2%}")
    print(f"  Top 3 Accuracy: {metrics.top_3_accuracy:.2%}")
    print(f"  Win ROI: {metrics.win_bet_roi:+.2f}%")
    print(f"  Brier Score: {metrics.brier_score:.4f}")

# Find best configuration
print("\n" + "-"*80)
print(" STEP 3: Best Configuration Analysis")
print("-"*80)

best_win_rate = max(results_summary.items(), key=lambda x: x[1]['win_rate'])
best_roi = max(results_summary.items(), key=lambda x: x[1]['win_roi'])
best_itm = max(results_summary.items(), key=lambda x: x[1]['itm_rate'])

print(f"\nBest Win Rate: {best_win_rate[0]}")
print(f"  {best_win_rate[1]['win_rate']:.2%} win rate")
print(f"  Weights: {best_win_rate[1]['weights']}")

print(f"\nBest ROI: {best_roi[0]}")
print(f"  {best_roi[1]['win_roi']:+.2f}% ROI")
print(f"  Weights: {best_roi[1]['weights']}")

print(f"\nBest ITM Rate: {best_itm[0]}")
print(f"  {best_itm[1]['itm_rate']:.2%} ITM")
print(f"  Weights: {best_itm[1]['weights']}")

# Run grid search optimization
print("\n" + "-"*80)
print(" STEP 4: Grid Search Optimization")
print("-"*80)

print("\nRunning grid search to find optimal weights...")
print("(This may take several minutes)")

optimizer = WeightOptimizer(races)

# Define grid for optimization
param_grid = {
    'speed': [0.25, 0.27, 0.30, 0.32, 0.35],
    'form': [0.18, 0.20, 0.23, 0.25],
    'class': [0.15, 0.18, 0.20, 0.22],
    'pace': [0.12, 0.15, 0.18],
    'jockey': [0.07, 0.08, 0.10],
    'trainer': [0.07, 0.08, 0.10],
}

best_weights = optimizer.grid_search(param_grid, metric='roi')
best_score = optimizer.best_score

print(f"\nOptimization complete!")
print(f"  Best ROI: {best_score:+.2f}%")
print(f"  Optimal Weights: {best_weights}")

# Test optimal weights
print("\n" + "-"*80)
print(" STEP 5: Testing Optimal Weights")
print("-"*80)

bt_optimal = RacingBacktest(scoring_weights=best_weights)
optimal_metrics = bt_optimal.run_backtest(races)

print(f"\nOptimal Configuration Results:")
print(f"  Win Rate: {optimal_metrics.top_pick_win_rate:.2%}")
print(f"  ITM Rate: {(optimal_metrics.top_pick_wins + optimal_metrics.top_pick_places + optimal_metrics.top_pick_shows) / optimal_metrics.total_races:.2%}")
print(f"  Top 3 Accuracy: {optimal_metrics.top_3_accuracy:.2%}")
print(f"  Win ROI: {optimal_metrics.win_bet_roi:+.2f}%")
print(f"  Exacta Hit Rate: {optimal_metrics.exacta_hit_rate:.2%}")
print(f"  Brier Score: {optimal_metrics.brier_score:.4f}")

# Save results
print("\n" + "-"*80)
print(" STEP 6: Saving Results")
print("-"*80)

full_report = {
    'date_run': datetime.now().isoformat(),
    'dataset': {
        'total_races': stats['total_races'],
        'total_horses': stats['total_horses'],
        'enhanced_horses': stats['enhanced_horses'],
        'coverage_pct': stats['enhanced_horses']/stats['total_horses']*100,
    },
    'weight_configurations_tested': results_summary,
    'optimal_weights': best_weights,
    'optimal_performance': {
        'win_rate': optimal_metrics.top_pick_win_rate,
        'itm_rate': (optimal_metrics.top_pick_wins + optimal_metrics.top_pick_places + optimal_metrics.top_pick_shows) / optimal_metrics.total_races,
        'top_3_accuracy': optimal_metrics.top_3_accuracy,
        'win_roi': optimal_metrics.win_bet_roi,
        'exacta_hit_rate': optimal_metrics.exacta_hit_rate,
        'brier_score': optimal_metrics.brier_score,
    },
    'improvements_applied': [
        'FTS bias fix with trainer/sire statistics',
        'Pace scenario analysis',
        'Real past performance data integration',
        'Jockey and trainer win percentages',
    ]
}

report_file = 'output/backtests/full_2023_backtest_report.json'
with open(report_file, 'w') as f:
    json.dump(full_report, f, indent=2)

print(f"\n✓ Full report saved to: {report_file}")

# Save optimal weights
weights_file = 'output/optimized_weights_2023_full.json'
with open(weights_file, 'w') as f:
    json.dump(best_weights, f, indent=2)

print(f"✓ Optimal weights saved to: {weights_file}")

# Print summary
print("\n" + "="*80)
print(" FINAL SUMMARY")
print("="*80)

print(f"\n2023 Full Dataset Performance:")
print(f"  Races Analyzed: {stats['total_races']}")
print(f"  Data Coverage: {stats['enhanced_horses']/stats['total_horses']*100:.1f}%")
print(f"\nOptimal Model Performance:")
print(f"  Win Rate: {optimal_metrics.top_pick_win_rate:.2%} (Target: 15-20%)")
print(f"  ITM Rate: {(optimal_metrics.top_pick_wins + optimal_metrics.top_pick_places + optimal_metrics.top_pick_shows) / optimal_metrics.total_races:.2%} (Target: 55%+)")
print(f"  Win ROI: {optimal_metrics.win_bet_roi:+.2f}% (Target: +5%)")
print(f"  Top 3 Accuracy: {optimal_metrics.top_3_accuracy:.2%} (Target: 50%+)")

print(f"\nOptimal Weights:")
for factor, weight in best_weights.items():
    print(f"  {factor:10s}: {weight:.4f}")

print(f"\nCompleted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("="*80)
print()
