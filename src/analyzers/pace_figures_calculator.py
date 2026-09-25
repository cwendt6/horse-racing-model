"""
Pace Analysis Module for Horse Racing
Analyzes running styles, pace scenarios, fractional times, and race speed
"""

import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import statistics


class RunningStyle(Enum):
    """Running style classifications"""
    EARLY_SPEED = "E"      # Front runner - leads or contests lead
    PRESSER = "P"          # Presser - sits 2-4 lengths off pace
    STALKER = "S"          # Stalker - mid-pack, moves up late
    CLOSER = "C"           # Closer - comes from behind
    UNKNOWN = "?"


@dataclass
class FractionalTime:
    """Represents a fractional time at a specific point in race"""
    distance: str          # e.g., "1/4", "1/2", "3/4", "final"
    time: float           # Time in seconds
    furlongs: float       # Distance in furlongs


@dataclass
class PositionCall:
    """Position at a specific call point in the race"""
    call_point: str       # "Start", "1st Call", "2nd Call", "Stretch", "Finish"
    position: int         # Position (1=lead, 2=2nd, etc.)
    lengths_behind: float # Lengths behind leader
    beaten_lengths: float # Total lengths behind


@dataclass
class PastPerformance:
    """Single past performance line"""
    date: str
    track: str
    distance: float       # In furlongs
    surface: str          # Dirt, Turf, Synthetic
    fractional_times: List[FractionalTime] = field(default_factory=list)
    position_calls: List[PositionCall] = field(default_factory=list)
    final_time: Optional[float] = None
    beyer: Optional[int] = None
    speed_rating: Optional[int] = None
    field_size: Optional[int] = None
    race_class: Optional[str] = None
    
    def get_early_position(self) -> Optional[int]:
        """Get position at first call"""
        if self.position_calls and len(self.position_calls) > 0:
            return self.position_calls[0].position
        return None
    
    def get_stretch_position(self) -> Optional[int]:
        """Get position at stretch call"""
        if self.position_calls and len(self.position_calls) >= 2:
            return self.position_calls[-2].position  # Second to last is stretch
        return None
    
    def get_finish_position(self) -> Optional[int]:
        """Get finish position"""
        if self.position_calls and len(self.position_calls) > 0:
            return self.position_calls[-1].position
        return None
    
    def calculate_position_change(self) -> Optional[int]:
        """Calculate position change from first call to finish"""
        early = self.get_early_position()
        finish = self.get_finish_position()
        if early and finish:
            return early - finish  # Positive = gained ground, negative = lost ground
        return None


@dataclass
class PaceAnalysis:
    """Complete pace analysis for a horse"""
    horse_name: str
    running_style: RunningStyle
    running_style_confidence: float  # 0-1, how confident we are
    avg_early_position: float
    avg_stretch_position: float
    avg_finish_position: float
    avg_position_change: float
    early_speed_points: int   # Points for early speed tendencies
    closer_points: int        # Points for closer tendencies
    pace_versatility: float   # How versatile (can run different styles)
    recent_pps: List[PastPerformance] = field(default_factory=list)


@dataclass
class RacePaceScenario:
    """Pace scenario for an upcoming race"""
    early_speed_horses: List[str]  # Horses with early speed
    pressers: List[str]
    stalkers: List[str]
    closers: List[str]
    pace_scenario: str            # "HOT", "MODERATE", "SLOW", "CONTENTIOUS"
    projected_leader: Optional[str]
    pace_advantage: List[str]     # Horses with pace advantage


