"""
Weight Optimization Script
Finds optimal weight distribution for 9-factor scoring system
Uses grid search on October 2025 Keeneland validation data
"""

import sys
import json
from pathlib import Path
from itertools import product
import pdfplumber
import re

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.parsers.pdf_parser import parse_pdf_file
from src.analyzers import racing_statistics as stats
from src.data_loaders.statistics_loader import StatisticsLoader
from src.analyzers.fts_analyzer import FTSAnalyzer


def parse_results_pdf(pdf_path):
    """Parse results PDF to extract winners"""
    results = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            lines = text.split('\n')

            for i, line in enumerate(lines):
                if 'KEENELAND' in line and 'Race' in line:
                    race_match = re.search(r'Race(\d+)', line)
                    if not race_match:
                        continue
                    race_num = int(race_match.group(1))

                    finishers = []
                    for j in range(i, min(i+50, len(lines))):
                        result_line = lines[j]

                        if re.match(r'^\d{1,2}[A-Z][a-z]{2}\d{2}', result_line):
                            parts = result_line.split()
                            if len(parts) >= 3:
                                pgm_num = parts[1]
                                horse_name = parts[2].split('(')[0]

                                finishers.append({
                                    'program_number': pgm_num,
                                    'horse_name': horse_name,
                                    'finish_position': len(finishers) + 1
                                })

                        if 'FractionalTimes:' in result_line:
                            break

                    if finishers:
                        results.append({
                            'race_number': race_num,
                            'winner_pgm': finishers[0]['program_number']
                        })

    return results


def calculate_race_predictions(pdf_race, race_data, weights, stats_loader, fts_analyzer):
    """
    Calculate predictions with custom weights

    Returns:
        list of predictions sorted by score
    """
    predictions = []

    for horse in pdf_race.horses:
        # Get jockey/trainer stats
        jockey_stats = stats_loader.get_jockey_stats(horse.jockey_name)
        trainer_stats = stats_loader.get_trainer_stats(horse.trainer_name)

        # Check FTS
        fts_data = {'is_fts': horse.career_starts == 0, 'advantage': 0.0}
        if fts_data['is_fts']:
            fts_multiplier, _ = fts_analyzer.calculate_fts_multiplier(
                trainer_name=horse.trainer_name,
                sire_name=horse.sire_name
            )
            fts_data['advantage'] = fts_multiplier - 1.0

        # Parse odds
        try:
            if '-' in horse.morning_line_odds:
                num, denom = horse.morning_line_odds.split('-')
                decimal_odds = (float(num) / float(denom)) + 1
            else:
                decimal_odds = float(horse.morning_line_odds) + 1
        except:
            decimal_odds = 6.0

        # Recent finishes
        recent_finishes = []
        if horse.past_performances:
            recent_finishes = [pp['finish'] for pp in horse.past_performances[:5] if 'finish' in pp]

        # Post position
        try:
            post_position = int(horse.program_number)
        except (ValueError, TypeError):
            post_position = 5

        # Days since last race
        days_since_last = 999
        if horse.last_race_date and race_data.get('date'):
            try:
                from datetime import datetime
                race_date = datetime.strptime(race_data['date'], '%Y-%m-%d')
                last_race = datetime.strptime(horse.last_race_date, '%Y-%m-%d')
                days_since_last = (race_date - last_race).days
            except:
                pass

        # Build horse_data
        horse_data = {
            'name': horse.name,
            'program_number': horse.program_number,
            'jockey_name': horse.jockey_name,
            'trainer_name': horse.trainer_name,
            'morning_line_odds': decimal_odds,
            'post': post_position,
            'best_beyer': horse.best_speed_figure if horse.best_speed_figure > 0 else 70,
            'last_beyer': horse.last_speed_figure if horse.last_speed_figure > 0 else 70,
            'avg_beyer': horse.avg_speed_figure if horse.avg_speed_figure > 0 else 70,
            'career_starts': horse.career_starts if horse.career_starts > 0 else 10,
            'career_wins': horse.career_wins,
            'career_earnings': horse.career_earnings if horse.career_earnings > 0 else 50000,
            'recent_finishes': recent_finishes,
            'days_since_last_race': days_since_last,
            'past_performances': horse.past_performances if horse.past_performances else [],
            'jockey_win_pct': jockey_stats.win_percentage / 100.0 if jockey_stats else 0.15,
            'trainer_win_pct': trainer_stats.win_percentage / 100.0 if trainer_stats else 0.15,
            'running_style': horse.running_style,
            'is_fts': fts_data['is_fts'],
            'fts_advantage': fts_data['advantage'],
        }

        # Calculate component scores (using default weights internally)
        score = stats.calculate_comprehensive_score(horse_data, race_data)

        # Apply CUSTOM weights for optimization
        final_score = (
            score.speed * weights['speed'] +
            score.form * weights['form'] +
            score.class_rating * weights['class'] +
            score.pace * weights['pace'] +
            score.recency * weights['recency'] +
            score.progression * weights['progression'] +
            score.jockey * weights['jockey'] +
            score.trainer * weights['trainer'] +
            score.post * weights['post']
        )

        predictions.append({
            'program_number': horse.program_number,
            'score': final_score
        })

    # Sort by score
    predictions.sort(key=lambda x: x['score'], reverse=True)

    return predictions


