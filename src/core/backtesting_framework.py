import os
"""
Backtesting Framework for Horse Racing Model
Tests model predictions against historical results
"""

import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from collections import defaultdict
import json

from src.analyzers import racing_statistics as stats
from src.parsers.equibase_parser import Race, Horse
from src.analyzers.pace_analyzer import PaceAnalyzer


@dataclass
class PredictionResult:
    """Stores prediction and actual outcome for a single horse"""
    race_id: str
    horse_name: str
    program_number: str
    
    # Predictions
    predicted_win_prob: float
    predicted_position: int
    predicted_score: float
    
    # Actuals
    actual_position: int
    actual_win: bool
    actual_place: bool
    actual_show: bool
    
    # Odds and payoffs
    morning_line_odds: float
    win_payoff: float
    
    # Metrics
    is_overlay: bool
    overlay_percentage: float
    expected_value: float


@dataclass
class RaceResult:
    """Stores full race prediction vs actual results"""
    race_id: str
    date: str
    race_number: int
    track: str
    distance: str
    surface: str
    purse: float
    field_size: int
    
    # Predictions
    predicted_winner: str
    predicted_winner_prob: float
    predicted_exacta: Tuple[str, str]
    
    # Actuals
    actual_winner: str
    actual_win_payoff: float
    actual_exacta: Tuple[str, str]
    actual_exacta_payoff: float
    
    # Model performance
    top_pick_won: bool
    top_pick_placed: bool
    top_pick_showed: bool
    top_3_included_winner: bool
    exacta_hit: bool
    
    # Horse-level results
    horses: List[PredictionResult] = field(default_factory=list)


@dataclass
class BacktestMetrics:
    """Overall backtest performance metrics"""
    
    # Basic counts
    total_races: int = 0
    total_horses: int = 0
    
    # Win prediction accuracy
    top_pick_wins: int = 0
    top_pick_places: int = 0
    top_pick_shows: int = 0
    top_3_includes_winner: int = 0
    
    # Exacta accuracy
    exacta_hits: int = 0
    
    # ROI metrics (flat $1 bets)
    win_bet_total_wagered: float = 0.0
    win_bet_total_returned: float = 0.0
    place_bet_total_wagered: float = 0.0
    place_bet_total_returned: float = 0.0
    
    # Value betting (only overlays)
    overlay_bets_made: int = 0
    overlay_bets_won: int = 0
    overlay_total_wagered: float = 0.0
    overlay_total_returned: float = 0.0
    
    # Probability calibration
    brier_score: float = 0.0
    log_loss: float = 0.0
    
    # By category breakdowns
    by_surface: Dict[str, dict] = field(default_factory=dict)
    by_distance: Dict[str, dict] = field(default_factory=dict)
    by_field_size: Dict[str, dict] = field(default_factory=dict)
    
    def calculate_derived_metrics(self):
        """Calculate percentage and ROI metrics"""
        self.top_pick_win_rate = self.top_pick_wins / self.total_races if self.total_races > 0 else 0
        self.top_pick_place_rate = self.top_pick_places / self.total_races if self.total_races > 0 else 0
        self.top_pick_show_rate = self.top_pick_shows / self.total_races if self.total_races > 0 else 0
        self.top_3_accuracy = self.top_3_includes_winner / self.total_races if self.total_races > 0 else 0
        self.exacta_hit_rate = self.exacta_hits / self.total_races if self.total_races > 0 else 0
        
        # ROI calculations
        self.win_bet_roi = (self.win_bet_total_returned / self.win_bet_total_wagered - 1) * 100 if self.win_bet_total_wagered > 0 else 0
        self.place_bet_roi = (self.place_bet_total_returned / self.place_bet_total_wagered - 1) * 100 if self.place_bet_total_wagered > 0 else 0
        self.overlay_roi = (self.overlay_total_returned / self.overlay_total_wagered - 1) * 100 if self.overlay_total_wagered > 0 else 0
        
        # Win rate on overlays
        self.overlay_win_rate = self.overlay_bets_won / self.overlay_bets_made if self.overlay_bets_made > 0 else 0


