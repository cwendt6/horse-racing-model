#!/usr/bin/env python3
"""
Merge existing comprehensive statistics with October-extracted names to create
complete reference databases for fuzzy matching.
"""

import json
import os

print('='*80)
print(' MERGING REFERENCE DATABASES')
print('='*80)
print()

# Load existing comprehensive stats
print('Loading existing comprehensive databases...')

# Trainers from comprehensive stats
with open('data/stats/trainer_statistics_comprehensive.json', 'r') as f:
    trainer_stats = json.load(f)
    # Extract names from list of trainer objects
    existing_trainers = set(trainer['name'] for trainer in trainer_stats['trainers'])
    print(f'  Trainers from comprehensive stats: {len(existing_trainers)}')

# Jockeys from comprehensive stats
with open('data/stats/jockey_statistics_comprehensive.json', 'r') as f:
    jockey_stats = json.load(f)
    # Extract names from list of jockey objects
    existing_jockeys = set(jockey['name'] for jockey in jockey_stats['jockeys'])
    print(f'  Jockeys from comprehensive stats: {len(existing_jockeys)}')

# Sires from FTS stats
with open('data/stats/fts_sire_statistics.json', 'r') as f:
    sire_stats = json.load(f)
    existing_sires = set(sire_stats.keys())
    print(f'  Sires from FTS stats: {len(existing_sires)}')

print()

# Load October-extracted databases (if they exist)
print('Loading October-extracted databases...')

oct_trainers = set()
oct_jockeys = set()
oct_horses = set()
oct_sires = set()
oct_dams = set()

if os.path.exists('data/reference_databases/trainers.json'):
    with open('data/reference_databases/trainers.json', 'r') as f:
        oct_trainers = set(json.load(f))
        print(f'  Trainers from October: {len(oct_trainers)}')

if os.path.exists('data/reference_databases/jockeys.json'):
    with open('data/reference_databases/jockeys.json', 'r') as f:
        oct_jockeys = set(json.load(f))
        print(f'  Jockeys from October: {len(oct_jockeys)}')

if os.path.exists('data/reference_databases/horses.json'):
    with open('data/reference_databases/horses.json', 'r') as f:
        oct_horses = set(json.load(f))
        print(f'  Horses from October: {len(oct_horses)}')

if os.path.exists('data/reference_databases/sires.json'):
    with open('data/reference_databases/sires.json', 'r') as f:
        oct_sires = set(json.load(f))
        print(f'  Sires from October: {len(oct_sires)}')

if os.path.exists('data/reference_databases/dams.json'):
    with open('data/reference_databases/dams.json', 'r') as f:
        oct_dams = set(json.load(f))
        print(f'  Dams from October: {len(oct_dams)}')

print()

# Merge databases
print('Merging databases...')

merged_trainers = existing_trainers | oct_trainers
merged_jockeys = existing_jockeys | oct_jockeys
merged_sires = existing_sires | oct_sires
merged_horses = oct_horses  # Only from October
merged_dams = oct_dams  # Only from October

print(f'  Merged trainers: {len(merged_trainers)} (added {len(oct_trainers - existing_trainers)} new)')
print(f'  Merged jockeys: {len(merged_jockeys)} (added {len(oct_jockeys - existing_jockeys)} new)')
print(f'  Merged sires: {len(merged_sires)} (added {len(oct_sires - existing_sires)} new)')
print(f'  Horses: {len(merged_horses)} (October only)')
print(f'  Dams: {len(merged_dams)} (October only)')

print()

# Save merged databases
output_dir = 'data/reference_databases'
os.makedirs(output_dir, exist_ok=True)

print('Saving merged databases...')

with open(f'{output_dir}/trainers_merged.json', 'w') as f:
    json.dump(sorted(list(merged_trainers)), f, indent=2)

with open(f'{output_dir}/jockeys_merged.json', 'w') as f:
    json.dump(sorted(list(merged_jockeys)), f, indent=2)

with open(f'{output_dir}/sires_merged.json', 'w') as f:
    json.dump(sorted(list(merged_sires)), f, indent=2)

with open(f'{output_dir}/horses_merged.json', 'w') as f:
    json.dump(sorted(list(merged_horses)), f, indent=2)

with open(f'{output_dir}/dams_merged.json', 'w') as f:
    json.dump(sorted(list(merged_dams)), f, indent=2)

print()
print('='*80)
print(' SAVED MERGED DATABASES')
print('='*80)
print()
print(f'✓ {output_dir}/trainers_merged.json ({len(merged_trainers)} entries)')
print(f'✓ {output_dir}/jockeys_merged.json ({len(merged_jockeys)} entries)')
print(f'✓ {output_dir}/sires_merged.json ({len(merged_sires)} entries)')
print(f'✓ {output_dir}/horses_merged.json ({len(merged_horses)} entries)')
print(f'✓ {output_dir}/dams_merged.json ({len(merged_dams)} entries)')
print()
print('These merged databases provide comprehensive coverage for fuzzy matching.')
print()
