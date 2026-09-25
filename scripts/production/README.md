# Production Scripts

**Status**: PRODUCTION - These scripts are optimized and validated.

## Core Scripts

### predict_from_pdf.py
Main prediction engine using optimized weights.

**Usage**:
```bash
python3 scripts/production/predict_from_pdf.py "path/to/pp.pdf" [race_number]
```

**Features**:
- 5-layer hybrid parser (99%+ accuracy)
- Optimized weights (Form #1, Class #2)
- 18 integrated analyzers
- High-confidence probability calibration

**Performance**:
- Win Rate: 7.0% (4/57 races)
- High-Confidence Win Rate: 100% (4/4 when >25% probability)
- ROI: +381.8% on high-confidence picks

### run_october_validation.py
Validation orchestrator comparing predictions to actual results.

**Usage**:
```bash
python3 scripts/production/run_october_validation.py
```

**Output**:
- Generates validation report in output/
- Compares predictions to Results Files
- Calculates win rate, top-3, top-5, ROI

## Optimization Results

**Weight Discoveries**:
- Form: 0.225 (was #4, now #1) - +54% increase
- Class: 0.215 (was #3, now #2) - +72% increase
- Speed: 0.068 (was #1, now #7) - -70% decrease
- Workout Scale: 1.66x (+66%)
- Trip Notes Scale: 0.56x (-44%)

**Key Insight**: Form and Class are more predictive than Speed.

See `docs/OPTIMIZATION_COMPLETE_SUMMARY.md` for full details.

---

*Last Updated*: October 21, 2025
*Model Version*: Hybrid Parser V3 + Optimized 5-Component Scoring
