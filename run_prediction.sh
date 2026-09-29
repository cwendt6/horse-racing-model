#!/bin/bash
# Quick Prediction Script - Production Model
# Usage: ./run_prediction.sh "path/to/pp.pdf" [race_number]

set -e

# Check if PDF path provided
if [ -z "$1" ]; then
    echo "Usage: ./run_prediction.sh \"path/to/pp.pdf\" [race_number]"
    echo ""
    echo "Examples:"
    echo "  ./run_prediction.sh \"Keeneland October PPs/10-18-25-kee-ppspdf.pdf\""
    echo "  ./run_prediction.sh \"Keeneland October PPs/10-18-25-kee-ppspdf.pdf\" 3"
    exit 1
fi

PDF_PATH="$1"
RACE_NUMBER="${2:-}"

# Check if file exists
if [ ! -f "$PDF_PATH" ]; then
    echo "Error: PDF file not found: $PDF_PATH"
    exit 1
fi

echo "========================================"
echo " Production Model - Optimized Weights"
echo "========================================"
echo ""
echo "PDF: $PDF_PATH"
if [ -n "$RACE_NUMBER" ]; then
    echo "Race: $RACE_NUMBER"
else
    echo "Mode: All Races"
fi
echo ""
echo "Backtest results and their limits (small samples, overfitting): see README.md"
echo ""
echo "----------------------------------------"

# Run prediction
if [ -n "$RACE_NUMBER" ]; then
    python3 scripts/production/predict_from_pdf.py "$PDF_PATH" "$RACE_NUMBER"
else
    python3 scripts/production/predict_from_pdf.py "$PDF_PATH"
fi

echo ""
echo "✅ Prediction complete!"
