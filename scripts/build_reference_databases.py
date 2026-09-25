#!/usr/bin/env python3
"""
Build reference databases of trainers, jockeys, and horses from existing October PPs.
These will be used for fuzzy matching to correct extraction errors.
"""

import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.parsers.pdf_parser import parse_pdf_file
from src.utils.data_cleaning import clean_trainer_field, clean_jockey_field
import json
import os
from collections import defaultdict

# All October PP files
test_files = [
    'Keeneland October PPs/10-3-25-kee-ppspdf.pdf',
    'Keeneland October PPs/10-5-25-kee-ppspdf.pdf',
    'Keeneland October PPs/10-8-25-kee-ppspdf.pdf',
    'Keeneland October PPs/10-9-25-kee-ppspdf.pdf',
    'Keeneland October PPs/10-10-25-kee-ppspdf.pdf',
    'Keeneland October PPs/10-11-25-kee-ppspdf.pdf',
    'Keeneland October PPs/10-12-25-kee-ppspdf.pdf',
    'Keeneland October PPs/10-15-25-kee-ppspdf.pdf',
    'Keeneland October PPs/10-16-25-kee-ppspdf.pdf',
    'Keeneland October PPs/10-17-25-kee-ppspdf.pdf',
    'Keeneland October PPs/10-18-25-kee-ppspdf.pdf',
    'Keeneland October PPs/10-19-25-kee-ppspdf.pdf',
]

print('='*80)
print(' BUILDING REFERENCE DATABASES FROM OCTOBER 2025 PPs')
print('='*80)
print()

# Collect all unique names with frequency counts
trainers = defaultdict(int)
jockeys = defaultdict(int)
horses = defaultdict(int)
owners = defaultdict(int)
sires = defaultdict(int)
dams = defaultdict(int)

total_horses = 0
total_races = 0

for pdf_path in test_files:
    if not os.path.exists(pdf_path):
        continue

    date_label = pdf_path.split('/')[-1].replace('-kee-ppspdf.pdf', '')
    print(f'Processing {date_label}...')

    try:
        races = parse_pdf_file(pdf_path, debug=False)
        total_races += len(races)

        for race in races:
            for horse in race.horses:
                total_horses += 1

                # Collect trainers (cleaned)
                if horse.trainer_name and horse.trainer_name != 'Unknown':
                    cleaned_trainer = clean_trainer_field(horse.trainer_name)
                    if cleaned_trainer != 'Unknown' and len(cleaned_trainer) > 3:
                        # Exclude corrupted patterns
                        if not any(x in cleaned_trainer for x in ['Kee', 'Dirt:', 'Clm', '0 0 0']):
                            trainers[cleaned_trainer] += 1

                # Collect jockeys (cleaned)
                if horse.jockey_name and horse.jockey_name != 'Unknown':
                    cleaned_jockey = clean_jockey_field(horse.jockey_name)
                    if cleaned_jockey != 'Unknown' and len(cleaned_jockey) > 3:
                        # Exclude corrupted patterns
                        if not any(x in cleaned_jockey for x in ['Claimedby', 'Owner', 'Kee']):
                            jockeys[cleaned_jockey] += 1

                # Collect horses
                if horse.name and not horse.name.startswith('Horse ') and horse.name != 'Workout':
                    if len(horse.name) > 2:
                        horses[horse.name] += 1

                # Collect sires
                if horse.sire_name and horse.sire_name != 'Unknown' and len(horse.sire_name) > 2:
                    sires[horse.sire_name] += 1

                # Collect dams
                if horse.dam_name and horse.dam_name != 'Unknown' and len(horse.dam_name) > 2:
                    dams[horse.dam_name] += 1

    except Exception as e:
        print(f'  Error: {str(e)[:100]}')

print()
print('='*80)
print(' EXTRACTION SUMMARY')
print('='*80)
print()
print(f'Processed: {len([f for f in test_files if os.path.exists(f)])} PDFs')
print(f'Total Races: {total_races}')
print(f'Total Horses: {total_horses}')
print()
print(f'Unique Trainers: {len(trainers)}')
print(f'Unique Jockeys: {len(jockeys)}')
print(f'Unique Horses: {len(horses)}')
print(f'Unique Sires: {len(sires)}')
print(f'Unique Dams: {len(dams)}')
print()

