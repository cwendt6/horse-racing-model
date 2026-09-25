"""
Exotic Betting Strategy

Analyzes exacta, trifecta, and superfecta opportunities using
model's top picks. Exotic bets pay significantly more than win bets
but require getting multiple horses correct.

Betting Structures:
- Straight: Exact order (e.g., #3-#7 exacta)
- Box: Any order (e.g., box #3,#7 = covers #3-#7 and #7-#3)
- Wheel: Key horse with others (e.g., #3 with #1,#5,#7)
- Part Wheel: Multiple keys (e.g., #3,#7 with #1,#5,#9)
"""

from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from itertools import combinations, permutations


@dataclass
class ExoticBet:
    """Represents an exotic betting opportunity"""
    bet_type: str  # 'exacta', 'trifecta', 'superfecta'
    structure: str  # 'straight', 'box', 'wheel', 'part_wheel'
    horses: List[str]  # Program numbers
    cost: float  # Total cost of bet
    expected_hit_rate: float  # Probability of winning
    expected_payout: float  # Expected payout (average)
    expected_value: float  # EV = (hit_rate * payout) - cost
    roi: float  # Expected ROI percentage


class ExoticStrategy:
    """
    Analyzes exotic betting opportunities

    Uses model predictions to construct optimal exotic bets
    """

    def __init__(self, base_bet: float = 1.0):
        """
        Initialize exotic strategy

        Args:
            base_bet: Base bet amount (e.g., $1 exacta, $0.50 trifecta)
        """
        self.base_bet = base_bet

    def calculate_exacta_cost(
        self,
        num_horses: int,
        structure: str = 'box'
    ) -> float:
        """
        Calculate cost of exacta bet

        Args:
            num_horses: Number of horses in combination
            structure: 'straight' (1 combo) or 'box' (n*(n-1) combos)

        Returns:
            Total cost

        Example:
            >>> strategy.calculate_exacta_cost(3, 'box')
            6.0  # 3*2 = 6 combinations at $1 each
        """
        if structure == 'straight':
            return self.base_bet
        elif structure == 'box':
            # n horses boxed = n * (n-1) combinations
            return self.base_bet * num_horses * (num_horses - 1)
        elif structure == 'wheel':
            # 1 key with (n-1) others = (n-1) combinations
            return self.base_bet * (num_horses - 1)
        else:
            return self.base_bet

    def calculate_trifecta_cost(
        self,
        num_horses: int,
        structure: str = 'box'
    ) -> float:
        """
        Calculate cost of trifecta bet

        Args:
            num_horses: Number of horses in combination
            structure: 'straight' or 'box'

        Returns:
            Total cost

        Example:
            >>> strategy.calculate_trifecta_cost(4, 'box')
            24.0  # 4*3*2 = 24 combinations
        """
        if structure == 'straight':
            return self.base_bet
        elif structure == 'box':
            # n horses boxed = n * (n-1) * (n-2) combinations
            combos = num_horses * (num_horses - 1) * (num_horses - 2)
            return self.base_bet * combos
        elif structure == 'wheel':
            # 1 key with (n-1) others = (n-1) * (n-2) combinations
            combos = (num_horses - 1) * (num_horses - 2)
            return self.base_bet * combos
        else:
            return self.base_bet

    def estimate_exacta_hit_rate(
        self,
        predictions: List[Dict],
        num_selections: int = 2
    ) -> float:
        """
        Estimate probability of hitting exacta with top N picks

        Uses calibrated probabilities to estimate hit rate

        Args:
            predictions: Model predictions with 'probability' field
            num_selections: How many horses to include (2-5 typical)

        Returns:
            Estimated hit rate (0.0 to 1.0)

        Example:
            >>> # Top 2 picks: 25% and 12% win probabilities
            >>> # P(1st wins AND 2nd is 2nd) + P(2nd wins AND 1st is 2nd)
            >>> estimate_exacta_hit_rate(predictions, 2)
            0.08  # ~8% hit rate
        """
        if len(predictions) < 2 or num_selections < 2:
            return 0.0

        top_picks = predictions[:num_selections]

        # Simple approximation:
        # For exacta box with N horses, estimate as:
        # Sum of (P(horse_i wins) * P(horse_j is 2nd | horse_i wins))
        # Simplified: Sum of top 2 probabilities * 0.35
        # (assuming ~35% chance our 2nd pick finishes 2nd when our 1st wins)

        if num_selections == 2:
            # Straight exacta: P(1 wins) * P(2 is 2nd)
            p1 = top_picks[0].get('probability', 0)
            # Rough estimate: if our pick wins, 2nd pick has ~30% to be 2nd
            return p1 * 0.30
        else:
            # Box: multiple combinations
            # Rough estimate based on win probabilities
            total_prob = sum(p.get('probability', 0) for p in top_picks)
            # Hit rate roughly proportional to sum of probabilities
            # But diminishes with more horses
            return min(total_prob * 0.20, 0.50)

    def estimate_trifecta_hit_rate(
        self,
        predictions: List[Dict],
        num_selections: int = 3
    ) -> float:
        """
        Estimate probability of hitting trifecta with top N picks

        Args:
            predictions: Model predictions
            num_selections: How many horses to include (3-6 typical)

        Returns:
            Estimated hit rate

        Example:
            >>> estimate_trifecta_hit_rate(predictions, 3)
            0.05  # ~5% hit rate for 3-horse box
        """
        if len(predictions) < 3 or num_selections < 3:
            return 0.0

        top_picks = predictions[:num_selections]

        # Trifecta is harder - need top 3 correct
        # Rough approximation
        if num_selections == 3:
            # Straight tri: P(1 wins) * P(2 is 2nd) * P(3 is 3rd)
            p1 = top_picks[0].get('probability', 0)
            return p1 * 0.20  # Very rough estimate
        else:
            # Box: more combinations help
            total_prob = sum(p.get('probability', 0) for p in top_picks)
            return min(total_prob * 0.12, 0.35)

    def generate_exacta_recommendations(
        self,
        predictions: List[Dict],
        min_expected_value: float = 0.0,
        max_cost: float = 10.0
    ) -> List[ExoticBet]:
        """
        Generate exacta betting recommendations

        Tests different combinations and structures to find
        best expected value

        Args:
            predictions: Model predictions with probabilities
            min_expected_value: Minimum EV to recommend
            max_cost: Maximum bet cost

        Returns:
            List of recommended ExoticBet objects

        Example:
            >>> recommendations = strategy.generate_exacta_recommendations(predictions)
            >>> recommendations[0].bet_type
            'exacta'
            >>> recommendations[0].structure
            'box'
            >>> recommendations[0].cost
            6.0
        """
        recommendations = []

        if len(predictions) < 2:
            return recommendations

        # Test different combinations
        for num_horses in [2, 3, 4, 5]:
            if len(predictions) < num_horses:
                break

            # Box bet
            cost_box = self.calculate_exacta_cost(num_horses, 'box')
            if cost_box <= max_cost:
                hit_rate = self.estimate_exacta_hit_rate(predictions, num_horses)

                # Estimate average exacta payout
                # Typical exacta with favorites: $20-$80
                # With longer shots: $100-$300+
                # Use average odds of top picks
                avg_odds = sum(p.get('fair_odds', 5.0) for p in predictions[:num_horses]) / num_horses
                estimated_payout = avg_odds * 15.0  # Rule of thumb

                ev = (hit_rate * estimated_payout) - cost_box
                roi = (ev / cost_box * 100) if cost_box > 0 else 0

                if ev >= min_expected_value:
                    bet = ExoticBet(
                        bet_type='exacta',
                        structure='box',
                        horses=[p['program_number'] for p in predictions[:num_horses]],
                        cost=cost_box,
                        expected_hit_rate=hit_rate,
                        expected_payout=estimated_payout,
                        expected_value=ev,
                        roi=roi
                    )
                    recommendations.append(bet)

        # Sort by EV descending
        recommendations.sort(key=lambda x: x.expected_value, reverse=True)

        return recommendations

    def generate_trifecta_recommendations(
        self,
        predictions: List[Dict],
        min_expected_value: float = 0.0,
        max_cost: float = 20.0
    ) -> List[ExoticBet]:
        """
        Generate trifecta betting recommendations

        Args:
            predictions: Model predictions
            min_expected_value: Minimum EV to recommend
            max_cost: Maximum bet cost

        Returns:
            List of recommended ExoticBet objects
        """
        recommendations = []

        if len(predictions) < 3:
            return recommendations

        # Test different combinations
        for num_horses in [3, 4, 5, 6]:
            if len(predictions) < num_horses:
                break

            # Box bet
            cost_box = self.calculate_trifecta_cost(num_horses, 'box')
            if cost_box <= max_cost:
                hit_rate = self.estimate_trifecta_hit_rate(predictions, num_horses)

                # Estimate average trifecta payout
                # Trifectas typically pay 3-5x more than exactas
                avg_odds = sum(p.get('fair_odds', 5.0) for p in predictions[:num_horses]) / num_horses
                estimated_payout = avg_odds * 50.0  # Higher than exacta

                ev = (hit_rate * estimated_payout) - cost_box
                roi = (ev / cost_box * 100) if cost_box > 0 else 0

                if ev >= min_expected_value:
                    bet = ExoticBet(
                        bet_type='trifecta',
                        structure='box',
                        horses=[p['program_number'] for p in predictions[:num_horses]],
                        cost=cost_box,
                        expected_hit_rate=hit_rate,
                        expected_payout=estimated_payout,
                        expected_value=ev,
                        roi=roi
                    )
                    recommendations.append(bet)

        recommendations.sort(key=lambda x: x.expected_value, reverse=True)

        return recommendations

    def format_exotic_bet(self, bet: ExoticBet) -> str:
        """
        Format exotic bet as readable string

        Args:
            bet: ExoticBet object

        Returns:
            Formatted string

        Example:
            >>> format_exotic_bet(bet)
            'Exacta Box: #3, #7, #1 ($6.00)'
        """
        horses_str = ', '.join(f"#{h}" for h in bet.horses)
        return f"{bet.bet_type.title()} {bet.structure.title()}: {horses_str} (${bet.cost:.2f})"

    def generate_betting_ticket(
        self,
        predictions: List[Dict],
        race_number: int,
        budget: float = 20.0
    ) -> Dict:
        """
        Generate complete betting ticket for a race

        Includes both exacta and trifecta recommendations
        within budget

        Args:
            predictions: Model predictions with probabilities
            race_number: Race number
            budget: Total budget for exotic bets

        Returns:
            Dict with recommendations and analysis

        Example:
            >>> ticket = strategy.generate_betting_ticket(predictions, 5, 20.0)
            >>> ticket['total_cost']
            18.0
            >>> ticket['expected_return']
            23.50
        """
        # Allocate budget: 60% exacta, 40% trifecta (typical split)
        exacta_budget = budget * 0.60
        trifecta_budget = budget * 0.40

        # Generate recommendations
        exacta_recs = self.generate_exacta_recommendations(
            predictions,
            min_expected_value=-5.0,  # Allow some negative EV for coverage
            max_cost=exacta_budget
        )

        trifecta_recs = self.generate_trifecta_recommendations(
            predictions,
            min_expected_value=-5.0,
            max_cost=trifecta_budget
        )

        # Select best from each
        best_exacta = exacta_recs[0] if exacta_recs else None
        best_trifecta = trifecta_recs[0] if trifecta_recs else None

        # Build ticket
        ticket = {
            'race_number': race_number,
            'budget': budget,
            'exacta': None,
            'trifecta': None,
            'total_cost': 0.0,
            'expected_return': 0.0,
            'expected_profit': 0.0,
        }

        if best_exacta:
            ticket['exacta'] = {
                'bet': self.format_exotic_bet(best_exacta),
                'horses': best_exacta.horses,
                'cost': best_exacta.cost,
                'hit_rate': best_exacta.expected_hit_rate,
                'ev': best_exacta.expected_value,
            }
            ticket['total_cost'] += best_exacta.cost
            ticket['expected_return'] += best_exacta.expected_hit_rate * best_exacta.expected_payout

        if best_trifecta:
            ticket['trifecta'] = {
                'bet': self.format_exotic_bet(best_trifecta),
                'horses': best_trifecta.horses,
                'cost': best_trifecta.cost,
                'hit_rate': best_trifecta.expected_hit_rate,
                'ev': best_trifecta.expected_value,
            }
            ticket['total_cost'] += best_trifecta.cost
            ticket['expected_return'] += best_trifecta.expected_hit_rate * best_trifecta.expected_payout

        ticket['expected_profit'] = ticket['expected_return'] - ticket['total_cost']

        return ticket


