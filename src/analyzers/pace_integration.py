"""
Pace Analyzer Integration Guide
How to connect the PDF parser with the pace analyzer
"""

from src.analyzers.pace_analyzer import (
    PaceAnalyzer, PaceFigureCalculator,
    PastPerformance, FractionalTime, PositionCall,
    RunningStyle
)
import re
from typing import List, Dict


class PDFToPaceAnalyzer:
    """Bridge between PDF parser and pace analyzer"""
    
    def __init__(self):
        self.pace_analyzer = PaceAnalyzer()
        self.pace_calculator = PaceFigureCalculator()
    
    def parse_pp_line_to_pastperformance(self, pp_line: str) -> PastPerformance:
        """
        Convert a single past performance line from PDF to PastPerformance object
        
        Example PP line format:
        "11Sep25 3CD ft 1m :46¹⁰ 1:10⁴³ 1:35⁴⁷ 3†‡ Str 30000nw1/x 54-86 4 6²j 6⁴ 6² 6⁸ 7¹¹ Morales E 122 bL 23.57"
        
        Breakdown:
        - Date: 11Sep25
        - Track/Race: 3CD (race 3 at Churchill Downs)
        - Condition: ft (fast)
        - Distance: 1m (1 mile)
        - Fractionals: :46¹⁰ 1:10⁴³ 1:35⁴⁷
        - Class: Str 30000nw1/x
        - Field size: 54-86 (betting range or field size)
        - Positions: 4 6²j 6⁴ 6² 6⁸ 7¹¹ (start through finish)
        - Jockey: Morales E
        - Weight: 122
        - Equipment: bL (blinkers, Lasix)
        - Beyer: 23.57 or could be final time
        """
        
        # Extract date
        date_match = re.search(r'(\d{1,2}[A-Za-z]{3}\d{2})', pp_line)
        date = date_match.group(1) if date_match else ""
        
        # Extract track code
        track_match = re.search(r'\d+([A-Z]{2,3})', pp_line)
        track = track_match.group(1) if track_match else ""
        
        # Extract surface condition
        surface = "Dirt"  # Default
        if ' ft ' in pp_line or pp_line.startswith('ft '):
            surface = "Dirt"
        elif ' fm ' in pp_line or ' gd ' in pp_line:
            surface = "Turf"
        elif ' sy ' in pp_line or ' sys ' in pp_line:
            surface = "Synthetic"
        
        # Extract distance
        distance = self._parse_distance(pp_line)
        
        # Extract fractional times
        fractional_times = self._parse_fractional_times(pp_line)
        
        # Extract position calls
        position_calls = self._parse_position_calls(pp_line)
        
        # Extract final time (usually at end of line)
        final_time = self._extract_final_time(pp_line)
        
        # Extract Beyer (if present)
        beyer = self._extract_beyer(pp_line)
        
        # Extract field size
        field_size = self._extract_field_size(pp_line)
        
        return PastPerformance(
            date=date,
            track=track,
            distance=distance,
            surface=surface,
            fractional_times=fractional_times,
            position_calls=position_calls,
            final_time=final_time,
            beyer=beyer,
            field_size=field_size
        )
    
    def _parse_distance(self, pp_line: str) -> float:
        """
        Parse distance from PP line
        Examples: "1m" = 8f, "6f" = 6f, "1 1/16m" = 8.5f, "7f" = 7f
        """
        # Look for patterns like "1m", "6f", "1 1/16m"
        
        # Mile patterns
        mile_match = re.search(r'(\d+)\s*(\d+/\d+)?m\b', pp_line)
        if mile_match:
            miles = int(mile_match.group(1))
            fraction = mile_match.group(2)
            
            furlongs = miles * 8
            if fraction:
                if fraction == "1/16":
                    furlongs += 0.5
                elif fraction == "1/8":
                    furlongs += 1
                elif fraction == "1/4":
                    furlongs += 2
            return furlongs
        
        # Furlong patterns
        furlong_match = re.search(r'(\d+(?:\.\d+)?)f\b', pp_line)
        if furlong_match:
            return float(furlong_match.group(1))
        
        # Yard patterns (rare)
        yard_match = re.search(r'(\d+)y\b', pp_line)
        if yard_match:
            yards = int(yard_match.group(1))
            return yards / 220  # 220 yards = 1 furlong
        
        return 8.0  # Default to 1 mile if can't parse
    
    def _parse_fractional_times(self, pp_line: str) -> List[FractionalTime]:
        """
        Parse fractional times from PP line
        Examples: ":46¹⁰" = 46.10, "1:10⁴³" = 70.43 (1 minute 10.43 seconds)
        """
        fractionals = []
        
        # Pattern for fractional times: :22¹, :46², 1:10³, etc.
        # Matches both :XX and X:XX formats
        time_pattern = r'(?::(\d{2})|(\d+):(\d{2}))([¹²³⁴⁵⁶⁷⁸⁹⁰]+)'
        
        matches = re.finditer(time_pattern, pp_line)
        
        call_distances = [2, 4, 6, 8]  # Typical call points in furlongs
        
        for i, match in enumerate(matches):
            if match.group(1):  # Format :XX
                seconds = int(match.group(1))
                fraction = match.group(4)
            else:  # Format X:XX
                minutes = int(match.group(2))
                seconds = int(match.group(3))
                fraction = match.group(4)
                seconds += minutes * 60
            
            # Parse fractional seconds from superscript
            fractional_seconds = self._superscript_to_decimal(fraction)
            total_time = seconds + fractional_seconds / 100
            
            distance_furlongs = call_distances[i] if i < len(call_distances) else 0
            
            fractionals.append(FractionalTime(
                distance=f"{distance_furlongs}f",
                time=total_time,
                furlongs=distance_furlongs
            ))
        
        return fractionals
    
    def _superscript_to_decimal(self, superscript: str) -> float:
        """Convert superscript to decimal number"""
        superscript_map = {
            '⁰': '0', '¹': '1', '²': '2', '³': '3', '⁴': '4',
            '⁵': '5', '⁶': '6', '⁷': '7', '⁸': '8', '⁹': '9'
        }
        
        decimal_str = ''.join(superscript_map.get(c, c) for c in superscript)
        
        try:
            return float(decimal_str)
        except ValueError:
            return 0.0
    
    def _parse_position_calls(self, pp_line: str) -> List[PositionCall]:
        """
        Parse position calls
        Example: "4 6²j 6⁴ 6² 6⁸ 7¹¹"
        This means: 4th at start, 6th (2j lengths behind) at 1st call, etc.
        """
        position_calls = []
        
        # Find the sequence of positions (usually 5-6 consecutive numbers)
        # Pattern: number followed by optional superscript and letter
        position_pattern = r'\b(\d{1,2})([¹²³⁴⁵⁶⁷⁸⁹⁰½¼¾hd]*[a-z]*)\b'
        
        # We need to identify where positions are vs other numbers
        # Typically after fractional times and class, before jockey name
        
        # Strategy: Look for a sequence of 4-6 numbers in a row
        potential_positions = []
        matches = list(re.finditer(position_pattern, pp_line))
        
        # Find the longest sequence of position-like patterns
        for i in range(len(matches)):
            sequence = []
            for j in range(i, min(i + 6, len(matches))):
                match = matches[j]
                position = int(match.group(1))
                if 1 <= position <= 20:  # Valid position range
                    sequence.append(match)
                else:
                    break
            
            if len(sequence) >= 4:  # Need at least 4 calls
                potential_positions = sequence
                break
        
        call_names = ["Start", "1st Call", "2nd Call", "Stretch", "Finish", "Final"]
        
        for i, match in enumerate(potential_positions):
            position = int(match.group(1))
            lengths_str = match.group(2).rstrip('abcdefghijklmnopqrstuvwxyz')
            
            lengths_behind = self._parse_lengths_behind(lengths_str)
            
            call_name = call_names[i] if i < len(call_names) else f"Call {i+1}"
            
            position_calls.append(PositionCall(
                call_point=call_name,
                position=position,
                lengths_behind=lengths_behind,
                beaten_lengths=lengths_behind
            ))
        
        return position_calls
    
    def _parse_lengths_behind(self, lengths_str: str) -> float:
        """Parse lengths behind from superscript notation"""
        if not lengths_str:
            return 0.0
        
        superscript_map = {
            '⁰': '0', '¹': '1', '²': '2', '³': '3', '⁴': '4',
            '⁵': '5', '⁶': '6', '⁷': '7', '⁸': '8', '⁹': '9',
            '½': '.5', '¼': '.25', '¾': '.75', 'hd': '0.1', 'nk': '0.2', 'ns': '0.05'
        }
        
        result = ''
        i = 0
        while i < len(lengths_str):
            char = lengths_str[i]
            # Check for two-character patterns
            if i + 1 < len(lengths_str):
                two_char = lengths_str[i:i+2]
                if two_char in superscript_map:
                    result += superscript_map[two_char]
                    i += 2
                    continue
            
            if char in superscript_map:
                result += superscript_map[char]
            i += 1
        
        try:
            return float(result) if result else 0.0
        except ValueError:
            return 0.0
    
    def _extract_final_time(self, pp_line: str) -> Optional[float]:
        """Extract final time from PP line"""
        # Final time usually at end, format like "1:49.23" or ":23.45"
        time_match = re.search(r'(\d+):(\d+)\.(\d+)$', pp_line)
        if time_match:
            minutes = int(time_match.group(1))
            seconds = int(time_match.group(2))
            hundredths = int(time_match.group(3))
            return minutes * 60 + seconds + hundredths / 100
        
        # Try without minutes
        time_match = re.search(r':(\d+)\.(\d+)$', pp_line)
        if time_match:
            seconds = int(time_match.group(1))
            hundredths = int(time_match.group(2))
            return seconds + hundredths / 100
        
        return None
    
    def _extract_beyer(self, pp_line: str) -> Optional[int]:
        """Extract Beyer speed figure if present"""
        # Beyer usually appears in comments or at end
        # Look for patterns like "Beyer 85" or just a number 70-130 range
        beyer_match = re.search(r'\b([7-9]\d|1[0-2]\d)\b', pp_line)
        if beyer_match:
            beyer = int(beyer_match.group(1))
            if 70 <= beyer <= 130:  # Typical Beyer range
                return beyer
        
        return None
    
    def _extract_field_size(self, pp_line: str) -> Optional[int]:
        """Extract field size from PP line"""
        # Look for patterns like "54-86" or "12" before positions
        field_match = re.search(r'(\d{1,2})-\d{1,2}', pp_line)
        if field_match:
            return int(field_match.group(1))
        
        return None
    
    def parse_horse_pps_from_text(self, horse_text: str) -> List[PastPerformance]:
        """
        Parse all past performance lines for a horse from extracted text
        
        Args:
            horse_text: The full text block for a single horse
        
        Returns:
            List of PastPerformance objects
        """
        pps = []
        
        # Split into lines
        lines = horse_text.split('\n')
        
        # Look for lines that match PP pattern
        # PP lines typically start with a date pattern
        pp_pattern = r'^\d{1,2}[A-Za-z]{3}\d{2}'
        
        for line in lines:
            if re.match(pp_pattern, line.strip()):
                try:
                    pp = self.parse_pp_line_to_pastperformance(line)
                    pps.append(pp)
                except Exception as e:
                    print(f"Error parsing PP line: {e}")
                    print(f"Line: {line[:100]}...")
        
        return pps
    
    def analyze_horse_from_text(self, horse_name: str, horse_text: str) -> Dict:
        """
        Complete analysis of a horse from PDF text
        
        Returns comprehensive pace analysis
        """
        # Parse past performances
        pps = self.parse_horse_pps_from_text(horse_text)
        
        if not pps:
            return {
                'horse_name': horse_name,
                'error': 'No past performances found',
                'running_style': 'UNKNOWN'
            }
        
        # Analyze pace
        pace_analysis = self.pace_analyzer.analyze_horse_pace(horse_name, pps)
        
        # Calculate pace figures for recent races
        pace_figures = []
        for pp in pps[-5:]:  # Last 5 races
            speed_metrics = self.pace_analyzer.analyze_race_speed(pp)
            pace_figures.append({
                'date': pp.date,
                'track': pp.track,
                'distance': pp.distance,
                'beyer': pp.beyer,
                **speed_metrics
            })
        
        return {
            'horse_name': horse_name,
            'running_style': pace_analysis.running_style.value,
            'style_confidence': pace_analysis.running_style_confidence,
            'avg_early_position': pace_analysis.avg_early_position,
            'avg_stretch_position': pace_analysis.avg_stretch_position,
            'avg_finish_position': pace_analysis.avg_finish_position,
            'avg_position_change': pace_analysis.avg_position_change,
            'pace_versatility': pace_analysis.pace_versatility,
            'num_past_performances': len(pps),
            'recent_pace_figures': pace_figures,
            'past_performances': pps
        }