class PaceAnalyzer:
    """Analyzes pace and running styles from past performances"""
    
    def __init__(self):
        self.style_thresholds = {
            'early_speed_position': 2,      # Must be in first 2 positions early
            'presser_position': 4,          # Positions 3-4 early
            'stalker_position': 6,          # Positions 5-6 early
            'early_speed_points': 7,        # 7+ points = definite early speed
            'closer_points': 7              # 7+ points = definite closer
        }
    
    def parse_fractional_times(self, pp_text: str) -> List[FractionalTime]:
        """
        Parse fractional times from PP line
        Example: "1m :46¹⁰ 1:10⁴³ 1:35⁴⁷"
        """
        fractionals = []
        
        # Pattern for times like :46¹⁰ or 1:10⁴³
        time_pattern = r':?(\d{1,2}):?(\d{2})([¹²³⁴⁵⁰]+)?'
        matches = re.finditer(time_pattern, pp_text)
        
        for match in matches:
            minutes = match.group(1) if ':' in match.group(0) and len(match.group(1)) <= 2 else None
            seconds = int(match.group(1)) if not minutes else int(match.group(2))
            
            # Convert to total seconds
            if minutes:
                total_seconds = int(minutes) * 60 + seconds + int(match.group(2)) / 100
            else:
                total_seconds = seconds + (int(match.group(2)) if len(match.group(2)) == 2 else 0) / 100
            
            fractionals.append(FractionalTime(
                distance="fraction",
                time=total_seconds,
                furlongs=0  # Would need context to determine
            ))
        
        return fractionals
    
    def parse_position_calls(self, pp_text: str) -> List[PositionCall]:
        """
        Parse position calls from PP line
        Example: "4 6²j 6⁴ 6² 6⁸ 7¹¹"
        Positions: start, 1st call, 2nd call, stretch, finish
        """
        position_calls = []
        
        # Pattern for positions like "6²j", "4", "7¹¹"
        # Format: position number followed by optional superscript for lengths behind
        position_pattern = r'(\d+)([¹²³⁴⁵⁶⁷⁸⁹⁰½¼¾]*[a-z]*)'
        
        # Look for sequence of positions in the middle of PP line
        # Typically after fractional times and before jockey name
        matches = re.findall(position_pattern, pp_text)
        
        call_names = ["Start", "1st Call", "2nd Call", "Stretch", "Finish"]
        
        for i, match in enumerate(matches[:5]):  # Usually 5 position calls
            position = int(match[0])
            lengths_behind_str = match[1].rstrip('abcdefghijklmnopqrstuvwxyz')
            
            # Parse lengths behind (superscript numbers)
            lengths_behind = self._parse_superscript_to_float(lengths_behind_str)
            
            position_calls.append(PositionCall(
                call_point=call_names[i] if i < len(call_names) else f"Call {i+1}",
                position=position,
                lengths_behind=lengths_behind,
                beaten_lengths=lengths_behind
            ))
        
        return position_calls
    
    def _parse_superscript_to_float(self, superscript: str) -> float:
        """Convert superscript numbers to float"""
        if not superscript:
            return 0.0
        
        # Map superscript to regular numbers
        superscript_map = {
            '⁰': '0', '¹': '1', '²': '2', '³': '3', '⁴': '4',
            '⁵': '5', '⁶': '6', '⁷': '7', '⁸': '8', '⁹': '9',
            '½': '0.5', '¼': '0.25', '¾': '0.75'
        }
        
        result = ''
        for char in superscript:
            result += superscript_map.get(char, char)
        
        try:
            return float(result)
        except ValueError:
            return 0.0
    
    def classify_running_style(self, past_performances: List[PastPerformance]) -> Tuple[RunningStyle, float]:
        """
        Classify running style based on past performances
        Returns: (RunningStyle, confidence_score)
        """
        if not past_performances:
            return RunningStyle.UNKNOWN, 0.0
        
        early_speed_points = 0
        closer_points = 0
        presser_points = 0
        stalker_points = 0
        
        for pp in past_performances[-10:]:  # Use last 10 races
            early_pos = pp.get_early_position()
            finish_pos = pp.get_finish_position()
            position_change = pp.calculate_position_change()
            
            if early_pos and finish_pos:
                # Award points based on running pattern
                if early_pos == 1:
                    early_speed_points += 3
                elif early_pos == 2:
                    early_speed_points += 2
                elif early_pos <= 4:
                    presser_points += 2
                elif early_pos <= 6:
                    stalker_points += 2
                else:
                    closer_points += 2
                
                # Bonus points for finishing position relative to early
                if position_change and position_change > 0:
                    # Gained ground
                    if position_change >= 4:
                        closer_points += 2
                    elif position_change >= 2:
                        stalker_points += 1
                
                # Penalty for losing ground from early lead
                if early_pos <= 2 and position_change and position_change < -2:
                    early_speed_points -= 1
        
        # Determine style based on point totals
        total_points = early_speed_points + closer_points + presser_points + stalker_points
        
        if total_points == 0:
            return RunningStyle.UNKNOWN, 0.0
        
        # Calculate confidence (0-1 scale)
        max_points = max(early_speed_points, closer_points, presser_points, stalker_points)
        confidence = max_points / total_points if total_points > 0 else 0
        
        # Determine primary style
        if early_speed_points >= self.style_thresholds['early_speed_points']:
            return RunningStyle.EARLY_SPEED, confidence
        elif closer_points >= self.style_thresholds['closer_points']:
            return RunningStyle.CLOSER, confidence
        elif presser_points > stalker_points:
            return RunningStyle.PRESSER, confidence
        elif stalker_points > 0:
            return RunningStyle.STALKER, confidence
        else:
            # Default based on highest points
            if early_speed_points > closer_points:
                return RunningStyle.EARLY_SPEED, confidence * 0.7  # Lower confidence
            else:
                return RunningStyle.CLOSER, confidence * 0.7
    
    def analyze_horse_pace(self, horse_name: str, past_performances: List[PastPerformance]) -> PaceAnalysis:
        """
        Complete pace analysis for a single horse
        """
        if not past_performances:
            return PaceAnalysis(
                horse_name=horse_name,
                running_style=RunningStyle.UNKNOWN,
                running_style_confidence=0.0,
                avg_early_position=0.0,
                avg_stretch_position=0.0,
                avg_finish_position=0.0,
                avg_position_change=0.0,
                early_speed_points=0,
                closer_points=0,
                pace_versatility=0.0,
                recent_pps=[]
            )
        
        # Classify running style
        style, confidence = self.classify_running_style(past_performances)
        
        # Calculate average positions
        early_positions = [pp.get_early_position() for pp in past_performances if pp.get_early_position()]
        stretch_positions = [pp.get_stretch_position() for pp in past_performances if pp.get_stretch_position()]
        finish_positions = [pp.get_finish_position() for pp in past_performances if pp.get_finish_position()]
        position_changes = [pp.calculate_position_change() for pp in past_performances if pp.calculate_position_change()]
        
        avg_early = statistics.mean(early_positions) if early_positions else 0.0
        avg_stretch = statistics.mean(stretch_positions) if stretch_positions else 0.0
        avg_finish = statistics.mean(finish_positions) if finish_positions else 0.0
        avg_change = statistics.mean(position_changes) if position_changes else 0.0
        
        # Calculate versatility (standard deviation of early positions - lower = more consistent)
        versatility = 1.0 - (statistics.stdev(early_positions) / 10.0) if len(early_positions) > 1 else 0.5
        versatility = max(0.0, min(1.0, versatility))
        
        # Count points for classification
        early_speed_points = sum(1 for pos in early_positions if pos <= 2)
        closer_points = sum(1 for pos in early_positions if pos > 4)
        
        return PaceAnalysis(
            horse_name=horse_name,
            running_style=style,
            running_style_confidence=confidence,
            avg_early_position=avg_early,
            avg_stretch_position=avg_stretch,
            avg_finish_position=avg_finish,
            avg_position_change=avg_change,
            early_speed_points=early_speed_points,
            closer_points=closer_points,
            pace_versatility=versatility,
            recent_pps=past_performances[-5:]  # Keep last 5 for reference
        )
    
    def analyze_race_pace(self, pace_analyses: List[PaceAnalysis]) -> RacePaceScenario:
        """
        Analyze the pace scenario for an entire race
        """
        early_speed = []
        pressers = []
        stalkers = []
        closers = []
        
        # Categorize horses by running style
        for analysis in pace_analyses:
            if analysis.running_style == RunningStyle.EARLY_SPEED:
                early_speed.append(analysis.horse_name)
            elif analysis.running_style == RunningStyle.PRESSER:
                pressers.append(analysis.horse_name)
            elif analysis.running_style == RunningStyle.STALKER:
                stalkers.append(analysis.horse_name)
            elif analysis.running_style == RunningStyle.CLOSER:
                closers.append(analysis.horse_name)
        
        # Determine pace scenario
        num_early_speed = len(early_speed)
        
        if num_early_speed >= 4:
            pace_scenario = "VERY HOT"
        elif num_early_speed == 3:
            pace_scenario = "HOT"
        elif num_early_speed == 2:
            pace_scenario = "CONTENTIOUS"
        elif num_early_speed == 1:
            pace_scenario = "MODERATE"
        else:
            pace_scenario = "SLOW"
        
        # Project likely leader
        projected_leader = None
        if early_speed:
            # Find horse with best early position average
            best_early = min(pace_analyses, 
                           key=lambda x: x.avg_early_position if x.horse_name in early_speed else 999)
            projected_leader = best_early.horse_name
        
        # Determine pace advantage
        pace_advantage = []
        if pace_scenario in ["HOT", "VERY HOT"]:
            # Closers and stalkers have advantage in hot pace
            pace_advantage = closers + stalkers
        elif pace_scenario == "SLOW":
            # Early speed has advantage in slow pace
            pace_advantage = early_speed + pressers
        else:
            # Balanced - versatile horses have advantage
            pace_advantage = [a.horse_name for a in sorted(pace_analyses, 
                            key=lambda x: x.pace_versatility, reverse=True)[:3]]
        
        return RacePaceScenario(
            early_speed_horses=early_speed,
            pressers=pressers,
            stalkers=stalkers,
            closers=closers,
            pace_scenario=pace_scenario,
            projected_leader=projected_leader,
            pace_advantage=pace_advantage
        )
    
    def calculate_pace_figure(self, fractional_times: List[FractionalTime], distance: float) -> Optional[float]:
        """
        Calculate a pace figure based on fractional times
        This is a simplified version - you'd want to adjust for track variant
        """
        if not fractional_times or len(fractional_times) < 2:
            return None
        
        # Use first two fractions for early pace
        early_fraction = fractional_times[0].time if len(fractional_times) > 0 else 0
        
        # Calculate pace figure (simplified - lower is faster)
        # Normalize to a 100 scale
        if distance >= 8:  # Route race
            par_time = 46.0  # Par for first quarter in route
        else:  # Sprint
            par_time = 22.0  # Par for first quarter in sprint
        
        # Calculate points off par
        points_off = (early_fraction - par_time) * 5
        
        # Pace figure (100 = par, higher = faster)
        pace_figure = 100 - points_off
        
        return pace_figure
    
    def analyze_race_speed(self, pp: PastPerformance, track_variant: float = 0) -> Dict[str, float]:
        """
        Analyze how fast a prior race was run
        Returns speed metrics
        """
        metrics = {}
        
        # Beyer speed figure (if available)
        if pp.beyer:
            metrics['beyer'] = pp.beyer
        
        # Calculate pace figure
        if pp.fractional_times:
            pace_fig = self.calculate_pace_figure(pp.fractional_times, pp.distance)
            if pace_fig:
                metrics['pace_figure'] = pace_fig
        
        # Final time analysis
        if pp.final_time and pp.distance:
            # Calculate seconds per furlong
            seconds_per_furlong = pp.final_time / pp.distance
            metrics['seconds_per_furlong'] = seconds_per_furlong
            
            # Compare to par (12 seconds per furlong is roughly par for fast track)
            par_seconds_per_furlong = 12.0
            metrics['points_off_par'] = (seconds_per_furlong - par_seconds_per_furlong) * pp.distance
        
        # Track variant adjustment
        if track_variant != 0:
            for key in ['beyer', 'pace_figure']:
                if key in metrics:
                    metrics[key] += track_variant
        
        return metrics