def demo_exotic_strategy():
    """Demonstrate exotic betting strategy"""
    strategy = ExoticStrategy(base_bet=1.0)

    # Sample race predictions
    sample_predictions = [
        {'program_number': '3', 'name': 'Fast Horse', 'rank': 1, 'probability': 0.28, 'fair_odds': 2.6},
        {'program_number': '7', 'name': 'Second Best', 'rank': 2, 'probability': 0.15, 'fair_odds': 5.7},
        {'program_number': '1', 'name': 'Third Pick', 'rank': 3, 'probability': 0.12, 'fair_odds': 7.3},
        {'program_number': '5', 'name': 'Fourth Choice', 'rank': 4, 'probability': 0.10, 'fair_odds': 9.0},
    ]

    print('='*80)
    print(' EXOTIC BETTING STRATEGY DEMO')
    print('='*80)
    print()

    # Generate recommendations
    print('EXACTA RECOMMENDATIONS:')
    print('-'*80)
    exacta_recs = strategy.generate_exacta_recommendations(sample_predictions, max_cost=10.0)

    for i, bet in enumerate(exacta_recs[:3], 1):
        print(f"{i}. {strategy.format_exotic_bet(bet)}")
        print(f"   Hit Rate: {bet.expected_hit_rate*100:.1f}%")
        print(f"   Expected Payout: ${bet.expected_payout:.2f}")
        print(f"   Expected Value: ${bet.expected_value:+.2f}")
        print(f"   ROI: {bet.roi:+.1f}%")
        print()

    print('TRIFECTA RECOMMENDATIONS:')
    print('-'*80)
    trifecta_recs = strategy.generate_trifecta_recommendations(sample_predictions, max_cost=20.0)

    for i, bet in enumerate(trifecta_recs[:3], 1):
        print(f"{i}. {strategy.format_exotic_bet(bet)}")
        print(f"   Hit Rate: {bet.expected_hit_rate*100:.1f}%")
        print(f"   Expected Payout: ${bet.expected_payout:.2f}")
        print(f"   Expected Value: ${bet.expected_value:+.2f}")
        print(f"   ROI: {bet.roi:+.1f}%")
        print()

    # Generate complete ticket
    print('='*80)
    print(' RECOMMENDED BETTING TICKET - Race 5')
    print('='*80)
    print()

    ticket = strategy.generate_betting_ticket(sample_predictions, race_number=5, budget=20.0)

    if ticket['exacta']:
        print(f"EXACTA: {ticket['exacta']['bet']}")
        print(f"  Cost: ${ticket['exacta']['cost']:.2f}")
        print(f"  Hit Rate: {ticket['exacta']['hit_rate']*100:.1f}%")
        print()

    if ticket['trifecta']:
        print(f"TRIFECTA: {ticket['trifecta']['bet']}")
        print(f"  Cost: ${ticket['trifecta']['cost']:.2f}")
        print(f"  Hit Rate: {ticket['trifecta']['hit_rate']*100:.1f}%")
        print()

    print('-'*80)
    print(f"TOTAL COST: ${ticket['total_cost']:.2f}")
    print(f"EXPECTED RETURN: ${ticket['expected_return']:.2f}")
    print(f"EXPECTED PROFIT: ${ticket['expected_profit']:+.2f}")
    print(f"EXPECTED ROI: {(ticket['expected_profit']/ticket['total_cost']*100):+.1f}%")
    print('='*80)


if __name__ == '__main__':
    demo_exotic_strategy()
