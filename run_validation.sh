#!/bin/bash
# Run Validation - Compare Predictions to Results
# Usage: ./run_validation.sh

set -e

echo "========================================"
echo " Validation - October 2025 Results"
echo "========================================"
echo ""
echo "Comparing predictions to actual results..."
echo "Results files: data/Results Files/KEE*.pdf"
echo ""

# Check if predictions exist
PRED_COUNT=$(ls output/predictions_*.json 2>/dev/null | wc -l)
if [ "$PRED_COUNT" -eq 0 ]; then
    echo "Error: No prediction files found in output/"
    echo "Run predictions first: ./run_prediction.sh \"path/to/pp.pdf\""
    exit 1
fi

echo "Found $PRED_COUNT prediction files"
echo ""
echo "Running validation..."
echo ""

# Run validation
python3 scripts/production/run_october_validation.py

echo ""
echo "✅ Validation complete!"
echo ""
echo "Output files:"
echo "  - output/october_validation_report.json"
echo ""
echo "View summary:"
echo "  python3 -c \"import json; r=json.load(open('output/october_validation_report.json')); print(f\\\"Win: {r['win_rate']:.1f}%, Top-3: {r['top_3_rate']:.1f}%, ROI: {r.get('roi', 0):.1f}%\\\")\""
