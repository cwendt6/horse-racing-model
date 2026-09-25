#!/usr/bin/env python3
"""Analyze model performance by surface to determine if surface-specific models would help"""

import json
from collections import defaultdict

print("=" * 80)
print("SURFACE-SPECIFIC PERFORMANCE ANALYSIS")
print("=" * 80)

# Load TB analysis results
with open('output/2023_predictions/thoroughbred_analysis_results.json', 'r') as f:
    data = json.load(f)

matches = data['matches']

# Organize by surface
by_surface = defaultdict(list)
for m in matches:
    surface = m.get('surface', 'Unknown')
    by_surface[surface].append(m)

# Analyze each surface
for surface in sorted(by_surface.keys()):
    surface_matches = by_surface[surface]
    surface_name = {'D': 'DIRT', 'T': 'TURF', 'A': 'ALL-WEATHER'}.get(surface, surface)

    print(f"\n{'=' * 80}")
    print(f"{surface_name}")
    print(f"{'=' * 80}")

    # Overall stats
    total_races = len(surface_matches)
    wins = sum(1 for m in surface_matches if m['is_win'])
    win_rate = (wins / total_races * 100) if total_races > 0 else 0

    # Calculate ROI
    total_bets = total_races * 2
    total_return = sum(m['model_odds'] * 2 for m in surface_matches if m['is_win'])
    roi = ((total_return - total_bets) / total_bets * 100) if total_bets > 0 else 0

    print(f"\nOverall Performance:")
    print(f"  Races:       {total_races:>6,d}")
    print(f"  Wins:        {wins:>6,d}")
    print(f"  Win Rate:    {win_rate:>6.2f}%")
    print(f"  Total Bets:  ${total_bets:>7,.2f}")
    print(f"  Total Return:${total_return:>7,.2f}")
    print(f"  Net P/L:     ${total_return - total_bets:>7,.2f}")
    print(f"  ROI:         {roi:>6.2f}%")

    # Performance by distance
    by_distance = defaultdict(lambda: {'total': 0, 'wins': 0, 'return': 0})
    for m in surface_matches:
        dist = m['distance']
        by_distance[dist]['total'] += 1
        if m['is_win']:
            by_distance[dist]['wins'] += 1
            by_distance[dist]['return'] += m['model_odds'] * 2

    # Sort by total races
    dist_sorted = sorted(by_distance.items(), key=lambda x: x[1]['total'], reverse=True)

    print(f"\nTop 10 Distances on {surface_name}:")
    print(f"{'Distance':<12} {'Races':<8} {'Wins':<8} {'Win %':<10} {'ROI':<10}")
    print("-" * 60)
    for dist, stats in dist_sorted[:10]:
        win_pct = (stats['wins'] / stats['total'] * 100) if stats['total'] > 0 else 0
        bets = stats['total'] * 2
        dist_roi = ((stats['return'] - bets) / bets * 100) if bets > 0 else 0
        print(f"{dist:<12} {stats['total']:<8} {stats['wins']:<8} {win_pct:<10.1f}% {dist_roi:<10.1f}%")

# Compare surfaces
print(f"\n{'=' * 80}")
print("SURFACE COMPARISON SUMMARY")
print(f"{'=' * 80}\n")

print(f"{'Surface':<15} {'Races':<10} {'Win %':<10} {'ROI':<10} {'Sample':<10}")
print("-" * 60)

surface_stats = {}
for surface in sorted(by_surface.keys()):
    surface_matches = by_surface[surface]
    surface_name = {'D': 'Dirt', 'T': 'Turf', 'A': 'All-Weather'}.get(surface, surface)

    total = len(surface_matches)
    wins = sum(1 for m in surface_matches if m['is_win'])
    win_rate = (wins / total * 100) if total > 0 else 0

    bets = total * 2
    returns = sum(m['model_odds'] * 2 for m in surface_matches if m['is_win'])
    roi = ((returns - bets) / bets * 100) if bets > 0 else 0

    sample_quality = "Large" if total > 1000 else "Medium" if total > 300 else "Small"

    surface_stats[surface] = {
        'name': surface_name,
        'total': total,
        'win_rate': win_rate,
        'roi': roi,
        'sample': sample_quality
    }

    print(f"{surface_name:<15} {total:<10,d} {win_rate:<10.2f}% {roi:>+9.2f}% {sample_quality:<10}")

# Recommendation
print(f"\n{'=' * 80}")
print("RECOMMENDATIONS")
print(f"{'=' * 80}\n")

dirt_stats = surface_stats.get('D', {})
turf_stats = surface_stats.get('T', {})

if dirt_stats and turf_stats:
    win_diff = abs(dirt_stats['win_rate'] - turf_stats['win_rate'])
    roi_diff = abs(dirt_stats['roi'] - turf_stats['roi'])

    print(f"Win Rate Difference: {win_diff:.2f}%")
    print(f"ROI Difference:      {roi_diff:.2f}%")

    if win_diff > 2.0 or roi_diff > 5.0:
        print("\n✅ RECOMMENDED: Build separate models for dirt and turf")
        print("   Significant performance difference between surfaces")
        print(f"   Better surface: {'Turf' if turf_stats['win_rate'] > dirt_stats['win_rate'] else 'Dirt'}")
    else:
        print("\n❌ NOT RECOMMENDED: Single model sufficient")
        print("   Performance is similar across surfaces")
        print("   Splitting may not improve ROI significantly")
else:
    print("\nInsufficient data to compare surfaces")

print(f"\n{'=' * 80}")
