"""
Predict All 2023 Races from SIMD Files
Generates predictions that can be compared against results later
"""

print("SCRIPT STARTING - TOP OF FILE", flush=True)

import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

print("IMPORTS STARTING", flush=True)

import json
import os
from datetime import datetime
from glob import glob
from typing import Dict, List
import zipfile
import tempfile

print("Basic imports done", flush=True)

from src.parsers.simd_parser import parse_simd_file
print("SIMD parser imported", flush=True)
from src.data_loaders.statistics_loader import StatisticsLoader
print("Statistics loader imported", flush=True)
from src.analyzers.fts_analyzer import FTSAnalyzer
print("FTS analyzer imported", flush=True)
from src.analyzers.pace_analyzer import PaceAnalyzer
print("Pace analyzer imported", flush=True)
from src.analyzers import racing_statistics as stats
print("Racing stats imported", flush=True)
import numpy as np
print("ALL IMPORTS COMPLETE", flush=True)


def parse_distance_to_furlongs(distance: int, distance_text: str = '') -> float:
    """
    Convert distance to furlongs

    Args:
        distance: Distance in yards
        distance_text: Distance as text (e.g., "6F", "1 1/8")

    Returns:
        Distance in furlongs
    """
    try:
        # If distance is numeric (yards), convert to furlongs
        if isinstance(distance, (int, float)) and distance > 0:
            return distance / 220.0
    except:
        pass

    # Try to parse distance_text
    if distance_text:
        text = distance_text.strip().upper()

        # Handle "6F", "7F", etc.
        if 'F' in text and len(text) <= 3:
            try:
                return float(text.replace('F', '').strip())
            except:
                pass

        # Handle "1M", "1 1/16M", etc. (miles)
        if 'M' in text:
            try:
                text = text.replace('M', '').strip()
                if '/' in text:
                    # e.g., "1 1/16" = 1 + 1/16 = 1.0625 miles = 8.5 furlongs
                    parts = text.split()
                    miles = float(parts[0])
                    if len(parts) > 1 and '/' in parts[1]:
                        num, denom = parts[1].split('/')
                        miles += float(num) / float(denom)
                    return miles * 8.0  # 1 mile = 8 furlongs
                else:
                    miles = float(text)
                    return miles * 8.0
            except:
                pass

        # Handle fractional furlongs like "7 1/2"
        if '/' in text:
            try:
                parts = text.split()
                furlongs = float(parts[0])
                if len(parts) > 1 and '/' in parts[1]:
                    num, denom = parts[1].split('/')
                    furlongs += float(num) / float(denom)
                return furlongs
            except:
                pass

        # Handle yards like "870Y"
        if 'Y' in text:
            try:
                yards = float(text.replace('Y', '').strip())
                return yards / 220.0
            except:
                pass

    # Default to 6 furlongs
    return 6.0


def extract_track_code_from_filename(file_path: str) -> str:
    """
    Extract track code from SIMD filename

    Args:
        file_path: Path like "SIMD20230101AQU_USA.xml"

    Returns:
        Track code like "AQU"
    """
    import os
    import re

    filename = os.path.basename(file_path)
    # Pattern: SIMD[DATE][TRACK]_[COUNTRY].xml
    # Example: SIMD20230101AQU_USA.xml -> AQU
    match = re.search(r'SIMD\d{8}([A-Z]{2,4})_', filename)
    if match:
        return match.group(1)
    return 'UNK'


def extract_simd_file(file_path: str, temp_dir: str) -> str:
    """
    Extract SIMD file if zipped, return path to XML

    Args:
        file_path: Path to SIMD file (.xml or .zip)
        temp_dir: Temporary directory for extraction

    Returns:
        Path to XML file
    """
    if file_path.endswith('.xml'):
        return file_path

    elif file_path.endswith('.zip'):
        # Extract to temp directory
        with zipfile.ZipFile(file_path, 'r') as zip_ref:
            # Find the XML file in the zip
            xml_files = [f for f in zip_ref.namelist() if f.endswith('.xml')]
            if not xml_files:
                return None

            # Extract just the XML file
            xml_file = xml_files[0]
            zip_ref.extract(xml_file, temp_dir)
            return os.path.join(temp_dir, xml_file)

    return None


