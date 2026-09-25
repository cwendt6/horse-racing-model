"""
ENHANCED PACE ANALYZER - Professional Grade
Includes all features: pace figures, pressure analysis, track variants, 
actual fractional times, and track bias integration
"""

import json
import numpy as np
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from datetime import date
from enum import Enum

# Import existing models - use pace_adapter classes if available
try:
    from horse_racing_models import Horse, Race, RunningStyle, Surface, TrackBias
except ImportError:
    try:
        # Try importing from pace_adapter (which we created)
        from .pace_adapter import Horse, Race, RunningStyle
    except ImportError:
        # Last resort: define minimal versions here
        class RunningStyle(Enum):
            E = "E"
            EP = "EP"
            P = "P"
            S = "S"
            C = "C"

        # Use Any for Horse and Race to avoid type errors
        from typing import Any
        Horse = Any
        Race = Any

    # Define fallback Surface and TrackBias
    class Surface(Enum):
        DIRT = "dirt"
        TURF = "turf"
        SYNTHETIC = "synthetic"

    @dataclass
    class TrackBias:
        pace_bias: str  # "SPEED", "CLOSER", or "NEUTRAL"
        pace_bias_strength: float  # 0.0-1.0


@dataclass
class PaceFigures:
    """Pace figures for a horse"""
    early_pace_figure: float  # 0-150 scale
    late_pace_figure: float   # 0-150 scale
    combined_rating: float
    method_used: str  # "fractional_times" or "positions"
    confidence: float  # 0-1 based on data quality


@dataclass
class RacePaceAnalysis:
    """Complete pace analysis for a race"""
    pace_pressure_index: float
    projected_quarter: float
    projected_half: float
    scenario: str  # "fast", "honest", "slow"
    speed_advantage_horses: List[str]
    closer_advantage_horses: List[str]
    pressure_adjustments: Dict[str, float]
    track_bias_applied: bool = False
    track_variant_applied: bool = False


