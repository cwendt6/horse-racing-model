import os
#!/usr/bin/env python3
"""Compare Thoroughbred predictions to actual results"""

import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import json
import glob
from collections import defaultdict
from src.parsers.equibase_parser import EquibaseXMLParser

print("=" * 80)
print("THOROUGHBRED PREDICTIONS VS ACTUAL RESULTS")
print("=" * 80)

# Load TB predictions
print("\n1. Loading Thoroughbred predictions...")
with open('output/2023_predictions/thoroughbred_only_predictions.json', 'r') as f:
    data = json.load(f)

predictions = data['predictions']
print(f"   ✓ Loaded {len(predictions):,} Thoroughbred predictions")

# Load results
print("\n2. Loading result files...")
parser = EquibaseXMLParser()
result_files = glob.glob('equibase 2023 data/2023 Result Charts/*.xml')
print(f"   Found {len(result_files):,} result files")

all_results = []
for i, result_file in enumerate(result_files):
    if (i + 1) % 500 == 0:
        print(f"   Parsing {i+1:,}/{len(result_files):,}...")
    try:
        races = parser.parse_tch_file(result_file)
        all_results.extend(races)
    except Exception:
        continue

print(f"   ✓ Loaded {len(all_results):,} result races")

# Match predictions to results
print("\n3. Matching predictions to results...")
matches = []
no_match = []

def normalize_date(date_str):
    """Normalize date format"""
    if '-' in date_str:
        return date_str.replace('-', '')
    return date_str

for pred in predictions:
    pred_date = normalize_date(pred['date'])
    pred_track = pred['track_code']
    pred_race = pred['race_number']

    # Find matching result
    matched = False
    for result in all_results:
        if (result.track_code == pred_track and
            result.race_number == pred_race and
            normalize_date(result.date) == pred_date):

            # Find winner
            winner = next((h for h in result.horses if h.final_position == 1), None)
            if winner:
                matches.append({
                    'prediction': pred,
                    'result': result,
                    'winner_name': winner.name,
                    'predicted_winner': pred['top_pick']['horse_name'],
                    'is_win': winner.name == pred['top_pick']['horse_name']
                })
                matched = True
                break

    if not matched:
        no_match.append(pred)

print(f"   ✓ Matched: {len(matches):,} races ({len(matches)/len(predictions)*100:.1f}%)")
print(f"   ✗ No match: {len(no_match):,} races")

# Calculate statistics
print("\n" + "=" * 80)
print("PERFORMANCE METRICS")
print("=" * 80)

wins = sum(1 for m in matches if m['is_win'])
total_bets = len(matches) * 2  # $2 per race

# Calculate return using model_odds (decimal format)
total_return = 0
for m in matches:
    if m['is_win']:
        # model_odds is decimal (e.g., 5.99 = $5.99 for $1)
        # For a $2 bet, payout = $2 * model_odds
        model_odds = m['prediction']['top_pick'].get('model_odds', 0)
        total_return += 2 * model_odds

net_profit = total_return - total_bets
roi = (net_profit / total_bets * 100) if total_bets > 0 else 0

print(f"\n📊 Overall Performance:")
print(f"   Win Rate:      {wins}/{len(matches)} = {wins/len(matches)*100:.2f}%")
print(f"   Total Bets:    ${total_bets:,.2f} ({len(matches):,} races × $2)")
print(f"   Total Return:  ${total_return:,.2f}")
print(f"   Net P/L:       ${net_profit:,.2f}")
print(f"   ROI:           {roi:+.2f}%")

# Performance by distance
print("\n📏 Performance by Distance:")
by_distance = defaultdict(lambda: {'total': 0, 'wins': 0})
for m in matches:
    dist = m['prediction']['distance']
    by_distance[dist]['total'] += 1
    if m['is_win']:
        by_distance[dist]['wins'] += 1

# Sort by total races
dist_sorted = sorted(by_distance.items(), key=lambda x: x[1]['total'], reverse=True)
print(f"\n{'Distance':<12} {'Races':<8} {'Wins':<8} {'Win %':<10}")
print("-" * 50)
for dist, stats in dist_sorted[:15]:
    win_pct = (stats['wins'] / stats['total'] * 100) if stats['total'] > 0 else 0
    print(f"{dist:<12} {stats['total']:<8} {stats['wins']:<8} {win_pct:<10.1f}%")

# Save detailed results (exclude Race objects which aren't JSON serializable)
serializable_matches = []
for m in matches:
    serializable_matches.append({
        'track_code': m['prediction']['track_code'],
        'race_number': m['prediction']['race_number'],
        'date': m['prediction']['date'],
        'distance': m['prediction']['distance'],
        'surface': m['prediction']['surface'],
        'winner_name': m['winner_name'],
        'predicted_winner': m['predicted_winner'],
        'is_win': m['is_win'],
        'model_odds': m['prediction']['top_pick'].get('model_odds', 0),
        'win_probability': m['prediction']['top_pick'].get('win_probability', 0)
    })

output = {
    'metadata': {
        'total_predictions': len(predictions),
        'matched_races': len(matches),
        'match_rate': len(matches) / len(predictions) * 100,
        'win_rate': wins / len(matches) * 100 if matches else 0,
        'roi': roi,
        'total_bets': total_bets,
        'total_return': total_return,
        'net_profit': net_profit
    },
    'matches': serializable_matches,
    'performance_by_distance': {
        dist: {
            'total': stats['total'],
            'wins': stats['wins'],
            'win_rate': (stats['wins'] / stats['total'] * 100) if stats['total'] > 0 else 0
        }
        for dist, stats in by_distance.items()
    }
}

output_file = 'output/2023_predictions/thoroughbred_analysis_results.json'
with open(output_file, 'w') as f:
    json.dump(output, f, indent=2)

print(f"\n\n✓ Detailed results saved to: {output_file}")
print("=" * 80)