class PaceFigureCalculator:
    """Calculate advanced pace figures"""
    
    def __init__(self):
        # Par times for different distances (in seconds per furlong)
        self.par_times = {
            'sprint_dirt': 12.0,
            'route_dirt': 12.5,
            'sprint_turf': 12.2,
            'route_turf': 12.7,
            'synthetic': 12.3
        }
    
    def calculate_early_pace_figure(self, pp: PastPerformance) -> Optional[int]:
        """
        Calculate early pace figure (first fraction)
        """
        if not pp.fractional_times or len(pp.fractional_times) == 0:
            return None
        
        first_fraction = pp.fractional_times[0].time
        
        # Determine par based on surface and distance
        if pp.distance <= 7:  # Sprint
            par_key = f'sprint_{pp.surface.lower()}' if pp.surface.lower() in ['dirt', 'turf'] else 'synthetic'
        else:  # Route
            par_key = f'route_{pp.surface.lower()}' if pp.surface.lower() in ['dirt', 'turf'] else 'synthetic'
        
        par_time = self.par_times.get(par_key, 12.0) * 2  # First fraction usually 2 furlongs
        
        # Calculate figure (100 = par)
        points_off = (first_fraction - par_time) * 5
        pace_figure = int(100 - points_off)
        
        return pace_figure
    
    def calculate_late_pace_figure(self, pp: PastPerformance) -> Optional[int]:
        """
        Calculate late pace figure (last fraction)
        """
        if not pp.fractional_times or len(pp.fractional_times) < 2:
            return None
        
        # Use last two fractions to calculate late pace
        if len(pp.fractional_times) >= 2:
            late_fraction = pp.fractional_times[-1].time - pp.fractional_times[-2].time
        else:
            return None
        
        # Par for late fraction
        par_late = 25.0  # Typical for final 2 furlongs
        
        points_off = (late_fraction - par_late) * 5
        late_figure = int(100 - points_off)
        
        return late_figure


