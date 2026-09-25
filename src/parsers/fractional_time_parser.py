"""
Equibase Fractional Time Parser
Decodes fractional times from Equibase PDFs and calculates pace figures
"""

import re
from typing import Dict, List, Tuple, Optional


# Equibase encoding: Each character represents a digit 0-9
EQUIBASE_CHAR_MAP = {
    '^': '0',
    '¶': '1',
    '¸': '2',
    '¹': '3',
    'º': '4',
    '»': '5',
    '¼': '6',
    '½': '7',
    '¾': '8',
    '¿': '9',
}


def decode_fractional_time(time_str: str) -> Optional[float]:
    """
    Decode Equibase fractional time to decimal seconds

    Examples:
        :46¶^ -> 46.10 seconds
        1:12¾¼ -> 72.86 seconds (1:12.86)
        :23¸º -> 23.24 seconds

    Args:
        time_str: Fractional time with Equibase encoding (e.g., ":46¶^")

    Returns:
        Time in decimal seconds, or None if parsing fails
    """
    if not time_str:
        return None

    # Pattern: optional minutes, colon, seconds, two special chars
    pattern = r'^(\d*):(\d{2})([^\s\d]{2})'
    match = re.match(pattern, time_str)

    if not match:
        return None

    minutes_str, seconds_str, encoded_decimal = match.groups()

    # Parse base time
    minutes = int(minutes_str) if minutes_str else 0
    seconds = int(seconds_str)

    # Decode decimal portion
    if len(encoded_decimal) == 2:
        char1, char2 = encoded_decimal[0], encoded_decimal[1]
        digit1 = EQUIBASE_CHAR_MAP.get(char1, '0')
        digit2 = EQUIBASE_CHAR_MAP.get(char2, '0')
        decimal_part = float(f'0.{digit1}{digit2}')
    else:
        decimal_part = 0.0

    # Total time in seconds
    total_seconds = (minutes * 60) + seconds + decimal_part

    return total_seconds


def parse_fractional_times_from_line(pp_line: str) -> List[float]:
    """
    Extract all fractional times from a past performance line

    Args:
        pp_line: Past performance text line

    Returns:
        List of fractional times in seconds (e.g., [23.24, 46.10, 72.86])
    """
    fractional_times = []

    # Pattern: time with encoded decimals
    pattern = r'(\d*:\d{2}[^\s\d]{2})'
    matches = re.findall(pattern, pp_line)

    for match in matches:
        decoded_time = decode_fractional_time(match)
        if decoded_time is not None:
            fractional_times.append(decoded_time)

    return fractional_times


def calculate_pace_figures(fractional_times: List[float], final_time: float, distance_furlongs: float) -> Dict[str, float]:
    """
    Calculate pace figures (E1, E2, LP) from fractional times

    Pace Figures Explained:
    - E1 (Early Pace): Speed in first call (usually 2f or 4f)
    - E2 (Middle Pace): Speed from first call to second call
    - LP (Late Pace): Speed from second call to finish

    Higher figures = faster pace

    Args:
        fractional_times: List of fractional times in seconds [call1, call2, ...]
        final_time: Final time in seconds
        distance_furlongs: Total distance in furlongs

    Returns:
        Dict with pace figures: {'e1': float, 'e2': float, 'lp': float}
    """
    if not fractional_times or final_time <= 0:
        return {'e1': 0.0, 'e2': 0.0, 'lp': 0.0}

    # E1: First call pace (usually 2f or 4f depending on distance)
    first_call = fractional_times[0] if len(fractional_times) > 0 else 0

    # E2: Second call pace
    second_call = fractional_times[1] if len(fractional_times) > 1 else first_call

    # LP: Late pace (from last fraction to finish)
    last_fraction = fractional_times[-1] if fractional_times else 0

    # Calculate pace figures
    # Formula: (Par Time - Actual Time) + 100
    # For simplicity, we'll use velocity-based figures

    # E1: Furlongs per second at first call (convert to figure)
    # Assume first call is at 2f for sprints, 4f for routes
    first_call_distance = 2.0 if distance_furlongs <= 7 else 4.0
    e1_velocity = first_call_distance / first_call if first_call > 0 else 0
    e1_figure = e1_velocity * 100  # Scale to 0-100 range

    # E2: Second call pace (from first to second call)
    e2_time = second_call - first_call if second_call > first_call else second_call
    second_call_distance = 4.0 if distance_furlongs <= 7 else 6.0
    e2_distance = second_call_distance - first_call_distance
    e2_velocity = e2_distance / e2_time if e2_time > 0 else 0
    e2_figure = e2_velocity * 100

    # LP: Late pace (from last fraction to finish)
    lp_time = final_time - last_fraction if final_time > last_fraction else final_time
    lp_distance = distance_furlongs - (second_call_distance if len(fractional_times) > 1 else first_call_distance)
    lp_velocity = lp_distance / lp_time if lp_time > 0 else 0
    lp_figure = lp_velocity * 100

    return {
        'e1': round(e1_figure, 1),
        'e2': round(e2_figure, 1),
        'lp': round(lp_figure, 1)
    }


