#!/usr/bin/env python3
"""Filter predictions to Thoroughbred distances only (remove QH < 440Y)"""

import json
import sys
from datetime import datetime

print("=" * 80)
print("FILTERING TO THOROUGHBRED DISTANCES ONLY")
print("=" * 80)

# Load predictions
print("\n1. Loading predictions...")
with open('output/2023_predictions/all_predictions_20251018_201921.json', 'r') as f:
    data = json.load(f)

original_count = len(data['predictions'])
print(f"   Original races: {original_count:,}")

# Define QH-only distances to remove (< 440Y / 2F)
qh_distances = {'100Y', '110Y', '220Y', '250Y', '300Y', '330Y', '350Y', '400Y'}

print("\n2. Filtering out Quarter Horse distances...")
print(f"   Removing: {', '.join(sorted(qh_distances))}")

# Filter predictions
thoroughbred_predictions = []
qh_removed = []

for pred in data['predictions']:
    distance = pred.get('distance', '')
    if distance in qh_distances:
        qh_removed.append(pred)
    else:
        thoroughbred_predictions.append(pred)

tb_count = len(thoroughbred_predictions)
qh_count = len(qh_removed)

print(f"\n   ✓ Kept: {tb_count:,} Thoroughbred races ({tb_count/original_count*100:.1f}%)")
print(f"   ✗ Removed: {qh_count:,} Quarter Horse races ({qh_count/original_count*100:.1f}%)")

# Save filtered predictions
print("\n3. Saving filtered predictions...")
filtered_data = {
    'metadata': {
        'generated': datetime.now().isoformat(),
        'model_version': '2.0',
        'total_races': tb_count,
        'filtered_from': original_count,
        'removed_qh_races': qh_count,
        'distance_filter': 'Thoroughbred only (>= 440Y / 2F)',
        'weights': data.get('metadata', {}).get('weights', {})
    },
    'predictions': thoroughbred_predictions
}

output_file = 'output/2023_predictions/thoroughbred_only_predictions.json'
with open(output_file, 'w') as f:
    json.dump(filtered_data, f, indent=2)

print(f"   ✓ Saved to: {output_file}")

# Show distance breakdown
print("\n" + "=" * 80)
print("THOROUGHBRED DISTANCE BREAKDOWN")
print("=" * 80)

from collections import Counter
distances = Counter(pred['distance'] for pred in thoroughbred_predictions)

print(f"\nTop 15 distances in Thoroughbred dataset ({tb_count:,} races):")
for dist, count in distances.most_common(15):
    pct = (count / tb_count) * 100
    print(f"  {dist:>10s}: {count:>5,d} races ({pct:>5.1f}%)")

print("\n" + "=" * 80)
print("COMPLETE")
print("=" * 80)
print(f"\nFiltered dataset ready for analysis:")
print(f"  • Thoroughbred races: {tb_count:,}")
print(f"  • Quarter Horse removed: {qh_count:,}")
print(f"  • File: {output_file}")
