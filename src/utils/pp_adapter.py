"""
Past Performance Adapter
Converts parser dictionary format to object format for enhanced pace analyzer
"""

from typing import List, Optional
from dataclasses import dataclass


@dataclass
class SimplePP:
    """
    Simple Past Performance object for enhanced pace analyzer
    Converts from parser dictionary format to object attributes
    """
    # Fractional times (in seconds)
    first_call: Optional[float] = None
    second_call: Optional[float] = None
    final_time: Optional[float] = None

    # Position calls
    position_first_call: Optional[int] = None
    position_second_call: Optional[int] = None
    finish_position: Optional[int] = None

    # Race context (from race data)
    distance: Optional[str] = None
    surface: Optional[str] = None
    track: Optional[str] = None

    def __init__(self, pp_dict: dict, race_distance: str = None, race_surface: str = None):
        """
        Convert parser PP dictionary to object

        Parser format:
        {
            'fractional_times': [22.35, 45.34, 70.26],  # in seconds
            'early': (post_pos, first_call_pos),
            'stretch': stretch_pos,
            'finish': finish_pos,
            'distance': '6f',
            'surface': 'Dirt',
            'track': 'KEE'
        }

        Args:
            pp_dict: PP dictionary from parser
            race_distance: Today's race distance (fallback if not in PP)
            race_surface: Today's race surface (fallback if not in PP)
        """
        # Extract fractional times
        frac_times = pp_dict.get('fractional_times', [])
        if len(frac_times) >= 1:
            self.first_call = frac_times[0]  # Quarter/first fraction
        if len(frac_times) >= 2:
            self.second_call = frac_times[1]  # Half mile
        if len(frac_times) >= 3:
            self.final_time = frac_times[2]  # Finish

        # Extract positions
        early_tuple = pp_dict.get('early', (None, None))
        if isinstance(early_tuple, tuple) and len(early_tuple) >= 2:
            # early is (post, first_call)
            self.position_first_call = early_tuple[1] if early_tuple[1] else None

        # Stretch position
        stretch = pp_dict.get('stretch')
        self.position_second_call = stretch if stretch else None

        # Finish position
        self.finish_position = pp_dict.get('finish')

        # Race context (use from PP dict if available, otherwise use race context)
        self.distance = pp_dict.get('distance', race_distance)
        self.surface = pp_dict.get('surface', race_surface)
        self.track = pp_dict.get('track', 'Unknown')


def convert_pp_dicts_to_objects(
    pp_dicts: List[dict],
    race_distance: str = None,
    race_surface: str = None
) -> List[SimplePP]:
    """
    Convert list of PP dictionaries to SimplePP objects

    Args:
        pp_dicts: List of PP dictionaries from parser
        race_distance: Today's race distance (for context)
        race_surface: Today's race surface (for context)

    Returns:
        List of SimplePP objects
    """
    if not pp_dicts:
        return []

    return [
        SimplePP(pp_dict, race_distance, race_surface)
        for pp_dict in pp_dicts
    ]


def add_pp_objects_to_horse(horse, race_distance: str = None, race_surface: str = None):
    """
    Convert horse's PP dictionaries to objects and add as attribute
    Modifies horse object in place

    Args:
        horse: PDFHorse object with past_performances as dictionaries
        race_distance: Today's race distance
        race_surface: Today's race surface
    """
    if hasattr(horse, 'past_performances') and horse.past_performances:
        # Convert dictionaries to objects
        horse.pp_objects = convert_pp_dicts_to_objects(
            horse.past_performances,
            race_distance,
            race_surface
        )
    else:
        horse.pp_objects = []

    return horse


# Test the adapter
if __name__ == "__main__":
    # Test with sample PP dictionary
    test_pp = {
        'fractional_times': [22.35, 45.34, 70.26],
        'early': (3, 2),  # post 3, first call 2nd
        'stretch': 1,
        'finish': 1,
        'distance': '6f',
        'surface': 'Dirt',
        'track': 'KEE'
    }

    # Convert to object
    pp_obj = SimplePP(test_pp)

    print("Testing PP Adapter:")
    print(f"  first_call: {pp_obj.first_call} seconds")
    print(f"  second_call: {pp_obj.second_call} seconds")
    print(f"  position_first_call: {pp_obj.position_first_call}")
    print(f"  finish_position: {pp_obj.finish_position}")
    print(f"  distance: {pp_obj.distance}")
    print(f"  surface: {pp_obj.surface}")
    print("\n✅ Adapter works!")