class EnhancedPaceAnalyzer:
    """
    Professional-grade pace analysis system
    
    Features:
    - Pace figures from actual fractional times or positions
    - Track variant adjustments
    - Pace pressure calculation
    - Track bias integration
    - Projected fractions
    """
    
    def __init__(self, track_variants_file: str = None, track_bias_file: str = None):
        """
        Initialize analyzer
        
        Args:
            track_variants_file: Path to track_variants.json
            track_bias_file: Path to track bias data (optional)
        """
        self.track_variants = {}
        self.track_bias_data = None
        
        # Load track variants
        if track_variants_file:
            try:
                with open(track_variants_file, 'r') as f:
                    self.track_variants = json.load(f)
            except FileNotFoundError:
                print(f"Warning: {track_variants_file} not found. Proceeding without variants.")
        
        # Par times for fractional calls (in seconds)
        self.par_fractions = {
            'dirt': {
                '6f': {'quarter': 22.0, 'half': 45.0},
                '6.5f': {'quarter': 22.2, 'half': 45.5},
                '7f': {'quarter': 22.5, 'half': 46.0},
                '1m': {'quarter': 23.0, 'half': 46.5},
                '1m70y': {'quarter': 23.0, 'half': 46.8},
                '1_1/16m': {'quarter': 23.2, 'half': 47.0},
                '1_1/8m': {'quarter': 23.5, 'half': 47.5},
            },
            'turf': {
                '1m': {'quarter': 24.0, 'half': 48.0},
                '1_1/16m': {'quarter': 24.2, 'half': 48.5},
                '1_1/8m': {'quarter': 24.5, 'half': 49.0},
            }
        }
    
    def _time_to_seconds(self, time_value) -> Optional[float]:
        """Convert time string or float to seconds"""
        if time_value is None:
            return None

        # Handle float/int directly (already in seconds from PDF parser)
        if isinstance(time_value, (int, float)):
            return float(time_value)

        # Handle string formats
        try:
            time_str = str(time_value).strip()

            # Handle formats: "22.3", ":22.3", "45.2"
            if time_str.startswith(':'):
                time_str = time_str[1:]

            # Handle minutes:seconds.fraction
            if ':' in time_str:
                parts = time_str.split(':')
                minutes = int(parts[0]) if parts[0] else 0
                seconds = float(parts[1])
                return minutes * 60 + seconds
            else:
                return float(time_str)
        except (ValueError, IndexError, AttributeError):
            return None
    
    def _get_par_fraction(self, distance, surface, call: str) -> Optional[float]:
        """Get par time for specific call (quarter or half)"""
        # Handle both Surface enum and string
        if hasattr(surface, 'value'):
            surface_key = surface.value
        else:
            surface_key = 'dirt' if 'D' in str(surface).upper() else 'turf'

        # Handle both string and int distance
        if isinstance(distance, str):
            distance_clean = distance.strip().lower().replace(' ', '')
        else:
            distance_clean = str(distance).lower()

        if distance_clean in self.par_fractions[surface_key]:
            return self.par_fractions[surface_key][distance_clean].get(call)

        return None
    
    def _get_track_variant(self, track_code: str, race_date, surface) -> float:
        """Get track variant for the day"""
        # Handle both date objects and date strings
        if hasattr(race_date, 'isoformat'):
            date_str = race_date.isoformat()
        elif isinstance(race_date, str):
            date_str = race_date
        else:
            return 0.0

        date_key = f"{track_code}_{date_str}"

        if date_key in self.track_variants:
            # Handle both Surface enum and string
            if hasattr(surface, 'value'):
                surface_key = surface.value
            else:
                surface_key = 'dirt' if 'D' in str(surface).upper() else 'turf'

            variant_data = self.track_variants[date_key].get(surface_key, {})
            return variant_data.get('variant', 0.0)

        return 0.0
    
    def calculate_early_pace_figure(
        self, 
        horse: Horse,
        track_code: str,
        race_date: date,
        surface: Surface
    ) -> PaceFigures:
        """
        Calculate pace figures using best available data
        Priority 1: Actual fractional times
        Priority 2: Position at first call
        """
        
        early_figures = []
        late_figures = []
        methods_used = []

        # Get track variant for adjustments
        track_variant = self._get_track_variant(track_code, race_date, surface)

        for pp in horse.past_performances[-3:]:  # Last 3 races
            
            # ===== EARLY PACE FIGURE =====
            # Try fractional time first (MORE ACCURATE)
            if hasattr(pp, 'first_call') and pp.first_call:
                fraction_time = self._time_to_seconds(pp.first_call)
                par_fraction = self._get_par_fraction(pp.distance, pp.surface, 'quarter')
                
                if fraction_time and par_fraction:
                    # Calculate figure: faster than par = higher
                    raw_figure = 100 + ((par_fraction - fraction_time) * 5.0)
                    
                    # Apply track variant adjustment
                    adjusted_figure = raw_figure - (track_variant * 0.5)
                    
                    early_figures.append(adjusted_figure)
                    methods_used.append("fractional_times")
                    continue
            
            # Fall back to position-based
            if hasattr(pp, 'position_first_call') and pp.position_first_call:
                position = pp.position_first_call
                position_figure = 100 - (position - 1) * 5
                early_figures.append(position_figure)
                methods_used.append("positions")
            
            # ===== LATE PACE FIGURE =====
            if (hasattr(pp, 'position_first_call') and pp.position_first_call and 
                hasattr(pp, 'finish_position') and pp.finish_position):
                
                position_gain = pp.position_first_call - pp.finish_position
                late_figure = 100 + (position_gain * 8)
                late_figures.append(late_figure)
        
        # Calculate averages
        avg_early = np.mean(early_figures) if early_figures else 50.0
        avg_late = np.mean(late_figures) if late_figures else 50.0
        
        # Apply class adjustment based on Beyer
        if horse.best_beyer:
            class_factor = horse.best_beyer / 75.0  # 75 is average
            avg_early *= class_factor
            avg_late *= class_factor
        
        # Calculate combined rating based on running style
        if horse.running_style:
            if horse.running_style == RunningStyle.E:
                combined = (avg_early * 0.8) + (avg_late * 0.2)
            elif horse.running_style == RunningStyle.EP:
                combined = (avg_early * 0.6) + (avg_late * 0.4)
            elif horse.running_style == RunningStyle.P:
                combined = (avg_early * 0.4) + (avg_late * 0.6)
            else:  # S (Closer)
                combined = (avg_early * 0.2) + (avg_late * 0.8)
        else:
            combined = (avg_early + avg_late) / 2
        
        # Determine confidence
        confidence = len(early_figures) / 3.0  # 0-1 based on sample size
        primary_method = max(set(methods_used), key=methods_used.count) if methods_used else "none"
        
        return PaceFigures(
            early_pace_figure=avg_early,
            late_pace_figure=avg_late,
            combined_rating=combined,
            method_used=primary_method,
            confidence=confidence
        )
    
    def calculate_pace_pressure_index(self, race_horses: List[Horse]) -> float:
        """
        Calculate Pace Pressure Index (PPI)

        FIXED: Option 1 - Sum ALL horses' EPFs / Field Size
        (Empirical testing showed this produces better scenario diversity than E/EP-only)

        PPI = Sum of ALL Early Pace Figures / Field Size

        Interpretation:
        - PPI < 60: Slow pace, speed advantage
        - PPI 60-90: Honest pace
        - PPI 90-120: Moderate pressure, closers edge
        - PPI > 120: Speed duel, closers major advantage
        """

        # Sum ALL horses' early pace figures (not just E/EP)
        total_epf = sum(h.pace_figures.early_pace_figure
                       for h in race_horses
                       if hasattr(h, 'pace_figures') and h.pace_figures)

        field_size = len(race_horses)

        return total_epf / field_size if field_size > 0 else 0.0
    
    def calculate_pressure_adjustments(
        self, 
        race_horses: List[Horse], 
        ppi: float
    ) -> Dict[str, float]:
        """
        Calculate score adjustments based on pace pressure
        
        Returns:
            Dict mapping horse name to adjustment points
        """
        
        adjustments = {}
        
        for horse in race_horses:
            adj = 0.0
            
            if horse.running_style == RunningStyle.E:
                # Early speed horses
                if ppi < 60:
                    adj = +15  # Huge advantage in slow pace
                elif ppi < 80:
                    adj = +5
                elif ppi < 100:
                    adj = -5
                else:
                    adj = -20  # Major disadvantage in speed duel
            
            elif horse.running_style == RunningStyle.EP:
                # Early pressers - versatile
                if ppi < 60:
                    adj = +10
                elif ppi < 80:
                    adj = +8
                elif ppi < 100:
                    adj = +5
                else:
                    adj = +3
            
            elif horse.running_style == RunningStyle.P:
                # Pressers - adapt to pace
                if ppi < 60:
                    adj = +5
                elif ppi > 100:
                    adj = +8
                else:
                    adj = +6
            
            elif horse.running_style == RunningStyle.S:
                # Closers
                if ppi < 60:
                    adj = -10  # Disadvantage - nothing to chase
                elif ppi < 80:
                    adj = 0
                elif ppi < 100:
                    adj = +10
                else:
                    adj = +25  # Huge advantage in speed duel
            
            adjustments[horse.name] = adj
        
        return adjustments
    
    def project_fractions(
        self,
        race_horses: List[Horse],
        distance,
        surface,
        ppi: float
    ) -> Dict:
        """Project quarter and half mile times based on pace pressure"""

        # Handle both Surface enum and string
        if hasattr(surface, 'value'):
            surface_key = surface.value
        else:
            surface_key = 'dirt' if 'D' in str(surface).upper() else 'turf'

        # Handle both string and int distance
        if isinstance(distance, str):
            distance_clean = distance.strip().lower().replace(' ', '')
        else:
            distance_clean = str(distance).lower()
        
        pars = self.par_fractions[surface_key].get(
            distance_clean,
            {'quarter': 23.0, 'half': 46.5}  # Default
        )
        
        # Adjust based on pace pressure
        if ppi > 100:  # Speed duel - fast early, slow late
            quarter = pars['quarter'] - 0.5
            half = pars['half'] - 0.8
            scenario = "fast"
        elif ppi < 60:  # Slow pace
            quarter = pars['quarter'] + 0.5
            half = pars['half'] + 0.8
            scenario = "slow"
        else:  # Honest pace
            quarter = pars['quarter']
            half = pars['half']
            scenario = "honest"
        
        return {
            'projected_quarter': quarter,
            'projected_half': half,
            'scenario': scenario
        }
    
    def integrate_track_bias(
        self,
        adjustments: Dict[str, float],
        track_bias: Optional[TrackBias],
        ppi: float
    ) -> Dict[str, float]:
        """
        Integrate track bias with pace analysis
        Amplify adjustments when bias and pace align
        """
        
        if not track_bias:
            return adjustments
        
        integrated = adjustments.copy()
        
        for horse_name, base_adj in adjustments.items():
            additional = 0.0
            
            # When track bias and pace scenario align, amplify!
            if track_bias.pace_bias == "SPEED" and ppi < 60:
                # Track favors speed AND pace is slow = double bonus
                if base_adj > 0:  # Speed horses
                    additional = 5 * track_bias.pace_bias_strength
            
            elif track_bias.pace_bias == "CLOSERS" and ppi > 100:
                # Track favors closers AND speed duel = triple bonus
                if base_adj > 10:  # Closers benefiting
                    additional = 8 * track_bias.pace_bias_strength
            
            elif track_bias.pace_bias == "SPEED" and ppi > 100:
                # Track favors speed BUT speed duel = conflict, moderate
                if base_adj < 0:  # Speed horses hurting
                    additional = 3 * track_bias.pace_bias_strength  # Soften the blow
            
            integrated[horse_name] = base_adj + additional
        
        return integrated
    
    def analyze_race_pace(
        self,
        race: Race,
        track_bias: Optional[TrackBias] = None
    ) -> RacePaceAnalysis:
        """
        Complete pace analysis for a race
        
        Args:
            race: Race object with horses
            track_bias: Optional track bias data
            
        Returns:
            RacePaceAnalysis object
        """
        
        # Step 1: Calculate pace figures for all horses
        for horse in race.horses:
            # Handle both 'race_date' and 'date' attributes
            race_date = getattr(race, 'race_date', getattr(race, 'date', None))
            pace_figs = self.calculate_early_pace_figure(
                horse,
                race.track_code,
                race_date,
                race.surface
            )
            horse.pace_figures = pace_figs
        
        # Step 2: Calculate pace pressure index
        ppi = self.calculate_pace_pressure_index(race.horses)
        
        # Step 3: Calculate base pressure adjustments
        base_adjustments = self.calculate_pressure_adjustments(race.horses, ppi)
        
        # Step 4: Integrate track bias if available
        if track_bias:
            final_adjustments = self.integrate_track_bias(
                base_adjustments,
                track_bias,
                ppi
            )
            bias_applied = True
        else:
            final_adjustments = base_adjustments
            bias_applied = False
        
        # Step 5: Project fractions
        projections = self.project_fractions(
            race.horses,
            race.distance,
            race.surface,
            ppi
        )
        
        # Step 6: Identify advantage horses
        speed_advantage = [
            name for name, adj in final_adjustments.items()
            if adj >= 10
        ][:3]
        
        closer_advantage = [
            name for name, adj in final_adjustments.items()
            if adj >= 15
        ][:3]
        
        # Check if variants were applied
        variant_applied = any(
            h.pace_figures.method_used == "fractional_times" 
            for h in race.horses 
            if hasattr(h, 'pace_figures')
        )
        
        return RacePaceAnalysis(
            pace_pressure_index=ppi,
            projected_quarter=projections['projected_quarter'],
            projected_half=projections['projected_half'],
            scenario=projections['scenario'],
            speed_advantage_horses=speed_advantage,
            closer_advantage_horses=closer_advantage,
            pressure_adjustments=final_adjustments,
            track_bias_applied=bias_applied,
            track_variant_applied=variant_applied
        )


