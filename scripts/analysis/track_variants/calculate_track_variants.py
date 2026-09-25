"""
Calculate Track Variants for October 2025 Keeneland
Uses actual race times from results PDFs vs par times to determine daily track speed
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pdfplumber
import re
import json
from collections import defaultdict
from typing import Dict, List, Tuple, Optional


# October 2025 race dates with results files
RACE_DATES = [
    ('2025-10-03', 'KEE100325USA.pdf'),
    ('2025-10-04', 'KEE100425USA.pdf'),
    ('2025-10-05', 'KEE100525USA.pdf'),
    ('2025-10-08', 'KEE100825USA.pdf'),
    ('2025-10-09', 'KEE100925USA.pdf'),
    ('2025-10-10', 'KEE101025USA.pdf'),
    ('2025-10-11', 'KEE101125USA.pdf'),
    ('2025-10-12', 'KEE101225USA.pdf'),
    ('2025-10-15', 'KEE101525USA.pdf'),
    ('2025-10-16', 'KEE101625USA.pdf'),
    ('2025-10-17', 'KEE101725USA.pdf'),
    ('2025-10-18', 'KEE101825USA.pdf'),
    ('2025-10-19', 'KEE101925USA.pdf'),
]

# Par times for different distances on dirt and turf (in seconds)
# These are from the enhanced pace analyzer
PAR_TIMES = {
    'dirt': {
        '5f': 57.0,    # 5 furlongs
        '5.5f': 63.0,  # 5.5 furlongs
        '6f': 69.0,    # 6 furlongs sprint
        '6.5f': 75.0,  # 6.5 furlongs
        '7f': 81.0,    # 7 furlongs
        '1m': 95.0,    # 1 mile (8 furlongs)
        '1m70y': 97.0, # 1 mile 70 yards
        '8.5f': 101.0, # 8.5 furlongs
        '9f': 108.0,   # 9 furlongs
        '1m1f': 115.0, # 1 mile 1 furlong
    },
    'turf': {
        '5f': 55.0,
        '5.5f': 61.0,
        '6f': 67.0,
        '7f': 79.0,
        '7.5f': 85.0,
        '1m': 93.0,
        '8.5f': 99.0,
        '9f': 106.0,
        '1m1f': 113.0,
    }
}


def parse_distance(distance_text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Parse distance from results PDF text
    Returns: (normalized_distance, surface)

    Examples:
    "AboutSevenFurlongsOnTheDirt" -> ("7f", "dirt")
    "OneMileOnTheTurf" -> ("1m", "turf")
    """
    distance_text = distance_text.lower()

    # Determine surface
    if 'turf' in distance_text:
        surface = 'turf'
    elif 'dirt' in distance_text:
        surface = 'dirt'
    else:
        surface = 'dirt'  # Default

    # Parse distance (handle both "seven furlongs" and "sevenfurlongs")
    if 'fivefurlong' in distance_text or 'five furlong' in distance_text or '5 furlong' in distance_text:
        if 'half' in distance_text or '5.5' in distance_text:
            distance = '5.5f'
        else:
            distance = '5f'
    elif 'sixfurlong' in distance_text or 'six furlong' in distance_text or '6 furlong' in distance_text:
        if 'half' in distance_text or '6.5' in distance_text:
            distance = '6.5f'
        else:
            distance = '6f'
    elif 'sevenfurlong' in distance_text or 'seven furlong' in distance_text or '7 furlong' in distance_text:
        if 'half' in distance_text or '7.5' in distance_text:
            distance = '7.5f'
        else:
            distance = '7f'
    elif 'onemile' in distance_text or 'one mile' in distance_text or '1 mile' in distance_text or '1m' in distance_text:
        if 'seventyyard' in distance_text or 'seventy yard' in distance_text or '70 yard' in distance_text:
            distance = '1m70y'
        elif 'onefurlong' in distance_text or 'one furlong' in distance_text or '1 furlong' in distance_text:
            distance = '1m1f'
        else:
            distance = '1m'
    elif 'eightandahalf' in distance_text or 'eight and a half' in distance_text or '8.5 furlong' in distance_text:
        distance = '8.5f'
    elif 'eightfurlong' in distance_text or 'eight furlong' in distance_text or '8 furlong' in distance_text:
        distance = '1m'  # 8F = 1 mile
    elif 'ninefurlong' in distance_text or 'nine furlong' in distance_text or '9 furlong' in distance_text:
        distance = '9f'
    else:
        # Try to extract numeric pattern
        match = re.search(r'(\d+\.?\d*)\s*furlong', distance_text)
        if match:
            furlongs = float(match.group(1))
            distance = f'{furlongs}f'
        else:
            distance = None

    return distance, surface


