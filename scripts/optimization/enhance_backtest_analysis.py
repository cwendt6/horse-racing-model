#!/usr/bin/env python3
"""
Enhanced Backtest Analysis
Adds deep-dive analysis to existing October 2025 backtest results:
- Scratch analysis
- Fractional times vs predictions
- Running positions/pace dynamics
- Speed figure vs actual time analysis
- Weight adjustment recommendations
"""

import json
import sys
import os
from typing import Dict, List
from collections import defaultdict
import pdfplumber
import re

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class EnhancedBacktestAnalyzer:
    """Enhances existing backtest with detailed race analysis"""

    def __init__(self, backtest_json_path: str):
        """Load existing backtest results"""
        with open(backtest_json_path) as f:
            self.backtest_data = json.load(f)

        self.results_by_date_race = {}
        for result in self.backtest_data['detailed_results']:
            key = (result['date'], result['race'])
            self.results_by_date_race[key] = result

    def extract_scratches(self, results_pdf_path: str) -> Dict:
        """Extract scratched horses from results PDF"""

        scratches = {}

        with pdfplumber.open(results_pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if not text:
                    continue

                lines = text.split('\n')

                # Find race number
                race_num = None
                for line in lines:
                    race_match = re.search(r'KEENELAND.*?October\d+,2025.*?Race(\d+)', line)
                    if race_match:
                        race_num = int(race_match.group(1))
                        break

                if not race_num:
                    continue

                # Find scratched horses
                scratched_horses = []
                for line in lines:
                    if 'ScratchedHorse' in line or 'Scratched' in line:
                        scratch_text = re.sub(r'ScratchedHorse\(s\):\s*', '', line)
                        for horse_part in scratch_text.split(','):
                            horse_match = re.search(r'([A-Z][a-zA-Z]+(?:[A-Z][a-z]+)*)', horse_part)
                            if horse_match:
                                scratched_horses.append(horse_match.group(1))
                        break

                scratches[race_num] = scratched_horses if scratched_horses else []

        return scratches

    def _time_to_seconds(self, time_str: str) -> float:
        """Convert time string to seconds"""
        time_str = time_str.strip()
        try:
            if ':' in time_str:
                parts = time_str.split(':')
                if len(parts) == 2:
                    minutes = int(parts[0]) if parts[0] else 0
                    seconds = float(parts[1])
                    return minutes * 60 + seconds
            else:
                return float(time_str)
        except (ValueError, IndexError):
            return 0.0

    def extract_fractional_times(self, results_pdf_path: str) -> Dict:
        """Extract fractional times from results"""

        times = {}

        with pdfplumber.open(results_pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if not text:
                    continue

                lines = text.split('\n')

                # Find race number
                race_num = None
                for line in lines:
                    race_match = re.search(r'KEENELAND.*?October\d+,2025.*?Race(\d+)', line)
                    if race_match:
                        race_num = int(race_match.group(1))
                        break

                if not race_num:
                    continue

                # Find fractional times
                for line in lines:
                    if 'FractionalTimes:' in line:
                        # Try sprint format (3 fractions)
                        match = re.search(
                            r'FractionalTimes:([\d\.:]+)\s+([\d\.:]+)\s+([\d\.:]+)\s+FinalTime:([\d\.:]+)',
                            line
                        )
                        if match:
                            times[race_num] = {
                                'quarter': self._time_to_seconds(match.group(1)),
                                'half': self._time_to_seconds(match.group(2)),
                                'six_f': self._time_to_seconds(match.group(3)),
                                'final': self._time_to_seconds(match.group(4))
                            }
                        else:
                            # Try route format (4 fractions)
                            match = re.search(
                                r'FractionalTimes:([\d\.:]+)\s+([\d\.:]+)\s+([\d\.:]+)\s+([\d\.:]+)\s+FinalTime:([\d\.:]+)',
                                line
                            )
                            if match:
                                times[race_num] = {
                                    'quarter': self._time_to_seconds(match.group(1)),
                                    'half': self._time_to_seconds(match.group(2)),
                                    'six_f': self._time_to_seconds(match.group(3)),
                                    'mile': self._time_to_seconds(match.group(4)),
                                    'final': self._time_to_seconds(match.group(5))
                                }
                        break

        return times

    def analyze_scratches_impact(self):
        """Analyze how scratches affected our predictions"""

        scratch_analysis = {
            'total_scratches': 0,
            'our_picks_scratched': 0,
            'top3_scratched': 0,
            'days_with_scratches': 0,
            'scratch_details': []
        }

        # Get all results PDFs
        results_dir = "data/Results Files"
        dates_processed = set()

        for result in self.backtest_data['detailed_results']:
            date = result['date']

            if date in dates_processed:
                continue
            dates_processed.add(date)

            # Find results PDF for this date
            month, day, year = date.split('-')
            results_file = f"{results_dir}/KEE{month}{day}{year}USA.pdf"

            if not os.path.exists(results_file):
                continue

            # Extract scratches for this day
            scratches_by_race = self.extract_scratches(results_file)

            if any(scratches_by_race.values()):
                scratch_analysis['days_with_scratches'] += 1

            for race_num, scratched_horses in scratches_by_race.items():
                if not scratched_horses:
                    continue

                scratch_analysis['total_scratches'] += len(scratched_horses)

                # Find this race in backtest results
                key = (date, race_num)
                if key in self.results_by_date_race:
                    race_result = self.results_by_date_race[key]

                    # Check if any of our top picks scratched
                    top5_names = [p['name'] for p in race_result['top_5']]

                    for scratch in scratched_horses:
                        # Check if scratch matches any top pick
                        for pick_name in top5_names:
                            if scratch.lower() in pick_name.lower() or pick_name.lower() in scratch.lower():
                                scratch_analysis['our_picks_scratched'] += 1

                                scratch_analysis['scratch_details'].append({
                                    'date': date,
                                    'race': race_num,
                                    'scratched_horse': scratch,
                                    'our_pick_name': pick_name
                                })
                                break

        return scratch_analysis

    def analyze_pace_vs_actuals(self):
        """Compare pace predictions to actual fractional times"""

        pace_analysis = {
            'by_scenario': defaultdict(lambda: {
                'total': 0,
                'fast_starts': 0,  # Quarter < 22.5s for sprint
                'slow_starts': 0,  # Quarter > 23.5s
                'accurate_predictions': 0
            }),
            'pace_details': []
        }

        # Process each results file
        results_dir = "data/Results Files"
        dates_processed = set()

        for result in self.backtest_data['detailed_results']:
            date = result['date']
            race_num = result['race']

            # Find results PDF
            month, day, year = date.split('-')
            results_file = f"{results_dir}/KEE{month}{day}{year}USA.pdf"

            if not os.path.exists(results_file):
                continue

            # Skip if already processed this day
            if date not in dates_processed:
                dates_processed.add(date)

                # Extract fractional times for all races this day
                times_by_race = self.extract_fractional_times(results_file)

                # Analyze each race
                for race_num_day, times in times_by_race.items():
                    key = (date, race_num_day)
                    if key not in self.results_by_date_race:
                        continue

                    race_result = self.results_by_date_race[key]
                    predicted_pace = race_result['pace_scenario']

                    # Classify actual pace based on quarter time
                    quarter_time = times.get('quarter', 99)

                    actual_pace = None
                    if quarter_time < 22.5:
                        actual_pace = "FAST_PACE"
                    elif quarter_time > 23.5:
                        actual_pace = "SLOW_PACE"
                    else:
                        actual_pace = "MODERATE_PACE"

                    # Update stats
                    pace_analysis['by_scenario'][predicted_pace]['total'] += 1

                    if quarter_time < 22.5:
                        pace_analysis['by_scenario'][predicted_pace]['fast_starts'] += 1
                    elif quarter_time > 23.5:
                        pace_analysis['by_scenario'][predicted_pace]['slow_starts'] += 1

                    # Check if prediction was accurate
                    # SPEED_DUEL should correlate with fast starts
                    # NO_SPEED should correlate with slow starts
                    accurate = False
                    if predicted_pace == "SPEED_DUEL" and quarter_time < 22.5:
                        accurate = True
                    elif predicted_pace == "NO_SPEED" and quarter_time > 23.5:
                        accurate = True
                    elif predicted_pace == "HONEST_PACE" and 22.5 <= quarter_time <= 23.5:
                        accurate = True

                    if accurate:
                        pace_analysis['by_scenario'][predicted_pace]['accurate_predictions'] += 1

                    pace_analysis['pace_details'].append({
                        'date': date,
                        'race': race_num_day,
                        'predicted_pace': predicted_pace,
                        'actual_pace': actual_pace,
                        'quarter_time': quarter_time,
                        'final_time': times.get('final', 0),
                        'accurate': accurate
                    })

        return pace_analysis

    def generate_weight_recommendations(self):
        """Generate specific weight adjustment recommendations"""

        recommendations = []

        # Analyze which pace scenarios performed best
        pace_scenarios = self.backtest_data.get('pace_scenarios', {})

        print("\n" + "="*80)
        print(" ANALYZING PACE SCENARIO PERFORMANCE")
        print("="*80)

        for scenario, stats in sorted(pace_scenarios.items(), key=lambda x: x[1].get('win_rate', 0), reverse=True):
            win_rate = stats.get('win_rate', 0)
            races = stats.get('races', 0)

            print(f"\n{scenario}:")
            print(f"  Win Rate: {win_rate}% ({stats.get('wins', 0)}/{races})")

            if win_rate > 35:
                recommendations.append({
                    'factor': 'pace',
                    'recommendation': f"INCREASE pace weight for {scenario} races (high win rate: {win_rate}%)",
                    'current_impact': '+',
                    'suggested_change': '+2-3 points'
                })
            elif win_rate < 15:
                recommendations.append({
                    'factor': 'pace',
                    'recommendation': f"DECREASE pace weight for {scenario} races (low win rate: {win_rate}%)",
                    'current_impact': '-',
                    'suggested_change': '-1-2 points'
                })

        # Analyze top picks that didn't win
        print("\n" + "="*80)
        print(" TOP PICKS THAT DIDN'T WIN (Learning Opportunities)")
        print("="*80)

        misses = [r for r in self.backtest_data['detailed_results'] if not r['win_hit'] and r['top3_hit']]
        print(f"\nFound {len(misses)} races where our pick finished 2nd or 3rd")

        if misses:
            print("\nSample of near-misses:")
            for miss in misses[:5]:
                print(f"  {miss['date']} R{miss['race']}: Picked #{miss['top_pick_pgm']} {miss['top_pick_name']}")
                print(f"    Winner: #{miss['winner_pgm']} {miss['winner_name']}")
                print(f"    Pace: {miss['pace_scenario']}")

        return recommendations

    def generate_enhanced_report(self):
        """Generate comprehensive analysis report"""

        print("\n" + "="*80)
        print(" ENHANCED BACKTEST ANALYSIS - OCTOBER 2025 KEENELAND")
        print("="*80)

        # Original backtest summary
        summary = self.backtest_data['summary']
        print(f"\n📊 OVERALL PERFORMANCE:")
        print(f"  Total Races: {summary['total_races']}")
        print(f"  Win Rate: {summary['win_rate']}")
        print(f"  Top-3 Rate: {summary['top3_rate']}")
        print(f"  Top-5 Rate: {summary['top5_rate']}")

        # Scratch analysis
        print("\n🚫 SCRATCH ANALYSIS:")
        scratch_analysis = self.analyze_scratches_impact()
        print(f"  Total Scratches: {scratch_analysis['total_scratches']}")
        print(f"  Days with Scratches: {scratch_analysis['days_with_scratches']}")
        print(f"  Our Picks Scratched: {scratch_analysis['our_picks_scratched']}")

        if scratch_analysis['scratch_details']:
            print(f"\n  Scratched Picks Details:")
            for detail in scratch_analysis['scratch_details'][:5]:
                print(f"    {detail['date']} R{detail['race']}: {detail['scratched_horse']}")

        # Pace analysis
        print("\n⚡ PACE PREDICTION ACCURACY:")
        pace_analysis = self.analyze_pace_vs_actuals()

        for scenario, stats in pace_analysis['by_scenario'].items():
            if stats['total'] > 0:
                accuracy = stats['accurate_predictions'] / stats['total'] * 100
                print(f"\n  {scenario}:")
                print(f"    Races: {stats['total']}")
                print(f"    Fast Starts: {stats['fast_starts']}")
                print(f"    Slow Starts: {stats['slow_starts']}")
                print(f"    Accuracy: {accuracy:.1f}%")

        # Weight recommendations
        print("\n💡 WEIGHT ADJUSTMENT RECOMMENDATIONS:")
        recommendations = self.generate_weight_recommendations()

        for i, rec in enumerate(recommendations, 1):
            print(f"\n  {i}. {rec['recommendation']}")
            print(f"     Suggested Change: {rec['suggested_change']}")

        # Save enhanced results
        enhanced_data = {
            'original_backtest': self.backtest_data,
            'scratch_analysis': scratch_analysis,
            'pace_analysis': dict(pace_analysis['by_scenario']),
            'recommendations': recommendations
        }

        output_path = "output/enhanced_backtest_analysis.json"
        with open(output_path, 'w') as f:
            json.dump(enhanced_data, f, indent=2)

        print(f"\n✓ Enhanced analysis saved to: {output_path}")


if __name__ == "__main__":
    backtest_path = "output/october_2025_backtest_results.json"

    if not os.path.exists(backtest_path):
        print(f"Error: Backtest results not found at {backtest_path}")
        print("Please run october_2025_backtest.py first")
        sys.exit(1)

    analyzer = EnhancedBacktestAnalyzer(backtest_path)
    analyzer.generate_enhanced_report()

    print("\n" + "="*80)
    print(" ANALYSIS COMPLETE")
    print("="*80)
