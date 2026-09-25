"""
Value Bet Detector

Identifies betting opportunities where public odds (morning line)
are greater than the model's fair odds, indicating positive expected value.

Value Betting Strategy:
- Compare model's fair odds to morning line odds
- Bet when: Morning Line > Fair Odds (by threshold)
- Edge = (Morning Line / Fair Odds) - 1.0
"""

from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass


@dataclass
class ValueBet:
    """Represents a value betting opportunity"""
    program_number: str
    name: str
    rank: int
    score: float
    probability: float
    fair_odds: float
    morning_line_odds: float
    edge: float  # Percentage edge (e.g., 0.25 = 25% edge)
    expected_value: float  # Expected value per $1 bet
    recommended_bet: bool
    confidence: str  # 'HIGH', 'MEDIUM', 'LOW'


class ValueDetector:
    """
    Detects value betting opportunities

    Compares model probabilities to market odds to find overlays
    """

    def __init__(
        self,
        min_edge: float = 0.15,  # 15% minimum edge
        min_probability: float = 0.10,  # Don't bet horses < 10% win prob
        max_odds: float = 20.0,  # Don't bet extreme longshots > 20-1
    ):
        """
        Initialize value detector with betting criteria

        Args:
            min_edge: Minimum edge required (0.15 = 15% edge)
            min_probability: Minimum win probability to consider
            max_odds: Maximum fair odds to consider
        """
        self.min_edge = min_edge
        self.min_probability = min_probability
        self.max_odds = max_odds

    def parse_morning_line(self, ml_str: str) -> float:
        """
        Convert morning line odds string to decimal

        Args:
            ml_str: Morning line in format "3-1", "5/2", "6-5", "EVEN", etc.

        Returns:
            Decimal odds (e.g., 3.0 for 3-1)

        Example:
            >>> detector.parse_morning_line("3-1")
            3.0
            >>> detector.parse_morning_line("5/2")
            2.5
        """
        ml_str = ml_str.upper().strip()

        # Handle special cases
        if ml_str in ['EVEN', 'EVN', '1-1']:
            return 1.0
        if ml_str in ['SCRATCH', 'SCR', 'SCRATCHED']:
            return 999.0

        try:
            # Handle "3-1" format
            if '-' in ml_str:
                num, denom = ml_str.split('-')
                return float(num) / float(denom)

            # Handle "5/2" format
            if '/' in ml_str:
                num, denom = ml_str.split('/')
                return float(num) / float(denom)

            # Handle plain decimal
            return float(ml_str)

        except (ValueError, ZeroDivisionError):
            return 6.0  # Default to 6-1 if can't parse

    def calculate_edge(self, fair_odds: float, morning_line_odds: float) -> float:
        """
        Calculate betting edge

        Edge = (Morning Line / Fair Odds) - 1.0

        Args:
            fair_odds: Model's fair odds
            morning_line_odds: Public odds

        Returns:
            Edge as decimal (0.25 = 25% edge)

        Example:
            >>> detector.calculate_edge(3.0, 5.0)
            0.667  # 66.7% edge - big overlay!
        """
        if fair_odds <= 0:
            return -1.0

        return (morning_line_odds / fair_odds) - 1.0

    def calculate_expected_value(
        self,
        probability: float,
        morning_line_odds: float,
        bet_amount: float = 1.0
    ) -> float:
        """
        Calculate expected value of a bet

        EV = (Probability * Payout) - ((1 - Probability) * Stake)

        Args:
            probability: Win probability (0.0 to 1.0)
            morning_line_odds: Odds if bet wins
            bet_amount: Bet size (default $1)

        Returns:
            Expected value in dollars

        Example:
            >>> detector.calculate_expected_value(0.25, 5.0, 2.0)
            +0.50  # Positive EV of $0.50 on $2 bet
        """
        payout = bet_amount * morning_line_odds
        win_return = probability * payout
        loss = (1.0 - probability) * bet_amount

        return win_return - loss

    def get_confidence_level(self, edge: float, probability: float) -> str:
        """
        Determine confidence level for a value bet

        Args:
            edge: Betting edge (0.15 = 15%)
            probability: Win probability

        Returns:
            'HIGH', 'MEDIUM', or 'LOW'
        """
        # High confidence: Big edge + decent probability
        if edge >= 0.40 and probability >= 0.15:
            return 'HIGH'

        # High confidence: Huge edge even with lower probability
        if edge >= 0.60:
            return 'HIGH'

        # Medium confidence: Good edge
        if edge >= 0.25 and probability >= 0.10:
            return 'MEDIUM'

        # Low confidence: Marginal edge
        return 'LOW'

    def identify_value_bets(
        self,
        predictions: List[Dict],
        strict_mode: bool = False
    ) -> List[ValueBet]:
        """
        Identify value betting opportunities in a race

        Args:
            predictions: List of horse predictions with:
                - program_number
                - name
                - rank
                - score
                - probability (calibrated)
                - fair_odds (calibrated)
                - morning_line_odds (from PP)
            strict_mode: If True, only return HIGH confidence bets

        Returns:
            List of ValueBet objects

        Example:
            >>> predictions = [
            ...     {
            ...         'program_number': '3',
            ...         'name': 'Big Value',
            ...         'rank': 1,
            ...         'score': 75.0,
            ...         'probability': 0.25,
            ...         'fair_odds': 3.0,
            ...         'morning_line_odds': 6.0  # Public undervalues this horse!
            ...     }
            ... ]
            >>> value_bets = detector.identify_value_bets(predictions)
            >>> value_bets[0].edge
            1.0  # 100% edge!
        """
        value_bets = []

        for pred in predictions:
            # Extract data
            probability = pred.get('probability', 0)
            fair_odds = pred.get('fair_odds', 999)
            ml_odds_raw = pred.get('morning_line_odds', 999)

            # Parse morning line if it's a string
            if isinstance(ml_odds_raw, str):
                ml_odds = self.parse_morning_line(ml_odds_raw)
            else:
                ml_odds = ml_odds_raw

            # Calculate edge and EV
            edge = self.calculate_edge(fair_odds, ml_odds)
            ev = self.calculate_expected_value(probability, ml_odds, bet_amount=1.0)
            confidence = self.get_confidence_level(edge, probability)

            # Check if this qualifies as a value bet
            is_value = (
                edge >= self.min_edge and
                probability >= self.min_probability and
                fair_odds <= self.max_odds and
                ev > 0
            )

            # Apply strict mode filter
            if strict_mode and confidence != 'HIGH':
                is_value = False

            value_bet = ValueBet(
                program_number=pred.get('program_number', '?'),
                name=pred.get('name', 'Unknown'),
                rank=pred.get('rank', 99),
                score=pred.get('score', 0),
                probability=probability,
                fair_odds=fair_odds,
                morning_line_odds=ml_odds,
                edge=edge,
                expected_value=ev,
                recommended_bet=is_value,
                confidence=confidence
            )

            if is_value:
                value_bets.append(value_bet)

        # Sort by EV descending
        value_bets.sort(key=lambda x: x.expected_value, reverse=True)

        return value_bets

    def format_value_bet_report(self, value_bets: List[ValueBet]) -> str:
        """
        Create formatted report of value bets

        Args:
            value_bets: List of ValueBet objects

        Returns:
            Formatted string report
        """
        if not value_bets:
            return "No value bets identified in this race."

        lines = []
        lines.append("="*80)
        lines.append(" VALUE BETTING OPPORTUNITIES")
        lines.append("="*80)
        lines.append("")

        for i, vb in enumerate(value_bets, 1):
            lines.append(f"{i}. #{vb.program_number} {vb.name}")
            lines.append(f"   Rank: {vb.rank}")
            lines.append(f"   Model Probability: {vb.probability*100:.1f}%")
            lines.append(f"   Fair Odds: {vb.fair_odds:.1f}-1")
            lines.append(f"   Morning Line: {vb.morning_line_odds:.1f}-1")
            lines.append(f"   Edge: {vb.edge*100:+.1f}% ({vb.confidence} confidence)")
            lines.append(f"   Expected Value: ${vb.expected_value:+.2f} per $1 bet")
            lines.append(f"   RECOMMENDATION: ✓ BET")
            lines.append("")

        lines.append("="*80)
        lines.append(f"Total Value Opportunities: {len(value_bets)}")
        total_ev = sum(vb.expected_value for vb in value_bets)
        lines.append(f"Combined EV (if betting $1 each): ${total_ev:+.2f}")
        lines.append("="*80)

        return "\n".join(lines)