def parse_final_time(time_text: str) -> Optional[float]:
    """
    Parse final time in seconds

    Examples:
    "1:27.05" -> 87.05
    "1:10.38" -> 70.38
    ":57.23" -> 57.23
    """
    time_text = time_text.strip()

    try:
        if ':' in time_text:
            parts = time_text.split(':')
            if len(parts) == 2:
                minutes = int(parts[0]) if parts[0] else 0
                seconds = float(parts[1])
                return minutes * 60 + seconds
        else:
            return float(time_text)
    except (ValueError, IndexError):
        return None


def extract_race_data(pdf_path: str) -> List[Dict]:
    """
    Extract race data from results PDF

    Returns list of dicts with:
    - race_number
    - distance
    - surface
    - final_time (seconds)
    - track_condition
    """
    races = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue

            lines = text.split('\n')

            # Look for race header (format: "KEENELAND-October18,2025-Race1")
            for i, line in enumerate(lines):
                if line.startswith('KEENELAND-') and 'Race' in line:
                    # Extract race number
                    race_match = re.search(r'Race(\d+)', line)
                    if not race_match:
                        continue
                    race_number = int(race_match.group(1))

                    race_data = {
                        'race_number': race_number,
                        'distance': None,
                        'surface': None,
                        'final_time': None,
                        'track_condition': None,
                    }

                    # Look for distance and time (scan next 30 lines)
                    for j in range(i+1, min(i+30, len(lines))):
                        # Distance line
                        if 'furlong' in lines[j].lower() or 'mile' in lines[j].lower():
                            distance, surface = parse_distance(lines[j])
                            race_data['distance'] = distance
                            race_data['surface'] = surface

                        # Track condition
                        if 'Track:' in lines[j]:
                            condition_match = re.search(r'Track:\s*(\w+)', lines[j])
                            if condition_match:
                                race_data['track_condition'] = condition_match.group(1)

                        # Final time
                        if 'FinalTime:' in lines[j]:
                            time_match = re.search(r'FinalTime:\s*([\d:\.]+)', lines[j])
                            if time_match:
                                final_time = parse_final_time(time_match.group(1))
                                race_data['final_time'] = final_time
                            break

                    # Debug: Show what we extracted
                    # print(f"    Race {race_number}: dist={race_data['distance']}, time={race_data['final_time']}, surf={race_data['surface']}")

                    # Only add if we got the essential data
                    if race_data['distance'] and race_data['final_time']:
                        races.append(race_data)

    return races


def calculate_variant(actual_time: float, par_time: float) -> float:
    """
    Calculate track variant

    Positive = track is fast (horses running faster than par)
    Negative = track is slow (horses running slower than par)

    Formula: (par_time - actual_time) * 5
    This gives us points where 1 second difference = 5 points
    """
    return (par_time - actual_time) * 5.0


