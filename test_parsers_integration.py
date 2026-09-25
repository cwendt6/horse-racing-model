#!/usr/bin/env python3
"""Test script to validate SIMD and TCH parsers work together"""

import sys
sys.path.insert(0, 'src')

from parsers.simd_xml_parser import SIMDXMLParser
from parsers.tch_xml_parser import parse_tch_file

# Parse past performances (SIMD)
simd_file = 'equibase 2023 data/2023 PPs/SIMD20231007KEE_USA.xml'
simd_parser = SIMDXMLParser(debug=False)
pp_races = simd_parser.parse_xml_file(simd_file)

# Parse results (TCH)
tch_file = 'equibase 2023 data/2023 Result Charts/kee20231007tch.xml'
result_races = parse_tch_file(tch_file)

print('='*80)
print(' TESTING BOTH PARSERS ON OCTOBER 7, 2023 KEENELAND')
print('='*80)
print()
print(f'✓ SIMD Parser: {len(pp_races)} races with past performances')
print(f'✓ TCH Parser: {len(result_races)} races with results')
print()

# Verify race counts match
if len(pp_races) == len(result_races):
    print(f'✅ Race counts match! {len(pp_races)} races in both files')
else:
    print(f'⚠️  Race count mismatch: {len(pp_races)} SIMD vs {len(result_races)} TCH')

print()
print('='*80)
print(' RACE 1 VALIDATION')
print('='*80)
print()

# Check Race 1 in detail
if pp_races and result_races:
    pp_race1 = pp_races[0]
    result_race1 = result_races[0]

    print(f'SIMD (Past Performances):')
    print(f'  Race {pp_race1.race_number} at {pp_race1.track_code}')
    print(f'  {pp_race1.distance} {pp_race1.surface}')
    print(f'  {len(pp_race1.horses)} horses with PPs')
    print()

    print(f'TCH (Results):')
    print(f'  Race {result_race1.race_number} at {result_race1.track_code}')
    print(f'  {result_race1.distance}F {result_race1.surface}')
    print(f'  {len(result_race1.horses)} horses with results')
    print(f'  Winner: #{result_race1.winner_program_number} {result_race1.winner_name}')
    print()

    # Check if winner exists in PP file
    winner_found = False
    for horse in pp_race1.horses:
        if horse.program_number == result_race1.winner_program_number:
            print(f'✅ Winner found in SIMD file:')
            print(f'   #{horse.program_number}: {horse.name}')
            print(f'   Jockey: {horse.jockey_name}')
            print(f'   Trainer: {horse.trainer_name}')
            print(f'   Past performances: {len(horse.past_performances)} races')
            winner_found = True
            break

    if not winner_found:
        print(f'❌ Winner #{result_race1.winner_program_number} NOT found in SIMD file')

print()
print('='*80)
print('✅ PARSER INTEGRATION TEST COMPLETE')
print('='*80)
