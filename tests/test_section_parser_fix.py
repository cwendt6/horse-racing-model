#!/usr/bin/env python3
import sys

# Clear cache
for mod in list(sys.modules.keys()):
    if 'section' in mod or 'parser' in mod:
        del sys.modules[mod]

sys.path.insert(0, 'src/parsers')
from section_parser import SectionBasedParser

# Test updated parser
parser = SectionBasedParser()
races = parser.parse('Keeneland October PPs/10-18-25-kee-ppspdf.pdf', debug=False)

print('\nRACE 1 - FIRST 3 HORSES (claiming race format):')
print('='*80)
race1 = races[0]
for horse in sorted(race1.horses[:3], key=lambda h: int(h.program_number) if h.program_number.isdigit() else 99):
    print(f'#{horse.program_number}: {horse.name[:25]:<25} | J: {horse.jockey_name[:25]:<25}')

print('\nRACE 2 - FIRST 5 HORSES (non-claiming race format):')
print('='*80)
race2 = races[1]
for horse in sorted(race2.horses[:5], key=lambda h: int(h.program_number) if h.program_number.isdigit() else 99):
    print(f'#{horse.program_number}: {horse.name[:25]:<25} | J: {horse.jockey_name[:25]:<25}')

print(f'\nTotal: {len(races)} races, {sum(len(r.horses) for r in races)} horses')
