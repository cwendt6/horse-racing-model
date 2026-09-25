"""
Adapter to make PDFHorse/PDFRace work with EnhancedPaceAnalyzer
Converts between PDF parser format and enhanced pace analyzer format
"""

from enum import Enum
from typing import List, Dict, Optional
from dataclasses import dataclass, field


class RunningStyle(Enum):
    """Running style enum for enhanced pace analyzer"""
    E = "E"   # Early speed
    EP = "EP"  # Early presser
    P = "P"    # Presser
    S = "S"    # Stalker/Closer
    C = "C"    # Closer (alias for S)


@dataclass
class PastPerformance:
    """
    Past performance data structure for enhanced pace analyzer
    Compatible with PDF parser output
    """
    date: str = ''
    track: str = ''
    distance: str = ''
    surface: str = 'D'

    # Position calls
    first_call: int = 0
    second_call: int = 0
    stretch_call: int = 0
    finish: int = 0

    # Fractional times (in seconds)
    fractional_times: List[float] = field(default_factory=list)

    # Speed figures
    speed_figure: int = 0

    # Race info
    class_rating: int = 0
    winners_time: float = 0.0


@dataclass
class Horse:
    """
    Horse data structure compatible with EnhancedPaceAnalyzer
    Maps from PDFHorse format
    """
    name: str
    program_number: str
    jockey_name: str
    trainer_name: str

    # Running style
    running_style: RunningStyle = RunningStyle.P

    # Speed figures
    best_beyer: int = 0
    last_beyer: int = 0
    avg_beyer: int = 0

    # Past performances
    past_performances: List[PastPerformance] = field(default_factory=list)

    # These will be populated by EnhancedPaceAnalyzer
    pace_figures: Optional[object] = None
    pace_adjustment: float = 0.0


@dataclass
class Race:
    """
    Race data structure compatible with EnhancedPaceAnalyzer
    Maps from PDFRace format
    """
    track_code: str
    track_name: str
    date: str
    race_number: int

    # Race conditions
    distance: int  # In furlongs * 100 (e.g., 600 = 6f)
    distance_text: str
    surface: str  # 'D', 'T', 'AWT'
    track_condition: str = 'FT'

    # Horses
    horses: List[Horse] = field(default_factory=list)


def convert_pdf_horse_to_enhanced(pdf_horse) -> Horse:
    """
    Convert PDFHorse to Horse format for EnhancedPaceAnalyzer

    Args:
        pdf_horse: PDFHorse object from PDF parser

    Returns:
        Horse object compatible with EnhancedPaceAnalyzer
    """

    # Convert running style string to enum
    running_style_str = getattr(pdf_horse, 'running_style', 'P')
    try:
        if running_style_str == 'C':
            running_style = RunningStyle.S  # Convert C to S
        else:
            running_style = RunningStyle(running_style_str)
    except (ValueError, KeyError):
        running_style = RunningStyle.P  # Default to presser

    # Convert past performances
    past_perfs = []
    for pp_dict in getattr(pdf_horse, 'past_performances', []):
        # Extract position calls
        early = pp_dict.get('early', (0, 0))
        first_call_position = early[0] if isinstance(early, tuple) and len(early) > 0 else 0
        second_call_position = early[1] if isinstance(early, tuple) and len(early) > 1 else 0
        stretch = pp_dict.get('stretch', 0)
        finish = pp_dict.get('finish', 0)

        # Extract fractional times (already in seconds as floats)
        fractional_times = pp_dict.get('fractional_times', [])

        # IMPORTANT: enhanced pace analyzer expects first_call to be the FRACTIONAL TIME (float),
        # not the position (int). Use first fractional time if available, otherwise None.
        first_call_time = fractional_times[0] if len(fractional_times) > 0 else None

        # Extract distance and surface from PP dict
        distance = pp_dict.get('distance', '')
        surface = pp_dict.get('surface', 'D')

        past_perf = PastPerformance(
            first_call=first_call_time,  # Fractional time in seconds (float or None)
            second_call=second_call_position,  # Position (for now)
            stretch_call=stretch,
            finish=finish,
            fractional_times=fractional_times,
            distance=distance if distance else '',  # Distance like "6f", "1m"
            surface=surface  # 'D' or 'T'
        )
        past_perfs.append(past_perf)

    # Create Horse object
    horse = Horse(
        name=getattr(pdf_horse, 'name', 'Unknown'),
        program_number=getattr(pdf_horse, 'program_number', '0'),
        jockey_name=getattr(pdf_horse, 'jockey_name', 'Unknown'),
        trainer_name=getattr(pdf_horse, 'trainer_name', 'Unknown'),
        running_style=running_style,
        best_beyer=getattr(pdf_horse, 'best_speed_figure', 0),
        last_beyer=getattr(pdf_horse, 'last_speed_figure', 0),
        avg_beyer=getattr(pdf_horse, 'avg_speed_figure', 0),
        past_performances=past_perfs
    )

    return horse