def evaluate_weights(weights, test_data, stats_loader, fts_analyzer):
    """
    Evaluate weight combination on test data

    Returns:
        dict with win_rate and other metrics
    """
    total_races = 0
    wins = 0
    top3_hits = 0

    for race_data in test_data:
        pp_race = race_data['pp_race']
        actual_winner = race_data['actual_winner']

        # Create race_data dict
        race_info = {
            'date': pp_race.date,
            'distance': pp_race.distance_text,
            'surface': pp_race.surface_description.lower(),
            'track_condition': pp_race.track_condition,
            'purse': pp_race.purse if pp_race.purse > 0 else 50000,
            'field_size': len(pp_race.horses),
            'avg_beyer': 70,
        }

        # Get predictions with these weights
        predictions = calculate_race_predictions(pp_race, race_info, weights, stats_loader, fts_analyzer)

        if not predictions:
            continue

        total_races += 1

        # Check if top pick won
        if predictions[0]['program_number'] == actual_winner:
            wins += 1

        # Check if winner in top 3
        top3_pgms = [p['program_number'] for p in predictions[:3]]
        if actual_winner in top3_pgms:
            top3_hits += 1

    win_rate = wins / total_races if total_races > 0 else 0.0
    top3_rate = top3_hits / total_races if total_races > 0 else 0.0

    return {
        'win_rate': win_rate,
        'top3_rate': top3_rate,
        'wins': wins,
        'total': total_races
    }


def load_test_data(test_dates, pp_dir, results_dir, stats_loader, fts_analyzer):
    """Load all test race data"""
    test_data = []

    print("Loading test data...")
    for pp_file, results_file in test_dates:
        pp_path = pp_dir / pp_file
        results_path = results_dir / results_file

        if not pp_path.exists() or not results_path.exists():
            continue

        # Parse results
        actual_results = parse_results_pdf(str(results_path))

        # Parse PPs
        pp_races = parse_pdf_file(str(pp_path), debug=False)

        # Match them
        for pp_race in pp_races:
            matching_result = None
            for result in actual_results:
                if result['race_number'] == pp_race.race_number:
                    matching_result = result
                    break

            if matching_result:
                test_data.append({
                    'pp_race': pp_race,
                    'actual_winner': matching_result['winner_pgm']
                })

    print(f"✓ Loaded {len(test_data)} races for optimization\n")
    return test_data


