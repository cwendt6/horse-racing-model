#!/usr/bin/env python3
"""Analyze what distances are run at Keeneland"""

import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import os
import glob
from collections import Counter
from src.parsers.tch_parser import parse_tch_file

print("=" * 80)
print("KEENELAND DISTANCE ANALYSIS")
print("=" * 80)

# Find all Keeneland result files
kee_files = glob.glob("equibase 2023 data/2023 Result Charts/kee*.xml")
print(f"\nFound {len(kee_files)} Keeneland result files\n")

# Track distances
distances = Counter()
surfaces = Counter()
race_types = Counter()

for tch_file in kee_files:
    try:
        races = parse_tch_file(tch_file)
        for race in races:
            if hasattr(race, 'distance') and race.distance:
                distances[race.distance] += 1
            if hasattr(race, 'surface') and race.surface:
                surfaces[race.surface] += 1
            if hasattr(race, 'race_type') and race.race_type:
                race_types[race.race_type] += 1
    except Exception as e:
        print(f"Error parsing {tch_file}: {e}")
        continue

# Display results
print("\n" + "=" * 80)
print("DISTANCES AT KEENELAND (2023)")
print("=" * 80)
for distance, count in distances.most_common():
    print(f"{distance:>10s}: {count:>3d} races")

print("\n" + "=" * 80)
print("SURFACES AT KEENELAND")
print("=" * 80)
for surface, count in surfaces.most_common():
    print(f"{surface:>10s}: {count:>3d} races")

print("\n" + "=" * 80)
print("RACE TYPES AT KEENELAND")
print("=" * 80)
for race_type, count in race_types.most_common(10):
    print(f"{race_type:>10s}: {count:>3d} races")

# Suggest distances to keep
print("\n" + "=" * 80)
print("RECOMMENDED DISTANCES TO KEEP")
print("=" * 80)
print("Based on Keeneland 2023 racing:\n")
keeneland_distances = set(distances.keys())
print(f"Keeneland uses these {len(keeneland_distances)} distances:")
for dist in sorted(keeneland_distances):
    print(f"  - {dist}")

print("\n" + "=" * 80)
print("DISTANCES TO REMOVE")
print("=" * 80)
print("These are NOT run at Keeneland and should be filtered out:")
print("  - All yard distances (440Y, 870Y, etc.) - Quarter Horse racing")
print("  - Any other distances not in the Keeneland list above")
