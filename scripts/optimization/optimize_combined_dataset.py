#!/usr/bin/env python3
"""
Combined Dataset Weight Optimizer (2023 + 2025 Keeneland)

Optimizes model weights on combined dataset of:
- 86 races from October 2023 Keeneland (XML format)
- 64 races from October 2025 Keeneland (PDF format)
Total: 150 races for robust weight optimization

Multi-objective optimization targeting:
- Win rate
- Exotic wager ROI (exacta, trifecta)
- Top-3 hit rate

Uses train/validation split to prevent overfitting.
"""

import sys
sys.path.insert(0, 'src')
sys.path.insert(0, '.')
sys.path.insert(0, 'scripts')

import json
import numpy as np
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime
from scipy.optimize import differential_evolution
from sklearn.model_selection import train_test_split

# Import the existing backtest infrastructure
from backtest_2023_keeneland import Keeneland2023Backtester

# Results validator for 2025 data
from results_validator import ResultsValidator


@dataclass
class CombinedRaceData:
    """Unified race data structure for both XML and PDF sources"""
    date: str
    race_number: int
    track_code: str
    distance: str
    surface: str

    # Parsed race object (from either XML or PDF parser)
    race_obj: any

    # Actual results
    winner_program_number: str
    winner_name: str
    all_finishers: List[Tuple[str, str]]  # (program_number, name) in finish order

    # Exotic payoffs (if available)
    exacta_payoff: Optional[float] = None
    trifecta_payoff: Optional[float] = None
    superfecta_payoff: Optional[float] = None

    # Source metadata
    source: str = "xml"  # "xml" or "pdf"


