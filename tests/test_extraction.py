import os
#!/usr/bin/env python3
"""Test PDF extraction after position-based integration"""

import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.parsers.pdf_parser import parse_pdf_file

# Parse with debug OFF to reduce output
races = parse_pdf_file('Keeneland October PPs/10-3-25-kee-ppspdf.pdf', debug=False)

print('EXTRACTION RESULTS:')
print('='*80)
print(f'Total races: {len(races)}\n')

total_horses = 0
for race in races:
    print(f'Race {race.race_number}: {race.distance_text} {race.surface_description} - ${race.purse:,.0f}')
    print(f'  Horses: {len(race.horses)}')
    total_horses += len(race.horses)

    if len(race.horses) > 0:
        for h in race.horses[:3]:  # Show first 3 horses
            print(f'    #{h.program_number} {h.name:30s} J: {h.jockey_name:20s} ML: {h.morning_line_odds}')
        if len(race.horses) > 3:
            print(f'    ... and {len(race.horses) - 3} more')
    print()

print('='*80)
print(f'TOTAL HORSES EXTRACTED: {total_horses}')
print('='*80)
