#!/usr/bin/env python3
"""Extract top picks from new model predictions"""
import re

with open('output/oct23_predictions_FINAL_TEST.txt', 'r') as f:
    content = f.read()

# Find all race sections
races = re.split(r'RACE (\d+):', content)

print("NEW MODEL TOP PICKS (with maiden weights + combos):")
print("=" * 60)

for i in range(1, len(races), 2):
    race_num = races[i].strip()
    race_content = races[i+1]

    # Look for maiden detection (appears AFTER previous race's predictions)
    is_maiden = '🎯 MAIDEN RACE DETECTED' in race_content

    # Find the top pick in "TOP 5 PREDICTIONS" section
    # Pattern: "1. #7 Sprint Out Pass [P]"
    match = re.search(r'TOP 5 PREDICTIONS.*?1\. #(\d+)\s+([^\[]+)', race_content, re.DOTALL)
    if match:
        horse_num = match.group(1)
        horse_name = match.group(2).strip()

        maiden_flag = ' [MAIDEN]' if is_maiden else ''
        print(f'Race {race_num}: #{horse_num} {horse_name}{maiden_flag}')
