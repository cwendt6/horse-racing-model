"""
Generate predictions for all October 2025 race days

This script generates predictions for each PP PDF in the October folder
and saves them as JSON files for validation.
"""

import os
import glob
import subprocess
from datetime import datetime


def main():
    """Generate predictions for all October dates"""

    print()
    print("="*80)
    print(" GENERATING PREDICTIONS FOR ALL OCTOBER 2025 DATES")
    print("="*80)
    print()

    # Find all PP PDFs
    pp_files = sorted(glob.glob("Keeneland October PPs/*-kee-ppspdf.pdf"))

    print(f"Found {len(pp_files)} PP files")
    print()

    success_count = 0
    error_count = 0

    for pp_file in pp_files:
        # Extract date from filename
        filename = os.path.basename(pp_file)
        date_str = filename.split('-kee')[0]

        print(f"Processing {date_str}...")

        # Run predictions
        result = subprocess.run(
            ['python3', 'scripts/predict_from_pdf.py', pp_file],
            capture_output=True,
            text=True,
            timeout=600  # 10 minute timeout
        )

        if result.returncode == 0:
            # Check if JSON was created
            json_file = f"output/predictions_{date_str}.json"
            if os.path.exists(json_file):
                print(f"  ✓ Generated: {json_file}")
                success_count += 1
            else:
                print(f"  ✗ JSON not found: {json_file}")
                error_count += 1
        else:
            print(f"  ✗ Error running predictor")
            print(f"  {result.stderr[:200]}")
            error_count += 1

        print()

    print("="*80)
    print("SUMMARY:")
    print(f"  Success: {success_count}")
    print(f"  Errors: {error_count}")
    print("="*80)


if __name__ == "__main__":
    main()
