"""
October 2025 Validation - Compare Predictions to Actual Results

This script:
1. Loads predictions from predict_from_pdf.py output
2. Parses actual results from results PDFs
3. Compares predictions to actuals
4. Generates comprehensive accuracy report
"""

import os
import sys
import json
import glob
from datetime import datetime
from typing import List, Dict

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from scripts.results_validator import ResultsValidator, PredictionResult


def find_pp_file(date_str: str) -> str:
    """
    Find the PP PDF file for a given date

    Args:
        date_str: Date in format "2025-10-18"

    Returns:
        Path to PP PDF file
    """
    # Convert 2025-10-18 to 10-18-25
    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    filename_date = date_obj.strftime("%m-%d-%y")

    # Look for file
    pattern = f"Keeneland October PPs/{filename_date}-kee-ppspdf.pdf"

    if os.path.exists(pattern):
        return pattern
    else:
        return None


def find_results_file(date_str: str) -> str:
    """
    Find the results PDF file for a given date

    Args:
        date_str: Date in format "2025-10-18"

    Returns:
        Path to results PDF file
    """
    # Convert 2025-10-18 to KEE101825USA.pdf
    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    month = date_obj.strftime("%m")
    day = date_obj.strftime("%d")
    year = date_obj.strftime("%y")

    filename = f"data/Results Files/KEE{month}{day}{year}USA.pdf"

    if os.path.exists(filename):
        return filename
    else:
        return None


def generate_predictions(pp_file: str, date_str: str) -> Dict:
    """
    Generate predictions for a race card

    Args:
        pp_file: Path to PP PDF
        date_str: Date string for output filename

    Returns:
        Dict with predictions for all races
    """
    print(f"  Generating predictions from {pp_file}...")

    # Import predict_from_pdf
    sys.path.insert(0, 'scripts')
    from predict_from_pdf import main as predict_main

    # Run predictions (captures output)
    # This will generate predictions and save to output files
    import subprocess
    result = subprocess.run(
        ['python3', 'scripts/predict_from_pdf.py', pp_file],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print(f"    ✗ Prediction failed: {result.stderr[:200]}")
        return None

    # Look for generated JSON output
    # predict_from_pdf.py doesn't create JSON by default, so we'll need to parse the text output
    # For now, return None and we'll implement JSON export separately
    print(f"    ⚠️  No JSON output - need to implement prediction JSON export")
    return None


def load_prediction_output(date_str: str) -> List[Dict]:
    """
    Load prediction output from file

    Args:
        date_str: Date in format "2025-10-18"

    Returns:
        List of prediction dicts (one per race)
    """
    # Convert date to filename format
    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    filename_date = date_obj.strftime("%m-%d-%y")

    # Look for JSON prediction file
    json_file = f"output/predictions_{filename_date}.json"

    if os.path.exists(json_file):
        with open(json_file) as f:
            data = json.load(f)

            # Convert to list of race dicts (compatible with validation)
            predictions = []
            for race_data in data.get('races', []):
                predictions.append({
                    'race_number': race_data['race_number'],
                    'predictions': race_data['predictions']
                })

            return predictions

    return None


def create_prediction_dict_from_results(validator: ResultsValidator, pp_file: str, results_file: str) -> List[Dict]:
    """
    Create prediction dictionaries by running predictor

    For now, this is a placeholder - we'll need to modify predict_from_pdf.py
    to output JSON that we can load here.

    Returns:
        List of prediction dicts (one per race)
    """
    # Parse results to know how many races there are
    results = validator.parse_results_pdf(results_file)

    print(f"    Found {len(results)} races in results file")

    # For each race, we need predictions
    # This is a placeholder - returning empty dicts for now
    predictions = []
    for result in results:
        predictions.append({
            'race_number': result.race_number,
            'predictions': []  # Empty for now
        })

    return predictions


def main():
    """Run October 2025 validation"""

    print()
    print("="*80)
    print(" OCTOBER 2025 VALIDATION - Predictions vs Actual Results")
    print("="*80)
    print()

    # Initialize validator
    validator = ResultsValidator()

    # Date range: October 10-19, 2025
    dates = [
        "2025-10-10",
        "2025-10-11",
        "2025-10-12",
        "2025-10-13",  # If exists
        "2025-10-16",  # If exists
        "2025-10-17",  # If exists
        "2025-10-18",
        "2025-10-19",
    ]

    all_comparisons = []
    dates_processed = 0

    for date_str in dates:
        print(f"\n{'='*80}")
        print(f" {date_str}")
        print(f"{'='*80}")

        # Find files
        pp_file = find_pp_file(date_str)
        results_file = find_results_file(date_str)

        if not pp_file or not os.path.exists(pp_file):
            print(f"  ⊗ PP file not found - skipping")
            continue

        if not results_file or not os.path.exists(results_file):
            print(f"  ⊗ Results file not found - skipping")
            continue

        print(f"  ✓ PP file: {pp_file}")
        print(f"  ✓ Results file: {results_file}")

        # Parse actual results
        results = validator.parse_results_pdf(results_file)
        print(f"  ✓ Parsed {len(results)} race results")

        # Load or generate predictions
        predictions = load_prediction_output(date_str)

        if not predictions:
            print(f"  ⚠️  No prediction JSON found")
            print(f"  ⚠️  This validation requires predict_from_pdf.py to export JSON")
            print(f"  ⚠️  Skipping {date_str} for now")
            continue

        # Compare predictions to results
        for result in results:
            # Find matching prediction
            pred = next((p for p in predictions if p['race_number'] == result.race_number), None)

            if pred:
                comparison = validator.compare_prediction_to_result(pred, result)
                all_comparisons.append(comparison)

        dates_processed += 1

    # Generate validation report
    print()
    print("="*80)
    print(" VALIDATION REPORT")
    print("="*80)

    if len(all_comparisons) == 0:
        print()
        print("⚠️  NO COMPARISONS AVAILABLE")
        print()
        print("REASON: predict_from_pdf.py does not currently export JSON output")
        print()
        print("NEXT STEPS:")
        print("1. Modify predict_from_pdf.py to save predictions to JSON")
        print("2. Re-run predictions for October 10-19")
        print("3. Re-run this validation script")
        print()
        print("="*80)
        return

    report = validator.generate_validation_report(all_comparisons)
    validator.print_report(report)

    # Save report to file
    output_file = 'output/october_validation_report.json'
    with open(output_file, 'w') as f:
        json.dump(report, f, indent=2)

    print(f"\n✓ Report saved to: {output_file}")
    print("="*80)


if __name__ == "__main__":
    main()
