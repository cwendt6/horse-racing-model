"""
Autonomous Model Optimizer
Optimizes prediction model weights using Bayesian optimization or genetic algorithms

Key Features:
- Multi-day validation windows (prevents overfitting)
- Convergence detection
- Performance degradation limits
- Comprehensive reporting
"""

import os
import sys
import json
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import pickle

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from scripts.results_validator import ResultsValidator, PredictionResult
import subprocess
import tempfile


@dataclass
class WeightConfig:
    """Model weight configuration - aligned with prediction engine"""
    # Base scoring components (from stats.calculate_comprehensive_score)
    speed: float = 0.2292      # Speed figures
    form: float = 0.1458       # Recent form
    class_rating: float = 0.1250  # Class level
    pace: float = 0.1042       # Pace scenario
    recency: float = 0.0833    # Days since last race
    progression: float = 0.0938  # Improvement trend
    jockey: float = 0.0625     # Jockey skill
    trainer: float = 0.0625    # Trainer skill
    post: float = 0.0521       # Post position

    # Bonus component scaling factors (applied to analyzer outputs)
    jt_combo_scale: float = 1.0       # Jockey-trainer combinations (base: -4 to +9)
    distance_surface_scale: float = 1.0  # Distance/surface fit (base: -13 to +10)
    equipment_scale: float = 1.0      # Equipment changes (base: -3 to +7)
    trip_notes_scale: float = 1.0     # Trip trouble/bounce-back (base: 0 to +15)
    workout_scale: float = 1.0        # Workout fitness (base: -5 to +15)
    trainer_pattern_scale: float = 1.0  # Trainer patterns (base: 0 to +10)

    # Confidence multiplier (amplifies probability differences)
    confidence_multiplier: float = 1.0

    def to_dict(self) -> Dict:
        return asdict(self)

    def to_prediction_engine_format(self) -> Dict:
        """Convert to format expected by prediction engine"""
        return {
            'speed': self.speed,
            'form': self.form,
            'class': self.class_rating,
            'pace': self.pace,
            'recency': self.recency,
            'progression': self.progression,
            'jockey': self.jockey,
            'trainer': self.trainer,
            'post': self.post,
            # Bonus scales are applied separately in prediction
            'jt_combo_scale': self.jt_combo_scale,
            'distance_surface_scale': self.distance_surface_scale,
            'equipment_scale': self.equipment_scale,
            'trip_notes_scale': self.trip_notes_scale,
            'workout_scale': self.workout_scale,
            'trainer_pattern_scale': self.trainer_pattern_scale,
            'confidence_multiplier': self.confidence_multiplier
        }

    @staticmethod
    def from_dict(d: Dict) -> 'WeightConfig':
        return WeightConfig(**d)

    def normalize(self):
        """Normalize base weights to sum to 1.0"""
        total = (
            self.speed +
            self.form +
            self.class_rating +
            self.pace +
            self.recency +
            self.progression +
            self.jockey +
            self.trainer +
            self.post
        )

        if total > 0:
            self.speed /= total
            self.form /= total
            self.class_rating /= total
            self.pace /= total
            self.recency /= total
            self.progression /= total
            self.jockey /= total
            self.trainer /= total
            self.post /= total


@dataclass
class OptimizationResult:
    """Results from optimization run"""
    config: WeightConfig
    win_rate: float
    top_3_rate: float
    top_5_rate: float
    avg_winner_rank: float
    confidence_picks_pct: float  # % of picks with >20% probability
    high_confidence_win_rate: float  # Win rate on >25% picks

    # Validation metrics
    train_win_rate: float
    val_win_rate: float
    degradation: float  # How much worse on validation

    iteration: int
    timestamp: str


