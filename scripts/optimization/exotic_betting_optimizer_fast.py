#!/usr/bin/env python3
"""
FAST Exotic Betting Weight Optimizer - In-Memory Cached Version

Optimizes weights for top-3 accuracy and exotic betting ROI.
Caches all prediction/results data in memory for 10-100x speedup.
"""

import sys
import os
sys.path.insert(0, 'src')
sys.path.insert(0, '.')
sys.path.insert(0, 'scripts')

from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Any, Tuple
import json
import numpy as np
from scipy.optimize import differential_evolution

from results_validator import ResultsValidator


@dataclass
class RaceCache:
    """Cached race data for fast re-scoring"""
    date: str
    race_number: int
    predictions: List[Dict[str, Any]]  # List of horse predictions
    winner_pgm: str
    winner_name: str


class FastExoticOptimizer:
    def __init__(self):
        print("=" * 80)
        print(" FAST EXOTIC BETTING WEIGHT OPTIMIZER")
        print("=" * 80)
        print()
        
        # Load baseline weights
        with open('config/optimized_weights.json', 'r') as f:
            self.baseline_weights = json.load(f)
        
        print("📊 Baseline Configuration:")
        print(f"   Form: {self.baseline_weights['form']:.3f}")
        print(f"   Speed: {self.baseline_weights['speed']:.3f}")
        print(f"   Class: {self.baseline_weights.get('class', self.baseline_weights.get('class_rating', 0)):.3f}")
        print(f"   Pace: {self.baseline_weights['pace']:.3f}")
        print(f"   Jockey: {self.baseline_weights['jockey']:.3f}")
        print(f"   Trainer: {self.baseline_weights['trainer']:.3f}")
        print()
        
        # Payout estimates
        self.AVG_EXACTA_PAYOUT = 16.00  # For $1
        self.AVG_TRIFECTA_PAYOUT = 72.50  # For $1
        
        # Cache all race data
        print("📥 Caching prediction and results data...")
        self.race_cache: List[RaceCache] = []
        self._cache_all_data()
        print(f"✓ Cached {len(self.race_cache)} races")
        print()
    
    def _cache_all_data(self):
        """Load all predictions and results into memory"""
        validator = ResultsValidator(results_dir="data/Results Files")
        
        # October dates we have
        dates = [
            '10-10-25', '10-11-25', '10-12-25', '10-15-25',
            '10-16-25', '10-17-25', '10-18-25', '10-19-25'
        ]
        
        for date in dates:
            # Load predictions
            pred_file = Path(f"output/predictions_{date}.json")
            if not pred_file.exists():
                continue
            
            with open(pred_file, 'r') as f:
                pred_data = json.load(f)
            
            # Load results
            month, day, year = date.split('-')
            results_file = Path(f"data/Results Files/KEE{month}{day}{year}USA.pdf")
            if not results_file.exists():
                continue
            
            race_results = validator.parse_results_pdf(str(results_file))
            
            # Cache each race
            for race_pred in pred_data['races']:
                race_num = race_pred['race_number']
                
                # Find matching result
                race_result = next((r for r in race_results if r.race_number == race_num), None)
                if not race_result:
                    continue
                
                # Only cache races with 3+ predictions
                if len(race_pred['predictions']) < 3:
                    continue
                
                self.race_cache.append(RaceCache(
                    date=date,
                    race_number=race_num,
                    predictions=race_pred['predictions'],
                    winner_pgm=race_result.winner_pgm.strip(),
                    winner_name=race_result.winner_name
                ))
    
    def _rescore_prediction(self, pred: Dict, weights: Dict) -> float:
        """Re-calculate final score with new weights"""
        # Extract component scores
        form = pred.get('form_score', 0)
        speed = pred.get('speed_score', 0)
        class_rating = pred.get('class_score', 0)
        pace = pred.get('pace_score', 0)
        jockey = pred.get('jockey_score', 0)
        trainer = pred.get('trainer_score', 0)
        
        # Apply core weights (normalized)
        core_weights = {
            'form': weights['form'],
            'speed': weights['speed'],
            'class': weights['class'],
            'pace': weights['pace'],
            'jockey': weights['jockey'],
            'trainer': weights['trainer']
        }
        
        total_weight = sum(core_weights.values())
        if total_weight > 0:
            for key in core_weights:
                core_weights[key] /= total_weight
        
        base_score = (
            form * core_weights['form'] +
            speed * core_weights['speed'] +
            class_rating * core_weights['class'] +
            pace * core_weights['pace'] +
            jockey * core_weights['jockey'] +
            trainer * core_weights['trainer']
        )
        
        # Apply bonuses with scales
        bonuses = (
            pred.get('jt_combo_bonus', 0) * weights.get('jt_combo_scale', 1.0) +
            pred.get('ds_bonus', 0) * weights.get('distance_surface_scale', 1.0) +
            pred.get('equip_bonus', 0) * weights.get('equipment_scale', 1.0) +
            pred.get('trip_bonus', 0) * weights.get('trip_notes_scale', 1.0) +
            pred.get('workout_bonus', 0) * weights.get('workout_scale', 1.0) +
            pred.get('trainer_bonus', 0) * weights.get('trainer_pattern_scale', 1.0)
        )
        
        return base_score + bonuses
    
    def evaluate_weights(self, weights_array: np.ndarray, races: List[RaceCache]) -> float:
        """Evaluate a weight configuration (minimize negative fitness)"""
        # Convert array to weights dict
        weights = {
            'form': weights_array[0],
            'speed': weights_array[1],
            'class': weights_array[2],
            'pace': weights_array[3],
            'jockey': weights_array[4],
            'trainer': weights_array[5],
            'jt_combo_scale': weights_array[6],
            'distance_surface_scale': weights_array[7],
            'equipment_scale': weights_array[8],
            'trip_notes_scale': weights_array[9],
            'workout_scale': weights_array[10],
            'trainer_pattern_scale': weights_array[11]
        }
        
        top_3_hits = 0
        total_races = len(races)
        
        for race in races:
            # Re-score all predictions
            rescored = []
            for pred in race.predictions:
                new_score = self._rescore_prediction(pred, weights)
                rescored.append({
                    'program_number': pred['program_number'],
                    'score': new_score
                })
            
            # Sort by new score
            rescored.sort(key=lambda x: x['score'], reverse=True)
            
            # Check if winner in top 3
            top_3_pgms = [r['program_number'].strip() for r in rescored[:3]]
            if race.winner_pgm in top_3_pgms:
                top_3_hits += 1
        
        # Calculate metrics
        top_3_rate = top_3_hits / total_races if total_races > 0 else 0
        
        # Estimate exotic ROI (simplified)
        exacta_cost = 6.0  # $1 box on 3 horses
        trifecta_cost = 6.0  # $1 box on 3 horses
        total_cost = exacta_cost + trifecta_cost
        
        exacta_return = top_3_hits * self.AVG_EXACTA_PAYOUT
        trifecta_return = top_3_hits * self.AVG_TRIFECTA_PAYOUT
        total_return = exacta_return + trifecta_return
        
        exotic_roi = ((total_return - (total_cost * total_races)) / (total_cost * total_races)) if total_races > 0 else 0
        
        # Fitness function: 70% top-3 rate + 30% exotic ROI (capped)
        roi_component = min(exotic_roi / 5.0, 1.0)  # Cap at 500% ROI
        fitness = 0.7 * top_3_rate + 0.3 * roi_component
        
        # Return negative (scipy minimizes)
        return -fitness
    
    def optimize(self, max_iter=30):
        """Run optimization"""
        print("=" * 80)
        print(" RUNNING FAST OPTIMIZATION")
        print("=" * 80)
        print()
        print(f"🎯 Races cached: {len(self.race_cache)}")
        print(f"🔬 Max iterations: {max_iter}")
        print(f"📈 Optimization method: Differential Evolution (fast)")
        print()
        
        # Define bounds for 12 parameters
        bounds = [
            # Core weights (0.01 to 0.5 each, will be normalized)
            (0.01, 0.5),  # form
            (0.01, 0.5),  # speed
            (0.01, 0.5),  # class
            (0.01, 0.5),  # pace
            (0.01, 0.5),  # jockey
            (0.01, 0.5),  # trainer
            # Bonus scales (0.0 to 2.0)
            (0.0, 2.0),  # jt_combo_scale
            (0.0, 2.0),  # distance_surface_scale
            (0.0, 2.0),  # equipment_scale
            (0.0, 2.0),  # trip_notes_scale
            (0.0, 2.0),  # workout_scale
            (0.0, 2.0),  # trainer_pattern_scale
        ]
        
        print("🚀 Starting optimization...")
        print()
        
        # Run optimization
        result = differential_evolution(
            func=lambda w: self.evaluate_weights(w, self.race_cache),
            bounds=bounds,
            maxiter=max_iter,
            popsize=15,
            strategy='best1bin',
            atol=0.001,
            tol=0.001,
            disp=True,
            workers=1,
            updating='immediate'
        )
        
        print()
        print("=" * 80)
        print(" OPTIMIZATION COMPLETE")
        print("=" * 80)
        print()
        
        # Build optimized weights
        optimized_weights = {
            'form': result.x[0],
            'speed': result.x[1],
            'class': result.x[2],
            'pace': result.x[3],
            'jockey': result.x[4],
            'trainer': result.x[5],
            'jt_combo_scale': result.x[6],
            'distance_surface_scale': result.x[7],
            'equipment_scale': result.x[8],
            'trip_notes_scale': result.x[9],
            'workout_scale': result.x[10],
            'trainer_pattern_scale': result.x[11]
        }
        
        # Normalize core weights
        core_total = sum([optimized_weights[k] for k in ['form', 'speed', 'class', 'pace', 'jockey', 'trainer']])
        for k in ['form', 'speed', 'class', 'pace', 'jockey', 'trainer']:
            optimized_weights[k] /= core_total
        
        # Evaluate final performance
        fitness = -self.evaluate_weights(result.x, self.race_cache)
        
        print("🏆 OPTIMIZED WEIGHTS:")
        print("-" * 80)
        print("Core Weights:")
        print(f"  Form: {optimized_weights['form']:.4f}")
        print(f"  Speed: {optimized_weights['speed']:.4f}")
        print(f"  Class: {optimized_weights['class']:.4f}")
        print(f"  Pace: {optimized_weights['pace']:.4f}")
        print(f"  Jockey: {optimized_weights['jockey']:.4f}")
        print(f"  Trainer: {optimized_weights['trainer']:.4f}")
        print()
        print("Bonus Scales:")
        print(f"  J/T Combo: {optimized_weights['jt_combo_scale']:.3f}x")
        print(f"  Dist/Surface: {optimized_weights['distance_surface_scale']:.3f}x")
        print(f"  Equipment: {optimized_weights['equipment_scale']:.3f}x")
        print(f"  Trip Notes: {optimized_weights['trip_notes_scale']:.3f}x")
        print(f"  Workouts: {optimized_weights['workout_scale']:.3f}x")
        print(f"  Trainer Patterns: {optimized_weights['trainer_pattern_scale']:.3f}x")
        print()
        print(f"📊 Fitness Score: {fitness:.4f}")
        print()
        
        # Calculate actual performance
        top_3_hits = 0
        for race in self.race_cache:
            rescored = []
            for pred in race.predictions:
                new_score = self._rescore_prediction(pred, optimized_weights)
                rescored.append({
                    'program_number': pred['program_number'],
                    'score': new_score
                })
            rescored.sort(key=lambda x: x['score'], reverse=True)
            top_3_pgms = [r['program_number'].strip() for r in rescored[:3]]
            if race.winner_pgm in top_3_pgms:
                top_3_hits += 1
        
        top_3_rate = (top_3_hits / len(self.race_cache)) * 100
        
        # Estimate ROI
        exacta_return = top_3_hits * self.AVG_EXACTA_PAYOUT
        trifecta_return = top_3_hits * self.AVG_TRIFECTA_PAYOUT
        total_return = exacta_return + trifecta_return
        total_cost = 12.0 * len(self.race_cache)
        exotic_roi = ((total_return - total_cost) / total_cost) * 100
        
        print("📈 PERFORMANCE METRICS:")
        print("-" * 80)
        print(f"Top-3 Hit Rate: {top_3_rate:.1f}% ({top_3_hits}/{len(self.race_cache)})")
        print(f"Estimated Exotic ROI: {exotic_roi:+.1f}%")
        print()
        print(f"Baseline Performance: 73.4% top-3, +441.6% ROI")
        if top_3_rate >= 73.4:
            print(f"✅ IMPROVEMENT: +{top_3_rate - 73.4:.1f}% top-3 rate")
        else:
            print(f"⚠️  Below baseline: {top_3_rate - 73.4:.1f}% top-3 rate")
        print()
        
        # Save optimized weights
        output_file = 'config/exotic_optimized_weights.json'
        with open(output_file, 'w') as f:
            json.dump(optimized_weights, f, indent=2)
        
        print(f"💾 Saved optimized weights to: {output_file}")
        print()
        print("=" * 80)
        
        return optimized_weights


if __name__ == '__main__':
    optimizer = FastExoticOptimizer()
    best_weights = optimizer.optimize(max_iter=30)
