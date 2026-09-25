#!/usr/bin/env python3
"""Test final extraction results"""

from src.parsers.pdf_parser import parse_pdf_file

races = parse_pdf_file('Keeneland October PPs/10-3-25-kee-ppspdf.pdf', debug=False)

total_horses = 0
horses_with_names = 0
horses_with_jockeys = 0

for race in races:
    total_horses += len(race.horses)
    for h in race.horses:
        if not h.name.startswith('Horse'):
            horses_with_names += 1
        if h.jockey_name != 'Unknown':
            horses_with_jockeys += 1

print('='*80)
print('🎯 FINAL EXTRACTION RESULTS')
print('='*80)
print(f'Horse names:  {horses_with_names}/{total_horses} ({horses_with_names/total_horses*100:.1f}%)')
print(f'Jockey names: {horses_with_jockeys}/{total_horses} ({horses_with_jockeys/total_horses*100:.1f}%)')
print('='*80)

# Show sample from first 3 races
print('\nSample predictions data:')
for i in range(min(3, len(races))):
    race = races[i]
    print(f'\nRace {race.race_number} ({race.distance_text} {race.surface_description}, Purse: ${race.purse:,.0f}):')
    for h in race.horses[:3]:
        print(f'  #{h.program_number:3s} {h.name:28s} J: {h.jockey_name:22s} Beyer: {h.best_speed_figure}')

if horses_with_names == total_horses and horses_with_jockeys >= 0.9 * total_horses:
    print('\n✅ PARSER READY FOR PREDICTIONS!')
else:
    print(f'\n⚠️  Needs work: Names {horses_with_names/total_horses*100:.1f}%, Jockeys {horses_with_jockeys/total_horses*100:.1f}%')