def convert_pdf_race_to_enhanced(pdf_race) -> Race:
    """
    Convert PDFRace to Race format for EnhancedPaceAnalyzer

    Args:
        pdf_race: PDFRace object from PDF parser

    Returns:
        Race object compatible with EnhancedPaceAnalyzer
    """

    # Convert horses
    horses = [convert_pdf_horse_to_enhanced(h) for h in pdf_race.horses]

    # Get distance and convert to text format if needed
    distance = getattr(pdf_race, 'distance', 600)
    distance_text = getattr(pdf_race, 'distance_text', '6f')

    # Ensure distance is string format for enhanced analyzer
    # PDFRace uses int (e.g., 700 = 7F), enhanced needs "7f"
    if isinstance(distance, int):
        distance_str = distance_text.lower()  # Use the text version
    else:
        distance_str = str(distance).lower()

    # Get surface
    surface = getattr(pdf_race, 'surface', 'D')
    # Convert single letter to full name if needed
    if isinstance(surface, str) and len(surface) == 1:
        surface_map = {'D': 'dirt', 'T': 'turf', 'A': 'synthetic'}
        surface = surface_map.get(surface.upper(), 'dirt')

    # Create Race object
    race = Race(
        track_code=getattr(pdf_race, 'track_code', 'UNK'),
        track_name=getattr(pdf_race, 'track_name', 'Unknown'),
        date=getattr(pdf_race, 'date', ''),
        race_number=getattr(pdf_race, 'race_number', 0),
        distance=distance,  # Keep as int
        distance_text=distance_str,  # Ensure string
        surface=surface,  # Now full name
        track_condition=getattr(pdf_race, 'track_condition', 'FT'),
        horses=horses
    )

    return race


def apply_pace_adjustments_to_pdf_horses(enhanced_horses: List[Horse], pdf_horses: List, pace_analysis) -> None:
    """
    Apply pace figures and adjustments from enhanced analyzer back to PDFHorse objects

    This modifies the pdf_horses in place to add:
    - pace_figures attribute
    - pace_adjustment value

    Args:
        enhanced_horses: List of Horse objects with pace data
        pdf_horses: List of PDFHorse objects to update
        pace_analysis: PaceAnalysisResult with pressure_adjustments dictionary
    """

    # Create mapping by name (or program number as fallback)
    enhanced_map = {h.name: h for h in enhanced_horses}

    for pdf_horse in pdf_horses:
        # Find matching enhanced horse
        enhanced_horse = enhanced_map.get(pdf_horse.name)

        if enhanced_horse:
            # Copy pace figures from enhanced horse
            pdf_horse.pace_figures = enhanced_horse.pace_figures

            # Get pace adjustment from pace_analysis.pressure_adjustments dictionary
            pdf_horse.pace_adjustment = pace_analysis.pressure_adjustments.get(pdf_horse.name, 0.0)

            # Also store EPF/LPF directly for easy access
            if hasattr(enhanced_horse, 'pace_figures') and enhanced_horse.pace_figures:
                pdf_horse.early_pace_figure = enhanced_horse.pace_figures.early_pace_figure
                pdf_horse.late_pace_figure = enhanced_horse.pace_figures.late_pace_figure
                pdf_horse.pace_confidence = enhanced_horse.pace_figures.confidence
                pdf_horse.pace_method = enhanced_horse.pace_figures.method_used
        else:
            # Horse not found in enhanced map, set defaults
            pdf_horse.pace_adjustment = 0.0
            pdf_horse.pace_figures = None
