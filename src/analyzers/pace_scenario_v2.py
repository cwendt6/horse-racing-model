"""
PACE SCENARIO V2 - Enhanced Pace Calculation
===============================================

Based on analysis of October 22, 2025 results where manual handicapping achieved:
- 42.9% win rate (3/7)
- 316.6% ROI
- 85.7% pace prediction accuracy (6/7)

While the model achieved:
- 0% win rate (0/8)
- 0% pace prediction accuracy (0/8)
- Catastrophic failure picking speed in speed duels

KEY IMPROVEMENTS:
1. Granular speed horse counting (not PPI abstract index)
2. Distinguish E (early speed) from EP (tactical presser)
3. Weight speed horses by quality (Beyer figures)
4. Clear rules: 3+ speed horses in sprint = HOT PACE
5. Stronger pace/style interaction multipliers
6. Distance-specific logic (sprints vs routes)

Author: Generated from Oct 22, 2025 post-mortem analysis
Date: October 22, 2025
"""

from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from enum import Enum


class PaceScenarioType(Enum):
    """Pace scenario classifications"""
    HOT_PACE = "HOT_PACE"           # Speed duel expected - closers benefit
    HONEST_PACE = "HONEST_PACE"     # Fair pace - no major advantage
    SLOW_PACE = "SLOW_PACE"         # Lone/no speed - tactical speed benefits
    MODERATE_PACE = "MODERATE_PACE" # Moderate pressure


class RunningStyleDetailed(Enum):
    """Detailed running style classifications"""
    E = "E"     # Pure Early Speed - on lead from gate
    EP = "EP"   # Tactical Speed/Early Presser - 2-3 wide, not on lead
    P = "P"     # Mid-Pack Presser - stalks 4-5 lengths back
    S = "S"     # Sustained Closer - comes from well back


@dataclass
class HorsePaceProfile:
    """Pace profile for a single horse"""
    name: str
    program_number: str
    running_style: str  # E, EP, P, or S
    best_beyer: float   # Best speed figure (for quality weighting)
    avg_early_position: float  # Average position at first call


@dataclass
class PaceScenarioV2:
    """Enhanced pace scenario analysis"""
    scenario_type: PaceScenarioType
    pace_pressure_score: float  # 0-100 scale
    early_speed_count: int      # Number of E horses
    tactical_speed_count: int   # Number of EP horses
    presser_count: int          # Number of P horses
    closer_count: int           # Number of S horses
    speed_quality_ratio: float  # Quality of speed horses vs field average

    # Explanations
    scenario_explanation: str
    pace_description: str

    # Advantage horses
    advantage_style: Optional[str]  # Which style has advantage (E, EP, P, S)
    advantage_horses: List[str]     # Horse names with pace advantage

    # Multipliers for scoring
    style_multipliers: Dict[str, float]  # Multiplier for each running style


