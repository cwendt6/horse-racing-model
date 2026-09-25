#!/usr/bin/env python3
"""
Save Predictions to JSON
Generates predictions from a PP PDF and saves them in JSON format for manual input system
"""

import sys
import os
import json
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = os.path.dirname(__file__)
sys.path.insert(0, project_root)

from scripts.predict_from_pdf import predict_race, load_optimized_weights
from src.parsers.hybrid_parser_v3 import parse_pdf_hybrid_v3
from src.data_loaders.statistics_loader import StatisticsLoader
from src.analyzers.fts_analyzer import FTSAnalyzer
from src.analyzers.pace_analyzer import PaceAnalyzer
from src.analyzers.pace_analyzer_enhanced import EnhancedPaceAnalyzer
from src.analyzers.track_bias_detector import TrackBiasDetector
from src.analyzers.jockey_trainer_analyzer import JockeyTrainerAnalyzer
from src.analyzers.distance_surface_analyzer import DistanceSurfaceAnalyzer


def save_predictions_to_json(pp_pdf_path, output_json_path):
    """Parse PDF, generate predictions, and save to JSON"""

    print(f"\n{'='*80}")
    print(f" GENERATING PREDICTIONS FROM {Path(pp_pdf_path).name}")
    print(f"{'='*80}\n")

    # Load stats and analyzers
    print("📚 Loading statistics databases...")
    stats_loader = StatisticsLoader(
        jockey_file='data/stats/jockey_statistics_comprehensive.json',
        trainer_file='data/stats/trainer_statistics_comprehensive.json'
    )

    print("🔧 Initializing analyzers...")
    fts_analyzer = FTSAnalyzer(
        trainer_stats_file='data/stats/fts_trainer_statistics.json',
        sire_stats_file='data/stats/fts_sire_statistics.json'
    )
    pace_analyzer = PaceAnalyzer()
    enhanced_pace_analyzer = EnhancedPaceAnalyzer(
        track_variants_file='data/track_variants.json'
    )
    track_bias_detector = TrackBiasDetector()
    jockey_trainer_analyzer = JockeyTrainerAnalyzer()
    distance_surface_analyzer = DistanceSurfaceAnalyzer()

    print("⚖️  Loading optimized weights...")
    weights = load_optimized_weights('dirt')

    # Parse PDF
    print(f"\n📄 Parsing {pp_pdf_path}...")
    races = parse_pdf_hybrid_v3(pp_pdf_path, debug=False)
    print(f"✓ Found {len(races)} races")

    # Generate predictions for all races
    all_race_data = []

    for race in races:
        print(f"\n{'='*80}")
        print(f"Processing Race {race.race_number}...")

        result = predict_race(
            race, stats_loader, fts_analyzer, pace_analyzer, enhanced_pace_analyzer,
            track_bias_detector, jockey_trainer_analyzer, distance_surface_analyzer, weights
        )

        # Unpack result
        if isinstance(result, tuple):
            predictions, pace_scenario, value_bets = result
        else:
            predictions = result['predictions']
            pace_scenario = result.get('pace_scenario')
            value_bets = result.get('value_bets', [])

        if not predictions:
            print(f"⚠️ No predictions for Race {race.race_number}")
            continue

        # Build race data structure
        race_data = {
            'race_number': race.race_number,
            'date': race.date,
            'track': race.track_name,
            'distance': race.distance_text,
            'surface': race.surface_description,
            'race_type': race.race_type,
            'purse': race.purse,
            'pace_scenario': pace_scenario.scenario_type if hasattr(pace_scenario, 'scenario_type') else str(pace_scenario),
            'predictions': predictions
        }

        all_race_data.append(race_data)
        print(f"✓ Generated predictions for {len(predictions)} horses")

    # Create output structure
    output_data = {
        'generated_at': datetime.now().isoformat(),
        'source_file': str(Path(pp_pdf_path).name),
        'track': races[0].track_name if races else 'Unknown',
        'date': races[0].date if races else 'Unknown',
        'total_races': len(all_race_data),
        'races': all_race_data
    }

    # Save to JSON
    output_path = Path(output_json_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump(output_data, f, indent=2)

    print(f"\n{'='*80}")
    print(f" PREDICTIONS SAVED")
    print(f"{'='*80}")
    print(f"\nFile: {output_path}")
    print(f"Races: {len(all_race_data)}")
    print(f"Horses: {sum(len(r['predictions']) for r in all_race_data)}")
    print(f"\nNext steps:")
    print(f"  1. Review predictions: python show_plays.py {output_path}")
    print(f"  2. Update with live data: python manual_input_system.py {output_path}")
    print()


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python save_predictions.py <pp_pdf_file> [output_json]")
        print("\nExample:")
        print("  python save_predictions.py 'Keeneland October PPs/10-19-25-kee-ppspdf.pdf'")
        print("  python save_predictions.py 'Keeneland October PPs/10-19-25-kee-ppspdf.pdf' predictions/oct19_base.json")
        sys.exit(1)

    pp_pdf_path = sys.argv[1]

    # Default output path if not specified
    if len(sys.argv) >= 3:
        output_json_path = sys.argv[2]
    else:
        # Auto-generate output filename from input
        input_name = Path(pp_pdf_path).stem
        output_json_path = f"predictions/{input_name}_predictions.json"

    save_predictions_to_json(pp_pdf_path, output_json_path)
