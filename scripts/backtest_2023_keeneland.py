#!/usr/bin/env python3
"""
2023 Keeneland Validation Backtest

Tests the production prediction model on historical 2023 Keeneland data
to validate that the model generalizes beyond October 2025 data.

IMPORTANT: This script does NOT modify the production PDF parser or scoring system.
It creates a separate validation instance using XML parsers for 2023 data only.

Scope: October 2023 Keeneland fall meet (~88 races across 9 dates)
"""

import sys
import os
import json
from pathlib import Path
from typing import List, Dict, Tuple
from datetime import datetime

# Add src to path
sys.path.insert(0, 'src')

# Import XML parsers (separate from production PDF parser)
from parsers.simd_xml_parser import SIMDXMLParser
from parsers.tch_xml_parser import parse_tch_file, RaceResult

# Import scoring/analysis components (same as production)
from data_loaders.statistics_loader import StatisticsLoader
from analyzers.fts_analyzer import FTSAnalyzer
from analyzers.pace_analyzer import PaceAnalyzer
from analyzers import racing_statistics as stats
from betting.probability_calibrator import ProbabilityCalibrator

# Import enhanced analyzers
from analyzers.jockey_trainer_analyzer import JockeyTrainerAnalyzer
from analyzers.distance_surface_analyzer import DistanceSurfaceAnalyzer
from analyzers.equipment_analyzer import EquipmentAnalyzer
from analyzers.trip_notes_analyzer import TripNotesAnalyzer
from analyzers.workout_analyzer import WorkoutAnalyzer
from analyzers.trainer_pattern_detector import TrainerPatternDetector
from analyzers.track_bias_detector import TrackBiasDetector


# October 2023 Keeneland dates to backtest (all dates with both SIMD and TCH files)
BACKTEST_DATES = [
    ('20231007', 'kee20231007tch.xml'),
    ('20231008', 'kee20231008tch.xml'),
    ('20231011', 'kee20231011tch.xml'),
    ('20231014', 'kee20231014tch.xml'),
    ('20231015', 'kee20231015tch.xml'),
    ('20231020', 'kee20231020tch.xml'),
    ('20231022', 'kee20231022tch.xml'),
    ('20231026', 'kee20231026tch.xml'),
    ('20231027', 'kee20231027tch.xml'),
]