def extract_pace_data_from_pp(pp_dict: Dict) -> Optional[Dict]:
    """
    Extract pace data from a parsed past performance dictionary

    Args:
        pp_dict: Past performance dict with keys like 'fractional_times', 'final_time', 'distance'

    Returns:
        Dict with pace figures or None if data insufficient
    """
    fractional_times = pp_dict.get('fractional_times', [])
    final_time = pp_dict.get('final_time')
    distance = pp_dict.get('distance')

    if not fractional_times or not final_time or not distance:
        return None

    # Convert distance to furlongs if needed
    if isinstance(distance, str):
        # Parse distance like "6f", "1m", "1 1/16m"
        if 'f' in distance.lower():
            distance_furlongs = float(distance.lower().replace('f', ''))
        elif 'm' in distance.lower():
            # 1m = 8f, 1 1/16m = 8.5f, etc.
            miles = distance.lower().replace('m', '').strip()
            if '/' in miles:
                # Handle fractions like "1 1/16"
                parts = miles.split()
                whole = int(parts[0]) if parts[0] else 0
                frac = parts[1] if len(parts) > 1 else "0"
                num, den = map(int, frac.split('/'))
                distance_furlongs = (whole + (num / den)) * 8
            else:
                distance_furlongs = float(miles) * 8 if miles else 8
        else:
            distance_furlongs = 8.0  # Default
    else:
        distance_furlongs = distance

    return calculate_pace_figures(fractional_times, final_time, distance_furlongs)


def format_fractional_time(seconds: float) -> str:
    """
    Format decimal seconds back to time string

    Args:
        seconds: Time in seconds (e.g., 72.86)

    Returns:
        Formatted time string (e.g., "1:12.86")
    """
    minutes = int(seconds // 60)
    remaining_seconds = seconds % 60

    if minutes > 0:
        return f"{minutes}:{remaining_seconds:05.2f}"
    else:
        return f":{remaining_seconds:05.2f}"


# Example usage and testing
if __name__ == '__main__':
    print("EQUIBASE FRACTIONAL TIME PARSER - TEST")
    print("=" * 80)
    print()

    # Test decoding
    test_times = [
        ':46¶^',   # 46.10
        '1:12¾¼',  # 72.86
        ':23¸º',   # 23.24
        '1:38¾¼',  # 98.86
        ':47º½',   # 47.47
    ]

    print("Decoding Test:")
    print("-" * 80)
    for time_str in test_times:
        decoded = decode_fractional_time(time_str)
        formatted = format_fractional_time(decoded) if decoded else "N/A"
        print(f"{time_str:10s} -> {decoded:6.2f} seconds -> {formatted}")

    print()
    print("=" * 80)
    print()

    # Test pace figure calculation
    print("Pace Figure Calculation Test:")
    print("-" * 80)

    # Example: 6f sprint
    sprint_fractions = [23.24, 46.10]  # 2f, 4f
    sprint_final = 72.50  # 6f final
    sprint_pace = calculate_pace_figures(sprint_fractions, sprint_final, 6.0)

    print(f"6f Sprint: {format_fractional_time(sprint_fractions[0])}, {format_fractional_time(sprint_fractions[1])}, Final: {format_fractional_time(sprint_final)}")
    print(f"  E1: {sprint_pace['e1']:.1f}")
    print(f"  E2: {sprint_pace['e2']:.1f}")
    print(f"  LP: {sprint_pace['lp']:.1f}")
    print()

    # Example: 1 mile route
    route_fractions = [23.70, 47.90, 72.62, 98.03]  # 2f, 4f, 6f, 1m
    route_final = 104.70  # 1m final
    route_pace = calculate_pace_figures(route_fractions, route_final, 8.0)

    print(f"1 Mile Route: {format_fractional_time(route_fractions[0])}, {format_fractional_time(route_fractions[1])}, Final: {format_fractional_time(route_final)}")
    print(f"  E1: {route_pace['e1']:.1f}")
    print(f"  E2: {route_pace['e2']:.1f}")
    print(f"  LP: {route_pace['lp']:.1f}")
