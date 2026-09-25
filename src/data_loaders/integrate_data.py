import os
"""
Data Integration Script
Combines SIMD (PP), TCH (results), and statistics into enhanced race data
"""

import re
from typing import Dict, List, Tuple
from glob import glob

import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.parsers.simd_parser import parse_simd_file
from src.parsers.equibase_parser import parse_equibase_files, Race, Horse
from src.data_loaders.statistics_loader import StatisticsLoader
from src.analyzers.fts_analyzer import FTSAnalyzer


def enhance_race_with_pp_data(tch_race: Race, simd_dir: str,
                               stats_loader: StatisticsLoader,
                               fts_analyzer: FTSAnalyzer = None) -> Race:
    """
    Enhance a TCH race with SIMD past performance data

    Args:
        tch_race: Race from TCH (result) file
        simd_dir: Directory containing SIMD files
        stats_loader: Statistics loader for jockey/trainer stats

    Returns:
        Enhanced race with real PP data
    """
    # Find matching SIMD file
    race_date = tch_race.date.replace('-', '')  # Convert to YYYYMMDD
    simd_file_pattern = f"{simd_dir}/SIMD{race_date}*_USA.xml"
    simd_files = glob(simd_file_pattern)

    if not simd_files:
        # No SIMD file found, return original race
        return tch_race

    # Parse SIMD file
    simd_races = parse_simd_file(simd_files[0])

    # Find matching race by race number
    simd_race = next((r for r in simd_races if r.race_number == tch_race.race_number), None)

    if not simd_race:
        return tch_race

    # Create mapping of SIMD horses by name
    simd_horses_by_name = {h.name.lower().strip(): h for h in simd_race.horses}

    # Extract year for stats lookup
    year = int(race_date[:4])

    # Enhance each horse in TCH race
    for horse in tch_race.horses:
        horse_key = horse.name.lower().strip()
        simd_horse = simd_horses_by_name.get(horse_key)

        if not simd_horse:
            continue

        # Get jockey statistics
        jockey_stats = stats_loader.get_jockey_stats(
            simd_horse.jockey_name,
            track='keeneland',
            meet='current',
            year=year
        )

        # Get trainer statistics
        trainer_stats = stats_loader.get_trainer_stats(
            simd_horse.trainer_name,
            track='keeneland',
            meet='current',
            year=year
        )

        # Calculate career stats from race summaries
        total_starts = sum(s.starts for s in simd_horse.race_summaries)
        total_wins = sum(s.wins for s in simd_horse.race_summaries)
        total_earnings = sum(s.earnings for s in simd_horse.race_summaries)

        # Get recent speed figures (divide by 10 to get actual Beyer scale)
        recent_speed_figures = [pp.speed_figure / 10 for pp in simd_horse.past_performances[:5]
                               if pp.speed_figure > 0]

        # Calculate best and last Beyer
        best_beyer = max(recent_speed_figures) if recent_speed_figures else 50
        last_beyer = recent_speed_figures[0] if recent_speed_figures else 50

        # Calculate running style
        running_style = calculate_running_style(simd_horse.past_performances)

        # Store enhanced data as horse attributes
        # These will be used by the backtesting framework
        horse._enhanced_best_beyer = best_beyer
        horse._enhanced_last_beyer = last_beyer
        horse._enhanced_running_style = running_style
        horse._enhanced_career_earnings = total_earnings if total_earnings > 0 else 100000
        horse._enhanced_career_starts = total_starts if total_starts > 0 else 10
        horse._enhanced_jockey_win_pct = jockey_stats.win_percentage / 100
        horse._enhanced_trainer_win_pct = f"{trainer_stats.win_percentage}%"
        horse._has_enhanced_data = True

        # Add FTS analysis if available
        if fts_analyzer and total_starts == 0:
            fts_analysis = fts_analyzer.get_fts_analysis(
                simd_horse.trainer_name,
                simd_horse.sire_name,
                total_starts
            )
            horse._fts_multiplier = fts_analysis['multiplier']
            horse._fts_explanation = fts_analysis['explanation']
            horse._is_fts = True
        else:
            horse._fts_multiplier = 1.0
            horse._fts_explanation = ''
            horse._is_fts = False

    return tch_race


