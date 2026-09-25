"""
Track Bias Analysis - October 2025 Keeneland

Analyzes post position and pace bias patterns to identify:
1. Post position bias by surface (dirt vs turf)
2. Post position bias by distance (sprint vs route)
3. Pace bias (early speed vs closers)
4. Track condition effects

Results will be used to create bias multipliers for the scoring system.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.parsers.pdf_parser import parse_pdf_file
from scripts.analyze_score_calibration import parse_results_pdf
from collections import defaultdict
import json


# October 2025 race dates
RACE_DATES = [
    ('10-3-25-kee-ppspdf.pdf', 'KEE100325USA.pdf'),
    ('10-5-25-kee-ppspdf.pdf', 'KEE100525USA.pdf'),
    ('10-8-25-kee-ppspdf.pdf', 'KEE100825USA.pdf'),
    ('10-9-25-kee-ppspdf.pdf', 'KEE100925USA.pdf'),
    ('10-10-25-kee-ppspdf.pdf', 'KEE101025USA.pdf'),
    ('10-11-25-kee-ppspdf.pdf', 'KEE101125USA.pdf'),
    ('10-12-25-kee-ppspdf.pdf', 'KEE101225USA.pdf'),
    ('10-15-25-kee-ppspdf.pdf', 'KEE101525USA.pdf'),
    ('10-16-25-kee-ppspdf.pdf', 'KEE101625USA.pdf'),
    ('10-17-25-kee-ppspdf.pdf', 'KEE101725USA.pdf'),
    ('10-18-25-kee-ppspdf.pdf', 'KEE101825USA.pdf'),
    ('10-19-25-kee-ppspdf.pdf', 'KEE101925USA.pdf'),
]


def classify_distance(distance_furlongs: float) -> str:
    """Classify race distance"""
    if distance_furlongs < 7.0:
        return 'sprint'  # < 7F
    elif distance_furlongs < 9.0:
        return 'mile'    # 7F - 8.5F
    else:
        return 'route'   # 9F+


def main():
    print('='*80)
    print(' TRACK BIAS ANALYSIS - OCTOBER 2025 KEENELAND')
    print('='*80)
    print()

    # Data structures for analysis
    post_position_data = defaultdict(lambda: {'starts': 0, 'wins': 0})
    pace_bias_data = defaultdict(lambda: {'starts': 0, 'wins': 0})
    surface_post_data = defaultdict(lambda: defaultdict(lambda: {'starts': 0, 'wins': 0}))
    distance_post_data = defaultdict(lambda: defaultdict(lambda: {'starts': 0, 'wins': 0}))

    total_races = 0
    total_starters = 0

    print('Loading and analyzing races...')
    print()

    for pp_date, results_file in RACE_DATES:
        pp_path = f'Keeneland October PPs/{pp_date}'
        results_path = f'data/Results Files/{results_file}'

        try:
            pp_races = parse_pdf_file(pp_path, debug=False)
            actual_results = parse_results_pdf(results_path)
        except FileNotFoundError:
            continue

        for pp_race in pp_races:
            race_num = pp_race.race_number
            total_races += 1

            # Find matching result
            matching_result = None
            for result in actual_results:
                if result['race_number'] == race_num:
                    matching_result = result
                    break

            if not matching_result:
                continue

            winner_pgm = matching_result['winner_pgm']

            # Get race characteristics
            surface = pp_race.surface_description.lower()
            distance_furlongs = pp_race.distance / 100.0
            distance_class = classify_distance(distance_furlongs)
            field_size = len(pp_race.horses)

            # Analyze each horse
            for horse in pp_race.horses:
                total_starters += 1

                # Get post position (program number as proxy)
                try:
                    post = int(horse.program_number)
                except (ValueError, TypeError):
                    continue

                is_winner = (str(horse.program_number) == str(winner_pgm))
                running_style = horse.running_style

                # Overall post position
                post_position_data[post]['starts'] += 1
                if is_winner:
                    post_position_data[post]['wins'] += 1

                # Post by surface
                surface_key = 'turf' if 'turf' in surface else 'dirt'
                surface_post_data[surface_key][post]['starts'] += 1
                if is_winner:
                    surface_post_data[surface_key][post]['wins'] += 1

                # Post by distance class
                distance_post_data[distance_class][post]['starts'] += 1
                if is_winner:
                    distance_post_data[distance_class][post]['wins'] += 1

                # Pace bias (running style)
                pace_bias_data[running_style]['starts'] += 1
                if is_winner:
                    pace_bias_data[running_style]['wins'] += 1

    print(f'✓ Analyzed {total_races} races, {total_starters} starters')
    print()

    # ============================================================================
    # OVERALL POST POSITION ANALYSIS
    # ============================================================================
    print('='*80)
    print(' POST POSITION BIAS - ALL RACES')
    print('='*80)
    print()
    print(f"{'Post':<6} {'Starts':<8} {'Wins':<6} {'Win %':<8} {'Impact':<10}")
    print('-'*80)

    # Calculate expected win rate (random distribution)
    expected_win_rate = 1.0 / (total_starters / total_races)  # Avg field size

    for post in sorted(post_position_data.keys()):
        if post > 14:  # Skip very high posts (outliers)
            continue

        starts = post_position_data[post]['starts']
        wins = post_position_data[post]['wins']

        if starts < 10:  # Need minimum sample size
            continue

        win_pct = wins / starts if starts > 0 else 0
        impact = (win_pct / expected_win_rate - 1.0) * 100

        impact_str = f"{impact:+.1f}%"
        if impact > 15:
            impact_str += " ✅"
        elif impact < -15:
            impact_str += " ❌"

        print(f"{post:<6} {starts:<8} {wins:<6} {win_pct*100:>5.1f}%  {impact_str:<10}")

    print()

    # ============================================================================
    # SURFACE-SPECIFIC POST BIAS
    # ============================================================================
    for surface_key in ['turf', 'dirt']:
        if surface_key not in surface_post_data:
            continue

        print('='*80)
        print(f' POST POSITION BIAS - {surface_key.upper()}')
        print('='*80)
        print()
        print(f"{'Post':<6} {'Starts':<8} {'Wins':<6} {'Win %':<8} {'Impact':<10}")
        print('-'*80)

        # Calculate surface-specific expected win rate
        surface_starts = sum(data['starts'] for data in surface_post_data[surface_key].values())
        surface_wins = sum(data['wins'] for data in surface_post_data[surface_key].values())
        surface_avg_field = surface_starts / total_races if total_races > 0 else 10
        surface_expected = 1.0 / surface_avg_field

        for post in sorted(surface_post_data[surface_key].keys()):
            if post > 14:
                continue

            starts = surface_post_data[surface_key][post]['starts']
            wins = surface_post_data[surface_key][post]['wins']

            if starts < 5:
                continue

            win_pct = wins / starts if starts > 0 else 0
            impact = (win_pct / surface_expected - 1.0) * 100

            impact_str = f"{impact:+.1f}%"
            if impact > 15:
                impact_str += " ✅"
            elif impact < -15:
                impact_str += " ❌"

            print(f"{post:<6} {starts:<8} {wins:<6} {win_pct*100:>5.1f}%  {impact_str:<10}")

        print()

    # ============================================================================
    # DISTANCE-SPECIFIC POST BIAS
    # ============================================================================
    for dist_class in ['sprint', 'mile', 'route']:
        if dist_class not in distance_post_data:
            continue

        print('='*80)
        print(f' POST POSITION BIAS - {dist_class.upper()} RACES')
        print('='*80)
        print()
        print(f"{'Post':<6} {'Starts':<8} {'Wins':<6} {'Win %':<8} {'Impact':<10}")
        print('-'*80)

        dist_starts = sum(data['starts'] for data in distance_post_data[dist_class].values())
        dist_avg_field = dist_starts / total_races if total_races > 0 else 10
        dist_expected = 1.0 / dist_avg_field

        for post in sorted(distance_post_data[dist_class].keys()):
            if post > 14:
                continue

            starts = distance_post_data[dist_class][post]['starts']
            wins = distance_post_data[dist_class][post]['wins']

            if starts < 3:
                continue

            win_pct = wins / starts if starts > 0 else 0
            impact = (win_pct / dist_expected - 1.0) * 100

            impact_str = f"{impact:+.1f}%"
            if impact > 20:
                impact_str += " ✅"
            elif impact < -20:
                impact_str += " ❌"

            print(f"{post:<6} {starts:<8} {wins:<6} {win_pct*100:>5.1f}%  {impact_str:<10}")

        print()

    # ============================================================================
    # PACE BIAS ANALYSIS
    # ============================================================================
    print('='*80)
    print(' PACE BIAS - RUNNING STYLE PERFORMANCE')
    print('='*80)
    print()
    print(f"{'Style':<12} {'Starts':<8} {'Wins':<6} {'Win %':<8} {'Impact':<10}")
    print('-'*80)

    for style in ['E', 'P', 'S', 'C']:
        if style not in pace_bias_data:
            continue

        starts = pace_bias_data[style]['starts']
        wins = pace_bias_data[style]['wins']

        if starts < 5:
            continue

        win_pct = wins / starts if starts > 0 else 0
        impact = (win_pct / expected_win_rate - 1.0) * 100

        style_name = {
            'E': 'Early Speed',
            'P': 'Presser',
            'S': 'Stalker',
            'C': 'Closer'
        }[style]

        impact_str = f"{impact:+.1f}%"
        if impact > 20:
            impact_str += " ✅ FAVORED"
        elif impact < -20:
            impact_str += " ❌ DISADVANTAGED"

        print(f"{style_name:<12} {starts:<8} {wins:<6} {win_pct*100:>5.1f}%  {impact_str:<10}")

    print()

    # ============================================================================
    # BIAS MULTIPLIERS RECOMMENDATIONS
    # ============================================================================
    print('='*80)
    print(' RECOMMENDED BIAS MULTIPLIERS')
    print('='*80)
    print()

    bias_multipliers = {
        'post_position': {},
        'pace_bias': {},
        'surface_post': {}
    }

    # Post position multipliers (overall)
    print('Post Position Multipliers (apply to post score):')
    for post in sorted(post_position_data.keys()):
        if post > 12 or post_position_data[post]['starts'] < 10:
            continue

        starts = post_position_data[post]['starts']
        wins = post_position_data[post]['wins']
        win_pct = wins / starts if starts > 0 else expected_win_rate

        # Multiplier: how much better/worse than expected
        multiplier = win_pct / expected_win_rate

        bias_multipliers['post_position'][post] = round(multiplier, 3)

        symbol = "✅" if multiplier > 1.1 else "❌" if multiplier < 0.9 else "→"
        print(f"  Post {post:2d}: {multiplier:.3f}x {symbol}")

    print()

    # Pace bias multipliers
    print('Pace Bias Multipliers (apply to pace score):')
    for style in ['E', 'P', 'S', 'C']:
        if style not in pace_bias_data or pace_bias_data[style]['starts'] < 10:
            continue

        starts = pace_bias_data[style]['starts']
        wins = pace_bias_data[style]['wins']
        win_pct = wins / starts if starts > 0 else expected_win_rate

        multiplier = win_pct / expected_win_rate

        bias_multipliers['pace_bias'][style] = round(multiplier, 3)

        style_name = {'E': 'Early', 'P': 'Presser', 'S': 'Stalker', 'C': 'Closer'}[style]
        symbol = "✅" if multiplier > 1.15 else "❌" if multiplier < 0.85 else "→"
        print(f"  {style_name:8s}: {multiplier:.3f}x {symbol}")

    print()

    # Save results
    output_file = 'output/track_bias_analysis_october_2025.json'
    with open(output_file, 'w') as f:
        json.dump({
            'total_races': total_races,
            'total_starters': total_starters,
            'expected_win_rate': expected_win_rate,
            'bias_multipliers': bias_multipliers,
            'raw_data': {
                'post_position': dict(post_position_data),
                'pace_bias': dict(pace_bias_data),
                'surface_post': {k: dict(v) for k, v in surface_post_data.items()},
                'distance_post': {k: dict(v) for k, v in distance_post_data.items()}
            }
        }, f, indent=2)

    print(f'✓ Saved analysis to: {output_file}')
    print()

    # Summary recommendations
    print('='*80)
    print(' IMPLEMENTATION RECOMMENDATIONS')
    print('='*80)
    print()

    # Identify key biases
    inside_posts = [p for p in range(1, 4) if p in bias_multipliers['post_position']]
    outside_posts = [p for p in range(8, 13) if p in bias_multipliers['post_position']]

    if inside_posts:
        inside_avg = sum(bias_multipliers['post_position'][p] for p in inside_posts) / len(inside_posts)
        print(f"Inside Posts (1-3): {inside_avg:.3f}x avg multiplier")
        if inside_avg > 1.1:
            print("  → INSIDE BIAS DETECTED - Boost inside posts")
        elif inside_avg < 0.9:
            print("  → OUTSIDE BIAS DETECTED - Penalize inside posts")
        print()

    # Pace bias summary
    if 'E' in bias_multipliers['pace_bias'] and 'C' in bias_multipliers['pace_bias']:
        speed_mult = bias_multipliers['pace_bias']['E']
        closer_mult = bias_multipliers['pace_bias']['C']

        print(f"Early Speed: {speed_mult:.3f}x")
        print(f"Closers: {closer_mult:.3f}x")

        if speed_mult > closer_mult * 1.2:
            print("  → SPEED-FAVORING TRACK - Boost early speed")
        elif closer_mult > speed_mult * 1.2:
            print("  → CLOSER-FAVORING TRACK - Boost closers")
        else:
            print("  → NEUTRAL TRACK - No strong pace bias")

    print()


if __name__ == '__main__':
    main()