def format_pace_analysis(analysis: RacePaceAnalysis, race: Race) -> str:
    """Format pace analysis for output"""
    
    output = []
    output.append("\n" + "="*80)
    output.append(" ENHANCED PACE ANALYSIS")
    output.append("="*80 + "\n")
    
    # Pace Pressure Index
    output.append(f"Pace Pressure Index: {analysis.pace_pressure_index:.1f}")
    
    if analysis.pace_pressure_index > 100:
        output.append("  ⚡ SPEED DUEL - High pressure on leaders")
    elif analysis.pace_pressure_index < 60:
        output.append("  🐌 SLOW PACE - Speed horses have advantage")
    else:
        output.append("  ⚖️  HONEST PACE - Fair race for all styles")
    
    # Projected Fractions
    output.append(f"\nProjected Fractions:")
    output.append(f"  Quarter: {analysis.projected_quarter:.1f} seconds")
    output.append(f"  Half: {analysis.projected_half:.1f} seconds")
    output.append(f"  Scenario: {analysis.scenario.upper()}")
    
    # Enhancements Applied
    output.append(f"\nEnhancements Applied:")
    output.append(f"  ✓ Track Variant Adjusted: {analysis.track_variant_applied}")
    output.append(f"  ✓ Track Bias Integrated: {analysis.track_bias_applied}")
    
    # Top pace figures
    output.append(f"\nTop Early Pace Figures:")
    sorted_epf = sorted(
        [h for h in race.horses if hasattr(h, 'pace_figures')],
        key=lambda h: h.pace_figures.early_pace_figure,
        reverse=True
    )
    for i, horse in enumerate(sorted_epf[:5], 1):
        method = horse.pace_figures.method_used
        confidence = horse.pace_figures.confidence
        output.append(
            f"  {i}. {horse.name}: {horse.pace_figures.early_pace_figure:.1f} "
            f"({method}, conf: {confidence:.2f})"
        )
    
    output.append(f"\nTop Late Pace Figures:")
    sorted_lpf = sorted(
        [h for h in race.horses if hasattr(h, 'pace_figures')],
        key=lambda h: h.pace_figures.late_pace_figure,
        reverse=True
    )
    for i, horse in enumerate(sorted_lpf[:5], 1):
        output.append(f"  {i}. {horse.name}: {horse.pace_figures.late_pace_figure:.1f}")
    
    # Pace Advantage Horses
    if analysis.speed_advantage_horses:
        output.append(f"\n🎯 Speed Advantage: {', '.join(analysis.speed_advantage_horses)}")
    
    if analysis.closer_advantage_horses:
        output.append(f"🎯 Closer Advantage: {', '.join(analysis.closer_advantage_horses)}")
    
    # Pressure Adjustments
    output.append(f"\nPace Pressure Adjustments:")
    sorted_adj = sorted(
        analysis.pressure_adjustments.items(),
        key=lambda x: x[1],
        reverse=True
    )
    for horse_name, adj in sorted_adj[:8]:
        emoji = "📈" if adj > 5 else "📉" if adj < -5 else "➡️"
        output.append(f"  {emoji} {horse_name}: {adj:+.0f} points")
    
    output.append("\n" + "="*80 + "\n")
    
    return '\n'.join(output)


# Example usage
if __name__ == '__main__':
    print("Enhanced Pace Analyzer - Ready for Integration")
    print("\nFeatures:")
    print("✓ Pace figures from actual fractional times")
    print("✓ Track variant adjustments")
    print("✓ Pace pressure index calculation")
    print("✓ Track bias integration")
    print("✓ Projected fractions")
    print("\nUse: analyzer = EnhancedPaceAnalyzer('track_variants.json')")