def predict_race(simd_race, stats_loader: StatisticsLoader,
                 fts_analyzer: FTSAnalyzer, pace_analyzer: PaceAnalyzer,
                 optimized_weights: Dict[str, float], track_code: str = 'UNK') -> Dict:
    """
    Generate predictions for a single race

    Args:
        simd_race: SIMD race object
        stats_loader: Statistics loader
        fts_analyzer: FTS analyzer
        pace_analyzer: Pace analyzer
        optimized_weights: Optimal weights from backtest
        track_code: Track code extracted from filename

    Returns:
        Dictionary with race predictions
    """
    # Build race data
    race_data = {
        'distance': simd_race.distance_text if hasattr(simd_race, 'distance_text') else '6F',
        'surface': simd_race.surface.lower() if simd_race.surface else 'dirt',
        'purse': simd_race.purse if hasattr(simd_race, 'purse') else 50000,
        'field_size': len(simd_race.horses),
        'pace_scenario': 'moderate',
        'avg_beyer': 70,
    }

    # Score all horses
    horse_scores = []
    horses_for_pace = []

    for horse in simd_race.horses:
        # Get enhanced stats
        jockey_stats_obj = stats_loader.get_jockey_stats(horse.jockey_name)
        trainer_stats_obj = stats_loader.get_trainer_stats(horse.trainer_name)

        # Determine running style
        running_style = 'P'  # Default presser
        if hasattr(horse, 'running_style_code'):
            running_style = horse.running_style_code
        elif hasattr(horse, 'past_performances') and horse.past_performances:
            # Infer from past performances if available
            early_positions = []
            for pp in horse.past_performances[:3]:
                if hasattr(pp, 'position_first_call') and pp.position_first_call:
                    early_positions.append(pp.position_first_call)
            if early_positions:
                avg_early = sum(early_positions) / len(early_positions)
                if avg_early <= 3:
                    running_style = 'E'
                elif avg_early >= 7:
                    running_style = 'S'

        # Get best/last Beyer
        best_beyer = 50
        last_beyer = 50
        if hasattr(horse, 'past_performances') and horse.past_performances:
            beyers = [pp.speed_rating for pp in horse.past_performances
                     if hasattr(pp, 'speed_rating') and pp.speed_rating and pp.speed_rating > 0]
            if beyers:
                best_beyer = max(beyers)
                last_beyer = beyers[0] if beyers else 50

        # Get FTS analysis
        total_starts = len(horse.past_performances) if hasattr(horse, 'past_performances') else 0
        fts_analysis = fts_analyzer.get_fts_analysis(
            horse.trainer_name,
            horse.sire_name,
            total_starts
        )

        # Build horse data
        horse_data = {
            'name': horse.name,
            'program_number': horse.program_number,
            'post': horse.post_position,
            'ml_odds': horse.morning_line_odds if hasattr(horse, 'morning_line_odds') else 5.0,
            'age': horse.age,
            'sex': horse.sex,
            'best_beyer': best_beyer,
            'last_beyer': last_beyer,
            'running_style': running_style,
            'career_earnings': horse.total_earnings if hasattr(horse, 'total_earnings') else 100000,
            'career_starts': total_starts,
            'jockey_win_pct': jockey_stats_obj.win_percentage / 100.0 if jockey_stats_obj else 0.15,
            'trainer_win_pct': trainer_stats_obj.win_percentage / 100.0 if trainer_stats_obj else 0.15,
            'jockey_name': horse.jockey_name,
            'trainer_name': horse.trainer_name,
            'fts_multiplier': fts_analysis['multiplier'],
            'is_fts': fts_analysis['is_fts'],
        }

        # Calculate score
        score = stats.calculate_comprehensive_score(horse_data, race_data)

        horse_scores.append({
            'horse_data': horse_data,
            'score': score.total,
            'factor_scores': {
                'speed': score.speed,
                'form': score.form,
                'class': score.class_rating,
                'pace': score.pace,
                'jockey': score.jockey,
                'trainer': score.trainer,
            }
        })

        horses_for_pace.append({
            'name': horse.name,
            'running_style': running_style
        })

    # Calculate average Beyer
    beyers = [h['horse_data']['best_beyer'] for h in horse_scores]
    race_data['avg_beyer'] = np.mean(beyers) if beyers else 70

    # Analyze pace scenario
    distance_furlongs = parse_distance_to_furlongs(
        simd_race.distance if hasattr(simd_race, 'distance') else 0,
        simd_race.distance_text if hasattr(simd_race, 'distance_text') else ''
    )
    pace_scenario = pace_analyzer.analyze_pace(
        horses_for_pace,
        distance_furlongs,
        simd_race.surface
    )

    # Apply FTS and Pace multipliers
    adjusted_scores = []
    for h in horse_scores:
        base_score = h['score']

        # Apply FTS multiplier
        fts_multiplier = h['horse_data']['fts_multiplier']
        score_after_fts = base_score * fts_multiplier

        # Apply pace multiplier
        running_style = h['horse_data']['running_style']
        horse_name = h['horse_data']['name']
        pace_multiplier, pace_explanation = pace_analyzer.calculate_pace_multiplier(
            horse_name, running_style, pace_scenario
        )
        final_score = score_after_fts * pace_multiplier

        h['final_score'] = final_score
        h['pace_explanation'] = pace_explanation
        adjusted_scores.append(h)

    # Normalize to probabilities
    total_score = sum(h['final_score'] for h in adjusted_scores)
    if total_score == 0:
        total_score = 1.0

    for h in adjusted_scores:
        h['win_probability'] = h['final_score'] / total_score

    # Sort by probability
    adjusted_scores.sort(key=lambda x: x['win_probability'], reverse=True)

    # Create predictions
    predictions = []
    for rank, h in enumerate(adjusted_scores, 1):
        pred = {
            'rank': rank,
            'program_number': h['horse_data']['program_number'],
            'horse_name': h['horse_data']['name'],
            'win_probability': h['win_probability'],
            'model_odds': (1 / h['win_probability']) if h['win_probability'] > 0 else 99.0,
            'jockey_name': h['horse_data']['jockey_name'],
            'trainer_name': h['horse_data']['trainer_name'],
            'is_fts': h['horse_data']['is_fts'],
            'running_style': h['horse_data']['running_style'],
            'speed_figure': h['horse_data']['best_beyer'],
        }
        predictions.append(pred)

    return {
        'track_code': track_code,  # Use filename-extracted track code
        'race_number': simd_race.race_number,
        'date': simd_race.date,
        'distance': simd_race.distance_text if hasattr(simd_race, 'distance_text') else 'Unknown',
        'surface': simd_race.surface,
        'race_type': simd_race.race_type if hasattr(simd_race, 'race_type') else 'Unknown',
        'purse': simd_race.purse if hasattr(simd_race, 'purse') else 0,
        'field_size': len(simd_race.horses),
        'pace_scenario': pace_scenario.scenario_type,
        'predictions': predictions,
        'top_pick': predictions[0] if predictions else None,
    }


