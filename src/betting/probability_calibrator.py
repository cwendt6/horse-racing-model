"""
Probability Calibrator for Value Betting

Converts model scores to calibrated win probabilities based on
historical performance analysis (October 2025 Keeneland data).

Calibration Data:
- 113 races, 1,197 horse predictions
- Top pick win rate: 25.7%
- Score range: 0-80+
"""

import json
import os
from pathlib import Path
from typing import Dict, Tuple, Optional


# Score and rank calibration from the October 2025 Keeneland backtest (aggregates only).
DEFAULT_CALIBRATION = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..', '..', 'config', 'probability_calibration.json'
)


class ProbabilityCalibrator:
    """
    Calibrates raw model scores to realistic win probabilities

    Uses historical data from October 2025 to map:
    - Score ranges → win probabilities
    - Ranks → win probabilities
    """

    def __init__(self, calibration_file: Optional[str] = None):
        """
        Initialize calibrator with historical calibration data

        Args:
            calibration_file: Path to JSON file with calibration data
                            Defaults to config/probability_calibration.json
        """
        if calibration_file is None:
            calibration_file = DEFAULT_CALIBRATION

        self.calibration_data = self._load_calibration_data(calibration_file)

    def _load_calibration_data(self, file_path: str) -> Dict:
        """Load calibration data from JSON file"""
        with open(file_path, 'r') as f:
            return json.load(f)

    def get_probability_from_rank(self, rank: int) -> float:
        """
        Get calibrated win probability based on rank

        Args:
            rank: Horse's rank (1 = top pick, 2 = second choice, etc.)

        Returns:
            Calibrated win probability (0.0 to 1.0)

        Example:
            >>> calibrator.get_probability_from_rank(1)
            0.257  # 25.7% win rate for top picks
        """
        rank_cal = self.calibration_data['rank_calibration']

        if rank == 1:
            return rank_cal['Top Pick']['win_rate']
        elif rank == 2:
            return rank_cal['2nd Choice']['win_rate']
        elif rank == 3:
            return rank_cal['3rd Choice']['win_rate']
        elif 4 <= rank <= 5:
            return rank_cal['4th-5th Choice']['win_rate']
        elif 6 <= rank <= 10:
            return rank_cal['6th-10th Choice']['win_rate']
        else:
            # Longshots (rank > 10)
            return 0.02  # 2% default for extreme longshots

    def get_probability_from_score(self, score: float) -> float:
        """
        Get calibrated win probability based on raw score

        Args:
            score: Model's raw score (typically 50-80 range)

        Returns:
            Calibrated win probability (0.0 to 1.0)

        Example:
            >>> calibrator.get_probability_from_score(75.0)
            0.250  # 25% win rate for 75-80 score range
        """
        score_cal = self.calibration_data['score_calibration']

        # Find matching score range
        if score >= 75:
            if 'Good (75-80)' in score_cal:
                return score_cal['Good (75-80)']['win_rate']
            else:
                return 0.25  # Default for elite scores
        elif score >= 70:
            if 'Above Average (70-75)' in score_cal:
                return score_cal['Above Average (70-75)']['win_rate']
            else:
                return 0.13
        elif score >= 65:
            if 'Average (65-70)' in score_cal:
                return score_cal['Average (65-70)']['win_rate']
            else:
                return 0.11
        elif score >= 60:
            if 'Below Average (60-65)' in score_cal:
                return score_cal['Below Average (60-65)']['win_rate']
            else:
                return 0.10
        elif score >= 50:
            if 'Poor (50-60)' in score_cal:
                return score_cal['Poor (50-60)']['win_rate']
            else:
                return 0.10
        else:
            if 'Very Poor (0-50)' in score_cal:
                return score_cal['Very Poor (0-50)']['win_rate']
            else:
                return 0.05

    def calculate_fair_odds(self, probability: float) -> float:
        """
        Convert win probability to fair odds

        Args:
            probability: Win probability (0.0 to 1.0)

        Returns:
            Fair odds in decimal format (e.g., 2.90 for 2.9-1)

        Example:
            >>> calibrator.calculate_fair_odds(0.257)
            2.89  # Fair odds for 25.7% probability
        """
        if probability <= 0:
            return 999.0

        # Fair odds = (1 / probability) - 1
        return (1.0 / probability) - 1.0

    def calculate_fair_odds_from_rank(self, rank: int) -> float:
        """
        Calculate fair odds directly from rank

        Args:
            rank: Horse's rank

        Returns:
            Fair odds in decimal format
        """
        prob = self.get_probability_from_rank(rank)
        return self.calculate_fair_odds(prob)

    def calculate_fair_odds_from_score(self, score: float) -> float:
        """
        Calculate fair odds directly from score

        Args:
            score: Model's raw score

        Returns:
            Fair odds in decimal format
        """
        prob = self.get_probability_from_score(score)
        return self.calculate_fair_odds(prob)

    def calibrate_race_probabilities(self, predictions: list) -> list:
        """
        Calibrate probabilities for all horses in a race

        Ensures probabilities sum to 100% after calibration

        Args:
            predictions: List of dicts with 'score' and 'rank' keys

        Returns:
            List of predictions with added 'probability', 'fair_odds' keys

        Example:
            >>> predictions = [
            ...     {'name': 'Horse A', 'rank': 1, 'score': 75.0},
            ...     {'name': 'Horse B', 'rank': 2, 'score': 70.0},
            ... ]
            >>> calibrated = calibrator.calibrate_race_probabilities(predictions)
            >>> calibrated[0]['probability']
            0.257
            >>> calibrated[0]['fair_odds']
            2.89
        """
        # Add raw probabilities based on rank
        for pred in predictions:
            rank = pred.get('rank', 99)
            pred['probability'] = self.get_probability_from_rank(rank)
            pred['fair_odds'] = self.calculate_fair_odds(pred['probability'])

        # Normalize probabilities to sum to 1.0
        total_prob = sum(p['probability'] for p in predictions)

        if total_prob > 0:
            for pred in predictions:
                pred['probability'] = pred['probability'] / total_prob
                # Recalculate fair odds with normalized probability
                pred['fair_odds'] = self.calculate_fair_odds(pred['probability'])

        return predictions

    def get_calibration_summary(self) -> Dict:
        """
        Get summary of calibration data

        Returns:
            Dict with calibration statistics
        """
        rank_cal = self.calibration_data['rank_calibration']

        return {
            'dataset': self.calibration_data.get('dataset', 'Unknown'),
            'total_races': self.calibration_data.get('total_races', 0),
            'total_predictions': self.calibration_data.get('total_predictions', 0),
            'top_pick_win_rate': rank_cal['Top Pick']['win_rate'],
            'top_pick_fair_odds': rank_cal['Top Pick']['fair_odds'],
            'top3_combined_rate': (
                rank_cal['Top Pick']['win_rate'] +
                rank_cal['2nd Choice']['win_rate'] +
                rank_cal['3rd Choice']['win_rate']
            )
        }


