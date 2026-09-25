"""
Probability Calculator with Odds Calibration
Implements odds compression and field size adjustments
"""

from typing import Tuple


class ProbabilityCalculator:
    """
    Calculates fair odds and probabilities with market efficiency adjustments
    """

    def __init__(self):
        # Market efficiency factors (compress odds to match market reality)
        self.BASE_EFFICIENCY = 0.75  # 25% compression for regular races
        self.STAKES_EFFICIENCY = 0.70  # 30% compression for stakes races

    def calculate_fair_odds(self, win_probability: float, field_size: int,
                           race_type: str = 'MSW') -> Tuple[float, float]:
        """
        Calculate fair odds from win probability with market adjustments

        Args:
            win_probability: Raw win probability (0-1)
            field_size: Number of horses in race
            race_type: Race type (G1, G2, G3, MSW, ALW, etc.)

        Returns:
            Tuple of (fractional_odds, decimal_odds)
        """
        if win_probability <= 0:
            return 99.0, 100.0

        # Apply field size adjustment
        # Larger fields = slightly compress probabilities
        field_adjustment = 1 + (field_size - 8) * 0.02
        adjusted_prob = min(win_probability * field_adjustment, 0.95)

        # Determine efficiency factor based on race type
        if race_type in ['G1', 'G2', 'G3']:
            efficiency_factor = self.STAKES_EFFICIENCY
        else:
            efficiency_factor = self.BASE_EFFICIENCY

        # Convert to decimal odds
        decimal_odds = (1 / adjusted_prob) if adjusted_prob > 0 else 99.0

        # Convert to fractional odds and apply compression
        fractional_odds = (decimal_odds - 1) * efficiency_factor

        # Final decimal odds
        final_decimal = fractional_odds + 1

        return fractional_odds, final_decimal

    def fractional_to_decimal(self, fractional_odds: float) -> float:
        """Convert fractional odds to decimal"""
        return fractional_odds + 1

    def decimal_to_fractional(self, decimal_odds: float) -> float:
        """Convert decimal odds to fractional"""
        return max(decimal_odds - 1, 0.0)

    def probability_to_american(self, win_probability: float) -> int:
        """
        Convert probability to American odds format

        Args:
            win_probability: Win probability (0-1)

        Returns:
            American odds (negative for favorites, positive for longshots)
        """
        if win_probability <= 0:
            return 10000

        if win_probability >= 0.5:
            # Favorite (negative odds)
            american = -(win_probability / (1 - win_probability)) * 100
        else:
            # Underdog (positive odds)
            american = ((1 - win_probability) / win_probability) * 100

        return int(american)

    def calculate_overlay_percentage(self, model_probability: float,
                                    morning_line_odds: str,
                                    field_size: int = 9,
                                    race_type: str = 'MSW') -> float:
        """
        Calculate overlay percentage between model and morning line

        Args:
            model_probability: Model's win probability
            morning_line_odds: Morning line odds string (e.g. "3/1", "5-2")
            field_size: Number of horses
            race_type: Race type

        Returns:
            Overlay percentage (positive = value bet, negative = underlay)
        """
        # Parse morning line odds
        try:
            if '-' in morning_line_odds:
                num, den = morning_line_odds.split('-')
                ml_fractional = float(num) / float(den)
            elif '/' in morning_line_odds:
                num, den = morning_line_odds.split('/')
                ml_fractional = float(num) / float(den)
            else:
                # Assume it's a decimal
                ml_fractional = float(morning_line_odds)

            ml_decimal = ml_fractional + 1
            ml_probability = 1 / ml_decimal if ml_decimal > 0 else 0.01

        except:
            # Default to 5/1 if parsing fails
            ml_probability = 1 / 6.0

        # Get model's fair odds
        model_fractional, model_decimal = self.calculate_fair_odds(
            model_probability, field_size, race_type
        )
        model_fair_probability = 1 / model_decimal if model_decimal > 0 else 0

        # Calculate overlay
        # Positive = model thinks horse is better than ML suggests
        if ml_probability > 0:
            overlay_pct = ((model_fair_probability - ml_probability) / ml_probability) * 100
        else:
            overlay_pct = 0

        return overlay_pct

    def calculate_expected_value(self, win_probability: float,
                                morning_line_odds: str,
                                bet_amount: float = 1.0,
                                field_size: int = 9,
                                race_type: str = 'MSW') -> float:
        """
        Calculate expected value of a bet

        Args:
            win_probability: Model's win probability
            morning_line_odds: Odds string
            bet_amount: Amount to bet
            field_size: Number of horses
            race_type: Race type

        Returns:
            Expected value in dollars
        """
        # Parse odds to get payout
        try:
            if '-' in morning_line_odds:
                num, den = morning_line_odds.split('-')
                fractional = float(num) / float(den)
            elif '/' in morning_line_odds:
                num, den = morning_line_odds.split('/')
                fractional = float(num) / float(den)
            else:
                fractional = float(morning_line_odds)

            payout = bet_amount * (fractional + 1)  # Win bet returns stake + profit
        except:
            payout = bet_amount * 6.0  # Default 5/1

        # Get model's adjusted probability
        _, model_decimal = self.calculate_fair_odds(win_probability, field_size, race_type)
        model_prob = 1 / model_decimal if model_decimal > 0 else 0

        # EV = (probability of winning * payout) - (probability of losing * bet amount)
        ev = (model_prob * payout) - ((1 - model_prob) * bet_amount)

        return ev


def test_probability_calculator():
    """Test the probability calculator"""
    print("\n" + "="*80)
    print(" TESTING PROBABILITY CALCULATOR")
    print("="*80)

    calc = ProbabilityCalculator()

    # Test cases
    test_cases = [
        (0.20, 9, 'MSW', "Model thinks 20% chance in 9-horse maiden"),
        (0.35, 8, 'G1', "Model thinks 35% chance in 8-horse Grade I"),
        (0.10, 12, 'ALW', "Model thinks 10% chance in 12-horse allowance"),
        (0.50, 6, 'MSW', "Model thinks 50% chance in 6-horse field"),
    ]

    for prob, field, race_type, description in test_cases:
        print(f"\n{description}:")
        print(f"  Input Probability: {prob:.1%}")
        print(f"  Field Size: {field}, Race Type: {race_type}")

        frac, dec = calc.calculate_fair_odds(prob, field, race_type)
        print(f"  Fair Fractional Odds: {frac:.2f}/1")
        print(f"  Fair Decimal Odds: {dec:.2f}")

        american = calc.probability_to_american(prob)
        print(f"  American Odds: {american:+d}")

        # Test overlay calculation
        ml_odds = "3/1"
        overlay = calc.calculate_overlay_percentage(prob, ml_odds, field, race_type)
        print(f"  vs ML {ml_odds}: {overlay:+.1f}% {'OVERLAY' if overlay > 0 else 'UNDERLAY'}")

        ev = calc.calculate_expected_value(prob, ml_odds, 1.0, field, race_type)
        print(f"  Expected Value (vs ML {ml_odds}): ${ev:+.2f}")

    print("\n" + "="*80)
    print()


if __name__ == '__main__':
    test_probability_calculator()
