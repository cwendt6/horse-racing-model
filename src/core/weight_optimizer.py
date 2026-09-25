import os
"""
Weight Optimization Module
Finds optimal scoring weights using various methods
"""

import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple
from scipy.optimize import minimize, differential_evolution
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import KFold
import itertools

from src.parsers.equibase_parser import Race
from src.core.backtesting_framework import RacingBacktest, BacktestMetrics


class WeightOptimizer:
    """Optimizes scoring weights for racing model"""
    
    def __init__(self, races: List[Race]):
        """
        Initialize optimizer
        
        Args:
            races: List of historical races
        """
        self.races = races
        self.best_weights = None
        self.best_score = -np.inf
        self.optimization_history = []
    
    def grid_search(self, param_grid: Dict[str, List[float]], 
                   metric: str = 'roi') -> Dict[str, float]:
        """
        Grid search over weight combinations
        
        Args:
            param_grid: Dictionary of parameter ranges
                Example: {'speed': [0.25, 0.30, 0.35], 'form': [0.15, 0.20, 0.25]}
            metric: Metric to optimize ('roi', 'win_rate', 'top3_accuracy')
            
        Returns:
            Best weights found
        """
        print(f"\n=== Grid Search Optimization ===")
        print(f"Optimizing for: {metric}")
        
        # Generate all combinations
        keys = list(param_grid.keys())
        values = list(param_grid.values())
        combinations = list(itertools.product(*values))
        
        print(f"Testing {len(combinations)} weight combinations...")
        
        best_score = -np.inf
        best_weights = None
        
        for i, combo in enumerate(combinations):
            weights = dict(zip(keys, combo))
            
            # Ensure weights sum to 1.0
            weights = self._normalize_weights(weights)
            
            # Run backtest
            backtester = RacingBacktest(scoring_weights=weights)
            metrics = backtester.run_backtest(self.races)
            
            # Get score based on metric
            score = self._get_metric_value(metrics, metric)
            
            # Track in history
            self.optimization_history.append({
                'weights': weights.copy(),
                'score': score,
                'method': 'grid_search'
            })
            
            if score > best_score:
                best_score = score
                best_weights = weights.copy()
                print(f"  New best ({i+1}/{len(combinations)}): {metric}={score:.4f}")
                print(f"    Weights: {self._format_weights(weights)}")
        
        self.best_weights = best_weights
        self.best_score = best_score
        
        print(f"\nBest weights found:")
        print(f"  {self._format_weights(best_weights)}")
        print(f"  {metric}: {best_score:.4f}")
        
        return best_weights
    
    def gradient_descent(self, initial_weights: Dict[str, float], 
                        metric: str = 'roi',
                        learning_rate: float = 0.01,
                        max_iterations: int = 100) -> Dict[str, float]:
        """
        Gradient descent optimization
        
        Args:
            initial_weights: Starting weights
            metric: Metric to optimize
            learning_rate: Step size
            max_iterations: Maximum iterations
            
        Returns:
            Optimized weights
        """
        print(f"\n=== Gradient Descent Optimization ===")
        print(f"Optimizing for: {metric}")
        print(f"Learning rate: {learning_rate}, Max iterations: {max_iterations}")
        
        current_weights = initial_weights.copy()
        current_score = self._evaluate_weights(current_weights, metric)
        
        print(f"Initial {metric}: {current_score:.4f}")
        
        for iteration in range(max_iterations):
            # Calculate gradients numerically
            gradients = {}
            epsilon = 0.01
            
            for param in current_weights:
                # Perturb parameter up
                weights_up = current_weights.copy()
                weights_up[param] = min(1.0, weights_up[param] + epsilon)
                weights_up = self._normalize_weights(weights_up)
                score_up = self._evaluate_weights(weights_up, metric)
                
                # Perturb parameter down
                weights_down = current_weights.copy()
                weights_down[param] = max(0.0, weights_down[param] - epsilon)
                weights_down = self._normalize_weights(weights_down)
                score_down = self._evaluate_weights(weights_down, metric)
                
                # Calculate gradient
                gradients[param] = (score_up - score_down) / (2 * epsilon)
            
            # Update weights
            for param in current_weights:
                current_weights[param] += learning_rate * gradients[param]
            
            # Normalize to sum to 1.0
            current_weights = self._normalize_weights(current_weights)
            
            # Evaluate new weights
            new_score = self._evaluate_weights(current_weights, metric)
            
            if (iteration + 1) % 10 == 0:
                print(f"  Iteration {iteration + 1}: {metric}={new_score:.4f}")
            
            # Check for convergence
            if abs(new_score - current_score) < 1e-6:
                print(f"  Converged at iteration {iteration + 1}")
                break
            
            current_score = new_score
        
        self.best_weights = current_weights
        self.best_score = current_score
        
        print(f"\nOptimized weights:")
        print(f"  {self._format_weights(current_weights)}")
        print(f"  {metric}: {current_score:.4f}")
        
        return current_weights
    
    def differential_evolution_optimize(self, metric: str = 'roi',
                                       maxiter: int = 50) -> Dict[str, float]:
        """
        Differential evolution optimization (robust global optimization)
        
        Args:
            metric: Metric to optimize
            maxiter: Maximum iterations
            
        Returns:
            Optimized weights
        """
        print(f"\n=== Differential Evolution Optimization ===")
        print(f"Optimizing for: {metric}")
        print(f"Max iterations: {maxiter}")
        
        # Define bounds for each parameter (0.05 to 0.50)
        param_names = ['speed', 'form', 'class', 'pace', 'jockey', 'trainer']
        bounds = [(0.05, 0.50) for _ in param_names]
        
        # Objective function (negative because we minimize)
        def objective(x):
            weights = dict(zip(param_names, x))
            weights = self._normalize_weights(weights)
            score = self._evaluate_weights(weights, metric)
            return -score  # Negative for minimization
        
        # Run optimization
        result = differential_evolution(
            objective,
            bounds,
            maxiter=maxiter,
            seed=42,
            disp=True
        )
        
        # Convert result to weights dict
        best_weights = dict(zip(param_names, result.x))
        best_weights = self._normalize_weights(best_weights)
        best_score = -result.fun
        
        self.best_weights = best_weights
        self.best_score = best_score
        
        print(f"\nOptimized weights:")
        print(f"  {self._format_weights(best_weights)}")
        print(f"  {metric}: {best_score:.4f}")
        
        return best_weights
    
    def cross_validate_weights(self, weights: Dict[str, float], 
                              n_folds: int = 5) -> Dict[str, float]:
        """
        Cross-validate weights to check for overfitting
        
        Args:
            weights: Weights to validate
            n_folds: Number of CV folds
            
        Returns:
            Dictionary of metrics across folds
        """
        print(f"\n=== Cross-Validation ===")
        print(f"Testing weights across {n_folds} folds")
        print(f"Weights: {self._format_weights(weights)}")
        
        # Split races into folds (chronologically)
        fold_size = len(self.races) // n_folds
        
        fold_metrics = {
            'win_rate': [],
            'top3_accuracy': [],
            'roi': [],
            'brier_score': []
        }
        
        for fold in range(n_folds):
            # Create test set for this fold
            start_idx = fold * fold_size
            end_idx = start_idx + fold_size if fold < n_folds - 1 else len(self.races)
            test_races = self.races[start_idx:end_idx]
            
            # Run backtest on this fold
            backtester = RacingBacktest(scoring_weights=weights)
            metrics = backtester.run_backtest(test_races)
            
            # Store metrics
            fold_metrics['win_rate'].append(metrics.top_pick_win_rate)
            fold_metrics['top3_accuracy'].append(metrics.top_3_accuracy)
            fold_metrics['roi'].append(metrics.win_bet_roi)
            fold_metrics['brier_score'].append(metrics.brier_score)
            
            print(f"  Fold {fold + 1}: Win Rate={metrics.top_pick_win_rate:.2%}, "
                  f"ROI={metrics.win_bet_roi:.2f}%")
        
        # Calculate averages and std
        print(f"\nCross-Validation Results:")
        for metric_name, values in fold_metrics.items():
            mean_val = np.mean(values)
            std_val = np.std(values)
            
            if metric_name == 'roi':
                print(f"  {metric_name}: {mean_val:.2f}% ± {std_val:.2f}%")
            elif metric_name == 'brier_score':
                print(f"  {metric_name}: {mean_val:.4f} ± {std_val:.4f}")
            else:
                print(f"  {metric_name}: {mean_val:.2%} ± {std_val:.2%}")
        
        return fold_metrics
    
    def compare_weight_sets(self, weight_sets: Dict[str, Dict[str, float]]) -> pd.DataFrame:
        """
        Compare multiple weight sets
        
        Args:
            weight_sets: Dictionary of {name: weights}
            
        Returns:
            DataFrame with comparison results
        """
        import pandas as pd
        
        print(f"\n=== Comparing {len(weight_sets)} Weight Sets ===")
        
        results = []
        
        for name, weights in weight_sets.items():
            print(f"\nTesting: {name}")
            print(f"  Weights: {self._format_weights(weights)}")
            
            # Run backtest
            backtester = RacingBacktest(scoring_weights=weights)
            metrics = backtester.run_backtest(self.races)
            
            results.append({
                'name': name,
                'win_rate': metrics.top_pick_win_rate,
                'place_rate': metrics.top_pick_place_rate,
                'show_rate': metrics.top_pick_show_rate,
                'top3_accuracy': metrics.top_3_accuracy,
                'exacta_hit_rate': metrics.exacta_hit_rate,
                'win_roi': metrics.win_bet_roi,
                'place_roi': metrics.place_bet_roi,
                'overlay_roi': metrics.overlay_roi,
                'brier_score': metrics.brier_score,
                'log_loss': metrics.log_loss,
            })
        
        df = pd.DataFrame(results)
        return df
    
    def _evaluate_weights(self, weights: Dict[str, float], metric: str) -> float:
        """Evaluate weights using specified metric"""
        backtester = RacingBacktest(scoring_weights=weights)
        metrics = backtester.run_backtest(self.races)
        return self._get_metric_value(metrics, metric)
    
    def _get_metric_value(self, metrics: BacktestMetrics, metric_name: str) -> float:
        """Extract metric value from BacktestMetrics"""
        if metric_name == 'roi':
            return metrics.win_bet_roi
        elif metric_name == 'win_rate':
            return metrics.top_pick_win_rate * 100
        elif metric_name == 'top3_accuracy':
            return metrics.top_3_accuracy * 100
        elif metric_name == 'overlay_roi':
            return metrics.overlay_roi
        elif metric_name == 'brier_score':
            return -metrics.brier_score  # Negative because lower is better
        else:
            return metrics.win_bet_roi
    
    def _normalize_weights(self, weights: Dict[str, float]) -> Dict[str, float]:
        """Normalize weights to sum to 1.0"""
        total = sum(weights.values())
        if total == 0:
            # Equal weights if sum is zero
            n = len(weights)
            return {k: 1.0/n for k in weights}
        return {k: v/total for k, v in weights.items()}
    
    def _format_weights(self, weights: Dict[str, float]) -> str:
        """Format weights for display"""
        parts = [f"{k}={v:.3f}" for k, v in sorted(weights.items())]
        return ", ".join(parts)


