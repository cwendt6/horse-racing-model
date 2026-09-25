import os
"""
Quick Enhanced Backtest Test
"""

import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.data_loaders.integrate_data import load_enhanced_races
from src.core.backtesting_framework import RacingBacktest

# Load enhanced races with FTS statistics
races, stats = load_enhanced_races(
    tch_dir='data/raw/Equibase Dataset/2023 Result Charts',
    simd_dir='data/raw/Equibase Dataset/2023 PPs',
    jockey_stats_file='data/stats/jockey_statistics_comprehensive.json',
    trainer_stats_file='data/stats/trainer_statistics_comprehensive.json',
    fts_trainer_stats_file='data/stats/fts_trainer_statistics.json',
    fts_sire_stats_file='data/stats/fts_sire_statistics.json'
)

print("\n" + "="*80)
print(" ENHANCED BACKTEST - QUICK TEST")
print("="*80)

# Test baseline weights
baseline_weights = {
    'speed': 0.30,
    'form': 0.20,
    'class': 0.15,
    'pace': 0.15,
    'jockey': 0.10,
    'trainer': 0.10,
}

bt = RacingBacktest(scoring_weights=baseline_weights)
metrics = bt.run_backtest(races)

print(f"\nTotal Races: {metrics.total_races}")
print(f"Horses with Enhanced Data: {stats['enhanced_horses']}/{stats['total_horses']} ({stats['enhanced_horses']/stats['total_horses']*100:.1f}%)")
print()
print(f"Top Pick Win Rate:        {metrics.top_pick_win_rate:>6.2%}")
print(f"Top 3 Accuracy:           {metrics.top_3_accuracy:>6.2%}")
print(f"Win Bet ROI:              {metrics.win_bet_roi:>6.2f}%")
print(f"Brier Score:              {metrics.brier_score:.4f}")

# Show a sample race prediction
print("\n" + "="*80)
print(" SAMPLE PREDICTION (First race with varied data)")
print("="*80)

for race in races[50:60]:
    # Find race with varied speed figures
    best_beyers = []
    for horse in race.horses:
        if hasattr(horse, '_enhanced_best_beyer'):
            best_beyers.append(horse._enhanced_best_beyer)

    if len(set(best_beyers)) >= 5:
        print(f"\nRace {race.race_number} at {race.track_code} - {race.distance_text}")
        print(f"{len(race.horses)} horses\n")

        # Get predictions for this race
        # Use a new backtester instance just for this race
        bt_single = RacingBacktest(scoring_weights=baseline_weights)
        results = bt_single.run_backtest([race])

        # Show top 5 horses by score
        # Sort horses by their enhanced speed figures as proxy
        horses_with_data = [(h, getattr(h, '_enhanced_best_beyer', 50))
                           for h in race.horses]
        horses_with_data.sort(key=lambda x: x[1], reverse=True)

        print(f"{'Horse':<25} {'Beyer':>6} {'Style':>6} {'Starts':>6} {'Jockey%':>8} {'FTS':>5}")
        print("-"*80)
        for horse, beyer in horses_with_data[:8]:
            if hasattr(horse, '_enhanced_best_beyer'):
                fts_marker = "FTS!" if getattr(horse, '_is_fts', False) else ""
                print(f"{horse.name:<25} {horse._enhanced_best_beyer:>6.0f} {horse._enhanced_running_style:>6} {horse._enhanced_career_starts:>6} {horse._enhanced_jockey_win_pct:>7.1%} {fts_marker:>5}")

        # Show actual winner
        winner = next((h for h in race.horses if h.final_position == 1), None)
        if winner:
            print(f"\nActual Winner: {winner.name}")

        break

print("\n" + "="*80)
print()
