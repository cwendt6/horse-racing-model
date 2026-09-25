import os
"""
Collect First-Time Starter (FTS) Statistics
Analyzes 2023 data to build trainer and sire statistics for FTS horses
"""

import sys
import json
from collections import defaultdict
from typing import Dict, List, Tuple

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.parsers.simd_parser import parse_simd_file
from src.parsers.equibase_parser import parse_equibase_files
from glob import glob


def collect_fts_trainer_stats(simd_dir: str, tch_dir: str) -> Dict:
    """
    Collect trainer statistics for first-time starters

    Returns:
        Dictionary with trainer FTS performance
    """
    print("\n" + "="*80)
    print(" COLLECTING FIRST-TIME STARTER STATISTICS")
    print("="*80)

    trainer_stats = defaultdict(lambda: {
        'fts_starts': 0,
        'fts_wins': 0,
        'fts_seconds': 0,
        'fts_thirds': 0,
        'fts_itm': 0,
        'fts_earnings': 0.0,
        'fts_horses': []
    })

    sire_stats = defaultdict(lambda: {
        'fts_starts': 0,
        'fts_wins': 0,
        'fts_seconds': 0,
        'fts_thirds': 0,
        'fts_itm': 0,
        'fts_horses': []
    })

    # Get all SIMD files
    simd_files = sorted(glob(f"{simd_dir}/*.xml"))
    print(f"\nFound {len(simd_files)} SIMD files")

    # Get all TCH files for results
    tch_files = sorted(glob(f"{tch_dir}/*.xml"))
    print(f"Found {len(tch_files)} TCH result files")

    # Parse TCH files to get results
    print("\nParsing result files...")
    all_tch_races = []
    for tch_file in tch_files:
        try:
            races = parse_equibase_files(tch_file)
            all_tch_races.extend(races)
        except Exception as e:
            print(f"  Error parsing {tch_file}: {e}")
            continue

    print(f"Loaded {len(all_tch_races)} races from results")

    # Create lookup by date and race number
    tch_lookup = {}
    for race in all_tch_races:
        key = (race.date, race.race_number)
        tch_lookup[key] = race

    # Parse SIMD files
    print("\nAnalyzing first-time starters...")
    total_fts = 0
    races_processed = 0

    for simd_file in simd_files:
        try:
            simd_races = parse_simd_file(simd_file)

            for simd_race in simd_races:
                races_processed += 1

                # Get corresponding results
                race_date = simd_race.date.replace('-', '')
                if len(race_date) == 8:
                    formatted_date = f"{race_date[:4]}-{race_date[4:6]}-{race_date[6:]}"
                else:
                    formatted_date = simd_race.date

                tch_key = (formatted_date, simd_race.race_number)
                tch_race = tch_lookup.get(tch_key)

                if not tch_race:
                    continue

                # Create horse lookup by name
                tch_horses = {h.name.lower().strip(): h for h in tch_race.horses}

                # Analyze each horse in SIMD
                for horse in simd_race.horses:
                    # Check if first-time starter (no past performances)
                    if len(horse.past_performances) == 0:
                        total_fts += 1

                        # Get result from TCH
                        horse_key = horse.name.lower().strip()
                        tch_horse = tch_horses.get(horse_key)

                        if not tch_horse:
                            continue

                        # Record trainer stats
                        trainer = horse.trainer_name.strip()
                        trainer_stats[trainer]['fts_starts'] += 1
                        trainer_stats[trainer]['fts_horses'].append(horse.name)

                        if tch_horse.final_position == 1:
                            trainer_stats[trainer]['fts_wins'] += 1
                        if tch_horse.final_position == 2:
                            trainer_stats[trainer]['fts_seconds'] += 1
                        if tch_horse.final_position == 3:
                            trainer_stats[trainer]['fts_thirds'] += 1
                        if tch_horse.final_position <= 3:
                            trainer_stats[trainer]['fts_itm'] += 1

                        # Record sire stats
                        sire = horse.sire_name.strip()
                        if sire:
                            sire_stats[sire]['fts_starts'] += 1
                            sire_stats[sire]['fts_horses'].append(horse.name)

                            if tch_horse.final_position == 1:
                                sire_stats[sire]['fts_wins'] += 1
                            if tch_horse.final_position == 2:
                                sire_stats[sire]['fts_seconds'] += 1
                            if tch_horse.final_position == 3:
                                sire_stats[sire]['fts_thirds'] += 1
                            if tch_horse.final_position <= 3:
                                sire_stats[sire]['fts_itm'] += 1

        except Exception as e:
            print(f"  Error processing {simd_file}: {e}")
            continue

        if races_processed % 50 == 0:
            print(f"  Processed {races_processed} races, found {total_fts} FTS so far...")

    print(f"\n✓ Processed {races_processed} races")
    print(f"✓ Found {total_fts} first-time starters")

    # Calculate percentages
    print("\nCalculating statistics...")

    trainer_output = {}
    for trainer, stats in trainer_stats.items():
        if stats['fts_starts'] >= 3:  # Minimum 3 starts
            trainer_output[trainer] = {
                'fts_starts': stats['fts_starts'],
                'fts_wins': stats['fts_wins'],
                'fts_win_pct': round(stats['fts_wins'] / stats['fts_starts'] * 100, 1),
                'fts_itm': stats['fts_itm'],
                'fts_itm_pct': round(stats['fts_itm'] / stats['fts_starts'] * 100, 1),
                'fts_roi': round(stats['fts_wins'] / stats['fts_starts'], 2)
            }

    sire_output = {}
    for sire, stats in sire_stats.items():
        if stats['fts_starts'] >= 5:  # Minimum 5 starts
            sire_output[sire] = {
                'fts_starts': stats['fts_starts'],
                'fts_wins': stats['fts_wins'],
                'fts_win_pct': round(stats['fts_wins'] / stats['fts_starts'] * 100, 1),
                'fts_itm': stats['fts_itm'],
                'fts_itm_pct': round(stats['fts_itm'] / stats['fts_starts'] * 100, 1),
                'fts_bonus': 1.0  # Will be calibrated later
            }

    return trainer_output, sire_output, total_fts