# Filter out low-frequency entries (likely errors)
# Keep only names that appear 2+ times
MIN_FREQUENCY = 2

filtered_trainers = {name: count for name, count in trainers.items() if count >= MIN_FREQUENCY}
filtered_jockeys = {name: count for name, count in jockeys.items() if count >= MIN_FREQUENCY}
filtered_horses = {name: count for name, count in horses.items() if count >= MIN_FREQUENCY}
filtered_sires = {name: count for name, count in sires.items() if count >= MIN_FREQUENCY}
filtered_dams = {name: count for name, count in dams.items() if count >= MIN_FREQUENCY}

print('After filtering (min 2 occurrences):')
print(f'  Trainers: {len(filtered_trainers)}')
print(f'  Jockeys: {len(filtered_jockeys)}')
print(f'  Horses: {len(filtered_horses)}')
print(f'  Sires: {len(filtered_sires)}')
print(f'  Dams: {len(filtered_dams)}')
print()

# Show top entries
print('='*80)
print(' TOP TRAINERS')
print('='*80)
for name, count in sorted(filtered_trainers.items(), key=lambda x: x[1], reverse=True)[:20]:
    print(f'  {name:40s} ({count:3d} occurrences)')

print()
print('='*80)
print(' TOP JOCKEYS')
print('='*80)
for name, count in sorted(filtered_jockeys.items(), key=lambda x: x[1], reverse=True)[:20]:
    print(f'  {name:40s} ({count:3d} occurrences)')

print()

# Save to JSON files
output_dir = 'data/reference_databases'
os.makedirs(output_dir, exist_ok=True)

# Convert to lists sorted by frequency
trainer_list = [name for name, count in sorted(filtered_trainers.items(), key=lambda x: x[1], reverse=True)]
jockey_list = [name for name, count in sorted(filtered_jockeys.items(), key=lambda x: x[1], reverse=True)]
horse_list = [name for name, count in sorted(filtered_horses.items(), key=lambda x: x[1], reverse=True)]
sire_list = [name for name, count in sorted(filtered_sires.items(), key=lambda x: x[1], reverse=True)]
dam_list = [name for name, count in sorted(filtered_dams.items(), key=lambda x: x[1], reverse=True)]

# Save as JSON
with open(f'{output_dir}/trainers.json', 'w') as f:
    json.dump(trainer_list, f, indent=2)

with open(f'{output_dir}/jockeys.json', 'w') as f:
    json.dump(jockey_list, f, indent=2)

with open(f'{output_dir}/horses.json', 'w') as f:
    json.dump(horse_list, f, indent=2)

with open(f'{output_dir}/sires.json', 'w') as f:
    json.dump(sire_list, f, indent=2)

with open(f'{output_dir}/dams.json', 'w') as f:
    json.dump(dam_list, f, indent=2)

# Also save with frequency counts for debugging
with open(f'{output_dir}/trainers_with_counts.json', 'w') as f:
    json.dump(filtered_trainers, f, indent=2)

with open(f'{output_dir}/jockeys_with_counts.json', 'w') as f:
    json.dump(filtered_jockeys, f, indent=2)

with open(f'{output_dir}/horses_with_counts.json', 'w') as f:
    json.dump(filtered_horses, f, indent=2)

with open(f'{output_dir}/sires_with_counts.json', 'w') as f:
    json.dump(filtered_sires, f, indent=2)

with open(f'{output_dir}/dams_with_counts.json', 'w') as f:
    json.dump(filtered_dams, f, indent=2)

print('='*80)
print(' SAVED REFERENCE DATABASES')
print('='*80)
print()
print(f'✓ {output_dir}/trainers.json ({len(trainer_list)} entries)')
print(f'✓ {output_dir}/jockeys.json ({len(jockey_list)} entries)')
print(f'✓ {output_dir}/horses.json ({len(horse_list)} entries)')
print(f'✓ {output_dir}/sires.json ({len(sire_list)} entries)')
print(f'✓ {output_dir}/dams.json ({len(dam_list)} entries)')
print()
print('These databases can now be used for fuzzy matching to correct extraction errors.')
print()
