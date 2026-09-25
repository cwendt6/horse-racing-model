"""
Pace Analyzer Module
Analyzes race pace scenarios and identifies horses with pace advantages
"""

from typing import List, Dict, Tuple
from dataclasses import dataclass


@dataclass
class PaceScenario:
    """Pace scenario for a race"""
    scenario_type: str  # LONE_SPEED, SPEED_DUEL, HONEST_PACE
    early_speed_count: int
    presser_count: int
    closer_count: int
    projected_fractions: List[float]
    advantage_horses: List[str]
    pace_description: str


class PaceAnalyzer:
    """
    Analyzes pace scenarios for races

    Identifies:
    - Lone speed scenarios (1 early speed horse)
    - Speed duels (3+ early speed horses)
    - Honest pace (2 early speed horses)
    - Pace advantages for specific horses
    """

    def __init__(self):
        # Distance-specific average pace fractions (in seconds)
        # These are baseline averages for Keeneland dirt races
        self.baseline_fractions = {
            # Sprint distances
            5.0: [22.0, 45.5],           # 5 furlongs
            5.5: [22.2, 45.8, 58.2],     # 5.5 furlongs
            6.0: [22.4, 46.0, 1*60+10.5], # 6 furlongs
            6.5: [22.6, 46.2, 1*60+11.0, 1*60+23.5], # 6.5 furlongs
            7.0: [23.0, 46.5, 1*60+11.5, 1*60+24.0], # 7 furlongs

            # Route distances
            8.0: [23.5, 47.0, 1*60+11.0, 1*60+35.0], # 1 mile
            8.5: [24.0, 48.0, 1*60+12.0, 1*60+37.0, 1*60+50.0], # 8.5F
            9.0: [24.5, 49.0, 1*60+13.5, 1*60+38.5, 1*60+52.0], # 1 1/16 miles
            10.0: [25.0, 50.0, 1*60+15.0, 1*60+40.0, 2*60+5.0], # 1 1/8 miles
        }

    def classify_running_style_simple(self, running_style: str) -> str:
        """
        Classify horse into pace category

        Args:
            running_style: E, P, S, C (Early, Presser, Stalker, Closer)

        Returns:
            'E' (early speed), 'P' (presser), 'S' (stalker), or 'C' (closer)
        """
        if running_style in ['E']:
            return 'E'
        elif running_style in ['P']:
            return 'P'
        elif running_style in ['S']:
            return 'S'
        elif running_style in ['C']:
            return 'C'
        else:  # Default to presser
            return 'P'

    def analyze_pace(self, horses: List[Dict], distance_furlongs: float,
                     surface: str = 'D') -> PaceScenario:
        """
        Analyze pace scenario for a race

        Args:
            horses: List of horse dicts with running_style
            distance_furlongs: Race distance in furlongs
            surface: D (dirt) or T (turf)

        Returns:
            PaceScenario object
        """
        # Count horses by running style (4 categories: E, P, S, C)
        early_speed_horses = []
        presser_horses = []
        stalker_horses = []
        closer_horses = []

        for horse in horses:
            running_style = horse.get('running_style', 'P')
            pace_type = self.classify_running_style_simple(running_style)

            if pace_type == 'E':
                early_speed_horses.append(horse['name'])
            elif pace_type == 'P':
                presser_horses.append(horse['name'])
            elif pace_type == 'S':
                stalker_horses.append(horse['name'])
            else:  # C
                closer_horses.append(horse['name'])

        early_count = len(early_speed_horses)
        presser_count = len(presser_horses)
        # Combine stalkers + closers for pace scenario counting (for backwards compatibility)
        closer_count = len(stalker_horses) + len(closer_horses)

        # Determine pace scenario
        if early_count == 0:
            scenario_type = "NO_SPEED"
            pace_desc = "No clear early speed - chaotic pace likely"
            advantage_horses = presser_horses[:1] if presser_horses else []

        elif early_count == 1:
            scenario_type = "LONE_SPEED"
            pace_desc = f"Lone speed scenario - {early_speed_horses[0]} uncontested (no proven advantage)"
            advantage_horses = []  # Backtest showed no advantage - don't favor lone speed

        elif early_count == 2:
            scenario_type = "HONEST_PACE"
            pace_desc = "Honest pace with two speed horses - likely fair fractions"
            advantage_horses = []

        elif early_count >= 3:
            scenario_type = "SPEED_DUEL"
            pace_desc = f"Speed duel with {early_count} early runners - benefits closers"
            # Include both stalkers and closers in speed duel advantage
            advantage_horses = stalker_horses + closer_horses

        else:
            scenario_type = "UNKNOWN"
            pace_desc = "Unknown pace scenario"
            advantage_horses = []

        # Get projected fractions (baseline for now)
        projected_fractions = self.get_projected_fractions(
            distance_furlongs, early_count, surface
        )

        return PaceScenario(
            scenario_type=scenario_type,
            early_speed_count=early_count,
            presser_count=presser_count,
            closer_count=closer_count,
            projected_fractions=projected_fractions,
            advantage_horses=advantage_horses,
            pace_description=pace_desc
        )

    def get_projected_fractions(self, distance_furlongs: float,
                                early_speed_count: int, surface: str) -> List[float]:
        """
        Calculate projected fractional times

        Args:
            distance_furlongs: Race distance
            early_speed_count: Number of early speed horses
            surface: D or T

        Returns:
            List of projected fractional times
        """
        # Round to nearest half furlong for lookup
        lookup_distance = round(distance_furlongs * 2) / 2

        baseline = self.baseline_fractions.get(lookup_distance, [46.0])

        if not baseline:
            return [46.0]  # Default if distance not found

        # Adjust based on early speed count
        if early_speed_count == 0:
            # Slower early, faster late
            adjustment = 0.5
        elif early_speed_count == 1:
            # Moderate pace
            adjustment = -0.3
        elif early_speed_count >= 3:
            # Fast early, slow late
            adjustment = -0.8
        else:
            # Honest pace
            adjustment = 0.0

        # Apply adjustment to early fractions only
        adjusted = [baseline[0] + adjustment]
        adjusted.extend(baseline[1:])

        return adjusted

    def calculate_pace_multiplier(self, horse_name: str, running_style: str,
                                   pace_scenario: PaceScenario) -> Tuple[float, str]:
        """
        Calculate pace advantage multiplier for a horse

        Args:
            horse_name: Name of horse
            running_style: E, P, or S
            pace_scenario: PaceScenario for the race

        Returns:
            Tuple of (multiplier, explanation)
        """
        multiplier = 1.0
        explanation_parts = []

        pace_type = self.classify_running_style_simple(running_style)

        if pace_scenario.scenario_type == "LONE_SPEED":
            # NOTE: October 2025 backtest showed lone E horses won 0/20 races
            # The "lone speed advantage" theory appears to be wrong in modern racing
            # Removing boost until further evidence supports it
            if horse_name in pace_scenario.advantage_horses:
                multiplier = 1.0  # NO BOOST - theory disproven by data
                explanation_parts.append("Lone speed (no boost - see backtest)")

        elif pace_scenario.scenario_type == "SPEED_DUEL":
            if pace_type == 'S':  # Closer benefits from speed duel
                multiplier = 1.15  # 15% boost for closers
                explanation_parts.append("Closer in speed duel: +15%")
            elif pace_type == 'E':  # Early speed penalized in duel
                multiplier = 0.90  # 10% penalty
                explanation_parts.append("Early speed in duel: -10%")

        elif pace_scenario.scenario_type == "NO_SPEED":
            if pace_type == 'P':  # Presser can control pace
                multiplier = 1.10  # 10% boost
                explanation_parts.append("Presser with no speed: +10%")

        elif pace_scenario.scenario_type == "HONEST_PACE":
            # No major advantages in honest pace
            explanation_parts.append("Honest pace (no advantage)")

        explanation = "; ".join(explanation_parts) if explanation_parts else "No pace adjustment"

        return multiplier, explanation

    def get_pace_report(self, pace_scenario: PaceScenario) -> str:
        """Generate human-readable pace report"""
        report = f"""
PACE ANALYSIS:
  Scenario: {pace_scenario.scenario_type}
  Early Speed Count: {pace_scenario.early_speed_count}
  Pressers: {pace_scenario.presser_count}
  Closers: {pace_scenario.closer_count}

  Description: {pace_scenario.pace_description}

  Projected Fractions: {', '.join([f'{f:.1f}' for f in pace_scenario.projected_fractions])}
"""

        if pace_scenario.advantage_horses:
            report += f"\n  Pace Advantage: {', '.join(pace_scenario.advantage_horses)}\n"

        return report