class PaceScenarioCalculatorV2:
    """
    Enhanced pace scenario calculator using granular speed horse counting

    Based on manual handicapping methodology that achieved 85.7% accuracy
    """

    def __init__(self):
        # Pace multipliers by scenario and style
        # Based on Oct 22 empirical results
        self.pace_multipliers = {
            PaceScenarioType.HOT_PACE: {
                'E': 0.70,   # Pure early speed vulnerable in duel (-30%)
                'EP': 1.30,  # Tactical speed benefits from position (+30%)
                'P': 1.25,   # Pressers can pick up pieces (+25%)
                'S': 1.45,   # Closers benefit most from pace collapse (+45%)
            },
            PaceScenarioType.HONEST_PACE: {
                'E': 1.00,   # Neutral
                'EP': 1.10,  # Slight advantage for tactical (+10%)
                'P': 1.05,   # Slight advantage (+5%)
                'S': 0.95,   # Slight disadvantage (-5%)
            },
            PaceScenarioType.SLOW_PACE: {
                'E': 1.40,   # Major advantage with uncontested lead (+40%)
                'EP': 1.25,  # Tactical speed benefits (+25%)
                'P': 1.05,   # Slight advantage (+5%)
                'S': 0.75,   # Major disadvantage - too much ground (-25%)
            },
            PaceScenarioType.MODERATE_PACE: {
                'E': 1.10,   # Slight advantage (+10%)
                'EP': 1.15,  # Good positioning (+15%)
                'P': 1.10,   # Good positioning (+10%)
                'S': 1.00,   # Neutral
            },
        }

    def classify_running_style(self, style_code: str) -> str:
        """
        Normalize running style to E, EP, P, or S

        Args:
            style_code: Running style code (various formats)

        Returns:
            Normalized code: E, EP, P, or S
        """
        if not style_code:
            return 'P'  # Default to presser

        style_upper = str(style_code).upper().strip()

        # Map various formats to standard codes
        if style_upper in ['E', 'EARLY', 'FRONT', 'LEADER']:
            return 'E'
        elif style_upper in ['EP', 'TACTICAL', 'PRESSER_EARLY']:
            return 'EP'
        elif style_upper in ['P', 'PRESS', 'PRESSER', 'STALKER', 'STALK']:
            return 'P'
        elif style_upper in ['S', 'C', 'CLOSE', 'CLOSER', 'SUSTAINED']:
            return 'S'
        else:
            return 'P'  # Default

    def calculate_pace_scenario(
        self,
        horses: List[HorsePaceProfile],
        distance_furlongs: float,
        surface: str = 'dirt'
    ) -> PaceScenarioV2:
        """
        Calculate pace scenario using granular speed horse counting

        This is the CORE FIX that addresses the model's 0/8 pace accuracy

        Args:
            horses: List of horse pace profiles
            distance_furlongs: Race distance in furlongs
            surface: 'dirt', 'turf', or 'synthetic'

        Returns:
            PaceScenarioV2 object with complete analysis
        """

        # Step 1: Categorize horses by running style
        early_speed_horses = []  # E - pure early speed
        tactical_horses = []     # EP - tactical/presser early
        presser_horses = []      # P - mid-pack
        closer_horses = []       # S - sustained closers

        for horse in horses:
            style = self.classify_running_style(horse.running_style)

            profile_data = {
                'name': horse.name,
                'beyer': horse.best_beyer if horse.best_beyer else 70,  # Default
                'style': style
            }

            if style == 'E':
                early_speed_horses.append(profile_data)
            elif style == 'EP':
                tactical_horses.append(profile_data)
            elif style == 'P':
                presser_horses.append(profile_data)
            else:  # S
                closer_horses.append(profile_data)

        # Count horses by style
        early_count = len(early_speed_horses)
        tactical_count = len(tactical_horses)
        presser_count = len(presser_horses)
        closer_count = len(closer_horses)

        # Step 2: Calculate quality metrics
        total_horses = len(horses)
        if total_horses == 0:
            return self._create_default_scenario()

        # Average Beyer for entire field
        all_beyers = [h.best_beyer if h.best_beyer else 70 for h in horses]
        avg_beyer = sum(all_beyers) / len(all_beyers)

        # Average Beyer for speed horses (E + EP combined)
        speed_horses = early_speed_horses + tactical_horses
        if speed_horses:
            speed_beyers = [h['beyer'] for h in speed_horses]
            avg_speed_beyer = sum(speed_beyers) / len(speed_beyers)
            quality_ratio = avg_speed_beyer / avg_beyer if avg_beyer > 0 else 1.0
        else:
            quality_ratio = 0.0

        # Step 3: Determine distance category
        is_sprint = distance_furlongs <= 7.0   # 7F or less
        is_route = distance_furlongs >= 9.0     # 9F or more
        is_middle = not is_sprint and not is_route  # 7F-9F

        # Step 4: Apply pace classification rules
        # CRITICAL: This is where we fix the model's pace prediction

        scenario_type, explanation, advantage_style = self._classify_pace_scenario(
            early_count, tactical_count, presser_count, closer_count,
            quality_ratio, is_sprint, is_middle, is_route
        )

        # Step 5: Calculate pace pressure score (0-100)
        pressure_score = self._calculate_pressure_score(
            early_count, tactical_count, quality_ratio,
            is_sprint, is_middle, is_route
        )

        # Step 6: Identify advantage horses
        advantage_horses = self._identify_advantage_horses(
            scenario_type, advantage_style,
            early_speed_horses, tactical_horses, presser_horses, closer_horses
        )

        # Step 7: Get style multipliers for this scenario
        style_multipliers = self.pace_multipliers[scenario_type]

        # Step 8: Create pace description
        pace_description = self._create_pace_description(
            scenario_type, early_count, tactical_count,
            pressure_score, quality_ratio, distance_furlongs
        )

        return PaceScenarioV2(
            scenario_type=scenario_type,
            pace_pressure_score=pressure_score,
            early_speed_count=early_count,
            tactical_speed_count=tactical_count,
            presser_count=presser_count,
            closer_count=closer_count,
            speed_quality_ratio=quality_ratio,
            scenario_explanation=explanation,
            pace_description=pace_description,
            advantage_style=advantage_style,
            advantage_horses=advantage_horses,
            style_multipliers=style_multipliers
        )

    def _classify_pace_scenario(
        self,
        early_count: int,
        tactical_count: int,
        presser_count: int,
        closer_count: int,
        quality_ratio: float,
        is_sprint: bool,
        is_middle: bool,
        is_route: bool
    ) -> Tuple[PaceScenarioType, str, Optional[str]]:
        """
        Classify pace scenario based on counts and quality

        Returns:
            Tuple of (scenario_type, explanation, advantage_style)
        """

        # SPRINT LOGIC (≤7F) - Speed matters most
        if is_sprint:
            total_speed = early_count + tactical_count

            # CRITICAL RULE: 3+ speed horses in sprint = HOT PACE
            if total_speed >= 3:
                if quality_ratio > 1.1:
                    return (
                        PaceScenarioType.HOT_PACE,
                        f"Speed duel: {total_speed} speed horses ({early_count}E + {tactical_count}EP) "
                        f"with {quality_ratio:.2f}x quality - closers benefit",
                        'S'  # Closers have advantage
                    )
                else:
                    return (
                        PaceScenarioType.HOT_PACE,
                        f"Speed duel: {total_speed} speed horses, moderate quality",
                        'S'
                    )

            # 2 speed horses - depends on quality
            elif total_speed == 2:
                if quality_ratio > 1.15:
                    return (
                        PaceScenarioType.HOT_PACE,
                        f"2 quality speed horses (ratio {quality_ratio:.2f}) will battle",
                        'S'
                    )
                else:
                    return (
                        PaceScenarioType.HONEST_PACE,
                        "2 speed horses, moderate pace expected",
                        None
                    )

            # 1 or 0 speed horses - slow/uncontested
            elif total_speed <= 1:
                if total_speed == 1:
                    return (
                        PaceScenarioType.SLOW_PACE,
                        "Lone speed - uncontested lead likely",
                        'E' if early_count == 1 else 'EP'
                    )
                else:
                    return (
                        PaceScenarioType.SLOW_PACE,
                        "No clear speed - chaotic early pace",
                        'EP'  # Tactical speed can control
                    )

            else:
                return (
                    PaceScenarioType.HONEST_PACE,
                    "Balanced sprint pace",
                    None
                )

        # ROUTE LOGIC (≥9F) - Less likely to sustain speed duel
        elif is_route:
            total_speed = early_count + tactical_count

            if total_speed >= 3 and quality_ratio > 1.2:
                return (
                    PaceScenarioType.HONEST_PACE,
                    f"Contested route: {total_speed} speed horses, but distance limits pressure",
                    'P'  # Pressers benefit in routes
                )
            elif total_speed >= 2:
                return (
                    PaceScenarioType.HONEST_PACE,
                    "Moderate route pace",
                    None
                )
            elif total_speed <= 1:
                return (
                    PaceScenarioType.SLOW_PACE,
                    "Slow route pace (little speed)",
                    'EP'
                )
            else:
                return (
                    PaceScenarioType.HONEST_PACE,
                    "Standard route pace",
                    None
                )

        # MIDDLE DISTANCE LOGIC (7F-9F)
        else:
            total_speed = early_count + tactical_count

            if total_speed >= 3 and quality_ratio > 1.15:
                return (
                    PaceScenarioType.HOT_PACE,
                    f"Multiple quality speedsters at middle distance",
                    'S'
                )
            elif total_speed >= 2 and quality_ratio > 1.1:
                return (
                    PaceScenarioType.HONEST_PACE,
                    "Contested middle distance",
                    'EP'
                )
            elif total_speed <= 1:
                return (
                    PaceScenarioType.SLOW_PACE,
                    "Uncontested middle distance pace",
                    'EP'
                )
            else:
                return (
                    PaceScenarioType.MODERATE_PACE,
                    "Moderate middle distance pace",
                    None
                )

    def _calculate_pressure_score(
        self,
        early_count: int,
        tactical_count: int,
        quality_ratio: float,
        is_sprint: bool,
        is_middle: bool,
        is_route: bool
    ) -> float:
        """
        Calculate pace pressure score (0-100 scale)

        Higher score = more pressure on leaders
        """
        total_speed = early_count + tactical_count

        # Base score from count
        base_score = total_speed * 20  # 0-100+ range

        # Adjust for quality
        quality_adjustment = (quality_ratio - 1.0) * 30  # Can add/subtract up to 30

        # Adjust for distance
        if is_sprint:
            distance_multiplier = 1.2  # Sprints intensify pressure
        elif is_route:
            distance_multiplier = 0.8  # Routes reduce pressure
        else:
            distance_multiplier = 1.0

        score = (base_score + quality_adjustment) * distance_multiplier

        # Clamp to 0-100
        return max(0.0, min(100.0, score))

    def _identify_advantage_horses(
        self,
        scenario_type: PaceScenarioType,
        advantage_style: Optional[str],
        early_speed_horses: List[Dict],
        tactical_horses: List[Dict],
        presser_horses: List[Dict],
        closer_horses: List[Dict]
    ) -> List[str]:
        """Identify horses with pace advantage"""

        if not advantage_style:
            return []

        # Map style to horse list
        style_map = {
            'E': early_speed_horses,
            'EP': tactical_horses,
            'P': presser_horses,
            'S': closer_horses
        }

        horses_with_advantage = style_map.get(advantage_style, [])

        # Return top 3 by quality (Beyer)
        sorted_horses = sorted(horses_with_advantage, key=lambda x: x['beyer'], reverse=True)
        return [h['name'] for h in sorted_horses[:3]]

    def _create_pace_description(
        self,
        scenario_type: PaceScenarioType,
        early_count: int,
        tactical_count: int,
        pressure_score: float,
        quality_ratio: float,
        distance_furlongs: float
    ) -> str:
        """Create human-readable pace description"""

        total_speed = early_count + tactical_count
        distance_desc = f"{distance_furlongs:.1f}F"

        if scenario_type == PaceScenarioType.HOT_PACE:
            return (
                f"🔥 HOT PACE at {distance_desc}: "
                f"{total_speed} speed horses ({early_count} pure early, {tactical_count} tactical) "
                f"will battle early. Quality ratio {quality_ratio:.2f}. "
                f"Pressure score: {pressure_score:.0f}/100. "
                f"Closers and tactical speed have major advantage."
            )
        elif scenario_type == PaceScenarioType.SLOW_PACE:
            return (
                f"🐌 SLOW PACE at {distance_desc}: "
                f"Only {total_speed} speed horse(s). "
                f"Uncontested or slow early fractions likely. "
                f"Early speed and tactical pressers have advantage."
            )
        elif scenario_type == PaceScenarioType.HONEST_PACE:
            return (
                f"⚖️ HONEST PACE at {distance_desc}: "
                f"{total_speed} speed horses create balanced pressure. "
                f"Fair race for all running styles. No major advantage."
            )
        else:  # MODERATE
            return (
                f"➡️ MODERATE PACE at {distance_desc}: "
                f"{total_speed} speed horses, moderate pressure. "
                f"Tactical speed and pressers have slight edge."
            )

    def _create_default_scenario(self) -> PaceScenarioV2:
        """Create default scenario when no horses available"""
        return PaceScenarioV2(
            scenario_type=PaceScenarioType.HONEST_PACE,
            pace_pressure_score=50.0,
            early_speed_count=0,
            tactical_speed_count=0,
            presser_count=0,
            closer_count=0,
            speed_quality_ratio=1.0,
            scenario_explanation="No horses available for analysis",
            pace_description="Default honest pace scenario",
            advantage_style=None,
            advantage_horses=[],
            style_multipliers={'E': 1.0, 'EP': 1.0, 'P': 1.0, 'S': 1.0}
        )

    def get_style_multiplier(self, scenario: PaceScenarioV2, horse_style: str) -> float:
        """
        Get pace multiplier for a specific horse's running style

        Args:
            scenario: PaceScenarioV2 object
            horse_style: Running style code (E, EP, P, S)

        Returns:
            Multiplier to apply to horse's score (e.g., 1.30 = +30% boost)
        """
        normalized_style = self.classify_running_style(horse_style)
        return scenario.style_multipliers.get(normalized_style, 1.0)

    def format_scenario_report(self, scenario: PaceScenarioV2) -> str:
        """Format pace scenario for display"""

        report = []
        report.append("\n" + "="*80)
        report.append(" PACE SCENARIO ANALYSIS V2")
        report.append("="*80)

        report.append(f"\n{scenario.pace_description}")
        report.append(f"\nScenario: {scenario.scenario_type.value}")
        report.append(f"Pressure Score: {scenario.pace_pressure_score:.1f}/100")

        report.append(f"\nHorse Distribution:")
        report.append(f"  Early Speed (E):  {scenario.early_speed_count} horses")
        report.append(f"  Tactical (EP):    {scenario.tactical_speed_count} horses")
        report.append(f"  Pressers (P):     {scenario.presser_count} horses")
        report.append(f"  Closers (S):      {scenario.closer_count} horses")

        report.append(f"\nSpeed Quality Ratio: {scenario.speed_quality_ratio:.2f}x")
        report.append(f"  (Speed horses' avg Beyer vs field average)")

        if scenario.advantage_horses:
            report.append(f"\n🎯 Pace Advantage ({scenario.advantage_style} style):")
            for horse in scenario.advantage_horses:
                report.append(f"  • {horse}")

        report.append(f"\nStyle Multipliers:")
        for style in ['E', 'EP', 'P', 'S']:
            mult = scenario.style_multipliers[style]
            change_pct = (mult - 1.0) * 100
            emoji = "📈" if mult > 1.05 else "📉" if mult < 0.95 else "➡️"
            report.append(f"  {emoji} {style:3s}: {mult:.2f}x ({change_pct:+.0f}%)")

        report.append("\n" + "="*80 + "\n")

        return '\n'.join(report)