class RacingBacktest:
    """Main backtesting class"""
    
    def __init__(self, scoring_weights: Optional[Dict[str, float]] = None):
        """
        Initialize backtester
        
        Args:
            scoring_weights: Optional custom weights for scoring components
        """
        self.scoring_weights = scoring_weights or {
            'speed': 0.30,
            'form': 0.20,
            'class': 0.15,
            'pace': 0.15,
            'jockey': 0.10,
            'trainer': 0.10,
        }

        self.race_results: List[RaceResult] = []
        self.all_predictions: List[PredictionResult] = []

        # Initialize pace analyzer
        self.pace_analyzer = PaceAnalyzer()
    
    def run_backtest(self, races: List[Race], overlay_threshold: float = 15.0) -> BacktestMetrics:
        """
        Run backtest on historical races
        
        Args:
            races: List of Race objects with actual results
            overlay_threshold: Minimum overlay % to bet (default 15%)
            
        Returns:
            BacktestMetrics object
        """
        metrics = BacktestMetrics()
        
        print(f"Running backtest on {len(races)} races...")
        
        for i, race in enumerate(races):
            if (i + 1) % 10 == 0:
                print(f"  Processing race {i+1}/{len(races)}...")
            
            # Skip races with issues
            if not race.horses or len(race.horses) < 4:
                continue
            
            # Generate predictions
            race_result = self._predict_race(race)
            self.race_results.append(race_result)
            
            # Update metrics
            self._update_metrics(metrics, race_result, race, overlay_threshold)
        
        # Calculate derived metrics
        metrics.calculate_derived_metrics()
        
        # Calculate probability calibration metrics
        metrics.brier_score = self._calculate_brier_score()
        metrics.log_loss = self._calculate_log_loss()
        
        return metrics
    
    def _predict_race(self, race: Race) -> RaceResult:
        """Generate predictions for a single race"""
        
        # Build race data dict
        race_data = {
            'distance': race.distance_text,
            'surface': race.surface.lower() if race.surface else 'dirt',
            'purse': race.purse,
            'field_size': len(race.horses),
            'pace_scenario': 'moderate',  # Will be calculated
            'avg_beyer': 70,  # Will be calculated
        }
        
        # Calculate average Beyer if available
        beyers = [h.speed_rating for h in race.horses if h.speed_rating and h.speed_rating > 0]
        if beyers:
            race_data['avg_beyer'] = np.mean(beyers)
        
        # Analyze pace scenario for this race
        horses_for_pace = []
        for horse in race.horses:
            if hasattr(horse, '_enhanced_running_style'):
                horses_for_pace.append({
                    'name': horse.name,
                    'running_style': horse._enhanced_running_style
                })

        # Get distance in furlongs
        distance_furlongs = race.distance / 220.0 if race.distance else 6.0
        pace_scenario = self.pace_analyzer.analyze_pace(
            horses_for_pace,
            distance_furlongs,
            race.surface
        )

        # Score all horses
        horse_scores = []
        for horse in race.horses:
            # Build horse data dict
            # Check if horse has enhanced data from PP integration
            if hasattr(horse, '_has_enhanced_data') and horse._has_enhanced_data:
                # Use real data from SIMD and statistics
                horse_data = {
                    'name': horse.name,
                    'program_number': horse.program_number,
                    'post': horse.post_position,
                    'ml_odds': horse.morning_line_odds,
                    'age': horse.age,
                    'sex': horse.sex,
                    'best_beyer': horse._enhanced_best_beyer,
                    'last_beyer': horse._enhanced_last_beyer,
                    'running_style': horse._enhanced_running_style,
                    'career_earnings': horse._enhanced_career_earnings,
                    'career_starts': horse._enhanced_career_starts,
                    'jockey_win_pct': horse._enhanced_jockey_win_pct,
                    'trainer_win_pct': horse._enhanced_trainer_win_pct,
                    # FTS multiplier (if available)
                    'fts_multiplier': getattr(horse, '_fts_multiplier', 1.0),
                    'is_fts': getattr(horse, '_is_fts', False),
                    'fts_explanation': getattr(horse, '_fts_explanation', ''),
                }
            else:
                # Fall back to hardcoded defaults (for horses without PP data)
                horse_data = {
                    'name': horse.name,
                    'program_number': horse.program_number,
                    'post': horse.post_position,
                    'ml_odds': horse.morning_line_odds,
                    'age': horse.age,
                    'sex': horse.sex,
                    'best_beyer': horse.speed_rating if horse.speed_rating else 50,
                    'last_beyer': horse.speed_rating if horse.speed_rating else 50,
                    'running_style': 'P',  # Default
                    'career_earnings': 100000,  # Default
                    'career_starts': 10,  # Default
                    'jockey_win_pct': 0.15,  # Default
                    'trainer_win_pct': '15%',  # Default
                }
            
            # Calculate score
            score = stats.calculate_comprehensive_score(horse_data, race_data)
            horse_scores.append({
                'horse': horse,
                'horse_data': horse_data,
                'score': score.total,
                'component_scores': score
            })
        
        # Apply FTS and Pace multipliers to scores before normalization
        adjusted_scores = []
        for h in horse_scores:
            base_score = h['score']

            # Apply FTS multiplier
            fts_multiplier = h['horse_data'].get('fts_multiplier', 1.0)
            score_after_fts = base_score * fts_multiplier

            # Apply pace multiplier
            running_style = h['horse_data'].get('running_style', 'P')
            horse_name = h['horse_data'].get('name', '')
            pace_multiplier, pace_explanation = self.pace_analyzer.calculate_pace_multiplier(
                horse_name, running_style, pace_scenario
            )
            final_score = score_after_fts * pace_multiplier

            adjusted_scores.append(final_score)

        # Normalize probabilities with FTS+Pace-adjusted scores
        scores_array = np.array(adjusted_scores)
        win_probs = stats.normalize_probabilities(scores_array)
        place_probs, show_probs = stats.calculate_place_show_probabilities(win_probs)
        
        # Assign probabilities and create predictions
        predictions = []
        for i, hs in enumerate(horse_scores):
            horse = hs['horse']
            
            # Calculate overlay
            overlay_pct = stats.calculate_overlay_percentage(
                win_probs[i],
                str(horse.morning_line_odds)
            )
            
            # Calculate expected value
            ev = stats.calculate_expected_value(
                win_probs[i],
                str(horse.morning_line_odds),
                bet_amount=1.0
            )
            
            prediction = PredictionResult(
                race_id=f"{race.date}_{race.track_code}_R{race.race_number}",
                horse_name=horse.name,
                program_number=horse.program_number,
                predicted_win_prob=win_probs[i],
                predicted_position=i + 1,  # Will be sorted later
                predicted_score=hs['score'],
                actual_position=horse.final_position or 999,
                actual_win=(horse.final_position == 1),
                actual_place=(horse.final_position and horse.final_position <= 2),
                actual_show=(horse.final_position and horse.final_position <= 3),
                morning_line_odds=horse.morning_line_odds,
                win_payoff=horse.win_payoff,
                is_overlay=(overlay_pct > 15.0),
                overlay_percentage=overlay_pct,
                expected_value=ev
            )
            predictions.append(prediction)
            self.all_predictions.append(prediction)
        
        # Sort by predicted win probability
        predictions.sort(key=lambda p: p.predicted_win_prob, reverse=True)
        
        # Update predicted positions
        for i, pred in enumerate(predictions):
            pred.predicted_position = i + 1
        
        # Get winner and top picks
        predicted_winner = predictions[0]
        actual_winner = [p for p in predictions if p.actual_position == 1][0] if any(p.actual_position == 1 for p in predictions) else None
        
        # Exacta
        predicted_exacta = (predictions[0].program_number, predictions[1].program_number)
        actual_exacta_horses = sorted([p for p in predictions if p.actual_position in [1, 2]], 
                                     key=lambda p: p.actual_position)
        actual_exacta = (actual_exacta_horses[0].program_number, actual_exacta_horses[1].program_number) if len(actual_exacta_horses) >= 2 else (None, None)
        
        # Create race result
        race_result = RaceResult(
            race_id=f"{race.date}_{race.track_code}_R{race.race_number}",
            date=race.date,
            race_number=race.race_number,
            track=race.track_code,
            distance=race.distance_text,
            surface=race.surface,
            purse=race.purse,
            field_size=len(race.horses),
            predicted_winner=predicted_winner.horse_name,
            predicted_winner_prob=predicted_winner.predicted_win_prob,
            predicted_exacta=predicted_exacta,
            actual_winner=actual_winner.horse_name if actual_winner else 'Unknown',
            actual_win_payoff=actual_winner.win_payoff if actual_winner else 0.0,
            actual_exacta=actual_exacta,
            actual_exacta_payoff=race.exacta_payoff['payoff'] if race.exacta_payoff else 0.0,
            top_pick_won=predicted_winner.actual_win,
            top_pick_placed=predicted_winner.actual_place,
            top_pick_showed=predicted_winner.actual_show,
            top_3_included_winner=any(p.actual_win for p in predictions[:3]),
            exacta_hit=(predicted_exacta == actual_exacta),
            horses=predictions
        )
        
        return race_result
    
    def _update_metrics(self, metrics: BacktestMetrics, race_result: RaceResult, 
                       race: Race, overlay_threshold: float):
        """Update metrics with race results"""
        
        metrics.total_races += 1
        metrics.total_horses += race_result.field_size
        
        # Win/Place/Show accuracy
        if race_result.top_pick_won:
            metrics.top_pick_wins += 1
        if race_result.top_pick_placed:
            metrics.top_pick_places += 1
        if race_result.top_pick_showed:
            metrics.top_pick_shows += 1
        if race_result.top_3_included_winner:
            metrics.top_3_includes_winner += 1
        
        # Exacta
        if race_result.exacta_hit:
            metrics.exacta_hits += 1
        
        # Win bet ROI (flat $1 on top pick)
        metrics.win_bet_total_wagered += 1.0
        if race_result.top_pick_won:
            metrics.win_bet_total_returned += race_result.actual_win_payoff
        
        # Place bet ROI (would need place payoffs)
        # Simplified: assume 50% of win payoff for place
        metrics.place_bet_total_wagered += 1.0
        if race_result.top_pick_placed:
            metrics.place_bet_total_returned += (race_result.actual_win_payoff * 0.4)
        
        # Overlay bets
        top_pick = race_result.horses[0]
        if top_pick.is_overlay:
            metrics.overlay_bets_made += 1
            metrics.overlay_total_wagered += 1.0
            if top_pick.actual_win:
                metrics.overlay_bets_won += 1
                metrics.overlay_total_returned += race_result.actual_win_payoff
        
        # By category breakdowns
        self._update_category_metrics(metrics, race_result, race)
    
    def _update_category_metrics(self, metrics: BacktestMetrics, 
                                 race_result: RaceResult, race: Race):
        """Update category-specific metrics"""
        
        # By surface
        surface = race.surface
        if surface not in metrics.by_surface:
            metrics.by_surface[surface] = {'races': 0, 'wins': 0, 'top3': 0}
        metrics.by_surface[surface]['races'] += 1
        if race_result.top_pick_won:
            metrics.by_surface[surface]['wins'] += 1
        if race_result.top_3_included_winner:
            metrics.by_surface[surface]['top3'] += 1
        
        # By distance category
        if race.distance <= 600:
            dist_cat = 'Sprint'
        elif race.distance <= 800:
            dist_cat = 'Mile'
        else:
            dist_cat = 'Route'
        
        if dist_cat not in metrics.by_distance:
            metrics.by_distance[dist_cat] = {'races': 0, 'wins': 0, 'top3': 0}
        metrics.by_distance[dist_cat]['races'] += 1
        if race_result.top_pick_won:
            metrics.by_distance[dist_cat]['wins'] += 1
        if race_result.top_3_included_winner:
            metrics.by_distance[dist_cat]['top3'] += 1
        
        # By field size
        if race_result.field_size <= 6:
            size_cat = 'Small (≤6)'
        elif race_result.field_size <= 9:
            size_cat = 'Medium (7-9)'
        else:
            size_cat = 'Large (≥10)'
        
        if size_cat not in metrics.by_field_size:
            metrics.by_field_size[size_cat] = {'races': 0, 'wins': 0, 'top3': 0}
        metrics.by_field_size[size_cat]['races'] += 1
        if race_result.top_pick_won:
            metrics.by_field_size[size_cat]['wins'] += 1
        if race_result.top_3_included_winner:
            metrics.by_field_size[size_cat]['top3'] += 1
    
    def _calculate_brier_score(self) -> float:
        """Calculate Brier score for probability calibration"""
        if not self.all_predictions:
            return 0.0
        
        squared_errors = []
        for pred in self.all_predictions:
            outcome = 1.0 if pred.actual_win else 0.0
            squared_error = (pred.predicted_win_prob - outcome) ** 2
            squared_errors.append(squared_error)
        
        return np.mean(squared_errors)
    
    def _calculate_log_loss(self) -> float:
        """Calculate log loss for probability calibration"""
        if not self.all_predictions:
            return 0.0
        
        log_losses = []
        for pred in self.all_predictions:
            outcome = 1.0 if pred.actual_win else 0.0
            # Clip probability to avoid log(0)
            prob = np.clip(pred.predicted_win_prob, 1e-15, 1 - 1e-15)
            log_loss = -(outcome * np.log(prob) + (1 - outcome) * np.log(1 - prob))
            log_losses.append(log_loss)
        
        return np.mean(log_losses)
    
    def export_results(self, output_file: str):
        """Export detailed results to JSON"""
        results = {
            'race_results': [
                {
                    'race_id': r.race_id,
                    'date': r.date,
                    'race_number': r.race_number,
                    'track': r.track,
                    'predicted_winner': r.predicted_winner,
                    'actual_winner': r.actual_winner,
                    'top_pick_won': r.top_pick_won,
                    'top_3_included_winner': r.top_3_included_winner,
                }
                for r in self.race_results
            ]
        }
        
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)


if __name__ == '__main__':
    print("Backtesting framework loaded. Import and use RacingBacktest class.")
