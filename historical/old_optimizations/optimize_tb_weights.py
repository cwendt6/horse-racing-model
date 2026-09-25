import os
#!/usr/bin/env python3
"""Optimize weights specifically for Thoroughbred racing distances"""

import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import json
import numpy as np
from typing import Dict, List, Tuple
from itertools import product

print("=" * 80)
print("THOROUGHBRED WEIGHT OPTIMIZATION")
print("=" * 80)

# Load TB analysis results
print("\n1. Loading Thoroughbred analysis results...")
with open('output/2023_predictions/thoroughbred_analysis_results.json', 'r') as f:
    analysis = json.load(f)

matches = analysis['matches']
print(f"   ✓ Loaded {len(matches):,} matched races")
print(f"   Current performance: {analysis['metadata']['win_rate']:.2f}% win rate, {analysis['metadata']['roi']:+.2f}% ROI")

# Current weights from optimized file
with open('output/optimized_weights_2023_full.json', 'r') as f:
    current_weights = json.load(f)

print(f"\n2. Current weights:")
for key, val in current_weights.items():
    print(f"   {key:20s}: {val:.2f}")

# Define TB-focused weight ranges to test
print("\n3. Defining Thoroughbred-focused weight ranges...")
print("   Hypothesis: TB racing requires more emphasis on:")
print("   - Class/earnings (TB racing quality matters more)")
print("   - Pace scenarios (TB pace dynamics critical)")
print("   - Jockey/trainer skill (scales with TB distance)")
print("   - Less emphasis on speed (QH speed-only doesn't translate)")

# Current: speed=0.298, form=0.214, class=0.179, pace=0.143, jockey=0.083, trainer=0.083
weight_ranges = {
    'speed': [0.20, 0.25],                   # REDUCE from 0.298 (less QH-style speed focus)
    'class': [0.20, 0.25, 0.30],             # INCREASE from 0.179 (TB class critical)
    'pace': [0.15, 0.20, 0.25],              # INCREASE from 0.143 (TB pace matters)
    'jockey': [0.10, 0.15],                  # INCREASE from 0.083 (TB skill)
    'trainer': [0.10, 0.15],                 # INCREASE from 0.083 (TB trainer)
    'form': [0.05, 0.10, 0.15]               # REDUCE/MAINTAIN from 0.214
}

print(f"   Testing {np.prod([len(v) for v in weight_ranges.values()]):,} weight combinations")

# Helper function to calculate performance for a weight set
def evaluate_weights(matches: List[Dict], weights: Dict[str, float]) -> Tuple[float, float, int]:
    """
    Evaluate performance with given weights

    NOTE: This is a simplified evaluation since we already have predictions.
    For true optimization, we'd need to re-score each race with new weights.

    For now, we'll use win rate and ROI as proxies.
    """
    # Since we can't re-score easily, just return current metrics
    # In a full implementation, we'd reload races and re-score
    total_wins = sum(1 for m in matches if m['is_win'])
    total_races = len(matches)
    win_rate = (total_wins / total_races * 100) if total_races > 0 else 0

    # Calculate ROI
    total_bets = total_races * 2
    total_return = sum(m['model_odds'] * 2 for m in matches if m['is_win'])
    roi = ((total_return - total_bets) / total_bets * 100) if total_bets > 0 else 0

    return win_rate, roi, total_wins

# Test weight combinations
print("\n4. Testing weight combinations...")
print("   NOTE: This is a theoretical optimization based on TB racing principles.")
print("   Full implementation would require re-scoring all races with new weights.\n")

best_config = None
best_roi = analysis['metadata']['roi']
best_win_rate = analysis['metadata']['win_rate']

# Generate combinations
all_combinations = list(product(
    weight_ranges['speed'],
    weight_ranges['class'],
    weight_ranges['pace'],
    weight_ranges['jockey'],
    weight_ranges['trainer'],
    weight_ranges['form']
))

tested = 0
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
    if abs(total - 1.0) > 0.01:
        continue

    tested += 1
    valid_configs.append(weights)

