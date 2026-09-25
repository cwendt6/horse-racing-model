#!/usr/bin/env python3
"""
Scratch Impact Analysis
Analyzes how scratches affected October 2025 backtest predictions
"""

import sys
import os
import re
import json
from pathlib import Path

project_root = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, project_root)

import pdfplumber


def extract_horses_that_ran(results_pdf_path):
    """Extract list of horses that actually ran in each race from results PDF"""
    races_data = {}

    with pdfplumber.open(results_pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue

            # Look for race headers
            race_pattern = r'KEENELAND.*?October\d+,2025.*?Race(\d+)'
            race_match = re.search(race_pattern, text)
            if not race_match:
                continue

            race_num = int(race_match.group(1))

            # Extract horses from "Past Performance Running Line Preview"
            # This section lists all horses that ran
            horses_ran = []
            scratched_horses = []

            lines = text.split('\n')
            in_pp_preview = False

            for i, line in enumerate(lines):
                # Look for scratches line
                if 'ScratchedHorse(s):' in line:
                    # Extract scratched horse names
                    scratch_text = line.replace('ScratchedHorse(s):', '').strip()
                    # Parse out horse names (format: "HorseName(Trainer)" or multiple)
                    scratch_matches = re.findall(r'([A-Z][a-zA-Z]+(?:[A-Z][a-z]+)?)\(', scratch_text)
                    scratched_horses.extend(scratch_matches)

                # Start of PP preview section
                if 'PastPerformanceRunningLinePreview' in line or \
                   (in_pp_preview and re.match(r'^\s*\d+\s+[A-Z]', line)):
                    in_pp_preview = True

                    # Extract horse name from line like "10 CriticalThreat 9 ..."
                    match = re.search(r'^\s*\d+\s+([A-Z][a-zA-Z]+(?:[A-Z][a-z]+)?)\s+', line)
                    if match:
                        horse_name = match.group(1)
                        horses_ran.append(horse_name)

                # End of PP preview section
                if in_pp_preview and ('Trainers:' in line or 'Owners:' in line):
                    break

            if horses_ran:
                races_data[race_num] = {
                    'ran': horses_ran,
                    'scratched': scratched_horses
                }

    return races_data


def analyze_scratches_for_date(date_str, pp_path, results_path):
    """Analyze scratches for a specific race date"""

    print(f"\n{'='*80}")
    print(f" ANALYZING SCRATCHES FOR {date_str}")
    print(f"{'='*80}\n")

    # Check if files exist
    if not os.path.exists(pp_path):
        print(f"⚠️ PP file not found: {pp_path}")
        return None

    if not os.path.exists(results_path):
        print(f"⚠️ Results file not found: {results_path}")
        return None

    # Extract horses that actually ran
    horses_that_ran = extract_horses_that_ran(results_path)

    if not horses_that_ran:
        print(f"⚠️ Could not extract horse data from results")
        return None

    print(f"✓ Found results for {len(horses_that_ran)} races")

    # Parse PP to see what horses we predicted with
    from src.parsers.hybrid_parser_v3 import parse_pdf_hybrid_v3

    predicted_races = parse_pdf_hybrid_v3(pp_path, debug=False)

    scratch_data = []

    for pred_race in predicted_races:
        race_num = pred_race.race_number

        if race_num not in horses_that_ran:
            continue

        predicted_horses = {h.name for h in pred_race.horses}
        actual_horses = set(horses_that_ran[race_num]['ran'])
        official_scratches = set(horses_that_ran[race_num]['scratched'])

        # Find scratches (in PP but not in results)
        scratches = predicted_horses - actual_horses

        # Find late entries (in results but not in PP - rare)
        late_entries = actual_horses - predicted_horses

        if scratches or late_entries or official_scratches:
            scratch_data.append({
                'race_number': race_num,
                'predicted_field_size': len(predicted_horses),
                'actual_field_size': len(actual_horses),
                'scratches': list(scratches),
                'official_scratches': list(official_scratches),
                'late_entries': list(late_entries),
                'scratch_count': len(scratches)
            })

            print(f"\nRace {race_num}:")
            print(f"  Predicted field: {len(predicted_horses)} horses")
            print(f"  Actual field: {len(actual_horses)} horses")
            if official_scratches:
                print(f"  📋 Official scratches: {', '.join(official_scratches)}")
            if scratches:
                print(f"  ❌ Scratched (from our PPs): {', '.join(scratches)}")
            if late_entries:
                print(f"  ⚠️ Late entries: {', '.join(late_entries)}")

    return {
        'date': date_str,
        'total_races': len(horses_that_ran),
        'races_with_scratches': len(scratch_data),
        'scratch_details': scratch_data
    }


def analyze_scratch_impact_on_predictions(date_str, pp_path, results_path, backtest_results):
    """Analyze how scratches affected our top picks"""

    print(f"\n{'='*80}")
    print(f" SCRATCH IMPACT ON PREDICTIONS - {date_str}")
    print(f"{'='*80}\n")

    horses_that_ran = extract_horses_that_ran(results_path)

    if not horses_that_ran:
        return

    # Find races where our top pick was scratched
    top_pick_scratched = []
    top_3_had_scratches = []

    for result in backtest_results:
        if result['date'] != date_str:
            continue

        race_num = result['race']

        if race_num not in horses_that_ran:
            continue

        actual_horses = horses_that_ran[race_num]['ran']

        # Check if top pick ran
        top_pick_name = result['top_pick_name']

        # Fuzzy match (case insensitive, handle spacing differences)
        top_pick_ran = any(top_pick_name.lower() in horse.lower() or
                          horse.lower() in top_pick_name.lower()
                          for horse in actual_horses)

        if not top_pick_ran and top_pick_name != '?':
            top_pick_scratched.append({
                'race': race_num,
                'horse': top_pick_name,
                'winner': result['winner_name'],
                'did_we_win': result['win_hit']
            })

        # Check top 5 for scratches
        top_5 = result.get('top_5', [])
        scratched_from_top_5 = []

        for horse_data in top_5:
            horse_name = horse_data['name']
            ran = any(horse_name.lower() in h.lower() or h.lower() in horse_name.lower()
                     for h in actual_horses)
            if not ran:
                scratched_from_top_5.append(horse_name)

        if scratched_from_top_5:
            top_3_had_scratches.append({
                'race': race_num,
                'scratched': scratched_from_top_5,
                'winner': result['winner_name'],
                'did_we_win': result['win_hit']
            })

    print(f"Races where top pick scratched: {len(top_pick_scratched)}")
    for item in top_pick_scratched:
        result = "✅ Still won!" if item['did_we_win'] else "❌ Did not win"
        print(f"  Race {item['race']}: {item['horse']} scratched → Winner: {item['winner']} [{result}]")

    print(f"\nRaces with scratches in top 5: {len(top_3_had_scratches)}")
    for item in top_3_had_scratches:
        result = "✅" if item['did_we_win'] else "❌"
        print(f"  Race {item['race']}: {', '.join(item['scratched'])} scratched [{result}]")

    return {
        'top_pick_scratched_count': len(top_pick_scratched),
        'races_with_scratches_in_top_5': len(top_3_had_scratches),
        'top_pick_scratches': top_pick_scratched,
        'top_5_scratch_details': top_3_had_scratches
    }


def main():
    """Analyze scratches across all October dates"""

    print("\n" + "="*80)
    print(" OCTOBER 2025 SCRATCH IMPACT ANALYSIS")
    print("="*80)

    # Load backtest results
    backtest_file = 'output/october_2025_backtest_results.json'
    if not os.path.exists(backtest_file):
        print(f"❌ Backtest results not found: {backtest_file}")
        return

    with open(backtest_file, 'r') as f:
        backtest_data = json.load(f)

    backtest_results = backtest_data['detailed_results']

    # Dates to analyze
    dates = [
        '10-03-25', '10-05-25', '10-08-25', '10-09-25', '10-10-25',
        '10-11-25', '10-12-25', '10-15-25', '10-16-25', '10-17-25',
        '10-18-25', '10-19-25'
    ]

    all_scratch_data = []
    total_races = 0
    total_scratches = 0
    total_top_pick_scratched = 0

    for date in dates:
        pp_path = f"Keeneland October PPs/{date}-kee-ppspdf.pdf"
        results_path_str = date.replace('-', '')
        results_path = f"data/Results Files/KEE{results_path_str}USA.pdf"

        # Get scratch data
        scratch_info = analyze_scratches_for_date(date, pp_path, results_path)

        if scratch_info:
            all_scratch_data.append(scratch_info)
            total_races += scratch_info['total_races']
            total_scratches += sum(sd['scratch_count'] for sd in scratch_info['scratch_details'])

        # Analyze impact on predictions
        impact = analyze_scratch_impact_on_predictions(date, pp_path, results_path, backtest_results)

        if impact:
            total_top_pick_scratched += impact['top_pick_scratched_count']

    # Summary
    print(f"\n{'='*80}")
    print(" SUMMARY")
    print(f"{'='*80}\n")

    print(f"Total races analyzed: {total_races}")
    print(f"Total scratches: {total_scratches}")
    if total_races > 0:
        print(f"Average scratches per race: {total_scratches/total_races:.2f}")
        print(f"\nTop picks scratched: {total_top_pick_scratched}")
        print(f"Impact on win rate: {total_top_pick_scratched/total_races*100:.1f}% of races affected")
    else:
        print("Average scratches per race: N/A (no races analyzed)")
        print(f"\nTop picks scratched: {total_top_pick_scratched}")
        print("Impact on win rate: N/A (no races analyzed)")

    # Save results
    output_file = 'output/scratch_impact_analysis.json'
    with open(output_file, 'w') as f:
        json.dump({
            'summary': {
                'total_races': total_races,
                'total_scratches': total_scratches,
                'avg_scratches_per_race': round(total_scratches/total_races if total_races > 0 else 0, 2),
                'top_picks_scratched': total_top_pick_scratched,
                'percent_races_affected': round(total_top_pick_scratched/total_races*100, 1) if total_races > 0 else 0
            },
            'by_date': all_scratch_data
        }, f, indent=2)

    print(f"\n✓ Detailed analysis saved to: {output_file}")
    print()


if __name__ == '__main__':
    main()
