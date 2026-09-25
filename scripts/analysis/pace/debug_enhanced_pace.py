#!/usr/bin/env python3
"""
Enhanced Pace Analyzer - Diagnostic Tool
==========================================
Systematically debugs the three issues:
1. Track variant loading
2. PPI calculations
3. Pace scenario thresholds
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, project_root)

from src.parsers.hybrid_parser_v3 import parse_pdf_hybrid_v3
from src.analyzers.pace_adapter import convert_pdf_race_to_enhanced
from src.analyzers.pace_analyzer_enhanced import EnhancedPaceAnalyzer

print("="*80)
print(" ENHANCED PACE ANALYZER - DIAGNOSTIC TOOL")
print("="*80)
print()

# Parse a sample race
pdf_path = "Keeneland October PPs/10-18-25-kee-ppspdf.pdf"
print(f"Parsing: {pdf_path}")
races = parse_pdf_hybrid_v3(pdf_path, debug=False)
pdf_race = races[0]  # Race 1

print(f"✓ Parsed Race {pdf_race.race_number}")
print(f"  Track: {pdf_race.track_name}")
print(f"  Distance: {pdf_race.distance}")
print(f"  Date: {pdf_race.date}")
print(f"  Surface: {pdf_race.surface_description}")
print()

# Convert to enhanced format
enhanced_race = convert_pdf_race_to_enhanced(pdf_race)

print("="*80)
print(" ISSUE #1: TRACK VARIANT LOADING")
print("="*80)
print()

# Check what the enhanced race object has
print(f"Enhanced race attributes:")
print(f"  track_code: {repr(enhanced_race.track_code)}")
print(f"  date: {repr(enhanced_race.date)}")
print(f"  surface: {repr(enhanced_race.surface)}")
print()

# Initialize analyzer and check track variants
analyzer = EnhancedPaceAnalyzer(track_variants_file='data/track_variants.json')

print(f"Track variants loaded: {len(analyzer.track_variants)} dates")
print(f"Track variant keys:")
for key in sorted(analyzer.track_variants.keys())[:5]:
    print(f"  - {key}")
print()

# Build the lookup key
track_key = f"{enhanced_race.track_code}_{enhanced_race.date}"
print(f"Lookup key being used: {repr(track_key)}")
print(f"Variant data found: {track_key in analyzer.track_variants}")

if track_key in analyzer.track_variants:
    print(f"✓ Variant data: {analyzer.track_variants[track_key]}")
else:
    print(f"✗ NO VARIANT DATA FOUND")
    print(f"\nDEBUG INFO:")
    print(f"  Expected key format: 'KEE_2025-10-18'")
    print(f"  Actual key generated: {repr(track_key)}")
    print(f"  Track code type: {type(enhanced_race.track_code)}")
    print(f"  Date type: {type(enhanced_race.date)}")

print()
print("="*80)
print(" ISSUE #2: PPI CALCULATION")
print("="*80)
print()

# Run pace analysis
pace_analysis = analyzer.analyze_race_pace(enhanced_race)

print(f"Pace Pressure Index: {pace_analysis.pace_pressure_index:.1f}")
print(f"Pace Scenario: {pace_analysis.scenario}")
print()

# Show individual early pace figures
print("Early Pace Figures (EPF) and Running Styles:")
e_ep_horses = []
all_epf_sum = 0.0
for horse in enhanced_race.horses:
    if hasattr(horse, 'pace_figures') and horse.pace_figures:
        epf = horse.pace_figures.early_pace_figure
        method = horse.pace_figures.method_used
        conf = horse.pace_figures.confidence
        style = horse.running_style if hasattr(horse, 'running_style') else 'None'

        # Track E/EP horses
        from src.analyzers.pace_analyzer_enhanced import RunningStyle
        if style in [RunningStyle.E, RunningStyle.EP, 'E', 'EP']:
            e_ep_horses.append((horse.name, epf))
            marker = " ← E/EP"
        else:
            marker = ""

        all_epf_sum += epf
        print(f"  {horse.name[:25]:<25}: EPF={epf:5.1f} | style={str(style):4s} | method={method:10s}{marker}")

print()
print(f"PPI Calculation Breakdown:")
print(f"  ALL horses EPF sum: {all_epf_sum:.1f}")
print(f"  E/EP horses count: {len(e_ep_horses)}")
print(f"  E/EP horses EPF sum: {sum([epf for _, epf in e_ep_horses]):.1f}")
print(f"  Total field size: {len(enhanced_race.horses)}")
print()
print(f"  Formula: Sum of E/EP EPFs / Total Field Size")
print(f"  Calculation: {sum([epf for _, epf in e_ep_horses]):.1f} / {len(enhanced_race.horses)} = {pace_analysis.pace_pressure_index:.1f}")
print()
print(f"  ⚠️  This formula results in low PPI values (20-40 range)")
print(f"  Alternative formula: Sum of ALL EPFs / Field Size = {all_epf_sum / len(enhanced_race.horses):.1f}")
print()

# Expected PPI range
print(f"Expected PPI Range: 0-150")
print(f"Actual PPI: {pace_analysis.pace_pressure_index:.1f}")

if pace_analysis.pace_pressure_index < 40:
    print(f"⚠️  PPI is TOO LOW - Suggests calculation issue")
    print(f"    Possible causes:")
    print(f"    - EPF calculations using positions instead of times")
    print(f"    - Confidence scores all 0.00 (fallback values)")
    print(f"    - Running style assignments incorrect")

print()
print("="*80)
print(" ISSUE #3: PACE SCENARIO THRESHOLDS")
print("="*80)
print()

print(f"Current Thresholds:")
print(f"  PPI < 60  → SLOW")
print(f"  PPI < 90  → HONEST")
print(f"  PPI < 120 → MODERATE_PRESSURE")
print(f"  PPI >= 120 → SPEED_DUEL")
print()

print(f"Actual PPI: {pace_analysis.pace_pressure_index:.1f}")
print(f"Classification: {pace_analysis.scenario}")
print()

# Analyze if thresholds need adjustment
print(f"RECOMMENDED ADJUSTMENTS (if using position-only data):")
print(f"  PPI < 20  → SLOW")
print(f"  PPI < 40  → HONEST")
print(f"  PPI < 60  → MODERATE_PRESSURE")
print(f"  PPI >= 60 → SPEED_DUEL")
print()

print("="*80)
print(" DIAGNOSTIC COMPLETE")
print("="*80)
print()

print("SUMMARY OF ISSUES:")
print(f"  1. Track variant loading: {'✓ WORKING' if track_key in analyzer.track_variants else '✗ NOT WORKING'}")
print(f"  2. PPI calculation: {'⚠️ TOO LOW' if pace_analysis.pace_pressure_index < 40 else '✓ REASONABLE'}")
print(f"  3. Pace thresholds: {'⚠️ NEED ADJUSTMENT' if pace_analysis.scenario == 'SLOW' and pace_analysis.pace_pressure_index < 40 else '✓ REASONABLE'}")
print()
