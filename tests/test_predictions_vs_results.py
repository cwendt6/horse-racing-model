#!/usr/bin/env python3
"""
Test predictions against actual results using full model
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pdfplumber
import re
from src.predictor import HorseRacingPredictor
from src.parsers.pdf_parser import parse_pdf_file

def parse_results_pdf(results_pdf_path):
    """Parse results PDF"""
    results = {}

    with pdfplumber.open(results_pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            lines = text.split('\n')

            race_match = re.search(r'Race\s*(\d+)', text, re.IGNORECASE)
            if not race_match:
                continue

            race_num = int(race_match.group(1))

            results_start = None
            for i, line in enumerate(lines):
                if 'LastRaced' in line and 'Pgm' in line and 'HorseName' in line:
                    results_start = i + 1
                    break

            if not results_start:
                continue

            finish_order = []
            for line in lines[results_start:results_start+15]:
                match = re.match(r'^\d+\w+\d+\s+(\d+)\s+([A-Za-z\s]+)\(', line)
                if match:
                    prog_num = match.group(1)
                    horse_name = match.group(2).strip()
                    position = len(finish_order) + 1
                    
                    finish_order.append({
                        'position': position,
                        'program_number': prog_num,
                        'name': horse_name
                    })
                elif line.strip().startswith('Fractional'):
                    break

            if finish_order:
                results[race_num] = {'finish_order': finish_order}

    return results

def main():
    pp_pdf = 'Keeneland October PPs/10-3-25-kee-ppspdf.pdf'
    results_pdf = 'data/October 3 Results eqbPDFChartPlus .pdf'

    print('Initializing predictor...')
    predictor = HorseRacingPredictor()

    print('Parsing past performances...')
    races = parse_pdf_file(pp_pdf, debug=False)
    print(f'Loaded {len(races)} races\n')

    print('Parsing results...')
    results = parse_results_pdf(results_pdf)
    print(f'Loaded results for {len(results)} races\n')

    print('='*80)
    print('FULL MODEL PREDICTION PERFORMANCE - OCTOBER 3, 2025')
    print('='*80)

    total_races = 0
    winners_picked = 0
    top3_picked = 0
    total_top_pick_odds = 0

    for race in races:
        if race.race_number not in results or len(race.horses) == 0:
            continue

        total_races += 1
        
        # Get predictions
        predictions = predictor.predict_race(race)
        
        if not predictions:
            continue

        actual_finish = results[race.race_number]['finish_order']
        winner_prog = actual_finish[0]['program_number']
        winner_name = actual_finish[0]['name']

        our_pick = predictions[0]
        
        print(f'\n--- Race {race.race_number} ({race.distance_text} {race.surface_description}) ---')
        print(f'Winner: #{winner_prog} {winner_name}')
        print(f'Our Top Pick: #{our_pick.program_number} {our_pick.name}')
        print(f'  Win Probability: {our_pick.win_probability:.1%}')
        print(f'  Model Odds: {our_pick.model_odds:.1f} | ML Odds: {our_pick.morning_line_odds}')

        if our_pick.program_number == winner_prog:
            print('  WINNER PICKED!')
            winners_picked += 1
            # Track odds of our winning picks
            ml_odds = our_pick.morning_line_odds
            try:
                if '-' in ml_odds:
                    parts = ml_odds.split('-')
                    decimal_odds = (float(parts[0]) / float(parts[1])) + 1
                    total_top_pick_odds += decimal_odds
            except:
                pass
        else:
            our_finish = None
            for f in actual_finish:
                if f['program_number'] == our_pick.program_number:
                    our_finish = f['position']
                    break
            if our_finish:
                print(f'  Our pick finished: {our_finish}')

        top3_prog_nums = [f['program_number'] for f in actual_finish[:3]]
        if our_pick.program_number in top3_prog_nums:
            print('  Top pick in top 3')
            top3_picked += 1

        print('\n  Our Top 3 Picks:')
        for i, pred in enumerate(predictions[:3], 1):
            in_actual_top3 = '✓' if pred.program_number in top3_prog_nums else ' '
            print(f'   {i}. [{in_actual_top3}] #{pred.program_number} {pred.name:25s} {pred.win_probability:5.1%}')

        print('\n  Actual Top 3:')
        for f in actual_finish[:3]:
            print(f'    {f["position"]}. #{f["program_number"]} {f["name"]}')

    print('\n' + '='*80)
    print('SUMMARY')
    print('='*80)
    print(f'Total Races: {total_races}')
    print(f'Winners Picked: {winners_picked}/{total_races} ({winners_picked/total_races*100:.1f}%)')
    print(f'Top Pick in Top 3: {top3_picked}/{total_races} ({top3_picked/total_races*100:.1f}%)')
    
    if winners_picked > 0:
        avg_winning_odds = total_top_pick_odds / winners_picked
        print(f'Average Winning Odds: {avg_winning_odds:.2f}')
        roi = (total_top_pick_odds - total_races) / total_races * 100
        print(f'Flat Bet ROI (Top Pick): {roi:.1f}%')
    
    print('='*80)

if __name__ == '__main__':
    main()
