#!/usr/bin/env python3
"""
Debug script to test exotic betting optimizer initialization
"""

import sys
import os
sys.path.insert(0, 'src')
sys.path.insert(0, '.')
sys.path.insert(0, 'scripts')

from pathlib import Path
import json

# Debug logging function
def debug_log(message):
    with open('output/optimizer_debug.log', 'a') as f:
        f.write(f"{message}\n")
        f.flush()
    print(message)

debug_log("=== STARTING DEBUG TEST ===")

try:
    debug_log("1. Testing imports...")
    from results_validator import ResultsValidator
    debug_log("   ✓ ResultsValidator imported")

    debug_log("2. Testing baseline weights load...")
    with open('config/optimized_weights.json', 'r') as f:
        baseline_data = json.load(f)
    debug_log(f"   ✓ Loaded {len(baseline_data)} weights")

    debug_log("3. Testing ResultsValidator initialization...")
    validator = ResultsValidator(results_dir="data/Results Files")
    debug_log("   ✓ ResultsValidator created")

    debug_log("4. Testing predictions directory...")
    predictions_dir = Path("output")
    pred_files = list(predictions_dir.glob("predictions_*.json"))
    debug_log(f"   ✓ Found {len(pred_files)} prediction files")

    debug_log("5. Testing results directory...")
    results_dir = Path("data/Results Files")
    results_files = list(results_dir.glob("KEE*.pdf"))
    debug_log(f"   ✓ Found {len(results_files)} results files")

    debug_log("\n=== ALL TESTS PASSED ===")
    debug_log("Initialization components work individually.")
    debug_log("Issue must be in the optimizer class itself.")

except Exception as e:
    debug_log(f"\n✗ ERROR: {str(e)}")
    import traceback
    debug_log(traceback.format_exc())