def test_pace_analyzer():
    """Test the pace analyzer"""
    print("\n" + "="*80)
    print(" TESTING PACE ANALYZER")
    print("="*80)

    analyzer = PaceAnalyzer()

    # Test case 1: Lone speed scenario
    print("\nTest 1: Lone Speed Scenario")
    print("-" * 80)
    horses = [
        {'name': 'Speed Demon', 'running_style': 'E'},
        {'name': 'Mid Pack Runner', 'running_style': 'P'},
        {'name': 'Closer One', 'running_style': 'S'},
        {'name': 'Closer Two', 'running_style': 'S'},
        {'name': 'Another Closer', 'running_style': 'S'},
    ]

    pace = analyzer.analyze_pace(horses, 6.0, 'D')
    print(analyzer.get_pace_report(pace))

    # Calculate multipliers
    for horse in horses:
        mult, expl = analyzer.calculate_pace_multiplier(
            horse['name'], horse['running_style'], pace
        )
        print(f"{horse['name']:<20} ({horse['running_style']}) → {mult:.2f}x - {expl}")

    # Test case 2: Speed duel
    print("\n" + "="*80)
    print("Test 2: Speed Duel Scenario")
    print("-" * 80)
    horses2 = [
        {'name': 'Early One', 'running_style': 'E'},
        {'name': 'Early Two', 'running_style': 'E'},
        {'name': 'Early Three', 'running_style': 'E'},
        {'name': 'Presser', 'running_style': 'P'},
        {'name': 'Closer', 'running_style': 'S'},
    ]

    pace2 = analyzer.analyze_pace(horses2, 8.0, 'D')
    print(analyzer.get_pace_report(pace2))

    for horse in horses2:
        mult, expl = analyzer.calculate_pace_multiplier(
            horse['name'], horse['running_style'], pace2
        )
        print(f"{horse['name']:<20} ({horse['running_style']}) → {mult:.2f}x - {expl}")

    # Test case 3: Honest pace
    print("\n" + "="*80)
    print("Test 3: Honest Pace Scenario")
    print("-" * 80)
    horses3 = [
        {'name': 'Early One', 'running_style': 'E'},
        {'name': 'Early Two', 'running_style': 'E'},
        {'name': 'Presser One', 'running_style': 'P'},
        {'name': 'Presser Two', 'running_style': 'P'},
        {'name': 'Closer', 'running_style': 'S'},
    ]

    pace3 = analyzer.analyze_pace(horses3, 10.0, 'D')
    print(analyzer.get_pace_report(pace3))

    for horse in horses3:
        mult, expl = analyzer.calculate_pace_multiplier(
            horse['name'], horse['running_style'], pace3
        )
        print(f"{horse['name']:<20} ({horse['running_style']}) → {mult:.2f}x - {expl}")

    print("\n" + "="*80)
    print()


if __name__ == '__main__':
    test_pace_analyzer()