def example_integration():
    """
    Example of how to integrate PDF parser with pace analyzer
    """
    
    # Assume you have extracted text from PDF
    sample_horse_text = """
    Owner: DiBello Racing, LLC (Joseph DiBello)
    Silks: Navy, white star, navy stars on grey sleeves, navy cap
    Trainer: Karyn Wittek ( 0-0-0-0 ) 0.00%
    
    Lady Lala (L)                                        122    Alex Achard (0-0-0-0) 0.00%
    
    B.f.4 Ocean Atlantique - Hipolalilina by High Cotton - Bred in Florida by Kevin W McKathan (Mar 02, 2021)
    
    11Sep25 3 CD  ft  1m  :46¹⁰ 1:10⁴³ 1:35⁴⁷ 3†‡  Str 30000nw1/x    54-86  4 6²j 6⁴ 6² 6⁸ 7¹¹  Morales E   122  bL  23.57
    01Aug25 7 Del ft  1m  :46⁸⁵ 1:10²⁰ 1:35⁴⁵ 3†‡  Str 30000nw1/x    56-75  2 2³ 2³j 3² 3⁹j  Diaz, Jr. H R  122  bL  9.30
    04May25 5 Lam  gd  1¹⁄₈  :47⁴⁶ 1:12⁹⁷ 1:39⁵⁴ 4†‡  Aoc 16000nw1/x-N  76-77  6 3² 3¹ 4³j 5¹¹j  Diaz, Jr. H R  118  bL  17.40
    """
    
    # Create bridge
    bridge = PDFToPaceAnalyzer()
    
    # Analyze horse
    analysis = bridge.analyze_horse_from_text("Lady Lala", sample_horse_text)
    
    # Print results
    print("=" * 70)
    print(f"PACE ANALYSIS: {analysis['horse_name']}")
    print("=" * 70)
    print(f"Running Style:      {analysis['running_style']} (Confidence: {analysis['style_confidence']:.2%})")
    print(f"Avg Early Position: {analysis['avg_early_position']:.1f}")
    print(f"Avg Stretch Position: {analysis['avg_stretch_position']:.1f}")
    print(f"Avg Finish Position: {analysis['avg_finish_position']:.1f}")
    print(f"Avg Position Change: {analysis['avg_position_change']:+.1f}")
    print(f"Pace Versatility:   {analysis['pace_versatility']:.2%}")
    print(f"\nPast Performances Found: {analysis['num_past_performances']}")
    
    print("\nRecent Pace Figures:")
    for pf in analysis['recent_pace_figures']:
        print(f"  {pf['date']} {pf['track']} {pf['distance']:.1f}f - Beyer: {pf.get('beyer', 'N/A')}")


if __name__ == "__main__":
    example_integration()
