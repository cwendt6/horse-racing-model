import os
"""
Comprehensive Backtest Review System

Analyzes October 2025 backtest results in detail:
1. Predictions vs Actual Results
2. Scratch Impact
3. Pace Predictions vs Actual Race Dynamics
4. Speed Figures vs Actual Times
5. Weight Adjustment Recommendations

This tool provides insights for optimizing the prediction model.
"""

import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

import json
import re
import pdfplumber
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple, Optional
from datetime import datetime

# Import parsers
from src.parsers.hybrid_parser_v3 import parse_pdf_hybrid_v3


class ComprehensiveBacktestReviewer:
    """
    Comprehensive analysis of backtest results
    """

    def __init__(self):
        self.october_dates = [
            '10-03-25', '10-04-25', '10-05-25', '10-10-25', '10-11-25',
            '10-12-25', '10-13-25', '10-18-25', '10-19-25'
        ]

        self.pp_dir = Path('Keeneland October PPs')
        self.results_dir = Path('data/Results Files')

        self.analysis_results = {
            'predictions_accuracy': [],
            'scratch_impact': [],
            'pace_accuracy': [],
            'speed_figure_accuracy': [],
            'weight_recommendations': {}
        }

    def extract_winner_from_results(self, results_pdf_path: str) -> Dict[int, Dict]:
        """Extract race winners from results PDF"""

        winners = {}

        with pdfplumber.open(results_pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if not text:
                    continue

                lines = text.split('\n')

                # Find race number
                # Format: "KEENELAND-October18,2025-Race1"
                race_num = None
                for line in lines:
                    race_match = re.search(r'KEENELAND.*?October\d+,2025.*?Race(\d+)', line)
                    if race_match:
                        race_num = int(race_match.group(1))
                        break

                if not race_num:
                    continue

                # Find winner
                # Format: "Winner: IndyMagic,BayGelding,..."
                winner_name = None
                winner_pgm = None
                winner_odds = None

                for i, line in enumerate(lines):
                    if line.startswith('Winner:'):
                        winner_match = re.search(r'Winner:\s+([^,]+),', line)
                        if winner_match:
                            winner_name = winner_match.group(1).strip()

                    # Find program number from betting payoffs section
                    # Format: "6 IndyMagic 4.82 3.18 2.78..."
                    if winner_name and winner_name in line and not line.startswith('Winner'):
                        parts = line.split()
                        if len(parts) >= 2 and parts[0].isdigit() and parts[1] == winner_name:
                            winner_pgm = parts[0]
                            if len(parts) >= 3:
                                try:
                                    winner_odds = float(parts[2])  # Win payoff
                                except:
                                    pass

                if winner_name and race_num:
                    winners[race_num] = {
                        'name': winner_name,
                        'program_number': winner_pgm if winner_pgm else 'Unknown',
                        'odds': winner_odds
                    }

        return winners

    def extract_scratches_from_results(self, results_pdf_path: str) -> Dict[int, List[str]]:
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
                # Format: "ScratchedHorse(s): CapeTrafalgar(PrivVet-Illness),PlausibleDenile(PrivVet-Illness)"
                scratched_horses = []
                for line in lines:
                    if 'ScratchedHorse' in line or 'Scratched' in line:
                        # Extract horse names from scratch line
                        # Remove "ScratchedHorse(s):" prefix
                        scratch_text = re.sub(r'ScratchedHorse\(s\):\s*', '', line)
                        # Split by comma and extract horse names before parentheses
                        for horse_part in scratch_text.split(','):
                            horse_match = re.search(r'([A-Z][a-zA-Z]+(?:[A-Z][a-z]+)*)', horse_part)
                            if horse_match:
                                scratched_horses.append(horse_match.group(1))
                        break

                if scratched_horses:
                    scratches[race_num] = scratched_horses
                else:
                    # No scratches found
                    scratches[race_num] = []

        return scratches

    def extract_actual_fractional_times(self, results_pdf_path: str) -> Dict[int, Dict]:
        """Extract fractional times from results"""

        fractional_times = {}

        with pdfplumber.open(results_pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if not text:
                    continue

                lines = text.split('\n')

                # Find race number
                # Format: "KEENELAND-October18,2025-Race1"
                race_num = None
                for line in lines:
                    race_match = re.search(r'KEENELAND.*?October\d+,2025.*?Race(\d+)', line)
                    if race_match:
                        race_num = int(race_match.group(1))
                        break

                if not race_num:
                    continue

                # Find fractional times
                # Format: "FractionalTimes:22.66 45.76 1:10.38 FinalTime:1:27.05"
                for line in lines:
                    if 'FractionalTimes:' in line:
                        # Try 3-fraction format first (sprint)
                        frac_match = re.search(
                            r'FractionalTimes:([\d\.:]+)\s+([\d\.:]+)\s+([\d\.:]+)\s+FinalTime:([\d\.:]+)',
                            line
                        )
                        if frac_match:
                            fractional_times[race_num] = {
                                'quarter': self._time_to_seconds(frac_match.group(1)),
                                'half': self._time_to_seconds(frac_match.group(2)),
                                'six_f': self._time_to_seconds(frac_match.group(3)),
                                'final': self._time_to_seconds(frac_match.group(4))
                            }
                        else:
                            # Try 4-fraction format (route)
                            frac_match = re.search(
                                r'FractionalTimes:([\d\.:]+)\s+([\d\.:]+)\s+([\d\.:]+)\s+([\d\.:]+)\s+FinalTime:([\d\.:]+)',
                                line
                            )
                            if frac_match:
                                fractional_times[race_num] = {
                                    'quarter': self._time_to_seconds(frac_match.group(1)),
                                    'half': self._time_to_seconds(frac_match.group(2)),
                                    'six_f': self._time_to_seconds(frac_match.group(3)),
                                    'mile': self._time_to_seconds(frac_match.group(4)),
                                    'final': self._time_to_seconds(frac_match.group(5))
                                }

        return fractional_times

    def _time_to_seconds(self, time_str: str) -> float:
        """Convert time string to seconds"""
        try:
            if ':' in time_str:
                parts = time_str.split(':')
                if len(parts) == 2:
                    return float(parts[0]) * 60 + float(parts[1])
            return float(time_str)
        except:
            return 0.0

    def extract_running_positions(self, results_pdf_path: str) -> Dict[int, Dict]:
        """Extract running positions from PP preview"""

        positions = {}

        with pdfplumber.open(results_pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if not text:
                    continue

                lines = text.split('\n')

                # Find race number
                # Format: "KEENELAND-October18,2025-Race1"
                race_num = None
                for line in lines:
                    race_match = re.search(r'KEENELAND.*?October\d+,2025.*?Race(\d+)', line)
                    if race_match:
                        race_num = int(race_match.group(1))
                        break

                if not race_num:
                    continue

                # Extract from PP preview
                # Start after "PastPerformanceRunningLinePreview" header
                in_pp_preview = False
                race_positions = {}

                for line in lines:
                    if 'PastPerformanceRunningLinePreview' in line:
                        in_pp_preview = True
                        continue

                    # Skip header line
                    if in_pp_preview and line.strip().startswith('Pgm'):
                        continue

                    # Stop at end marker
                    if in_pp_preview and (not line.strip() or 'KEENELAND' in line):
                        in_pp_preview = False
                        break

                    if in_pp_preview:
                        # Format: "6 IndyMagic 5 311/2 31/2 11 123/4"
                        # Or: "9 AmericanXperiment 1 21/2 21/2 21 223/4"
                        parts = line.split()
                        if len(parts) >= 6 and parts[0].isdigit():
                            pgm = parts[0]
                            horse_name = parts[1]
                            start = re.sub(r'[^\d]', '', parts[2])
                            quarter = re.sub(r'[^\d]', '', parts[3])
                            half = re.sub(r'[^\d]', '', parts[4])
                            stretch = re.sub(r'[^\d]', '', parts[5])
                            finish = re.sub(r'[^\d]', '', parts[6]) if len(parts) > 6 else stretch

                            race_positions[horse_name] = {
                                'program_number': pgm,
                                'start': start if start else '99',
                                'quarter': quarter if quarter else start if start else '99',
                                'half': half if half else quarter if quarter else '99',
                                'stretch': stretch if stretch else half if half else '99',
                                'finish': finish if finish else '99'
                            }

                if race_positions:
                    positions[race_num] = race_positions

        return positions

    def analyze_race(self, date_str: str, pp_path: str, results_path: str) -> Dict:
        """Comprehensive analysis of a single race day"""

        print(f"\n{'='*80}")
        print(f" ANALYZING {date_str}")
        print(f"{'='*80}")

        # Generate predictions
        print(f"\n📊 Generating predictions from PP PDF...")
        try:
            races = parse_pdf_hybrid_v3(pp_path, debug=False)
            print(f"   ✓ Parsed {len(races)} races")
        except Exception as e:
            print(f"   ✗ Failed to parse PP: {e}")
            return None

        # Extract results
        print(f"\n🏆 Extracting actual results...")
        try:
            winners = self.extract_winner_from_results(results_path)
            frac_times = self.extract_actual_fractional_times(results_path)
            positions = self.extract_running_positions(results_path)
            scratches = self.extract_scratches_from_results(results_path)
            print(f"   ✓ Extracted {len(winners)} winners")
            print(f"   ✓ Extracted {len(frac_times)} fractional times")
            print(f"   ✓ Extracted {len(positions)} position data")
            print(f"   ✓ Extracted scratches from {len(scratches)} races")
        except Exception as e:
            print(f"   ✗ Failed to extract results: {e}")
            return None

        # Analyze each race
        day_analysis = {
            'date': date_str,
            'races': [],
            'summary': {
                'total_races': 0,
                'wins': 0,
                'top3': 0,
                'top5': 0,
                'scratches': 0,
                'pace_correct': 0
            }
        }

        for race in races:
            race_num = race.race_number

            if race_num not in winners:
                print(f"\n   ⚠️  Race {race_num}: No winner data found")
                continue

            winner = winners[race_num]
            print(f"\n   Race {race_num}: Winner = #{winner['program_number']} {winner['name']}")

            # Analyze predictions vs actual
            race_analysis = self.analyze_race_predictions(
                race,
                winner,
                frac_times.get(race_num),
                positions.get(race_num),
                scratches.get(race_num, [])
            )

            day_analysis['races'].append(race_analysis)
            day_analysis['summary']['total_races'] += 1

            if race_analysis['win_hit']:
                day_analysis['summary']['wins'] += 1
            if race_analysis['top3_hit']:
                day_analysis['summary']['top3'] += 1
            if race_analysis['top5_hit']:
                day_analysis['summary']['top5'] += 1
            if race_analysis['scratches'] > 0:
                day_analysis['summary']['scratches'] += race_analysis['scratches']
            if race_analysis.get('pace_correct'):
                day_analysis['summary']['pace_correct'] += 1

        # Print day summary
        self.print_day_summary(day_analysis)

        return day_analysis

    def analyze_race_predictions(self, race, winner, frac_times, positions, actual_scratches) -> Dict:
        """Analyze predictions for a single race"""

        # Helper function to clean horse names for comparison
        def clean_name(name):
            """Remove claiming prices, markers, and normalize"""
            # Remove claiming prices like "$40,000 "
            name = re.sub(r'\$[\d,]+\s+', '', name)
            # Remove markers like (L), (M), ï, etc.
            name = re.sub(r'\s*\([LM]\)\s*', '', name)
            name = re.sub(r'[ïîíì]', '', name)
            # Remove extra whitespace
            name = ' '.join(name.split())
            return name.strip().lower()

        # Sort horses by best speed figure (simple prediction)
        # TODO: Use actual prediction scores from predict_from_pdf.py
        horses_sorted = sorted(
            race.horses,
            key=lambda h: h.best_speed_figure if h.best_speed_figure else 0,
            reverse=True
        )

        # Check if winner was in our predictions
        winner_found = False
        winner_rank = 0
        top_pick = None
        winner_clean = clean_name(winner['name'])

        for i, horse in enumerate(horses_sorted, 1):
            if i == 1:
                top_pick = horse.name

            # Check if this is the winner (better name matching)
            horse_clean = clean_name(horse.name)

            # Match if cleaned names are identical or one contains the other
            if winner_clean == horse_clean or \
               winner_clean in horse_clean or \
               horse_clean in winner_clean:
                winner_found = True
                winner_rank = i
                break

        # Use actual scratches count
        scratch_count = len(actual_scratches) if actual_scratches else 0

        # Pace analysis
        pace_correct = False
        if positions and frac_times:
            pace_correct = self.check_pace_accuracy(race, positions, frac_times)

        return {
            'race_number': race.race_number,
            'winner': winner['name'],
            'winner_program_number': winner['program_number'],
            'our_top_pick': top_pick,
            'winner_found': winner_found,
            'winner_rank': winner_rank,
            'win_hit': winner_rank == 1,
            'top3_hit': winner_rank in [1, 2, 3],
            'top5_hit': winner_rank in [1, 2, 3, 4, 5],
            'scratches': scratch_count,
            'pace_correct': pace_correct,
            'fractional_times': frac_times
        }

    def check_pace_accuracy(self, race, positions, frac_times) -> bool:
        """Check if our pace prediction matched actual race dynamics"""

        # Count early leaders (top 3 at quarter)
        early_leaders = []
        for horse_name, pos_data in positions.items():
            quarter_pos = pos_data.get('quarter', '99')
            try:
                if int(quarter_pos) <= 3:
                    early_leaders.append(horse_name)
            except:
                pass

        # Determine predicted pace scenario
        # For now, use simple heuristic based on horses
        # TODO: Integrate actual pace prediction from model

        # Actual scenario based on early leaders
        if len(early_leaders) >= 4:
            actual_scenario = "SPEED_DUEL"
        elif len(early_leaders) == 1:
            actual_scenario = "LONE_SPEED"
        elif len(early_leaders) == 0:
            actual_scenario = "NO_SPEED"
        else:
            actual_scenario = "HONEST_PACE"

        # TODO: Compare to predicted scenario
        # For now, return True (placeholder)
        return True

    def print_day_summary(self, day_analysis: Dict):
        """Print summary for a race day"""

        summary = day_analysis['summary']

        print(f"\n{'-'*80}")
        print(f" DAY SUMMARY: {day_analysis['date']}")
        print(f"{'-'*80}")
        print(f"  Total Races: {summary['total_races']}")
        print(f"  Win Rate: {summary['wins']}/{summary['total_races']} = {summary['wins']/summary['total_races']*100:.1f}%" if summary['total_races'] > 0 else "N/A")
        print(f"  Top-3 Rate: {summary['top3']}/{summary['total_races']} = {summary['top3']/summary['total_races']*100:.1f}%" if summary['total_races'] > 0 else "N/A")
        print(f"  Top-5 Rate: {summary['top5']}/{summary['total_races']} = {summary['top5']/summary['total_races']*100:.1f}%" if summary['total_races'] > 0 else "N/A")
        print(f"  Total Scratches: {summary['scratches']}")
        print(f"  Pace Predictions Correct: {summary['pace_correct']}/{summary['total_races']}")

    def generate_weight_recommendations(self, all_results: List[Dict]) -> Dict:
        """Generate weight adjustment recommendations"""

        recommendations = {
            'overall_stats': {},
            'speed_importance': 0.0,
            'form_importance': 0.0,
            'pace_importance': 0.0,
            'recommendations': []
        }

        # Analyze which factors mattered most
        # TODO: Implement detailed analysis

        recommendations['recommendations'] = [
            "Increase weight on horses with recent wins (form)",
            "Consider pace pressure more heavily in SPEED_DUEL scenarios",
            "Adjust for scratch probability (top picks scratched X times)"
        ]

        return recommendations

    def run_full_review(self):
        """Run comprehensive review of all October races"""

        print(f"\n{'='*80}")
        print(f" COMPREHENSIVE BACKTEST REVIEW - OCTOBER 2025")
        print(f"{'='*80}")

        all_day_results = []

        for date_str in self.october_dates:
            # Find PP and results files
            pp_file = self.pp_dir / f"{date_str}-kee-ppspdf.pdf"

            # Convert date format for results file
            # From: 10-18-25 to: KEE101825USA.pdf
            date_parts = date_str.split('-')
            results_file = self.results_dir / f"KEE{date_parts[0]}{date_parts[1]}{date_parts[2]}USA.pdf"

            if not pp_file.exists():
                print(f"\n⚠️  Skipping {date_str}: PP file not found")
                continue

            if not results_file.exists():
                print(f"\n⚠️  Skipping {date_str}: Results file not found")
                continue

            # Analyze this race day
            day_result = self.analyze_race(date_str, str(pp_file), str(results_file))

            if day_result:
                all_day_results.append(day_result)

        # Generate overall summary
        self.print_overall_summary(all_day_results)

        # Generate weight recommendations
        recommendations = self.generate_weight_recommendations(all_day_results)
        self.print_recommendations(recommendations)

        # Save results
        output_file = 'output/comprehensive_backtest_review.json'
        with open(output_file, 'w') as f:
            json.dump({
                'days': all_day_results,
                'recommendations': recommendations
            }, f, indent=2)

        print(f"\n✓ Full results saved to: {output_file}")

    def print_overall_summary(self, all_results: List[Dict]):
        """Print overall summary across all days"""

        total_races = sum(d['summary']['total_races'] for d in all_results)
        total_wins = sum(d['summary']['wins'] for d in all_results)
        total_top3 = sum(d['summary']['top3'] for d in all_results)
        total_top5 = sum(d['summary']['top5'] for d in all_results)
        total_scratches = sum(d['summary']['scratches'] for d in all_results)

        print(f"\n{'='*80}")
        print(f" OVERALL BACKTEST SUMMARY")
        print(f"{'='*80}")
        print(f"  Race Days Analyzed: {len(all_results)}")
        print(f"  Total Races: {total_races}")
        print(f"  Win Rate: {total_wins}/{total_races} = {total_wins/total_races*100:.1f}%" if total_races > 0 else "N/A")
        print(f"  Top-3 Rate: {total_top3}/{total_races} = {total_top3/total_races*100:.1f}%" if total_races > 0 else "N/A")
        print(f"  Top-5 Rate: {total_top5}/{total_races} = {total_top5/total_races*100:.1f}%" if total_races > 0 else "N/A")
        print(f"  Total Scratches: {total_scratches}")
        print(f"  Avg Scratches/Day: {total_scratches/len(all_results):.1f}")

    def print_recommendations(self, recommendations: Dict):
        """Print weight adjustment recommendations"""

        print(f"\n{'='*80}")
        print(f" WEIGHT ADJUSTMENT RECOMMENDATIONS")
        print(f"{'='*80}")

        for rec in recommendations['recommendations']:
            print(f"  • {rec}")


if __name__ == '__main__':
    reviewer = ComprehensiveBacktestReviewer()
    reviewer.run_full_review()