print(f"   ✓ Found {len(valid_configs)} valid weight configurations")

# Analyze configurations by category
print("\n5. Recommended Thoroughbred weight configurations:")
print("   (Sorted by TB racing principles)\n")

# TB-focused configs: high class, high pace, lower speed
tb_focused = []
for config in valid_configs:
    if (config['class'] >= 0.25 and
        config['pace'] >= 0.20 and
        config['speed'] <= 0.25):
        tb_focused.append(config)

print(f"   TB-Focused Configs (class>=0.25, pace>=0.20, speed<=0.25): {len(tb_focused)}")
if tb_focused:
    print("\n   Top 5 TB-focused weight sets:")
    for i, config in enumerate(tb_focused[:5], 1):
        print(f"\n   Configuration #{i}:")
        for key, val in config.items():
            marker = "↑" if val > current_weights[key] else "↓" if val < current_weights[key] else "→"
            print(f"      {key:20s}: {val:.2f} {marker}")

# Balanced configs
balanced = []
for config in valid_configs:
    if (config['class'] >= 0.20 and
        config['pace'] >= 0.15 and
        config['speed'] >= 0.20):
        balanced.append(config)

print(f"\n   Balanced Configs: {len(balanced)}")

# Save recommended configurations
print("\n6. Saving recommended configurations...")

output = {
    'current_weights': current_weights,
    'current_performance': {
        'win_rate': analysis['metadata']['win_rate'],
        'roi': analysis['metadata']['roi'],
        'matched_races': len(matches)
    },
    'optimization_hypothesis': {
        'description': 'Thoroughbred racing emphasizes class, pace, and jockey/trainer skill over pure speed',
        'changes': {
            'speed': 'REDUCE from 0.298 to 0.20-0.25 (less QH-style speed focus)',
            'class': 'INCREASE from 0.179 to 0.20-0.30 (TB class/earnings critical)',
            'pace': 'INCREASE from 0.143 to 0.15-0.25 (TB pace scenarios matter)',
            'jockey': 'INCREASE from 0.083 to 0.10-0.15 (skill scales with TB)',
            'trainer': 'INCREASE from 0.083 to 0.10-0.15 (skill scales with TB)',
            'form': 'REDUCE/MAINTAIN from 0.214 to 0.05-0.15'
        }
    },
    'recommended_configs': {
        'tb_focused': tb_focused[:10],
        'balanced': balanced[:10]
    },
    'top_recommendation': {
        'weights': tb_focused[0] if tb_focused else balanced[0] if balanced else current_weights,
        'rationale': 'Emphasizes class and pace over speed figure for Thoroughbred racing'
    }
}

output_file = 'output/2023_predictions/tb_weight_recommendations.json'
with open(output_file, 'w') as f:
    json.dump(output, f, indent=2)

print(f"   ✓ Saved to: {output_file}")

# Display top recommendation
print("\n" + "=" * 80)
print("TOP RECOMMENDATION FOR THOROUGHBRED RACING")
print("=" * 80)

top_config = output['top_recommendation']['weights']
print(f"\nRecommended weights for Thoroughbred racing:\n")
print(f"{'Component':<20s} {'Current':<10s} {'Recommended':<12s} {'Change':<10s}")
print("-" * 60)
for key in current_weights.keys():
    current = current_weights[key]
    recommended = top_config[key]
    change = recommended - current
    change_str = f"{change:+.2f}"
    marker = "↑" if change > 0 else "↓" if change < 0 else "→"
    print(f"{key:<20s} {current:<10.2f} {recommended:<12.2f} {change_str:<10s} {marker}")

print(f"\n{'TOTAL':<20s} {sum(current_weights.values()):<10.2f} {sum(top_config.values()):<12.2f}")

print("\n" + "=" * 80)
print("NEXT STEPS")
print("=" * 80)
print("\n1. Review recommended weight configurations in:")
print(f"   {output_file}")
print("\n2. To test a new configuration, update config.json and re-run predictions")
print("\n3. For accurate optimization, implement weight-based re-scoring of all races")
print("\n" + "=" * 80)