def format_odds(decimal_odds: float) -> str:
    """
    Format decimal odds to traditional fractional display

    Args:
        decimal_odds: Odds in decimal format (e.g., 2.90)

    Returns:
        Formatted string (e.g., "2.9-1")

    Example:
        >>> format_odds(2.90)
        '2.9-1'
        >>> format_odds(15.14)
        '15.1-1'
    """
    return f"{decimal_odds:.1f}-1"


def print_calibration_summary(calibrator: ProbabilityCalibrator):
    """
    Print a nice summary of calibration data

    Args:
        calibrator: Initialized ProbabilityCalibrator instance
    """
    summary = calibrator.get_calibration_summary()

    print('='*80)
    print(' PROBABILITY CALIBRATION SUMMARY')
    print('='*80)
    print()
    print(f"Dataset: {summary['dataset']}")
    print(f"Total Races: {summary['total_races']}")
    print(f"Total Predictions: {summary['total_predictions']}")
    print()
    print("KEY METRICS:")
    print(f"  Top Pick Win Rate: {summary['top_pick_win_rate']*100:.1f}%")
    print(f"  Top Pick Fair Odds: {format_odds(summary['top_pick_fair_odds'])}")
    print(f"  Top 3 Combined: {summary['top3_combined_rate']*100:.1f}%")
    print()
    print("VALUE BETTING RULE:")
    print(f"  Bet top picks when morning line > {format_odds(summary['top_pick_fair_odds'])}")
    print()


if __name__ == '__main__':
    # Demo usage
    calibrator = ProbabilityCalibrator()

    print_calibration_summary(calibrator)

    print('='*80)
    print(' EXAMPLE CALIBRATIONS')
    print('='*80)
    print()

    # Example 1: Top pick
    rank = 1
    prob = calibrator.get_probability_from_rank(rank)
    odds = calibrator.calculate_fair_odds(prob)
    print(f"Top Pick (Rank {rank}):")
    print(f"  Probability: {prob*100:.1f}%")
    print(f"  Fair Odds: {format_odds(odds)}")
    print()

    # Example 2: By score
    score = 75.0
    prob = calibrator.get_probability_from_score(score)
    odds = calibrator.calculate_fair_odds(prob)
    print(f"High Score ({score}):")
    print(f"  Probability: {prob*100:.1f}%")
    print(f"  Fair Odds: {format_odds(odds)}")
    print()

    # Example 3: Full race calibration
    sample_race = [
        {'name': 'Horse A', 'rank': 1, 'score': 75.0},
        {'name': 'Horse B', 'rank': 2, 'score': 70.0},
        {'name': 'Horse C', 'rank': 3, 'score': 68.0},
        {'name': 'Horse D', 'rank': 4, 'score': 65.0},
    ]

    calibrated = calibrator.calibrate_race_probabilities(sample_race)

    print("Sample Race Calibration:")
    print(f"{'Rank':<6} {'Horse':<12} {'Prob':<8} {'Fair Odds':<12}")
    print('-'*50)
    for horse in calibrated:
        print(f"{horse['rank']:<6} {horse['name']:<12} {horse['probability']*100:5.1f}%  {format_odds(horse['fair_odds']):<12}")

    total = sum(h['probability'] for h in calibrated)
    print('-'*50)
    print(f"{'TOTAL':<18} {total*100:5.1f}%")