def demo_value_detection():
    """Demonstrate value detection with sample data"""
    detector = ValueDetector(min_edge=0.15, min_probability=0.10)

    # Sample race with various scenarios
    sample_race = [
        {
            'program_number': '3',
            'name': 'Big Overlay',
            'rank': 1,
            'score': 75.0,
            'probability': 0.30,  # Model says 30% chance
            'fair_odds': 2.33,     # Fair odds 2.33-1
            'morning_line_odds': 5.0  # Public has 5-1 (20% implied)
        },
        {
            'program_number': '7',
            'name': 'Slight Value',
            'rank': 2,
            'score': 70.0,
            'probability': 0.20,
            'fair_odds': 4.0,
            'morning_line_odds': 6.0  # Some value
        },
        {
            'program_number': '1',
            'name': 'No Value',
            'rank': 3,
            'score': 68.0,
            'probability': 0.15,
            'fair_odds': 5.67,
            'morning_line_odds': 4.0  # Underlay - public overvalues
        },
        {
            'program_number': '5',
            'name': 'Extreme Longshot',
            'rank': 8,
            'score': 55.0,
            'probability': 0.05,
            'fair_odds': 19.0,
            'morning_line_odds': 30.0  # Value but risky
        },
    ]

    print("="*80)
    print(" VALUE DETECTION DEMO")
    print("="*80)
    print()

    # Detect value bets
    value_bets = detector.identify_value_bets(sample_race)

    print(detector.format_value_bet_report(value_bets))
    print()

    # Show analysis of all horses
    print("="*80)
    print(" FULL RACE ANALYSIS")
    print("="*80)
    print()
    print(f"{'Pgm':<5} {'Horse':<20} {'Rank':<6} {'Prob':<8} {'Fair':<8} {'ML':<8} {'Edge':<10} {'Value?':<10}")
    print("-"*80)

    for horse in sample_race:
        ml_odds = horse['morning_line_odds']
        fair_odds = horse['fair_odds']
        edge = detector.calculate_edge(fair_odds, ml_odds)
        is_value = any(vb.program_number == horse['program_number'] for vb in value_bets)

        print(
            f"#{horse['program_number']:<4} "
            f"{horse['name']:<20} "
            f"{horse['rank']:<6} "
            f"{horse['probability']*100:5.1f}%  "
            f"{fair_odds:5.1f}-1  "
            f"{ml_odds:5.1f}-1  "
            f"{edge*100:+6.1f}%   "
            f"{'✓ YES' if is_value else '✗ NO':<10}"
        )


if __name__ == '__main__':
    demo_value_detection()
