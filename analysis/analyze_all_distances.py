#!/usr/bin/env python3
"""Analyze all distances in 2023 predictions for review"""

import json
from collections import Counter

# Load predictions
with open('output/2023_predictions/all_predictions_20251018_201921.json', 'r') as f:
    data = json.load(f)

predictions = data['predictions']

# Count distances
distances = Counter()
for pred in predictions:
    dist = pred.get('distance', 'Unknown')
    distances[dist] += 1

print("=" * 80)
print("ALL DISTANCES IN 2023 PREDICTIONS")
print("=" * 80)
print(f"Total races: {len(predictions):,}\n")

# Sort by count
print("Distance | Count | % of Total | Category")
print("-" * 80)

total = len(predictions)
for dist, count in distances.most_common():
    pct = (count / total) * 100

    # Categorize
    if 'Y' in str(dist):
        yards = int(dist.replace('Y', ''))
        if yards < 440:
            category = "❌ Pure Quarter Horse (< 2F)"
        elif yards <= 1200:
            category = "✅ TB/Keeneland-style sprint"
        else:
            category = "✅ Thoroughbred"
    elif 'F' in str(dist):
        category = "✅ Thoroughbred"
    elif 'M' in str(dist) or '/' in str(dist):
        category = "✅ Thoroughbred"
    else:
        category = "❓ Unknown format"

    print(f"{dist:>8s} | {count:>5,d} | {pct:>6.2f}% | {category}")

print("\n" + "=" * 80)
print("RECOMMENDATION")
print("=" * 80)
print("\n❌ REMOVE these distances (Pure Quarter Horse, < 440Y / 2F):")
qh_distances = [d for d in distances.keys() if 'Y' in str(d) and int(d.replace('Y', '')) < 440]
if qh_distances:
    for d in sorted(qh_distances):
        print(f"   - {d} ({distances[d]:,} races)")
else:
    print("   None found!")

print("\n✅ KEEP these distances (Thoroughbred & Keeneland-style):")
print("   - All distances >= 440Y (2F)")
print("   - All standard furlongs (4F, 5F, 6F, 7F, etc.)")
print("   - All mile distances (1M, 1 1/8M, 1 1/4M, etc.)")
