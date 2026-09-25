import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.parsers.pdf_parser import parse_pdf_file

# Parse the October 3 PDF
races = parse_pdf_file('Keeneland October PPs/10-3-25-kee-ppspdf.pdf', debug=False)

print(f'\nFound {len(races)} races\n')

# Check Race 1 in detail
race1 = [r for r in races if r.race_number == 1][0]
print(f'RACE 1: {len(race1.horses)} horses')
print(f'Distance: {race1.distance_text}')
print(f'Surface: {race1.surface_description}')
print(f'Purse: ${race1.purse:,.0f}')
print(f'\nHorse extraction quality:')
print(f'{"#":<4} {"Name OK":<8} {"Horse Name":<30} {"Beyer":<8} {"Best":<5} {"Jockey OK":<10} {"Jockey Name":<20}')
print('-' * 100)

for i, h in enumerate(race1.horses, 1):
    name_ok = 'YES' if h.name and not h.name.startswith('Horse') else 'NO'
    beyer_ok = 'YES' if h.best_speed_figure > 0 else 'NO'
    jockey_ok = 'YES' if h.jockey_name and h.jockey_name != 'Unknown' else 'NO'

    print(f'{h.program_number:<4} {name_ok:<8} {h.name[:30]:<30} {beyer_ok:<8} {h.best_speed_figure:<5} {jockey_ok:<10} {h.jockey_name[:20]:<20}')

# Summary stats
names_extracted = sum(1 for h in race1.horses if h.name and not h.name.startswith('Horse'))
beyers_extracted = sum(1 for h in race1.horses if h.best_speed_figure > 0)
jockeys_extracted = sum(1 for h in race1.horses if h.jockey_name and h.jockey_name != 'Unknown')

print(f'\n{"-" * 100}')
print(f'Extraction Success Rate:')
print(f'  Names:   {names_extracted}/{len(race1.horses)} ({names_extracted/len(race1.horses)*100:.1f}%)')
print(f'  Beyers:  {beyers_extracted}/{len(race1.horses)} ({beyers_extracted/len(race1.horses)*100:.1f}%)')
print(f'  Jockeys: {jockeys_extracted}/{len(race1.horses)} ({jockeys_extracted/len(race1.horses)*100:.1f}%)')