class CombinedDatasetLoader:
    """Loads and combines 2023 XML data with 2025 PDF data"""

    # October 2023 dates (XML)
    XML_DATES = [
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

    # October 2025 dates (PDF)
    PDF_DATES = [
        '10-03-25',
        '10-10-25',
        '10-11-25',
        '10-12-25',
        '10-18-25',
        '10-19-25',
        '10-20-25',
        '10-25-25',
    ]

    def __init__(self):
        self.simd_parser = SIMDXMLParser(debug=False)
        self.results_validator = ResultsValidator(results_dir='data/Results Files')

    def load_xml_races(self) -> List[CombinedRaceData]:
        """Load all 2023 XML races"""
        print("\n" + "="*80)
        print(" LOADING 2023 KEENELAND DATA (XML)")
        print("="*80)

        all_races = []

        for date, tch_filename in self.XML_DATES:
            simd_file = f'equibase 2023 data/2023 PPs/SIMD{date}KEE_USA.xml'
            tch_file = f'equibase 2023 data/2023 Result Charts/{tch_filename}'

            try:
                # Parse past performances
                pp_races = self.simd_parser.parse_xml_file(simd_file)

                # Parse results
                result_races = parse_tch_file(tch_file)

                # Match and combine
                for pp_race, result_race in zip(pp_races, result_races):
                    # Get exacta/trifecta payoffs
                    exacta_payoff = None
                    trifecta_payoff = None
                    superfecta_payoff = None

                    for wager in result_race.exotic_wagers:
                        if wager.wager_type.lower() == 'exacta':
                            exacta_payoff = wager.payoff
                        elif wager.wager_type.lower() == 'trifecta':
                            trifecta_payoff = wager.payoff
                        elif wager.wager_type.lower() == 'superfecta':
                            superfecta_payoff = wager.payoff

                    # Get all finishers in order
                    finishers = sorted(
                        [(h.program_number, h.name) for h in result_race.horses],
                        key=lambda x: next((h.official_finish for h in result_race.horses if h.program_number == x[0]), 999)
                    )

                    combined = CombinedRaceData(
                        date=date,
                        race_number=pp_race.race_number,
                        track_code=pp_race.track_code,
                        distance=pp_race.distance,
                        surface=pp_race.surface,
                        race_obj=pp_race,
                        winner_program_number=result_race.winner_program_number,
                        winner_name=result_race.winner_name,
                        all_finishers=finishers,
                        exacta_payoff=exacta_payoff,
                        trifecta_payoff=trifecta_payoff,
                        superfecta_payoff=superfecta_payoff,
                        source="xml"
                    )
                    all_races.append(combined)

                print(f"  ✓ {date}: {len(pp_races)} races")

            except Exception as e:
                print(f"  ✗ {date}: Error - {str(e)}")

        print(f"\n✓ Loaded {len(all_races)} races from 2023 XML data")
        return all_races

    def load_pdf_races(self) -> List[CombinedRaceData]:
        """Load all 2025 PDF races"""
        print("\n" + "="*80)
        print(" LOADING 2025 KEENELAND DATA (PDF)")
        print("="*80)

        all_races = []

        for date_str in self.PDF_DATES:
            pdf_file = f'Keeneland October PPs/{date_str}-kee-ppspdf.pdf'

            # Convert date format for results file
            month, day, year = date_str.split('-')
            results_date = f'{month.upper()}{day}{year}'  # e.g., '10-18-25' -> 'KEE101825USA.pdf'
            results_file = f'data/Results Files/KEE{month}{day}{year}USA.pdf'

            try:
                # Parse PDF
                pdf_races = parse_pdf_hybrid_v3(pdf_file, debug=False)

                # Parse results
                result_races = self.results_validator.parse_results_pdf(results_file)

                # Match and combine
                for pdf_race in pdf_races:
                    # Find matching result
                    result_race = next(
                        (r for r in result_races if r.race_number == pdf_race.race_number),
                        None
                    )

                    if result_race:
                        # Get all finishers (results don't have exotic payoffs in our current parser)
                        finishers = [(result_race.winner_pgm, result_race.winner_name)]

                        combined = CombinedRaceData(
                            date=date_str,
                            race_number=pdf_race.race_number,
                            track_code='KEE',
                            distance=pdf_race.distance,
                            surface=pdf_race.surface,
                            race_obj=pdf_race,
                            winner_program_number=result_race.winner_pgm,
                            winner_name=result_race.winner_name,
                            all_finishers=finishers,
                            source="pdf"
                        )
                        all_races.append(combined)

                print(f"  ✓ {date_str}: {len(pdf_races)} races")

            except Exception as e:
                print(f"  ✗ {date_str}: Error - {str(e)}")

        print(f"\n✓ Loaded {len(all_races)} races from 2025 PDF data")
        return all_races

    def load_all(self) -> List[CombinedRaceData]:
        """Load and combine all races"""
        xml_races = self.load_xml_races()
        pdf_races = self.load_pdf_races()

        all_races = xml_races + pdf_races

        print("\n" + "="*80)
        print(" COMBINED DATASET")
        print("="*80)
        print(f"  2023 XML races: {len(xml_races)}")
        print(f"  2025 PDF races: {len(pdf_races)}")
        print(f"  Total races:    {len(all_races)}")
        print("="*80)

        return all_races


class CombinedDatasetOptimizer:
    """Optimizes weights on combined 2023+2025 dataset"""

    def __init__(self, races: List[CombinedRaceData], train_split: float = 0.7):
        self.all_races = races
        self.train_split = train_split

        # Split into train and validation
        self.train_races, self.val_races = train_test_split(
            races,
            train_size=train_split,
            random_state=42
        )

        print(f"\nDataset split:")
        print(f"  Training:   {len(self.train_races)} races ({train_split*100:.0f}%)")
        print(f"  Validation: {len(self.val_races)} races ({(1-train_split)*100:.0f}%)")

        # Initialize predictor
        self.predictor = HorseRacingPredictor()

        # Load baseline weights
        with open('config/optimized_weights.json', 'r') as f:
            self.baseline_weights = json.load(f)

    def evaluate_weights(self, weights_array: np.ndarray, dataset: List[CombinedRaceData]) -> Dict[str, float]:
        """Evaluate weights on a dataset"""

        # Convert array to weights dict
        weights = {
            'speed': weights_array[0],
            'form': weights_array[1],
            'class_rating': weights_array[2],
            'pace': weights_array[3],
            'recency': weights_array[4],
            'progression': weights_array[5],
            'jockey': weights_array[6],
            'trainer': weights_array[7],
            'post': weights_array[8],
            'jt_combo_scale': weights_array[9],
            'distance_surface_scale': weights_array[10],
            'equipment_scale': weights_array[11],
            'trip_notes_scale': weights_array[12],
            'workout_scale': weights_array[13],
            'trainer_pattern_scale': weights_array[14],
        }

        # Set weights in predictor
        self.predictor.config.update(weights)

        # Evaluate on dataset
        wins = 0
        top3 = 0
        top5 = 0
        exacta_hits = 0
        trifecta_hits = 0
        total_races = len(dataset)

        for race_data in dataset:
            # Generate predictions
            if race_data.source == "xml":
                # For XML data, use the race object directly
                predictions = self.predictor.predict_race(race_data.race_obj)
            else:
                # For PDF data, use the race object
                predictions = self.predictor.predict_race(race_data.race_obj)

            if not predictions:
                continue

            # Sort by probability
            predictions.sort(key=lambda x: x['probability'], reverse=True)

            # Check win
            if predictions[0]['program_number'] == race_data.winner_program_number:
                wins += 1

            # Check top-3
            top3_picks = [p['program_number'] for p in predictions[:3]]
            if race_data.winner_program_number in top3_picks:
                top3 += 1

            # Check top-5
            top5_picks = [p['program_number'] for p in predictions[:5]]
            if race_data.winner_program_number in top5_picks:
                top5 += 1

            # Check exacta (if we have finish order)
            if len(race_data.all_finishers) >= 2 and len(predictions) >= 2:
                our_exacta = (predictions[0]['program_number'], predictions[1]['program_number'])
                actual_exacta = (race_data.all_finishers[0][0], race_data.all_finishers[1][0])
                if our_exacta == actual_exacta:
                    exacta_hits += 1

            # Check trifecta (if we have finish order)
            if len(race_data.all_finishers) >= 3 and len(predictions) >= 3:
                our_trifecta = tuple(p['program_number'] for p in predictions[:3])
                actual_trifecta = tuple(f[0] for f in race_data.all_finishers[:3])
                if our_trifecta == actual_trifecta:
                    trifecta_hits += 1

        return {
            'win_rate': wins / total_races if total_races > 0 else 0,
            'top3_rate': top3 / total_races if total_races > 0 else 0,
            'top5_rate': top5 / total_races if total_races > 0 else 0,
            'exacta_rate': exacta_hits / total_races if total_races > 0 else 0,
            'trifecta_rate': trifecta_hits / total_races if total_races > 0 else 0,
        }

    def objective_function(self, weights_array: np.ndarray) -> float:
        """
        Multi-objective function combining:
        - Win rate (40% weight)
        - Top-3 rate (40% weight)
        - Exacta hit rate (20% weight)

        Lower is better for differential_evolution (so we negate)
        """
        # Evaluate on training set
        metrics = self.evaluate_weights(weights_array, self.train_races)

        # Combine metrics (user wants: win rate + exotic ROI + top-3 rate)
        # Since we don't have exotic payoffs for all races, use exacta hit rate as proxy for exotic ROI
        combined_score = (
            0.40 * metrics['win_rate'] +
            0.40 * metrics['top3_rate'] +
            0.20 * metrics['exacta_rate']
        )

        # Return negative (differential_evolution minimizes)
        return -combined_score

    def optimize(self, max_iterations: int = 100) -> Dict:
        """Run optimization"""

        print("\n" + "="*80)
        print(" RUNNING BAYESIAN OPTIMIZATION")
        print("="*80)
        print(f"  Max iterations: {max_iterations}")
        print(f"  Training races: {len(self.train_races)}")
        print(f"  Validation races: {len(self.val_races)}")
        print()
        print("  Objective: 40% Win + 40% Top-3 + 20% Exacta")
        print("="*80)

        # Define bounds for each weight
        # Component weights: [0.01, 0.40]
        # Bonus scales: [0.2, 2.5]
        bounds = [
            (0.01, 0.40),  # speed
            (0.01, 0.40),  # form
            (0.01, 0.40),  # class_rating
            (0.01, 0.40),  # pace
            (0.01, 0.40),  # recency
            (0.01, 0.40),  # progression
            (0.01, 0.40),  # jockey
            (0.01, 0.40),  # trainer
            (0.01, 0.40),  # post
            (0.2, 2.5),    # jt_combo_scale
            (0.2, 2.5),    # distance_surface_scale
            (0.2, 2.5),    # equipment_scale
            (0.2, 2.5),    # trip_notes_scale
            (0.2, 2.5),    # workout_scale
            (0.2, 2.5),    # trainer_pattern_scale
        ]

        # Run optimization
        result = differential_evolution(
            self.objective_function,
            bounds=bounds,
            maxiter=max_iterations,
            popsize=15,
            seed=42,
            workers=1,
            updating='deferred',
            disp=True
        )

        # Extract best weights
        best_weights_array = result.x
        best_weights = {
            'speed': float(best_weights_array[0]),
            'form': float(best_weights_array[1]),
            'class_rating': float(best_weights_array[2]),
            'pace': float(best_weights_array[3]),
            'recency': float(best_weights_array[4]),
            'progression': float(best_weights_array[5]),
            'jockey': float(best_weights_array[6]),
            'trainer': float(best_weights_array[7]),
            'post': float(best_weights_array[8]),
            'jt_combo_scale': float(best_weights_array[9]),
            'distance_surface_scale': float(best_weights_array[10]),
            'equipment_scale': float(best_weights_array[11]),
            'trip_notes_scale': float(best_weights_array[12]),
            'workout_scale': float(best_weights_array[13]),
            'trainer_pattern_scale': float(best_weights_array[14]),
        }

        # Evaluate on train and validation
        print("\n" + "="*80)
        print(" FINAL EVALUATION")
        print("="*80)

        train_metrics = self.evaluate_weights(best_weights_array, self.train_races)
        val_metrics = self.evaluate_weights(best_weights_array, self.val_races)

        print("\nTRAINING SET PERFORMANCE:")
        print(f"  Win Rate:     {train_metrics['win_rate']*100:.1f}%")
        print(f"  Top-3 Rate:   {train_metrics['top3_rate']*100:.1f}%")
        print(f"  Top-5 Rate:   {train_metrics['top5_rate']*100:.1f}%")
        print(f"  Exacta Rate:  {train_metrics['exacta_rate']*100:.1f}%")
        print(f"  Trifecta Rate: {train_metrics['trifecta_rate']*100:.1f}%")

        print("\nVALIDATION SET PERFORMANCE:")
        print(f"  Win Rate:     {val_metrics['win_rate']*100:.1f}%")
        print(f"  Top-3 Rate:   {val_metrics['top3_rate']*100:.1f}%")
        print(f"  Top-5 Rate:   {val_metrics['top5_rate']*100:.1f}%")
        print(f"  Exacta Rate:  {val_metrics['exacta_rate']*100:.1f}%")
        print(f"  Trifecta Rate: {val_metrics['trifecta_rate']*100:.1f}%")

        # Compare to baseline
        print("\n" + "="*80)
        print(" COMPARISON TO BASELINE WEIGHTS")
        print("="*80)

        baseline_array = np.array([
            self.baseline_weights['speed'],
            self.baseline_weights['form'],
            self.baseline_weights.get('class_rating', self.baseline_weights.get('class', 0.2)),
            self.baseline_weights['pace'],
            self.baseline_weights['recency'],
            self.baseline_weights['progression'],
            self.baseline_weights['jockey'],
            self.baseline_weights['trainer'],
            self.baseline_weights['post'],
            self.baseline_weights['jt_combo_scale'],
            self.baseline_weights['distance_surface_scale'],
            self.baseline_weights['equipment_scale'],
            self.baseline_weights['trip_notes_scale'],
            self.baseline_weights['workout_scale'],
            self.baseline_weights['trainer_pattern_scale'],
        ])

        baseline_train = self.evaluate_weights(baseline_array, self.train_races)
        baseline_val = self.evaluate_weights(baseline_array, self.val_races)

        print("\nBASELINE (Oct 2025 optimized weights):")
        print(f"  Training:   Win {baseline_train['win_rate']*100:.1f}%, Top-3 {baseline_train['top3_rate']*100:.1f}%")
        print(f"  Validation: Win {baseline_val['win_rate']*100:.1f}%, Top-3 {baseline_val['top3_rate']*100:.1f}%")

        print("\nNEW WEIGHTS (2023+2025 combined):")
        print(f"  Training:   Win {train_metrics['win_rate']*100:.1f}%, Top-3 {train_metrics['top3_rate']*100:.1f}%")
        print(f"  Validation: Win {val_metrics['win_rate']*100:.1f}%, Top-3 {val_metrics['top3_rate']*100:.1f}%")

        print("\nIMPROVEMENT:")
        print(f"  Training:   Win {(train_metrics['win_rate'] - baseline_train['win_rate'])*100:+.1f}%, Top-3 {(train_metrics['top3_rate'] - baseline_train['top3_rate'])*100:+.1f}%")
        print(f"  Validation: Win {(val_metrics['win_rate'] - baseline_val['win_rate'])*100:+.1f}%, Top-3 {(val_metrics['top3_rate'] - baseline_val['top3_rate'])*100:+.1f}%")

        print("="*80)

        return {
            'best_weights': best_weights,
            'train_metrics': train_metrics,
            'val_metrics': val_metrics,
            'baseline_train': baseline_train,
            'baseline_val': baseline_val,
        }


def main():
    print("\n" + "="*80)
    print(" COMBINED DATASET WEIGHT OPTIMIZER")
    print(" 2023 Keeneland (XML) + 2025 Keeneland (PDF)")
    print("="*80)

    # Load all races
    loader = CombinedDatasetLoader()
    all_races = loader.load_all()

    if len(all_races) < 100:
        print(f"\n⚠️  Warning: Only {len(all_races)} races loaded. Expected ~150.")
        print("Proceeding anyway...")

    # Initialize optimizer
    optimizer = CombinedDatasetOptimizer(all_races, train_split=0.7)

    # Run optimization
    results = optimizer.optimize(max_iterations=100)

    # Save new weights
    output_file = 'config/weights_combined_optimized.json'
    with open(output_file, 'w') as f:
        json.dump(results['best_weights'], f, indent=2)

    print(f"\n✅ New weights saved to: {output_file}")

    # Save detailed report
    report = {
        'optimization_date': datetime.now().isoformat(),
        'dataset': {
            'total_races': len(all_races),
            'train_races': len(optimizer.train_races),
            'val_races': len(optimizer.val_races),
            'xml_races': sum(1 for r in all_races if r.source == 'xml'),
            'pdf_races': sum(1 for r in all_races if r.source == 'pdf'),
        },
        'weights': results['best_weights'],
        'performance': {
            'training': {k: float(v) for k, v in results['train_metrics'].items()},
            'validation': {k: float(v) for k, v in results['val_metrics'].items()},
            'baseline_training': {k: float(v) for k, v in results['baseline_train'].items()},
            'baseline_validation': {k: float(v) for k, v in results['baseline_val'].items()},
        }
    }

    report_file = 'output/combined_optimization_report.json'
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)

    print(f"✅ Detailed report saved to: {report_file}")
    print("\n" + "="*80)
    print(" OPTIMIZATION COMPLETE")
    print("="*80)

    return 0


if __name__ == '__main__':
    sys.exit(main())
