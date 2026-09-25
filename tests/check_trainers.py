#!/usr/bin/env python3
import sys
sys.path.insert(0, 'src/parsers')

from hybrid_parser_v3 import parse_pdf_hybrid_v3

# Parse PDF
races = parse_pdf_hybrid_v3('Keeneland October PPs/10-18-25-kee-ppspdf.pdf', debug=False)

# Check what the quality check is filtering
print('\nTRAINER QUALITY ANALYSIS:')
print('='*80)

total_horses = sum(len(r.horses) for r in races)
good_trainers = sum(1 for r in races for h in r.horses if h.trainer_name and h.trainer_name != 'Unknown' and h.trainer_name != 'Owner')
trainers_with_owner = sum(1 for r in races for h in r.horses if h.trainer_name == 'Owner')
trainers_unknown = sum(1 for r in races for h in r.horses if h.trainer_name == 'Unknown')

print(f'Total horses: {total_horses}')
print(f'Good trainers (not Unknown, not Owner): {good_trainers}')
print(f'Trainers showing "Owner": {trainers_with_owner}')
print(f'Trainers showing "Unknown": {trainers_unknown}')
print()
print(f'Quality check formula (excludes Owner): {good_trainers}/{total_horses} = {good_trainers/total_horses*100:.1f}%')
print(f'Actual quality (includes Owner as valid): {good_trainers + trainers_with_owner}/{total_horses} = {(good_trainers + trainers_with_owner)/total_horses*100:.1f}%')
print()

# List horses with Owner
if trainers_with_owner > 0:
    print('HORSES WITH "Owner" AS TRAINER:')
    print('='*80)
    count = 0
    for race in races:
        for horse in race.horses:
            if horse.trainer_name == 'Owner':
                count += 1
                print(f'{count}. Race {race.race_number}, Horse #{horse.program_number}: {horse.name}')
                print(f'   Jockey: {horse.jockey_name}')
                print(f'   Trainer: {horse.trainer_name}')
                print()