class Backtest2023:
    """2023 Keeneland backtest validation"""

    def __init__(self, weights_file='config/optimized_weights.json'):
        """Initialize backtest with optimized weights"""

        # Load weights (from October 2025 optimization)
        with open(weights_file, 'r') as f:
            self.weights = json.load(f)

        # Initialize scoring components (same as production)
        self.stats_loader = StatisticsLoader(
            jockey_file='data/stats/jockey_statistics_comprehensive.json',
            trainer_file='data/stats/trainer_statistics_comprehensive.json'
        )
        self.fts_analyzer = FTSAnalyzer(
            trainer_stats_file='data/stats/fts_trainer_statistics.json',
            sire_stats_file='data/stats/fts_sire_statistics.json'
        )
        self.pace_analyzer = PaceAnalyzer()
        self.track_bias_detector = TrackBiasDetector()
        self.jockey_trainer_analyzer = JockeyTrainerAnalyzer()
        self.distance_surface_analyzer = DistanceSurfaceAnalyzer()
        self.equipment_analyzer = EquipmentAnalyzer()
        self.trip_notes_analyzer = TripNotesAnalyzer()
        self.workout_analyzer = WorkoutAnalyzer()
        self.trainer_pattern_detector = TrainerPatternDetector()

        # Initialize XML parser (separate from PDF parser)
        self.simd_parser = SIMDXMLParser(debug=False)

        # Results storage
        self.all_predictions = []
        self.all_results = []
        self.comparisons = []

    def score_horse(self, horse, race_data):
        """
        Score a single horse using production scoring system

        This is adapted from predict_from_pdf.py but uses XML data
        """
        # Get jockey/trainer stats
        jockey_stats = self.stats_loader.get_jockey_stats(horse.jockey_name)
        trainer_stats = self.stats_loader.get_trainer_stats(horse.trainer_name)

        # Parse ML odds to decimal
        ml_odds = horse.morning_line_odds
        try:
            if '-' in ml_odds:
                num, den = ml_odds.split('-')
                decimal_odds = (float(num) / float(den)) + 1.0
            elif '/' in ml_odds:
                num, den = ml_odds.split('/')
                decimal_odds = (float(num) / float(den)) + 1.0
            else:
                decimal_odds = float(ml_odds)
        except:
            decimal_odds = 6.0  # Default

        # Extract recent finishes from past performances
        recent_finishes = []
        if horse.past_performances:
            recent_finishes = [pp['finish'] for pp in horse.past_performances[:5] if 'finish' in pp]

        # Parse program number to integer for post position
        try:
            post_position = int(horse.program_number)
        except (ValueError, TypeError):
            post_position = 5  # Default middle post

        # Calculate days since last race
        days_since_last = 999  # Default
        if horse.last_race_date and race_data.get('date'):
            try:
                race_date = datetime.strptime(race_data['date'], '%Y-%m-%d')
                last_race = datetime.strptime(horse.last_race_date, '%Y-%m-%d')
                days_since_last = (race_date - last_race).days
            except:
                pass  # Keep default

        # Build horse data dict (same format as production)
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
            'is_fts': horse.career_starts == 0,
            'fts_advantage': 0.0,
        }

        # FTS multiplier
        if horse_data['is_fts']:
            fts_multiplier, _ = self.fts_analyzer.calculate_fts_multiplier(
                trainer_name=horse.trainer_name,
                sire_name=horse.sire_name
            )
            horse_data['fts_advantage'] = fts_multiplier - 1.0

        # Calculate component scores
        score = stats.calculate_comprehensive_score(horse_data, race_data)

        # Calculate bonuses (same as production)
        jt_bonus = 0.0
        if horse.jockey_name and horse.trainer_name:
            jockey_rate = jockey_stats.win_percentage / 100.0 if jockey_stats else 0.0
            trainer_rate = trainer_stats.win_percentage / 100.0 if trainer_stats else 0.0
            jt_bonus, _, _ = self.jockey_trainer_analyzer.analyze_combination(
                horse.jockey_name,
                horse.trainer_name,
                jockey_rate,
                trainer_rate
            )

        # Distance/surface bonus
        ds_bonus = 0.0
        try:
            ds_bonus, _ = self.distance_surface_analyzer.analyze_horse(
                horse,
                race_data.get('distance', '6f'),
                race_data['surface']
            )
        except:
            ds_bonus = 0.0

        # Equipment bonus
        equip_bonus = 0.0
        try:
            today_equip = getattr(horse, 'today_equipment', {'blinkers': False, 'lasix': False})
            pps = getattr(horse, 'past_performances', [])
            equip_bonus, _ = self.equipment_analyzer.analyze_horse(
                horse.name,
                today_equip,
                pps
            )
        except:
            equip_bonus = 0.0

        # Trip notes bonus
        trip_bonus = 0.0
        try:
            pps = getattr(horse, 'past_performances', [])
            trip_bonus, _, _ = self.trip_notes_analyzer.analyze_horse(
                horse.name,
                pps
            )
        except:
            trip_bonus = 0.0

        # Workout bonus
        workout_bonus = 0.0
        try:
            race_date = datetime.strptime(race_data['date'], '%Y-%m-%d') if isinstance(race_data['date'], str) else race_data['date']
            workout_bonus, _ = self.workout_analyzer.analyze_horse(
                horse,
                race_date,
                pdf_path=None
            )
        except:
            workout_bonus = 0.0

        # Trainer pattern bonus
        trainer_bonus = 0.0
        try:
            trainer_bonus, _ = self.trainer_pattern_detector.analyze_horse(
                horse,
                race_data.get('distance', '6f'),
                race_data['surface']
            )
        except:
            trainer_bonus = 0.0

        # Apply track bias adjustments
        surface = race_data['surface'].lower()
        distance_class = 'sprint' if race_data.get('distance_furlongs', 8.5) < 8 else 'mile' if race_data.get('distance_furlongs', 8.5) <= 9 else 'route'

        adjusted_post_score = self.track_bias_detector.apply_post_bias_adjustment(
            score.post,
            post_position,
            surface,
            distance_class
        )

        adjusted_pace_score = self.track_bias_detector.apply_pace_bias_adjustment(
            score.pace,
            horse.running_style,
            surface
        )

        # Calculate final score with optimized weights (October 2025 optimization)
        final_score = (
            score.speed * self.weights.get('speed', 0.2292) +
            score.form * self.weights.get('form', 0.1458) +
            score.class_rating * self.weights.get('class', 0.1250) +
            adjusted_pace_score * self.weights.get('pace', 0.1042) +
            score.recency * self.weights.get('recency', 0.0833) +
            score.progression * self.weights.get('progression', 0.0938) +
            score.jockey * self.weights.get('jockey', 0.0625) +
            score.trainer * self.weights.get('trainer', 0.0625) +
            adjusted_post_score * self.weights.get('post', 0.0521) +
            jt_bonus * self.weights.get('jt_combo_scale', 1.0) +
            ds_bonus * self.weights.get('distance_surface_scale', 1.0) +
            equip_bonus * self.weights.get('equipment_scale', 1.0) +
            trip_bonus * self.weights.get('trip_notes_scale', 1.0) +
            workout_bonus * self.weights.get('workout_scale', 1.0) +
            trainer_bonus * self.weights.get('trainer_pattern_scale', 1.0)
        )

        return {
            'program_number': horse.program_number,
            'horse_name': horse.name,
            'name': horse.name,
            'jockey_name': horse.jockey_name,
            'trainer_name': horse.trainer_name,
            'ml_odds': decimal_odds,
            'best_beyer': horse.best_speed_figure,
            'running_style': horse.running_style,
            'score': final_score,
            'speed_score': score.speed,
            'form_score': score.form,
            'class_score': score.class_rating,
            'pace_score': score.pace,
            'jockey_score': score.jockey,
            'trainer_score': score.trainer,
            'post_score': score.post,
            'jt_combo_bonus': jt_bonus,
            'ds_bonus': ds_bonus,
            'equip_bonus': equip_bonus,
            'trip_bonus': trip_bonus,
            'workout_bonus': workout_bonus,
            'trainer_bonus': trainer_bonus,
        }

    def predict_race(self, race):
        """Generate predictions for a race using production scoring system"""

        # Build race data dict
        race_data = {
            'date': race.date,
            'distance': race.distance_text,
            'distance_furlongs': race.distance / 100.0,  # Convert from 850 to 8.5
            'surface': race.surface_description.lower(),
            'track_condition': race.track_condition,
            'purse': race.purse if race.purse > 0 else 50000,
            'field_size': len(race.horses),
            'avg_beyer': 70,
        }

        # Analyze pace scenario
        horse_pace_data = [{'running_style': h.running_style, 'name': h.name} for h in race.horses]
        pace_scenario = self.pace_analyzer.analyze_pace(horse_pace_data, race_data['distance_furlongs'])
        race_data['pace_scenario'] = pace_scenario.scenario_type

        # Score each horse
        predictions = []
        for horse in race.horses:
            pred = self.score_horse(horse, race_data)
            predictions.append(pred)

        # Sort by score
        predictions.sort(key=lambda x: x['score'], reverse=True)

        # Add ranks
        for i, pred in enumerate(predictions, 1):
            pred['rank'] = i

        # Calibrate probabilities
        calibrator = ProbabilityCalibrator()
        predictions = calibrator.calibrate_race_probabilities(predictions)

        return predictions, pace_scenario.scenario_type

    def compare_prediction_to_result(self, prediction_list, result):
        """Compare predictions to actual race result"""

        # Find winner in predictions
        winner_pgm = result.winner_program_number
        winner_name = result.winner_name

        predicted_winner = prediction_list[0] if prediction_list else None
        predicted_winner_pgm = predicted_winner['program_number'] if predicted_winner else None
        predicted_winner_name = predicted_winner['horse_name'] if predicted_winner else 'Unknown'

        # Find where actual winner ranked in our predictions
        winner_rank = None
        winner_prob = 0.0
        for pred in prediction_list:
            if pred['program_number'] == winner_pgm:
                winner_rank = pred['rank']
                winner_prob = pred.get('probability', 0.0)
                break

        # Calculate hits
        win_hit = (predicted_winner_pgm == winner_pgm)
        top_3_hit = winner_rank is not None and winner_rank <= 3
        top_5_hit = winner_rank is not None and winner_rank <= 5

        return {
            'race_number': result.race_number,
            'winner_pgm': winner_pgm,
            'winner_name': winner_name,
            'predicted_winner_pgm': predicted_winner_pgm,
            'predicted_winner_name': predicted_winner_name,
            'winner_rank': winner_rank if winner_rank else 99,
            'winner_probability': winner_prob,
            'win_hit': win_hit,
            'top_3_hit': top_3_hit,
            'top_5_hit': top_5_hit,
            'field_size': len(prediction_list),
            'top_5_picks': prediction_list[:5],
        }

    def run_backtest_date(self, simd_file, tch_file, date_str):
        """Run backtest for a single date"""

        print(f"\n{'='*80}")
        print(f" BACKTESTING {date_str}")
        print(f"{'='*80}")

        # Parse SIMD file (past performances)
        print(f"📊 Parsing past performances: {simd_file}")
        pp_races = self.simd_parser.parse_xml_file(simd_file)
        print(f"   ✓ Parsed {len(pp_races)} races")

        # Parse TCH file (results)
        print(f"🏆 Parsing race results: {tch_file}")
        result_races = parse_tch_file(tch_file)
        print(f"   ✓ Parsed {len(result_races)} race results")

        # Validate counts match
        if len(pp_races) != len(result_races):
            print(f"⚠️  Race count mismatch: {len(pp_races)} PP races vs {len(result_races)} result races")
            print("   Continuing with available races...")

        # Process each race
        date_comparisons = []

        for i, (pp_race, result_race) in enumerate(zip(pp_races, result_races), 1):
            print(f"\n  Race {i}/{len(pp_races)}: {len(pp_race.horses)} horses")

            # Generate predictions
            predictions, pace_scenario = self.predict_race(pp_race)

            # Compare to actual result
            comparison = self.compare_prediction_to_result(predictions, result_race)
            comparison['date'] = date_str
            comparison['pace_scenario'] = pace_scenario

            date_comparisons.append(comparison)

            # Quick status
            if comparison['win_hit']:
                print(f"     ✅ WIN! Predicted #{comparison['predicted_winner_pgm']} {comparison['predicted_winner_name']}")
            elif comparison['top_3_hit']:
                print(f"     △ Top-3: Winner #{comparison['winner_pgm']} was our #{comparison['winner_rank']} pick")
            else:
                print(f"     ✗ Miss: Winner #{comparison['winner_pgm']} {comparison['winner_name']} was our #{comparison['winner_rank']} pick")

        self.comparisons.extend(date_comparisons)

        # Date summary
        wins = sum(1 for c in date_comparisons if c['win_hit'])
        top3 = sum(1 for c in date_comparisons if c['top_3_hit'])
        top5 = sum(1 for c in date_comparisons if c['top_5_hit'])

        print(f"\n  📊 {date_str} Summary:")
        print(f"     Win Rate: {wins}/{len(date_comparisons)} = {wins/len(date_comparisons)*100:.1f}%")
        print(f"     Top-3 Rate: {top3}/{len(date_comparisons)} = {top3/len(date_comparisons)*100:.1f}%")
        print(f"     Top-5 Rate: {top5}/{len(date_comparisons)} = {top5/len(date_comparisons)*100:.1f}%")

        return date_comparisons

    def run_full_backtest(self):
        """Run backtest on all October 2023 Keeneland dates"""

        print("\n" + "="*80)
        print(" 2023 KEENELAND VALIDATION BACKTEST")
        print("="*80)
        print(f"\nWeights: {os.path.basename(self.weights.__repr__())}")
        print(f"Dates: {len(BACKTEST_DATES)}")
        print()

        for date, tch_filename in BACKTEST_DATES:
            simd_file = f'equibase 2023 data/2023 PPs/SIMD{date}KEE_USA.xml'
            tch_file = f'equibase 2023 data/2023 Result Charts/{tch_filename}'

            # Check files exist
            if not Path(simd_file).exists():
                print(f"⚠️  SIMD file not found: {simd_file}")
                continue
            if not Path(tch_file).exists():
                print(f"⚠️  TCH file not found: {tch_file}")
                continue

            # Run backtest for this date
            self.run_backtest_date(simd_file, tch_file, date)

        # Overall summary
        self.print_summary()

        # Save results
        self.save_results()

    def print_summary(self):
        """Print overall backtest summary"""

        if not self.comparisons:
            print("\n⚠️  No comparisons to summarize")
            return

        total = len(self.comparisons)
        wins = sum(1 for c in self.comparisons if c['win_hit'])
        top3 = sum(1 for c in self.comparisons if c['top_3_hit'])
        top5 = sum(1 for c in self.comparisons if c['top_5_hit'])
        avg_winner_rank = sum(c['winner_rank'] for c in self.comparisons) / total

        print("\n" + "="*80)
        print(" BACKTEST RESULTS - 2023 KEENELAND VALIDATION")
        print("="*80)
        print(f"\nTotal Races: {total}")
        print(f"Dates Tested: {len(BACKTEST_DATES)}")
        print()
        print(f"Performance:")
        print(f"  Win Rate:     {wins}/{total} = {wins/total*100:.1f}%")
        print(f"  Top-3 Rate:   {top3}/{total} = {top3/total*100:.1f}%")
        print(f"  Top-5 Rate:   {top5}/{total} = {top5/total*100:.1f}%")
        print(f"  Avg Winner Rank: {avg_winner_rank:.1f}")
        print()

        # Compare to October 2025 results
        print("Comparison to October 2025 Validation:")
        print("  Oct 2025: 28.1% win rate, 73.4% top-3 rate")
        print(f"  2023:     {wins/total*100:.1f}% win rate, {top3/total*100:.1f}% top-3 rate")

        if top3/total >= 0.70:
            print("\n✅ VALIDATION SUCCESSFUL!")
            print("   Model generalizes well to 2023 data (70%+ top-3 hit rate)")
        elif top3/total >= 0.60:
            print("\n⚠️  VALIDATION MODERATE")
            print("   Model shows some generalization (60-70% top-3 hit rate)")
            print("   May benefit from weight adjustment on larger dataset")
        else:
            print("\n❌ VALIDATION NEEDS IMPROVEMENT")
            print("   Model may need re-training on 2023 data")
            print("   Consider re-optimizing weights on larger dataset")

        print("="*80)

    def save_results(self):
        """Save backtest results to JSON file"""

        # Calculate summary stats
        total = len(self.comparisons)
        wins = sum(1 for c in self.comparisons if c['win_hit'])
        top3 = sum(1 for c in self.comparisons if c['top_3_hit'])
        top5 = sum(1 for c in self.comparisons if c['top_5_hit'])

        report = {
            'backtest_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'scope': 'October 2023 Keeneland',
            'dates_tested': len(BACKTEST_DATES),
            'total_races': total,
            'weights_used': self.weights,
            'summary': {
                'win_rate': f"{wins}/{total} = {wins/total*100:.1f}%",
                'top_3_rate': f"{top3}/{total} = {top3/total*100:.1f}%",
                'top_5_rate': f"{top5}/{total} = {top5/total*100:.1f}%",
                'avg_winner_rank': sum(c['winner_rank'] for c in self.comparisons) / total,
            },
            'detailed_results': self.comparisons
        }

        # Save to file
        output_dir = Path('output')
        output_dir.mkdir(exist_ok=True)

        output_file = output_dir / '2023_keeneland_validation_report.json'
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)

        print(f"\n✓ Results saved to: {output_file}")


def main():
    """Main entry point"""

    # Check for weights file
    weights_file = 'config/optimized_weights.json'
    if not Path(weights_file).exists():
        print(f"❌ Weights file not found: {weights_file}")
        print("   Please ensure optimized weights exist before running backtest")
        return 1

    # Run backtest
    backtest = Backtest2023(weights_file=weights_file)
    backtest.run_full_backtest()

    return 0


if __name__ == '__main__':
    sys.exit(main())