def calculate_daily_variants(date: str, pdf_file: str) -> Dict:
    """
    Calculate track variants for a single race day

    Returns dict with dirt and turf variants
    """
    pdf_path = f'data/Results Files/{pdf_file}'

    print(f"\nProcessing {date} ({pdf_file})...")

    # Extract race data
    races = extract_race_data(pdf_path)

    if not races:
        print(f"  ⚠️  No race data extracted")
        return None

    print(f"  Found {len(races)} races")

    # Calculate variants for each surface
    dirt_variants = []
    turf_variants = []

    for race in races:
        distance = race['distance']
        surface = race['surface']
        actual_time = race['final_time']

        # Get par time
        if surface in PAR_TIMES and distance in PAR_TIMES[surface]:
            par_time = PAR_TIMES[surface][distance]
            variant = calculate_variant(actual_time, par_time)

            if surface == 'dirt':
                dirt_variants.append(variant)
            else:
                turf_variants.append(variant)

            print(f"    R{race['race_number']:2d}: {distance:>6} {surface:4} | "
                  f"Actual: {actual_time:6.2f}s | Par: {par_time:6.2f}s | "
                  f"Variant: {variant:+6.2f}")
        else:
            print(f"    R{race['race_number']:2d}: {distance:>6} {surface:4} | "
                  f"No par time available")

    # Calculate average variants
    result = {}

    if dirt_variants:
        avg_dirt = sum(dirt_variants) / len(dirt_variants)
        result['dirt'] = {
            'variant': round(avg_dirt, 1),
            'races_in_sample': len(dirt_variants),
            'confidence': min(0.9, 0.5 + (len(dirt_variants) * 0.1)),  # More races = higher confidence
        }

        # Add note based on variant
        if avg_dirt > 2.5:
            result['dirt']['note'] = 'Fast track, horses running faster than par'
        elif avg_dirt < -2.5:
            result['dirt']['note'] = 'Slow track, horses running slower than par'
        else:
            result['dirt']['note'] = 'Track playing close to par'

        print(f"  ✓ Dirt variant: {avg_dirt:+.1f} (based on {len(dirt_variants)} races)")

    if turf_variants:
        avg_turf = sum(turf_variants) / len(turf_variants)
        result['turf'] = {
            'variant': round(avg_turf, 1),
            'races_in_sample': len(turf_variants),
            'confidence': min(0.9, 0.5 + (len(turf_variants) * 0.1)),
        }

        if avg_turf > 2.5:
            result['turf']['note'] = 'Fast turf course'
        elif avg_turf < -2.5:
            result['turf']['note'] = 'Slow turf course'
        else:
            result['turf']['note'] = 'Turf course playing close to par'

        print(f"  ✓ Turf variant: {avg_turf:+.1f} (based on {len(turf_variants)} races)")

    return result


def main():
    """Calculate track variants for all October 2025 dates"""

    print("="*80)
    print(" TRACK VARIANT CALCULATOR - October 2025 Keeneland")
    print("="*80)

    all_variants = {}

    for date, pdf_file in RACE_DATES:
        variants = calculate_daily_variants(date, pdf_file)

        if variants:
            # Format key as "KEE_2025-10-18"
            key = f"KEE_{date}"
            all_variants[key] = variants

    # Save to JSON
    output_path = 'data/track_variants.json'

    with open(output_path, 'w') as f:
        json.dump(all_variants, f, indent=2)

    print("\n" + "="*80)
    print(" SUMMARY")
    print("="*80)
    print(f"✓ Calculated variants for {len(all_variants)} race dates")
    print(f"✓ Saved to: {output_path}")
    print("\nVariant Summary:")

    for key in sorted(all_variants.keys()):
        date_str = key.replace('KEE_', '')
        variants = all_variants[key]

        surfaces = []
        if 'dirt' in variants:
            surfaces.append(f"Dirt: {variants['dirt']['variant']:+.1f}")
        if 'turf' in variants:
            surfaces.append(f"Turf: {variants['turf']['variant']:+.1f}")

        print(f"  {date_str}: {' | '.join(surfaces)}")

    print("\n✅ Track variants calculation complete!")


if __name__ == '__main__':
    main()