def calculate_running_style(past_performances: List) -> str:
    """Calculate running style from past performances"""
    if not past_performances:
        return 'P'

    early_positions = []
    closing_moves = []

    for pp in past_performances[:5]:
        if not pp.points_of_call:
            continue

        first_call = None
        finish_call = None

        for poc in pp.points_of_call:
            if poc.call_point in ['S', '1']:
                first_call = poc.position
            if poc.call_point in ['F', '5']:
                finish_call = poc.position

        if first_call:
            early_positions.append(first_call)

        if first_call and finish_call:
            closing_move = first_call - finish_call
            closing_moves.append(closing_move)

    if not early_positions:
        return 'P'

    avg_early_pos = sum(early_positions) / len(early_positions)
    avg_closing_move = sum(closing_moves) / len(closing_moves) if closing_moves else 0

    if avg_early_pos <= 3:
        return 'E'
    elif avg_closing_move >= 2:
        return 'S'
    else:
        return 'P'


def load_enhanced_races(tch_dir: str, simd_dir: str,
                       jockey_stats_file: str, trainer_stats_file: str,
                       fts_trainer_stats_file: str = None,
                       fts_sire_stats_file: str = None) -> Tuple[List[Race], Dict]:
    """
    Load all TCH races and enhance with SIMD and statistics data

    Args:
        tch_dir: Directory with TCH result files
        simd_dir: Directory with SIMD PP files
        jockey_stats_file: Path to jockey statistics JSON
        trainer_stats_file: Path to trainer statistics JSON

    Returns:
        Tuple of (enhanced_races, stats_dict)
    """
    print("Loading and integrating all data sources...")

    # Load statistics
    print("  Loading jockey/trainer statistics...")
    stats_loader = StatisticsLoader(jockey_stats_file, trainer_stats_file)

    # Load FTS analyzer if stats files provided
    fts_analyzer = None
    if fts_trainer_stats_file and fts_sire_stats_file:
        print("  Loading FTS analyzer...")
        fts_analyzer = FTSAnalyzer(fts_trainer_stats_file, fts_sire_stats_file)

    # Load all TCH files
    print(f"  Loading TCH result files from {tch_dir}...")
    tch_files = sorted(glob(f"{tch_dir}/*.xml"))
    all_races = []

    for tch_file in tch_files:
        races = parse_equibase_files(tch_file)
        all_races.extend(races)

    print(f"    Loaded {len(all_races)} races from {len(tch_files)} files")

    # Enhance each race with SIMD data
    print("  Enhancing races with past performance data...")
    enhanced_races = []
    matched_count = 0
    total_horses = 0
    enhanced_horses = 0

    for i, race in enumerate(all_races):
        if (i + 1) % 50 == 0:
            print(f"    Processing race {i + 1}/{len(all_races)}...")

        enhanced_race = enhance_race_with_pp_data(race, simd_dir, stats_loader, fts_analyzer)

        # Count matched horses
        for horse in enhanced_race.horses:
            total_horses += 1
            if hasattr(horse, '_has_enhanced_data') and horse._has_enhanced_data:
                enhanced_horses += 1

        # Check if any horses were enhanced
        if any(hasattr(h, '_has_enhanced_data') for h in enhanced_race.horses):
            matched_count += 1

        enhanced_races.append(enhanced_race)

    print(f"\n  Summary:")
    print(f"    Total races: {len(enhanced_races)}")
    print(f"    Races with PP data: {matched_count} ({matched_count/len(enhanced_races)*100:.1f}%)")
    print(f"    Total horses: {total_horses}")
    print(f"    Horses with enhanced data: {enhanced_horses} ({enhanced_horses/total_horses*100:.1f}%)")

    stats_dict = {
        'total_races': len(enhanced_races),
        'matched_races': matched_count,
        'total_horses': total_horses,
        'enhanced_horses': enhanced_horses,
    }

    return enhanced_races, stats_dict


if __name__ == '__main__':
    # Test data integration
    races, stats = load_enhanced_races(
        tch_dir='Equibase Dataset/2023 Result Charts',
        simd_dir='Equibase Dataset/2023 PPs',
        jockey_stats_file='jockey_statistics_comprehensive.json',
        trainer_stats_file='trainer_statistics_comprehensive.json'
    )

    print("\n" + "="*80)
    print(" DATA INTEGRATION COMPLETE")
    print("="*80)
    print(f"\nTotal races loaded: {stats['total_races']}")
    print(f"Races with PP data: {stats['matched_races']}")
    print(f"Coverage: {stats['matched_races']/stats['total_races']*100:.1f}%")
