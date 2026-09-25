#!/usr/bin/env python3
"""Optimize weights specifically for DIRT racing"""

import json
import numpy as np
from typing import Dict, List, Tuple
from itertools import product

print("=" * 80)
print("DIRT RACING WEIGHT OPTIMIZATION")
print("=" * 80)

# Load TB analysis results and filter for dirt
print("\n1. Loading dirt race results...")
with open('output/2023_predictions/thoroughbred_analysis_results.json', 'r') as f:
    data = json.load(f)

all_matches = data['matches']
dirt_matches = [m for m in all_matches if m.get('surface') == 'D']

print(f"   ✓ Loaded {len(dirt_matches):,} dirt races")

# Calculate current performance
total_wins = sum(1 for m in dirt_matches if m['is_win'])
total_races = len(dirt_matches)
win_rate = (total_wins / total_races * 100) if total_races > 0 else 0
total_bets = total_races * 2
total_return = sum(m['model_odds'] * 2 for m in dirt_matches if m['is_win'])
roi = ((total_return - total_bets) / total_bets * 100) if total_bets > 0 else 0

print(f"   Current performance: {win_rate:.2f}% win rate, {roi:+.2f}% ROI")

# Current weights
with open('output/optimized_weights_2023_full.json', 'r') as f:
    current_weights = json.load(f)

print(f"\n2. Current weights (all surfaces):")
for key, val in current_weights.items():
    print(f"   {key:10s}: {val:.3f}")

# Define DIRT-focused weight ranges
print("\n3. Defining DIRT-focused weight ranges...")
print("   Hypothesis for dirt racing:")
print("   - Speed figures MORE predictive (firm, consistent surface)")
print("   - Pace scenarios CRITICAL (speed duels matter)")
print("   - Class important (higher purses = better horses)")
print("   - Jockey/trainer moderate (skill matters but less than turf)")
print("   - Form moderate (recent performance indicator)")

# Current: speed=0.298, form=0.214, class=0.179, pace=0.143, jockey=0.083, trainer=0.083
weight_ranges = {
    'speed': [0.22, 0.25, 0.28],             # INCREASE from 0.298 (speed matters on dirt)
    'class': [0.20, 0.23, 0.25],             # INCREASE from 0.179 (quality matters)
    'pace': [0.18, 0.20, 0.22],              # INCREASE from 0.143 (pace critical on dirt)
    'jockey': [0.08, 0.10, 0.12],            # INCREASE slightly from 0.083
    'trainer': [0.08, 0.10, 0.12],           # INCREASE slightly from 0.083
    'form': [0.08, 0.10, 0.12]               # REDUCE from 0.214 (less weight)
}

print(f"   Testing {np.prod([len(v) for v in weight_ranges.values()]):,} weight combinations")

# Generate all valid combinations
all_combinations = list(product(
    weight_ranges['speed'],
    weight_ranges['class'],
    weight_ranges['pace'],
    weight_ranges['jockey'],
    weight_ranges['trainer'],
    weight_ranges['form']
))

valid_configs = []
for combo in all_combinations:
    weights = {
        'speed': combo[0],
        'class': combo[1],
        'pace': combo[2],
        'jockey': combo[3],
        'trainer': combo[4],
        'form': combo[5]
    }

    # Ensure weights sum to 1.0 (within tolerance)
    total = sum(weights.values())
    if abs(total - 1.0) <= 0.01:
        valid_configs.append(weights)

print(f"\n4. Found {len(valid_configs)} valid weight configurations")

# Filter for dirt-optimized configs
dirt_focused = []
for config in valid_configs:
    # Dirt racing: high speed, high pace, moderate class
    if (config['speed'] >= 0.25 and
        config['pace'] >= 0.18 and
        config['class'] >= 0.20):
        dirt_focused.append(config)

print(f"\n5. Dirt-Focused Configs (speed>=0.25, pace>=0.18, class>=0.20): {len(dirt_focused)}")

if dirt_focused:
    print("\n   Top 10 dirt-focused weight sets:")
    for i, config in enumerate(dirt_focused[:10], 1):
        print(f"\n   Configuration #{i}:")
        for key, val in config.items():
            marker = "↑" if val > current_weights[key] else "↓" if val < current_weights[key] else "→"
            print(f"      {key:10s}: {val:.2f} {marker}")

# Save recommendations
output = {
    'surface': 'DIRT',
    'current_weights': current_weights,
    'current_performance': {
        'races': len(dirt_matches),
        'wins': total_wins,
        'win_rate': win_rate,
        'roi': roi,
        'total_bets': total_bets,
        'total_return': total_return,
        'net_profit': total_return - total_bets
    },
    'optimization_hypothesis': {
        'description': 'Dirt racing emphasizes speed figures, pace scenarios, and class',
        'changes': {
            'speed': 'MAINTAIN/INCREASE 0.22-0.28 (speed figures predictive on dirt)',
            'class': 'INCREASE 0.20-0.25 (quality matters)',
            'pace': 'INCREASE 0.18-0.22 (pace duels critical)',
            'jockey': 'MAINTAIN/INCREASE 0.08-0.12',
            'trainer': 'MAINTAIN/INCREASE 0.08-0.12',
            'form': 'REDUCE 0.08-0.12 (less emphasis)'
        }
    },
    'recommended_configs': {
        'dirt_focused': dirt_focused[:20]
    },
    'top_recommendation': {
        'weights': dirt_focused[0] if dirt_focused else current_weights,
        'rationale': 'Emphasizes speed, pace, and class for dirt racing'
    }
}

output_file = 'output/2023_predictions/dirt_weight_recommendations.json'
with open(output_file, 'w') as f:
    json.dump(output, f, indent=2)

print(f"\n   ✓ Saved to: {output_file}")

# Display top recommendation
print("\n" + "=" * 80)
print("TOP RECOMMENDATION FOR DIRT RACING")
print("=" * 80)

top_config = output['top_recommendation']['weights']
print(f"\nRecommended weights for dirt racing:\n")
print(f"{'Component':<12} {'Current':<10} {'Recommended':<12} {'Change':<10}")
print("-" * 50)
for key in current_weights.keys():
    current = current_weights[key]
    recommended = top_config[key]
    change = recommended - current
    change_str = f"{change:+.3f}"
    marker = "↑" if change > 0 else "↓" if change < 0 else "→"
    print(f"{key:<12} {current:<10.3f} {recommended:<12.3f} {change_str:<10} {marker}")

print(f"\n{'TOTAL':<12} {sum(current_weights.values()):<10.3f} {sum(top_config.values()):<12.3f}")

print("\n" + "=" * 80)
print("DIRT RACING CHARACTERISTICS")
print("=" * 80)
print("\nWhy these weights for dirt:")
print("  • Speed figures: Firm, consistent surface = reliable speed figures")
print("  • Pace scenarios: Speed duels common on dirt = pace advantage critical")
print("  • Class: Better horses handle dirt racing better")
print("  • Jockey/trainer: Skill matters but less specialized than turf")
print("  • Form: Recent performance indicator but not primary factor")
print("\n" + "=" * 80)
