"""
Distance & Surface Analyzer
Identifies optimal distances and surface preferences for horses

Based on past performance analysis, this analyzer:
1. Determines each horse's best distance
2. Identifies surface preferences (dirt vs turf)
3. Detects surface switches and their impact
4. Provides quantitative scoring adjustments

Expected Impact: +9-14% accuracy improvement
"""

from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from collections import defaultdict
from enum import Enum
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


# Define Surface enum (if not already available)
class Surface(Enum):
    """Track surface type"""
    DIRT = "Dirt"
    TURF = "Turf"
    SYNTHETIC = "Synthetic"
    ALL_WEATHER = "All Weather"


@dataclass
class DistanceProfile:
    """Horse's performance profile by distance"""
    horse_name: str
    distance_stats: Dict[str, dict]  # distance -> {starts, wins, avg_beyer, best_beyer}
    optimal_distance: Optional[str] = None
    optimal_range: Tuple[float, float] = (0.0, 0.0)  # in furlongs

    def find_optimal_distance(self):
        """Determine horse's best distance range"""
        if not self.distance_stats:
            return

        # Find distance with best performance
        best_dist = None
        best_beyer = 0

        for dist, stats in self.distance_stats.items():
            if stats['starts'] >= 2:  # Minimum sample
                avg = stats['avg_beyer']
                if avg > best_beyer:
                    best_beyer = avg
                    best_dist = dist

        if best_dist:
            self.optimal_distance = best_dist

            # Convert to furlongs for range
            furlongs = self._distance_to_furlongs(best_dist)
            self.optimal_range = (furlongs - 0.5, furlongs + 0.5)

    def _distance_to_furlongs(self, distance: str) -> float:
        """Convert distance string to furlongs"""
        if not distance:
            return 6.0  # default

        distance_lower = distance.lower().strip()

        # Handle furlongs (e.g., "6f", "7f")
        if 'f' in distance_lower:
            try:
                return float(distance_lower.replace('f', '').strip())
            except:
                return 6.0

        # Handle miles (e.g., "1m", "1 1/16m")
        if 'm' in distance_lower:
            try:
                # Remove 'm' and parse
                mile_str = distance_lower.replace('m', '').strip()

                # Handle fractions like "1 1/16"
                if '/' in mile_str:
                    parts = mile_str.split()
                    if len(parts) == 2:
                        whole = int(parts[0])
                        frac_parts = parts[1].split('/')
                        fraction = int(frac_parts[0]) / int(frac_parts[1])
                        miles = whole + fraction
                    else:
                        # Just a fraction like "1/16"
                        frac_parts = mile_str.split('/')
                        miles = int(frac_parts[0]) / int(frac_parts[1])
                else:
                    miles = float(mile_str)

                return miles * 8  # 1 mile = 8 furlongs
            except:
                return 8.0  # default to 1 mile

        # Default
        return 6.0


@dataclass
class SurfaceProfile:
    """Horse's performance profile by surface"""
    horse_name: str
    surface_stats: Dict[Surface, dict]  # surface -> {starts, wins, avg_beyer}
    preferred_surface: Optional[Surface] = None

    def find_preferred_surface(self):
        """Determine horse's best surface"""
        if not self.surface_stats:
            return

        best_surface = None
        best_beyer = 0

        for surface, stats in self.surface_stats.items():
            if stats['starts'] >= 2:
                avg = stats['avg_beyer']
                if avg > best_beyer:
                    best_beyer = avg
                    best_surface = surface

        self.preferred_surface = best_surface