def create_example_usage():
    """Example of how to use the pace analyzer"""
    
    # Create analyzer
    analyzer = PaceAnalyzer()
    
    # Example: Create past performances for a horse
    pps = [
        PastPerformance(
            date="15Sep25",
            track="KEE",
            distance=8.5,
            surface="Dirt",
            fractional_times=[
                FractionalTime("1/4", 23.0, 2),
                FractionalTime("1/2", 46.2, 4),
                FractionalTime("3/4", 110.5, 6)
            ],
            position_calls=[
                PositionCall("Start", 2, 0.5, 0.5),
                PositionCall("1st Call", 2, 1.0, 1.0),
                PositionCall("2nd Call", 3, 2.0, 2.0),
                PositionCall("Stretch", 3, 2.5, 2.5),
                PositionCall("Finish", 2, 1.0, 1.0)
            ],
            final_time=149.2,
            beyer=85
        ),
        # Add more past performances...
    ]
    
    # Analyze horse's pace
    pace_analysis = analyzer.analyze_horse_pace("Lady Lala", pps)
    
    print(f"Horse: {pace_analysis.horse_name}")
    print(f"Running Style: {pace_analysis.running_style.value}")
    print(f"Confidence: {pace_analysis.running_style_confidence:.2f}")
    print(f"Avg Early Position: {pace_analysis.avg_early_position:.1f}")
    print(f"Avg Position Change: {pace_analysis.avg_position_change:+.1f}")
    
    # Analyze race pace scenario
    # (would need pace analyses for all horses in the race)
    all_analyses = [pace_analysis]  # Add more horses
    race_scenario = analyzer.analyze_race_pace(all_analyses)
    
    print(f"\nRace Pace Scenario: {race_scenario.pace_scenario}")
    print(f"Early Speed Horses: {', '.join(race_scenario.early_speed_horses)}")
    print(f"Projected Leader: {race_scenario.projected_leader}")
    print(f"Pace Advantage: {', '.join(race_scenario.pace_advantage)}")


if __name__ == "__main__":
    create_example_usage()