def optimize_model_weights(races: List[Race], method: str = 'grid_search',
                          metric: str = 'roi') -> Dict[str, float]:
    """
    Convenience function to optimize model weights
    
    Args:
        races: List of historical races
        method: Optimization method ('grid_search', 'gradient_descent', 'differential_evolution')
        metric: Metric to optimize
        
    Returns:
        Optimized weights
    """
    optimizer = WeightOptimizer(races)
    
    if method == 'grid_search':
        param_grid = {
            'speed': [0.20, 0.25, 0.30, 0.35, 0.40],
            'form': [0.10, 0.15, 0.20, 0.25, 0.30],
            'class': [0.10, 0.15, 0.20],
            'pace': [0.10, 0.15, 0.20],
            'jockey': [0.05, 0.10, 0.15],
            'trainer': [0.05, 0.10, 0.15],
        }
        return optimizer.grid_search(param_grid, metric)
    
    elif method == 'gradient_descent':
        initial_weights = {
            'speed': 0.30,
            'form': 0.20,
            'class': 0.15,
            'pace': 0.15,
            'jockey': 0.10,
            'trainer': 0.10,
        }
        return optimizer.gradient_descent(initial_weights, metric)
    
    elif method == 'differential_evolution':
        return optimizer.differential_evolution_optimize(metric)
    
    else:
        raise ValueError(f"Unknown method: {method}")


if __name__ == '__main__':
    print("Weight optimization module loaded. Import and use WeightOptimizer class.")