# Convenience functions for quick usage

def analyze_race_pace(horses_data: List[Dict], distance_furlongs: float, surface: str = 'dirt') -> PaceScenarioV2:
    """
    Quick function to analyze pace for a race

    Args:
        horses_data: List of dicts with keys: name, program_number, running_style, best_beyer
        distance_furlongs: Race distance in furlongs
        surface: 'dirt', 'turf', or 'synthetic'

    Returns:
        PaceScenarioV2 object
    """
    # Convert to HorsePaceProfile objects
    horses = []
    for h in horses_data:
        profile = HorsePaceProfile(
            name=h.get('name', 'Unknown'),
            program_number=h.get('program_number', '?'),
            running_style=h.get('running_style', 'P'),
            best_beyer=h.get('best_beyer', 70.0),
            avg_early_position=h.get('avg_early_position', 5.0)
        )
        horses.append(profile)

    calculator = PaceScenarioCalculatorV2()
    return calculator.calculate_pace_scenario(horses, distance_furlongs, surface)


def get_pace_multiplier(scenario: PaceScenarioV2, horse_style: str) -> float:
    """
    Get pace multiplier for a horse given pace scenario

    Args:
        scenario: PaceScenarioV2 object
        horse_style: Running style (E, EP, P, S)

    Returns:
        Multiplier for score adjustment
    """
    calculator = PaceScenarioCalculatorV2()
    return calculator.get_style_multiplier(scenario, horse_style)