def identify_elite_trainers(trainer_stats: Dict) -> List[str]:
    """
    Identify elite FTS trainers (25%+ win rate)
    """
    elite = []
    for trainer, stats in trainer_stats.items():
        if stats['fts_win_pct'] >= 25.0 and stats['fts_starts'] >= 5:
            elite.append(trainer)
    return elite


def identify_hot_sires(sire_stats: Dict) -> List[str]:
    """
    Identify hot FTS sires (20%+ win rate)
    """
    hot = []
    for sire, stats in sire_stats.items():
        if stats['fts_win_pct'] >= 20.0 and stats['fts_starts'] >= 10:
            hot.append(sire)
    return hot


def main():
    # Collect statistics
    trainer_stats, sire_stats, total_fts = collect_fts_trainer_stats(
        simd_dir='data/raw/Equibase Dataset/2023 PPs',
        tch_dir='data/raw/Equibase Dataset/2023 Result Charts'
    )

    print(f"\n{'='*80}")
    print(" RESULTS SUMMARY")
    print(f"{'='*80}")

    print(f"\nTotal FTS found: {total_fts}")
    print(f"Trainers with 3+ FTS: {len(trainer_stats)}")
    print(f"Sires with 5+ FTS: {len(sire_stats)}")

    # Identify elite trainers
    elite_trainers = identify_elite_trainers(trainer_stats)
    print(f"\nElite FTS Trainers (25%+ win rate):")
    for trainer in sorted(elite_trainers):
        stats = trainer_stats[trainer]
        print(f"  {trainer:30} {stats['fts_wins']:2}/{stats['fts_starts']:2} ({stats['fts_win_pct']:5.1f}%) ITM: {stats['fts_itm_pct']:5.1f}%")

    # Identify hot sires
    hot_sires = identify_hot_sires(sire_stats)
    print(f"\nHot FTS Sires (20%+ win rate, 10+ starts):")
    for sire in sorted(hot_sires, key=lambda s: sire_stats[s]['fts_win_pct'], reverse=True)[:20]:
        stats = sire_stats[sire]
        print(f"  {sire:30} {stats['fts_wins']:2}/{stats['fts_starts']:2} ({stats['fts_win_pct']:5.1f}%) ITM: {stats['fts_itm_pct']:5.1f}%")

    # Calculate sire bonuses based on performance
    for sire, stats in sire_stats.items():
        win_pct = stats['fts_win_pct']
        if win_pct >= 30.0:
            stats['fts_bonus'] = 1.15  # 15% bonus
        elif win_pct >= 20.0:
            stats['fts_bonus'] = 1.10  # 10% bonus
        elif win_pct >= 15.0:
            stats['fts_bonus'] = 1.05  # 5% bonus
        else:
            stats['fts_bonus'] = 1.0   # No bonus

    # Save to JSON files
    print(f"\n{'='*80}")
    print(" SAVING STATISTICS")
    print(f"{'='*80}")

    trainer_file = 'data/stats/fts_trainer_statistics.json'
    with open(trainer_file, 'w') as f:
        json.dump(trainer_stats, f, indent=2)
    print(f"\n✓ Saved trainer stats to: {trainer_file}")

    sire_file = 'data/stats/fts_sire_statistics.json'
    with open(sire_file, 'w') as f:
        json.dump(sire_stats, f, indent=2)
    print(f"✓ Saved sire stats to: {sire_file}")

    # Create summary report
    summary = {
        'total_fts': total_fts,
        'trainers_analyzed': len(trainer_stats),
        'sires_analyzed': len(sire_stats),
        'elite_trainers': elite_trainers,
        'hot_sires': hot_sires[:20],
        'average_fts_win_pct': round(sum(s['fts_win_pct'] for s in trainer_stats.values()) / len(trainer_stats), 1) if len(trainer_stats) > 0 else 0,
        'average_sire_win_pct': round(sum(s['fts_win_pct'] for s in sire_stats.values()) / len(sire_stats), 1) if len(sire_stats) > 0 else 0
    }

    summary_file = 'data/stats/fts_summary.json'
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)
    print(f"✓ Saved summary to: {summary_file}")

    print(f"\n{'='*80}")
    print(" COMPLETE")
    print(f"{'='*80}")
    print(f"\nKey Insights:")
    print(f"  • Elite trainers (25%+ FTS win rate): {len(elite_trainers)}")
    print(f"  • Hot sires (20%+ FTS win rate): {len(hot_sires)}")
    print(f"  • Average trainer FTS win %: {summary['average_fts_win_pct']}%")
    print(f"  • Average sire FTS win %: {summary['average_sire_win_pct']}%")
    print(f"\nNext: Run FTS predictor adjustments with these statistics")
    print()


if __name__ == '__main__':
    main()