def load_weights_for_surface(surface: str) -> Dict[str, float]:
    """
    Load optimized weights based on surface

    Args:
        surface: 'D' for dirt, 'T' for turf, other for all-weather

    Returns:
        Dictionary of weight factors
    """
    try:
        if surface == 'D':  # Dirt
            with open('output/dirt_optimized_weights.json', 'r') as f:
                return json.load(f)
        elif surface == 'T':  # Turf
            with open('output/turf_optimized_weights.json', 'r') as f:
                return json.load(f)
        else:  # All-Weather or Unknown - use general weights
            with open('output/optimized_weights_2023_full.json', 'r') as f:
                return json.load(f)
    except:
        # Fallback to general weights
        try:
            with open('output/optimized_weights_2023_full.json', 'r') as f:
                return json.load(f)
        except:
            # Ultimate fallback
            return {
                'speed': 0.30, 'form': 0.20, 'class': 0.15,
                'pace': 0.15, 'jockey': 0.10, 'trainer': 0.10,
            }


def main():
    """Main prediction function"""
    print("\n" + "="*80)
    print(" 2023 FULL RACE PREDICTIONS (SURFACE-SPECIFIC)")
    print("="*80)
    print(f"\nStarted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Load surface-specific weights
    print("\nStep 1: Loading surface-specific optimized weights...")
    print("  Dirt weights:")
    dirt_weights = load_weights_for_surface('D')
    for factor, weight in dirt_weights.items():
        print(f"    {factor:10s}: {weight:.4f}")
    print("  Turf weights:")
    turf_weights = load_weights_for_surface('T')
    for factor, weight in turf_weights.items():
        print(f"    {factor:10s}: {weight:.4f}")
    print("✓ Surface-specific weights loaded")

    # Load statistics
    print("\nStep 2: Loading statistics...")
    stats_loader = StatisticsLoader(
        jockey_file='data/stats/jockey_statistics_comprehensive.json',
        trainer_file='data/stats/trainer_statistics_comprehensive.json'
    )
    print("✓ Loaded jockey and trainer statistics")

    # Load FTS analyzer
    print("\nStep 3: Loading FTS analyzer...")
    fts_analyzer = FTSAnalyzer(
        trainer_stats_file='data/stats/fts_trainer_statistics.json',
        sire_stats_file='data/stats/fts_sire_statistics.json'
    )
    print("✓ Loaded FTS analyzer")

    # Initialize pace analyzer
    pace_analyzer = PaceAnalyzer()

    # Get all SIMD files
    print("\nStep 4: Finding SIMD files...")
    simd_files = glob('equibase 2023 data/2023 PPs/*.xml') + \
                 glob('equibase 2023 data/2023 PPs/*.zip')
    print(f"✓ Found {len(simd_files)} SIMD files")

    # Create output directory
    os.makedirs('output/2023_predictions', exist_ok=True)

    # Process each file
    print("\nStep 5: Generating predictions...")
    all_predictions = []
    processed = 0
    errors = 0

    with tempfile.TemporaryDirectory() as temp_dir:
        for i, simd_file in enumerate(simd_files, 1):
            try:
                # Extract if needed
                xml_file = extract_simd_file(simd_file, temp_dir)
                if not xml_file:
                    errors += 1
                    continue

                # Parse SIMD file (returns list of races)
                simd_races = parse_simd_file(xml_file)
                if not simd_races:
                    errors += 1
                    continue

                # Extract track code from filename
                track_code = extract_track_code_from_filename(simd_file)

                # Process each race in the file
                for simd_race in simd_races:
                    if not simd_race.horses:
                        continue

                    # Load surface-specific weights for this race
                    race_surface = simd_race.surface if hasattr(simd_race, 'surface') else 'D'
                    surface_weights = load_weights_for_surface(race_surface)

                    # Generate predictions with surface-specific weights
                    race_predictions = predict_race(
                        simd_race, stats_loader, fts_analyzer,
                        pace_analyzer, surface_weights, track_code
                    )

                    all_predictions.append(race_predictions)
                    processed += 1

                if processed % 100 == 0:
                    print(f"  Processed {processed} races...")

            except Exception as e:
                errors += 1
                if errors <= 5:  # Only show first 5 errors
                    print(f"  Error processing {os.path.basename(simd_file)}: {e}")

    print(f"\n✓ Processed {processed} races ({errors} errors)")

    # Save all predictions
    print("\nStep 6: Saving predictions...")
    output_file = f'output/2023_predictions/all_predictions_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    with open(output_file, 'w') as f:
        json.dump({
            'generated_at': datetime.now().isoformat(),
            'total_races': processed,
            'weights_used': optimized_weights,
            'predictions': all_predictions
        }, f, indent=2)

    print(f"✓ Saved to: {output_file}")

    # Create summary
    print("\n" + "="*80)
    print(" PREDICTION SUMMARY")
    print("="*80)
    print(f"\nTotal races predicted: {processed}")
    print(f"Errors encountered: {errors}")
    print(f"Success rate: {processed/(processed+errors)*100:.1f}%")
    print(f"\nPredictions saved to: {output_file}")
    print("\nThese predictions can be compared against results once downloaded.")
    print("\n" + "="*80)
    print(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()


print("ABOUT TO CHECK __name__", flush=True)

if __name__ == '__main__':
    print("INSIDE __main__ BLOCK", flush=True)
    main()
    print("MAIN COMPLETED", flush=True)