def grid_search_optimization(test_data, stats_loader, fts_analyzer):
    """
    Grid search optimization

    Tests combinations of weights that sum to 1.0
    """
    print("="*80)
    print(" WEIGHT OPTIMIZATION - GRID SEARCH")
    print("="*80)
    print()

    # Define weight ranges (as percentages, will normalize to sum to 1.0)
    # Focus on the major factors
    speed_range = [0.22, 0.25, 0.28, 0.30]      # Currently 0.25
    form_range = [0.14, 0.16, 0.18, 0.20]       # Currently 0.16
    class_range = [0.10, 0.12, 0.14]            # Currently 0.12
    pace_range = [0.10, 0.12, 0.14]             # Currently 0.12
    recency_range = [0.08, 0.10, 0.12]          # Currently 0.10

    # Keep smaller weights in narrower ranges
    progression_range = [0.05, 0.07, 0.09]      # Currently 0.07
    jockey_range = [0.06, 0.07, 0.08]           # Currently 0.07
    trainer_range = [0.06, 0.07, 0.08]          # Currently 0.07
    post_range = [0.03, 0.04, 0.05]             # Currently 0.04

    best_win_rate = 0.0
    best_weights = None
    best_metrics = None

    total_combinations = (len(speed_range) * len(form_range) * len(class_range) *
                         len(pace_range) * len(recency_range) * len(progression_range) *
                         len(jockey_range) * len(trainer_range) * len(post_range))

    print(f"Testing {total_combinations} weight combinations...")
    print(f"This will take several minutes...\n")

    tested = 0
    improvements = 0

    for speed in speed_range:
        for form in form_range:
            for class_w in class_range:
                for pace in pace_range:
                    for recency in recency_range:
                        for progression in progression_range:
                            for jockey in jockey_range:
                                for trainer in trainer_range:
                                    for post in post_range:
                                        # Create weight dict
                                        weights = {
                                            'speed': speed,
                                            'form': form,
                                            'class': class_w,
                                            'pace': pace,
                                            'recency': recency,
                                            'progression': progression,
                                            'jockey': jockey,
                                            'trainer': trainer,
                                            'post': post
                                        }

                                        # Normalize to sum to 1.0
                                        total = sum(weights.values())
                                        weights = {k: v/total for k, v in weights.items()}

                                        # Evaluate
                                        metrics = evaluate_weights(weights, test_data, stats_loader, fts_analyzer)

                                        tested += 1

                                        # Track best
                                        if metrics['win_rate'] > best_win_rate:
                                            best_win_rate = metrics['win_rate']
                                            best_weights = weights.copy()
                                            best_metrics = metrics.copy()
                                            improvements += 1

                                            # Print improvement
                                            print(f"✓ New best: {best_win_rate*100:.1f}% win rate "
                                                  f"({best_metrics['wins']}/{best_metrics['total']})")

                                        # Progress indicator
                                        if tested % 500 == 0:
                                            print(f"  Progress: {tested}/{total_combinations} combinations tested...")

    print()
    print("="*80)
    print(" OPTIMIZATION COMPLETE")
    print("="*80)
    print()
    print(f"Tested: {tested} combinations")
    print(f"Improvements found: {improvements}")
    print()
    print(f"Best Win Rate: {best_win_rate*100:.2f}% ({best_metrics['wins']}/{best_metrics['total']})")
    print(f"Best Top-3 Rate: {best_metrics['top3_rate']*100:.2f}%")
    print()
    print("Optimal Weights:")
    for factor, weight in sorted(best_weights.items(), key=lambda x: x[1], reverse=True):
        print(f"  {factor:12s}: {weight*100:5.2f}%")
    print()

    return best_weights, best_metrics


def main():
    """Main optimization function"""

    # Initialize loaders
    print("Loading statistics and analyzers...")
    stats_loader = StatisticsLoader(
        jockey_file='data/stats/jockey_statistics_comprehensive.json',
        trainer_file='data/stats/trainer_statistics_comprehensive.json'
    )
    fts_analyzer = FTSAnalyzer(
        trainer_stats_file='data/stats/fts_trainer_statistics.json',
        sire_stats_file='data/stats/fts_sire_statistics.json'
    )
    print("✓ Statistics loaded\n")

    # Test dates - ALL October 2025 race days (12 dates)
    test_dates = [
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

    pp_dir = Path("Keeneland October PPs")
    results_dir = Path("data/Results Files")

    # Load test data
    test_data = load_test_data(test_dates, pp_dir, results_dir, stats_loader, fts_analyzer)

    # Run optimization
    best_weights, best_metrics = grid_search_optimization(test_data, stats_loader, fts_analyzer)

    # Save optimized weights
    output_file = 'output/optimized_weights_october_2025.json'
    with open(output_file, 'w') as f:
        json.dump(best_weights, f, indent=2)

    print(f"✓ Saved optimized weights to: {output_file}")
    print()

    # Show comparison to baseline
    baseline_weights = {
        'speed': 0.25,
        'form': 0.16,
        'class': 0.12,
        'pace': 0.12,
        'recency': 0.10,
        'progression': 0.07,
        'jockey': 0.07,
        'trainer': 0.07,
        'post': 0.04,
    }

    baseline_metrics = evaluate_weights(baseline_weights, test_data, stats_loader, fts_analyzer)

    print("="*80)
    print(" COMPARISON: BASELINE vs OPTIMIZED")
    print("="*80)
    print()
    print(f"Baseline Win Rate:  {baseline_metrics['win_rate']*100:.2f}% ({baseline_metrics['wins']}/{baseline_metrics['total']})")
    print(f"Optimized Win Rate: {best_metrics['win_rate']*100:.2f}% ({best_metrics['wins']}/{best_metrics['total']})")
    print(f"Improvement:        +{(best_metrics['win_rate'] - baseline_metrics['win_rate'])*100:.2f} percentage points")
    print()


if __name__ == '__main__':
    main()