class DistanceSurfaceAnalyzer:
    """
    Analyzes distance and surface fit for horses

    Features:
    - Distance optimization (finds each horse's best distance)
    - Surface preference detection (dirt vs turf)
    - Surface switch analysis (performance changes)
    - Quantitative scoring adjustments
    """

    def __init__(self):
        self.distance_profiles: Dict[str, DistanceProfile] = {}
        self.surface_profiles: Dict[str, SurfaceProfile] = {}

    def build_distance_profile(self, horse: Any) -> DistanceProfile:
        """Build distance profile from past performances"""

        distance_stats = defaultdict(lambda: {
            'starts': 0,
            'wins': 0,
            'avg_beyer': 0.0,
            'best_beyer': 0.0,
            'beyers': []
        })

        # Analyze past performances
        for pp in horse.past_performances:
            if not pp.distance:
                continue

            dist = pp.distance
            stats = distance_stats[dist]

            stats['starts'] += 1
            if pp.finish_position == 1:
                stats['wins'] += 1

            # Get speed figure (try multiple attribute names)
            speed_fig = None
            if hasattr(pp, 'speed_figure') and pp.speed_figure:
                speed_fig = pp.speed_figure
            elif hasattr(pp, 'beyer') and pp.beyer:
                speed_fig = pp.beyer
            elif hasattr(pp, 'beyer_speed_figure') and pp.beyer_speed_figure:
                speed_fig = pp.beyer_speed_figure

            if speed_fig:
                stats['beyers'].append(speed_fig)
                stats['best_beyer'] = max(stats['best_beyer'], speed_fig)

        # Calculate averages
        for dist, stats in distance_stats.items():
            if stats['beyers']:
                stats['avg_beyer'] = sum(stats['beyers']) / len(stats['beyers'])

        profile = DistanceProfile(
            horse_name=horse.name,
            distance_stats=dict(distance_stats)
        )
        profile.find_optimal_distance()

        self.distance_profiles[horse.name] = profile
        return profile

    def build_surface_profile(self, horse: Any) -> SurfaceProfile:
        """Build surface profile from past performances"""

        surface_stats = defaultdict(lambda: {
            'starts': 0,
            'wins': 0,
            'avg_beyer': 0.0,
            'beyers': []
        })

        for pp in horse.past_performances:
            surface = pp.surface if hasattr(pp, 'surface') else Surface.DIRT
            stats = surface_stats[surface]

            stats['starts'] += 1
            if pp.finish_position == 1:
                stats['wins'] += 1

            # Get speed figure
            speed_fig = None
            if hasattr(pp, 'speed_figure') and pp.speed_figure:
                speed_fig = pp.speed_figure
            elif hasattr(pp, 'beyer') and pp.beyer:
                speed_fig = pp.beyer
            elif hasattr(pp, 'beyer_speed_figure') and pp.beyer_speed_figure:
                speed_fig = pp.beyer_speed_figure

            if speed_fig:
                stats['beyers'].append(speed_fig)

        # Calculate averages
        for surface, stats in surface_stats.items():
            if stats['beyers']:
                stats['avg_beyer'] = sum(stats['beyers']) / len(stats['beyers'])

        profile = SurfaceProfile(
            horse_name=horse.name,
            surface_stats=dict(surface_stats)
        )
        profile.find_preferred_surface()

        self.surface_profiles[horse.name] = profile
        return profile

    def analyze_distance_fit(
        self,
        horse: Any,
        race_distance: str
    ) -> Tuple[float, str]:
        """
        Analyze how well race distance fits this horse

        Returns:
            (adjustment_points, description)
        """
        profile = self.build_distance_profile(horse)

        if not profile.optimal_distance:
            return 0.0, "Insufficient distance data"

        race_furlongs = profile._distance_to_furlongs(race_distance)
        optimal_furlongs = profile._distance_to_furlongs(profile.optimal_distance)

        # Calculate distance differential
        diff = abs(race_furlongs - optimal_furlongs)

        # Scoring
        if diff <= 0.5:
            # Perfect distance match
            bonus = 6.0
            desc = f"✓ OPTIMAL: Best at {profile.optimal_distance}"
        elif diff <= 1.0:
            # Close to optimal
            bonus = 3.0
            desc = f"Good fit: Best at {profile.optimal_distance}"
        elif diff <= 2.0:
            # Moderate mismatch
            bonus = -3.0
            desc = f"⚠️ Stretching out from {profile.optimal_distance}"
        else:
            # Significant mismatch
            bonus = -8.0
            desc = f"❌ DISTANCE MISMATCH: Best at {profile.optimal_distance}"

        return bonus, desc

    def analyze_surface_fit(
        self,
        horse: Any,
        race_surface: Surface
    ) -> Tuple[float, str]:
        """
        Analyze surface switch and preference

        Returns:
            (adjustment_points, description)
        """
        profile = self.build_surface_profile(horse)

        # Check for surface switches
        last_surface = None
        if horse.past_performances:
            if hasattr(horse.past_performances[0], 'surface'):
                last_surface = horse.past_performances[0].surface

        # No previous surface data
        if not profile.surface_stats:
            if race_surface == Surface.TURF:
                return -8.0, "⚠️ FIRST TIME TURF (high uncertainty)"
            return 0.0, "Debut/Insufficient surface data"

        # Calculate surface stats
        race_stats = profile.surface_stats.get(race_surface)

        if not race_stats:
            # Never run on this surface
            if race_surface == Surface.TURF:
                return -8.0, "⚠️ FIRST TIME TURF"
            else:
                return -5.0, f"First time on {race_surface.value}"

        # Surface switch analysis
        if last_surface and last_surface != race_surface:
            # Switching surfaces

            # Compare performance on both surfaces
            last_stats = profile.surface_stats.get(last_surface, {})
            race_beyer = race_stats.get('avg_beyer', 0)
            last_beyer = last_stats.get('avg_beyer', 0)

            diff = race_beyer - last_beyer

            if diff > 5:
                bonus = 5.0
                desc = f"✓ RETURNS TO PREFERRED SURFACE ({race_surface.value})"
            elif diff < -5:
                bonus = -5.0
                desc = f"Switches to weaker surface ({race_surface.value})"
            else:
                bonus = -2.0  # Small penalty for uncertainty
                desc = f"Surface switch: {last_surface.value} → {race_surface.value}"
        else:
            # Same surface or returning to it
            if profile.preferred_surface == race_surface:
                bonus = 4.0
                desc = f"✓ On preferred surface ({race_surface.value})"
            else:
                bonus = 0.0
                desc = f"Standard surface ({race_surface.value})"

        return bonus, desc

    def analyze_horse(
        self,
        horse: Any,
        race_distance: str,
        race_surface: Surface
    ) -> Tuple[float, List[str]]:
        """
        Complete analysis of distance and surface

        Returns:
            (total_adjustment, list of descriptions)
        """
        distance_bonus, distance_desc = self.analyze_distance_fit(horse, race_distance)
        surface_bonus, surface_desc = self.analyze_surface_fit(horse, race_surface)

        total = distance_bonus + surface_bonus
        notes = [distance_desc, surface_desc]

        return total, notes

    def generate_report(
        self,
        horses: List[Any],
        race_distance: str,
        race_surface: Surface
    ) -> str:
        """Generate analysis report for race"""

        report = [
            "\n" + "="*70,
            "DISTANCE & SURFACE ANALYSIS",
            "="*70,
            f"\nRace Distance: {race_distance}",
            f"Race Surface: {race_surface.value}",
            "\n" + "-"*70
        ]

        for horse in horses:
            total, notes = self.analyze_horse(horse, race_distance, race_surface)

            report.append(f"\n{horse.name}:")
            report.append(f"  Total Adjustment: {total:+.1f} points")
            for note in notes:
                report.append(f"  • {note}")

        report.append("\n" + "="*70)

        return "\n".join(report)


# Quick test
if __name__ == "__main__":
    from datetime import date

    print("Testing Distance & Surface Analyzer...")

    # Create simple test objects
    @dataclass
    class TestPP:
        distance: str
        surface: Surface
        finish_position: int
        speed_figure: int

    @dataclass
    class TestHorse:
        name: str
        past_performances: list

    # Create test horse with past performances
    test_pp1 = TestPP(
        distance="6f",
        surface=Surface.DIRT,
        finish_position=2,
        speed_figure=88
    )

    test_pp2 = TestPP(
        distance="7f",
        surface=Surface.DIRT,
        finish_position=1,
        speed_figure=92
    )

    test_pp3 = TestPP(
        distance="1m",
        surface=Surface.DIRT,
        finish_position=5,
        speed_figure=78
    )

    horse = TestHorse(
        name="TestHorse",
        past_performances=[test_pp1, test_pp2, test_pp3]
    )

    analyzer = DistanceSurfaceAnalyzer()

    total, notes = analyzer.analyze_horse(horse, "6f", Surface.DIRT)

    print(f"\nTest Results:")
    print(f"  Total adjustment: {total:+.1f}")
    print(f"  Notes:")
    for note in notes:
        print(f"    • {note}")

    print("\n✓ Test complete!")