class AutonomousOptimizer:
    """
    Autonomous model weight optimizer

    Uses Bayesian optimization to find optimal weights while:
    - Validating on multiple days (prevents overfitting)
    - Ensuring convergence
    - Limiting performance degradation
    """

    def __init__(
        self,
        start_date: str = '2025-10-03',
        end_date: str = '2025-10-19',
        method: str = 'bayesian',
        max_iterations: int = 100,
        convergence_threshold: float = 0.01,
        validation_window: int = 3,
        max_degradation: float = 0.05
    ):
        """
        Initialize optimizer

        Args:
            start_date: First date to use for optimization
            end_date: Last date to use for optimization
            method: Optimization method ('bayesian', 'genetic', 'grid')
            max_iterations: Maximum optimization iterations
            convergence_threshold: Stop if improvement < threshold for 5 iterations
            validation_window: Number of days to use for validation
            max_degradation: Maximum allowed performance drop on validation (0.05 = 5%)
        """
        self.start_date = start_date
        self.end_date = end_date
        self.method = method
        self.max_iterations = max_iterations
        self.convergence_threshold = convergence_threshold
        self.validation_window = validation_window
        self.max_degradation = max_degradation

        # Initialize results tracking
        self.results: List[OptimizationResult] = []
        self.best_result: Optional[OptimizationResult] = None
        self.validator = ResultsValidator()

        # Load available dates
        self.dates = self._get_available_dates()
        self.train_dates, self.val_dates = self._split_dates()

        print(f"\n{'='*80}")
        print(" AUTONOMOUS OPTIMIZER INITIALIZED")
        print(f"{'='*80}")
        print(f"  Method: {method}")
        print(f"  Date range: {start_date} to {end_date}")
        print(f"  Training dates: {len(self.train_dates)}")
        print(f"  Validation dates: {len(self.val_dates)}")
        print(f"  Max iterations: {max_iterations}")
        print(f"  Convergence threshold: {convergence_threshold}")
        print(f"  Max degradation: {max_degradation*100:.1f}%")
        print(f"{'='*80}\n")

    def _get_available_dates(self) -> List[str]:
        """Find all dates with prediction JSONs and results PDFs"""
        import glob

        dates = []

        # Find all prediction JSONs
        for json_file in glob.glob('output/predictions_*.json'):
            # Extract date (e.g., predictions_10-18-25.json -> 10-18-25)
            basename = os.path.basename(json_file)
            date_str = basename.replace('predictions_', '').replace('.json', '')

            # Convert to YYYY-MM-DD format
            month, day, year = date_str.split('-')
            full_date = f"2025-{month}-{day}"

            # Check if results file exists
            results_file = f"data/Results Files/KEE{month}{day}{year}USA.pdf"
            if os.path.exists(results_file):
                dates.append(full_date)

        return sorted(dates)

    def _split_dates(self) -> Tuple[List[str], List[str]]:
        """Split dates into training and validation sets"""
        n = len(self.dates)

        if n < self.validation_window:
            raise ValueError(f"Need at least {self.validation_window} dates, found {n}")

        # Last N dates for validation
        val_dates = self.dates[-self.validation_window:]
        train_dates = self.dates[:-self.validation_window]

        return train_dates, val_dates

    def evaluate_config(self, config: WeightConfig, dates: List[str]) -> Dict:
        """
        Evaluate a weight configuration on given dates

        This method:
        1. Loads existing prediction JSONs (which have component scores)
        2. Re-weights the component scores using the new configuration
        3. Recalculates final scores and probabilities
        4. Compares to actual results

        Args:
            config: Weight configuration to test
            dates: List of dates to evaluate on

        Returns:
            Dict with performance metrics
        """
        comparisons = []

        for date_str in dates:
            # Load predictions with component scores
            month, day = date_str.split('-')[1:]
            pred_file = f"output/predictions_{month}-{day}-25.json"

            if not os.path.exists(pred_file):
                continue

            with open(pred_file) as f:
                pred_data = json.load(f)

            # Load results
            year = "25"
            results_file = f"data/Results Files/KEE{month}{day}{year}USA.pdf"
            results = self.validator.parse_results_pdf(results_file)

            # Re-weight predictions for each race
            for race_data in pred_data.get('races', []):
                # Re-score each horse with new weights
                reweighted_predictions = []

                for pred in race_data.get('predictions', []):
                    # Extract component scores (these are from the original prediction)
                    speed_score = pred.get('speed_score', 0)
                    form_score = pred.get('form_score', 0)
                    class_score = pred.get('class_score', 0)
                    pace_score = pred.get('pace_score', 0)
                    recency_score = pred.get('recency_score', 0)
                    progression_score = pred.get('progression_score', 0)
                    jockey_score = pred.get('jockey_score', 0)
                    trainer_score = pred.get('trainer_score', 0)
                    post_score = pred.get('post_score', 0)

                    # Extract bonus scores
                    jt_bonus = pred.get('jt_combo_bonus', 0)
                    ds_bonus = pred.get('ds_bonus', 0)
                    equip_bonus = pred.get('equip_bonus', 0)
                    trip_bonus = pred.get('trip_bonus', 0)
                    workout_bonus = pred.get('workout_bonus', 0)
                    trainer_pattern_bonus = pred.get('trainer_bonus', 0)

                    # Apply new weights
                    new_score = (
                        speed_score * config.speed +
                        form_score * config.form +
                        class_score * config.class_rating +
                        pace_score * config.pace +
                        recency_score * config.recency +
                        progression_score * config.progression +
                        jockey_score * config.jockey +
                        trainer_score * config.trainer +
                        post_score * config.post +
                        jt_bonus * config.jt_combo_scale +
                        ds_bonus * config.distance_surface_scale +
                        equip_bonus * config.equipment_scale +
                        trip_bonus * config.trip_notes_scale +
                        workout_bonus * config.workout_scale +
                        trainer_pattern_bonus * config.trainer_pattern_scale
                    )

                    reweighted_predictions.append({
                        'program_number': pred.get('program_number'),
                        'horse_name': pred.get('horse_name'),
                        'score': new_score,
                        'ml_odds': pred.get('ml_odds', 5.0)
                    })

                # Sort by score (descending)
                reweighted_predictions.sort(key=lambda x: x['score'], reverse=True)

                # Calculate probabilities with confidence multiplier
                total_score = sum(max(0, p['score']) for p in reweighted_predictions)

                if total_score > 0:
                    for pred in reweighted_predictions:
                        raw_prob = max(0, pred['score']) / total_score
                        # Apply confidence multiplier (amplifies differences)
                        pred['probability'] = raw_prob ** (1.0 / config.confidence_multiplier)

                    # Re-normalize after multiplier
                    total_prob = sum(p['probability'] for p in reweighted_predictions)
                    if total_prob > 0:
                        for pred in reweighted_predictions:
                            pred['probability'] /= total_prob
                else:
                    # Fallback to equal probability
                    for pred in reweighted_predictions:
                        pred['probability'] = 1.0 / len(reweighted_predictions)

                # Compare to actual result
                result = next((r for r in results if r.race_number == race_data['race_number']), None)
                if result:
                    pred_dict = {
                        'race_number': race_data['race_number'],
                        'predictions': reweighted_predictions
                    }
                    comparison = self.validator.compare_prediction_to_result(pred_dict, result)
                    comparisons.append(comparison)

        # Calculate metrics
        if not comparisons:
            return {
                'win_rate': 0.0,
                'top_3_rate': 0.0,
                'top_5_rate': 0.0,
                'avg_winner_rank': 99.0,
                'confidence_picks_pct': 0.0,
                'high_confidence_win_rate': 0.0,
                'total_races': 0
            }

        total = len(comparisons)
        wins = sum(1 for c in comparisons if c.win_hit)
        top3 = sum(1 for c in comparisons if c.top_3_hit)
        top5 = sum(1 for c in comparisons if c.top_5_hit)

        winner_ranks = [c.winner_rank for c in comparisons if c.winner_rank is not None]
        avg_rank = sum(winner_ranks) / len(winner_ranks) if winner_ranks else 99.0

        # Confidence metrics (based on existing predictions)
        high_conf = [c for c in comparisons if c.winner_rank == 1 and c.winner_probability and c.winner_probability > 0.2]
        very_high_conf = [c for c in comparisons if c.winner_rank == 1 and c.winner_probability and c.winner_probability > 0.25]

        confidence_picks_pct = len(high_conf) / total * 100 if total > 0 else 0.0
        high_conf_win_rate = sum(1 for c in very_high_conf if c.win_hit) / len(very_high_conf) * 100 if very_high_conf else 0.0

        return {
            'win_rate': wins / total * 100,
            'top_3_rate': top3 / total * 100,
            'top_5_rate': top5 / total * 100,
            'avg_winner_rank': avg_rank,
            'confidence_picks_pct': confidence_picks_pct,
            'high_confidence_win_rate': high_conf_win_rate,
            'total_races': total
        }

    def run_bayesian_optimization(self) -> WeightConfig:
        """
        Run Bayesian optimization to find best weights

        NOTE: This is a simplified implementation
        For production, use scikit-optimize or similar library
        """
        print(f"\n{'='*80}")
        print(" RUNNING BAYESIAN OPTIMIZATION")
        print(f"{'='*80}\n")

        # Start with current weights (baseline)
        best_config = WeightConfig()
        best_config.normalize()

        # Evaluate baseline
        train_metrics = self.evaluate_config(best_config, self.train_dates)
        val_metrics = self.evaluate_config(best_config, self.val_dates)

        best_score = train_metrics['win_rate'] + train_metrics['top_3_rate'] * 0.5

        print(f"Baseline Performance:")
        print(f"  Train: {train_metrics['win_rate']:.1f}% win, {train_metrics['top_3_rate']:.1f}% top-3")
        print(f"  Val:   {val_metrics['win_rate']:.1f}% win, {val_metrics['top_3_rate']:.1f}% top-3")
        print(f"  Score: {best_score:.2f}\n")

        # Simple random search with validation
        # (In production, use proper Bayesian optimization)
        no_improvement_count = 0

        for iteration in range(self.max_iterations):
            # Generate candidate configuration
            candidate = self._generate_candidate(best_config, iteration)
            candidate.normalize()

            # Evaluate on training set
            train_metrics = self.evaluate_config(candidate, self.train_dates)
            val_metrics = self.evaluate_config(candidate, self.val_dates)

            # Calculate combined score (prioritize win rate)
            score = train_metrics['win_rate'] + train_metrics['top_3_rate'] * 0.5

            # Check validation degradation
            degradation = (train_metrics['win_rate'] - val_metrics['win_rate']) / 100.0

            # Accept if better and not overfitting
            if score > best_score and degradation <= self.max_degradation:
                improvement = score - best_score
                best_score = score
                best_config = candidate
                no_improvement_count = 0

                print(f"Iteration {iteration+1}: IMPROVEMENT (+{improvement:.2f})")
                print(f"  Train: {train_metrics['win_rate']:.1f}% win, {train_metrics['top_3_rate']:.1f}% top-3")
                print(f"  Val:   {val_metrics['win_rate']:.1f}% win, {val_metrics['top_3_rate']:.1f}% top-3")
                print(f"  Degradation: {degradation*100:.1f}%")
                print(f"  New Score: {score:.2f}\n")

                # Save result
                result = OptimizationResult(
                    config=candidate,
                    win_rate=train_metrics['win_rate'],
                    top_3_rate=train_metrics['top_3_rate'],
                    top_5_rate=train_metrics['top_5_rate'],
                    avg_winner_rank=train_metrics['avg_winner_rank'],
                    confidence_picks_pct=train_metrics['confidence_picks_pct'],
                    high_confidence_win_rate=train_metrics['high_confidence_win_rate'],
                    train_win_rate=train_metrics['win_rate'],
                    val_win_rate=val_metrics['win_rate'],
                    degradation=degradation,
                    iteration=iteration+1,
                    timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                )
                self.results.append(result)
                self.best_result = result
            else:
                no_improvement_count += 1

                if iteration % 10 == 0:
                    print(f"Iteration {iteration+1}: No improvement ({no_improvement_count} consecutive)")

            # Check convergence
            if no_improvement_count >= 5:
                print(f"\nConverged after {iteration+1} iterations (no improvement for 5 iterations)")
                break

        return best_config

    def _generate_candidate(self, base_config: WeightConfig, iteration: int) -> WeightConfig:
        """
        Generate a candidate configuration

        Uses simulated annealing-style exploration:
        - Early iterations: large random changes
        - Later iterations: small refinements
        """
        # Annealing schedule
        temperature = max(0.1, 1.0 - iteration / self.max_iterations)

        # Create candidate with random perturbations (base weights)
        candidate = WeightConfig(
            speed=max(0.05, base_config.speed + np.random.normal(0, 0.10 * temperature)),
            form=max(0.05, base_config.form + np.random.normal(0, 0.08 * temperature)),
            class_rating=max(0.03, base_config.class_rating + np.random.normal(0, 0.06 * temperature)),
            pace=max(0.03, base_config.pace + np.random.normal(0, 0.06 * temperature)),
            recency=max(0.02, base_config.recency + np.random.normal(0, 0.04 * temperature)),
            progression=max(0.02, base_config.progression + np.random.normal(0, 0.04 * temperature)),
            jockey=max(0.02, base_config.jockey + np.random.normal(0, 0.04 * temperature)),
            trainer=max(0.02, base_config.trainer + np.random.normal(0, 0.04 * temperature)),
            post=max(0.01, base_config.post + np.random.normal(0, 0.03 * temperature)),

            # Bonus scaling factors (can go above or below 1.0)
            jt_combo_scale=max(0.3, min(2.0, base_config.jt_combo_scale + np.random.normal(0, 0.3 * temperature))),
            distance_surface_scale=max(0.3, min(2.0, base_config.distance_surface_scale + np.random.normal(0, 0.3 * temperature))),
            equipment_scale=max(0.3, min(2.0, base_config.equipment_scale + np.random.normal(0, 0.3 * temperature))),
            trip_notes_scale=max(0.3, min(2.0, base_config.trip_notes_scale + np.random.normal(0, 0.3 * temperature))),
            workout_scale=max(0.3, min(2.0, base_config.workout_scale + np.random.normal(0, 0.3 * temperature))),
            trainer_pattern_scale=max(0.3, min(2.0, base_config.trainer_pattern_scale + np.random.normal(0, 0.3 * temperature))),

            # Confidence multiplier (KEY for increasing model confidence)
            confidence_multiplier=max(0.5, min(3.0, base_config.confidence_multiplier + np.random.normal(0, 0.4 * temperature)))
        )

        # Normalize base weights to sum to 1.0
        candidate.normalize()

        return candidate

    def run_autonomous(self) -> WeightConfig:
        """
        Run autonomous optimization

        Returns:
            Best weight configuration found
        """
        if self.method == 'bayesian':
            best_config = self.run_bayesian_optimization()
        else:
            raise ValueError(f"Method '{self.method}' not implemented yet")

        # Save best configuration
        self._save_best_config(best_config)

        return best_config

    def _save_best_config(self, config: WeightConfig):
        """Save best configuration to file"""
        output_file = 'config/optimized_weights.json'
        os.makedirs('config', exist_ok=True)

        with open(output_file, 'w') as f:
            json.dump(config.to_dict(), f, indent=2)

        print(f"\n✓ Best configuration saved to: {output_file}")

    def generate_report(self):
        """Generate comprehensive optimization report"""
        if not self.best_result:
            print("No optimization results to report")
            return

        print(f"\n{'='*80}")
        print(" OPTIMIZATION REPORT")
        print(f"{'='*80}\n")

        print(f"Method: {self.method}")
        print(f"Iterations: {len(self.results)}")
        print(f"Training dates: {', '.join(self.train_dates)}")
        print(f"Validation dates: {', '.join(self.val_dates)}")
        print()

        print("BEST CONFIGURATION:")
        print("-"*80)
        config = self.best_result.config
        print(f"  Speed Figure:      {config.speed_figure_weight:5.1f}")
        print(f"  Pace:              {config.pace_weight:5.1f}")
        print(f"  Running Style:     {config.running_style_weight:5.1f}")
        print(f"  Jockey:            {config.jockey_weight:5.1f}")
        print(f"  Trainer:           {config.trainer_weight:5.1f}")
        print(f"  Distance/Surface:  {config.distance_surface_weight:5.1f}")
        print(f"  Trip Notes:        {config.trip_notes_weight:5.1f}")
        print(f"  Workouts:          {config.workout_weight:5.1f}")
        print(f"  Equipment:         {config.equipment_weight:5.1f}")
        print(f"  Trainer Patterns:  {config.trainer_pattern_weight:5.1f}")
        print(f"  Confidence Mult:   {config.confidence_multiplier:5.2f}x")
        print()

        print("PERFORMANCE:")
        print("-"*80)
        print(f"  Training Win Rate:   {self.best_result.train_win_rate:5.1f}%")
        print(f"  Validation Win Rate: {self.best_result.val_win_rate:5.1f}%")
        print(f"  Degradation:         {self.best_result.degradation*100:5.1f}%")
        print(f"  Top-3 Rate:          {self.best_result.top_3_rate:5.1f}%")
        print(f"  Top-5 Rate:          {self.best_result.top_5_rate:5.1f}%")
        print(f"  Avg Winner Rank:     {self.best_result.avg_winner_rank:5.1f}")
        print()

        # Save detailed report
        report_file = 'output/optimization_report.json'
        with open(report_file, 'w') as f:
            json.dump({
                'method': self.method,
                'iterations': len(self.results),
                'train_dates': self.train_dates,
                'val_dates': self.val_dates,
                'best_result': asdict(self.best_result),
                'all_results': [asdict(r) for r in self.results]
            }, f, indent=2)

        print(f"✓ Detailed report saved to: {report_file}")
        print(f"{'='*80}\n")


if __name__ == "__main__":
    # Quick test
    optimizer = AutonomousOptimizer(
        start_date='2025-10-03',
        end_date='2025-10-19',
        method='bayesian',
        max_iterations=50,
        convergence_threshold=0.01,
        validation_window=3,
        max_degradation=0.05
    )

    best_config = optimizer.run_autonomous()
    optimizer.generate_report()
