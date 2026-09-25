#!/usr/bin/env python3
"""
SIMD XML Parser - Equibase Past Performance XML Parser
Parses SIMD (Simulcast) format XML files from Equibase 2023 data.

This parser is designed for 2023 data validation and does NOT modify
the existing PDF parser (per user's instructions).

Author: Claude Code
Date: October 21, 2025
"""

import xml.etree.ElementTree as ET
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime
import re

# Import existing data structures from PDF parser for compatibility
try:
    from .pdf_parser import PDFHorse, PDFRace
except ImportError:
    from pdf_parser import PDFHorse, PDFRace


class SIMDXMLParser:
    """
    Parser for Equibase SIMD XML files (past performances).

    SIMD XML provides 100% position call extraction, unlike PDFs.
    Also includes equipment changes, medications, and trip notes.
    """

    def __init__(self, debug: bool = False):
        self.debug = debug

    def parse_xml_file(self, xml_path: str) -> List[PDFRace]:
        """
        Parse SIMD XML file and return list of Race objects.

        Args:
            xml_path: Path to SIMD XML file

        Returns:
            List of PDFRace objects (compatible with existing system)
        """
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()

            races = []
            for race_elem in root.findall('.//Race'):
                race = self._parse_race_element(race_elem, xml_path)
                if race:
                    races.append(race)

            if self.debug:
                print(f"✓ Parsed {len(races)} races from {xml_path}")

            return races

        except Exception as e:
            print(f"✗ Error parsing {xml_path}: {e}")
            if self.debug:
                import traceback
                traceback.print_exc()
            return []

    def _parse_race_element(self, race_elem: ET.Element, xml_path: str) -> Optional[PDFRace]:
        """Parse a single Race element from XML."""
        try:
            # Extract race metadata
            race_number = int(race_elem.findtext('RaceNumber', '0'))

            # Distance
            distance_elem = race_elem.find('.//Distance')
            distance_id = int(distance_elem.findtext('DistanceId', '600'))  # In yards
            distance_text = distance_elem.findtext('PublishedValue', '6F')
            distance_furlongs = distance_id / 220  # Convert yards to furlongs

            # Surface
            surface_elem = race_elem.find('.//Course/CourseType/Value')
            surface_code = surface_elem.text if surface_elem is not None else 'D'
            surface_map = {'D': 'Dirt', 'T': 'Turf', 'A': 'All Weather', 'S': 'Synthetic'}
            surface = surface_map.get(surface_code, 'Dirt')

            # Track (from filename)
            track_code = self._extract_track_from_filename(xml_path)

            # Race date (from filename)
            race_date = self._extract_date_from_filename(xml_path)

            # Purse
            purse_text = race_elem.findtext('PurseUSA', '0')
            try:
                purse = float(purse_text)
            except:
                purse = 0.0

            # Race type
            race_type_elem = race_elem.find('.//RaceType/RaceType')
            race_type = race_type_elem.text if race_type_elem is not None else ''

            # Post time
            post_time = race_elem.findtext('PostTime', '')

            # Parse horses
            # Note: In SIMD XML, there are MULTIPLE <Starters> elements (one per horse)
            # Each <Starters> contains: <Horse>, <ProgramNumber>, <Trainer>, <Jockey>, etc.
            horses = []
            for starters_elem in race_elem.findall('.//Starters'):
                horse_elem = starters_elem.find('./Horse')
                if horse_elem is not None:
                    # Get ProgramNumber from same <Starters> element
                    program_number = starters_elem.findtext('ProgramNumber', '0')

                    # Parse the horse with the correct program number
                    horse = self._parse_horse_element(horse_elem, program_number, starters_elem)
                    if horse:
                        horses.append(horse)

            # Create race object
            race = PDFRace(
                track_code=track_code,
                track_name=track_code,
                date=race_date,
                race_number=race_number,
                distance=int(distance_furlongs * 100),  # Convert to integer format (e.g., 600 = 6F)
                distance_text=distance_text,
                surface=surface_code,
                surface_description=surface,
                track_condition='FT',  # Will be extracted from PPs if available
                race_type=race_type,
                race_type_description='',
                age_restriction='',
                sex_restriction='',
                purse=purse,
                post_time=post_time,
                horses=horses
            )

            return race

        except Exception as e:
            if self.debug:
                print(f"✗ Error parsing race element: {e}")
            return None

    def _parse_horse_element(self, horse_elem: ET.Element, program_number: str, starters_elem: ET.Element) -> Optional[PDFHorse]:
        """Parse a single Horse element from XML.

        Args:
            horse_elem: The <Horse> XML element (contains horse details and breeding)
            program_number: Program number extracted from <Starters> element
            starters_elem: The <Starters> parent element (contains race-specific data)
        """
        try:
            # Basic info from <Horse>
            horse_name = horse_elem.findtext('HorseName', 'Unknown')
            # program_number passed as parameter (from <Starters>)

            # Trainer (child of <Starters>, not <Horse>)
            trainer_elem = starters_elem.find('./Trainer')
            if trainer_elem is not None:
                trainer_first = trainer_elem.findtext('FirstName', '')
                trainer_last = trainer_elem.findtext('LastName', '')
                trainer_name = f"{trainer_first} {trainer_last}".strip()
            else:
                trainer_name = 'Unknown'

            # Jockey (child of <Starters>, not <Horse>)
            jockey_elem = starters_elem.find('./Jockey')
            if jockey_elem is not None:
                jockey_first = jockey_elem.findtext('FirstName', '')
                jockey_last = jockey_elem.findtext('LastName', '')
                jockey_name = f"{jockey_first} {jockey_last}".strip()
            else:
                jockey_name = 'Unknown'

            # Odds (child of <Starters>)
            odds_text = starters_elem.findtext('Odds', '0/1')

            # Weight (child of <Starters>)
            weight = int(starters_elem.findtext('WeightCarried', '0'))

            # Breeding
            sire_elem = horse_elem.find('.//Sire')
            dam_elem = horse_elem.find('.//Dam')
            sire_name = sire_elem.findtext('HorseName', '') if sire_elem is not None else ''
            dam_name = dam_elem.findtext('HorseName', '') if dam_elem is not None else ''

            # Equipment and medication (today's race)
            equipment_elem = horse_elem.find('.//Equipment/Value')
            medication_elem = horse_elem.find('.//Medication/Value')
            equipment_code = equipment_elem.text if equipment_elem is not None else ''
            medication_code = medication_elem.text if medication_elem is not None else ''

            today_equipment = {
                'blinkers': 'B' in equipment_code or 'F' in equipment_code,  # B=blinkers, F=front blinkers
                'lasix': 'L' in medication_code
            }

            # Parse past performances
            past_performances = []
            for pp_elem in horse_elem.findall('.//PastPerformance'):
                pp = self._parse_past_performance(pp_elem)
                if pp:
                    past_performances.append(pp)

            # Calculate speed figures from PPs
            speed_figures = [pp.get('speed_figure', 0) for pp in past_performances if pp.get('speed_figure', 0) > 0]
            best_speed_figure = max(speed_figures) if speed_figures else 0
            last_speed_figure = speed_figures[0] if speed_figures else 0
            avg_speed_figure = int(sum(speed_figures) / len(speed_figures)) if speed_figures else 0

            # Calculate running style from position calls
            running_style, style_metrics = self._calculate_running_style(past_performances)

            # Career stats from RaceSummary
            career_stats = self._extract_career_stats(horse_elem)

            # Create horse object
            horse = PDFHorse(
                program_number=program_number,
                name=horse_name,
                jockey_name=jockey_name,
                trainer_name=trainer_name,
                morning_line_odds=odds_text,
                weight=weight,
                age=0,  # Calculate from foaling date if needed
                sex='',
                best_speed_figure=best_speed_figure,
                last_speed_figure=last_speed_figure,
                avg_speed_figure=avg_speed_figure,
                career_starts=career_stats.get('starts', 0),
                career_wins=career_stats.get('wins', 0),
                career_seconds=career_stats.get('seconds', 0),
                career_thirds=career_stats.get('thirds', 0),
                career_earnings=career_stats.get('earnings', 0.0),
                days_since_last_race=999,  # Calculate from last PP if needed
                last_race_date='',
                last_race_finish=0,
                sire_name=sire_name,
                dam_name=dam_name,
                past_performances=past_performances,
                running_style=running_style,
                style_confidence=style_metrics.get('confidence', 0.0),
                avg_early_position=style_metrics.get('avg_early', 0.0),
                avg_stretch_position=style_metrics.get('avg_stretch', 0.0),
                avg_finish_position=style_metrics.get('avg_finish', 0.0),
                avg_position_change=style_metrics.get('avg_change', 0.0),
                versatility=style_metrics.get('versatility', 0.5),
                today_equipment=today_equipment
            )

            return horse

        except Exception as e:
            if self.debug:
                print(f"✗ Error parsing horse element: {e}")
            return None

    def _parse_past_performance(self, pp_elem: ET.Element) -> Optional[Dict]:
        """Parse a single PastPerformance element."""
        try:
            pp = {}

            # Track and date
            track_elem = pp_elem.find('.//Track/TrackID')
            pp['track'] = track_elem.text if track_elem is not None else ''

            race_date_text = pp_elem.findtext('RaceDate', '')
            if race_date_text:
                pp['date'] = race_date_text.split('+')[0]  # Remove timezone
            else:
                pp['date'] = ''

            # Distance
            distance_elem = pp_elem.find('.//Distance/DistanceId')
            if distance_elem is not None:
                distance_yards = int(distance_elem.text)
                pp['distance'] = distance_yards / 220  # Convert to furlongs
            else:
                pp['distance'] = 6.0  # Default

            # Surface
            surface_elem = pp_elem.find('.//Course/CourseType/Value')
            pp['surface'] = surface_elem.text if surface_elem is not None else 'D'

            # Extract position calls from Start element
            start_elem = pp_elem.find('.//Start')
            if start_elem is not None:
                # Position calls (S, 1, 2, 3, 4, 5, F)
                position_calls = {}
                for poc_elem in start_elem.findall('.//PointOfCall'):
                    call_name = poc_elem.findtext('PointOfCall', '')
                    position = int(poc_elem.findtext('Position', '0'))
                    if call_name and position > 0:
                        position_calls[call_name] = position

                # Map to our standard format
                pp['first_call'] = position_calls.get('1', 0)
                pp['second_call'] = position_calls.get('2', 0)
                pp['stretch'] = position_calls.get('5', 0)  # 5th call is typically stretch
                pp['finish'] = position_calls.get('F', 0)
                pp['early'] = position_calls.get('1', 0)  # For compatibility

                # Official finish
                pp['finish_position'] = int(start_elem.findtext('OfficialFinish', '0'))

                # Speed figure
                pp['speed_figure'] = int(start_elem.findtext('SpeedFigure', '0'))

                # Class rating
                pp['class_rating'] = int(start_elem.findtext('ClassRating', '0'))

                # Trip notes
                pp['short_comment'] = start_elem.findtext('ShortComment', '')
                pp['long_comment'] = start_elem.findtext('LongComment', '')

                # Equipment/medication in that race
                equip_elem = start_elem.find('.//Equipment/Value')
                med_elem = start_elem.find('.//Medication/Value')
                pp['equipment'] = equip_elem.text if equip_elem is not None else ''
                pp['medication'] = med_elem.text if med_elem is not None else ''

            # Fractional times
            fractions = []
            for frac_elem in pp_elem.findall('.//Fractions'):
                frac_time = int(frac_elem.findtext('Time', '0'))
                if frac_time > 0:
                    fractions.append(frac_time)
            pp['fractional_times'] = fractions

            return pp

        except Exception as e:
            if self.debug:
                print(f"✗ Error parsing past performance: {e}")
            return None

    def _calculate_running_style(self, past_performances: List[Dict]) -> tuple:
        """
        Calculate running style from position calls.

        Returns:
            Tuple of (style: str, metrics: dict)
        """
        if not past_performances:
            return 'P', {'confidence': 0.0, 'avg_early': 0.0, 'avg_stretch': 0.0,
                        'avg_finish': 0.0, 'avg_change': 0.0, 'versatility': 0.5}

        # Collect position data
        early_positions = []
        stretch_positions = []
        finish_positions = []

        for pp in past_performances:
            first_call = pp.get('first_call', 0)
            second_call = pp.get('second_call', 0)
            stretch = pp.get('stretch', 0)
            finish = pp.get('finish', 0)

            if first_call > 0:
                # Early position = average of first two calls
                if second_call > 0:
                    early_pos = (first_call + second_call) / 2
                else:
                    early_pos = first_call
                early_positions.append(early_pos)

            if stretch > 0:
                stretch_positions.append(stretch)

            if finish > 0:
                finish_positions.append(finish)

        # Calculate averages
        avg_early = sum(early_positions) / len(early_positions) if early_positions else 5.0
        avg_stretch = sum(stretch_positions) / len(stretch_positions) if stretch_positions else 5.0
        avg_finish = sum(finish_positions) / len(finish_positions) if finish_positions else 5.0

        # Calculate position change (ground gained/lost)
        position_changes = []
        for pp in past_performances:
            early = pp.get('first_call', 0)
            finish = pp.get('finish', 0)
            if early > 0 and finish > 0:
                # Positive = gained ground (closed), Negative = lost ground
                position_changes.append(early - finish)

        avg_change = sum(position_changes) / len(position_changes) if position_changes else 0.0

        # Classify running style
        if avg_early <= 2.0:
            style = 'E'  # Early speed
        elif avg_early <= 3.5:
            style = 'P'  # Presser
        elif avg_change >= 2.0:
            style = 'C'  # Closer (gains ground)
        else:
            style = 'S'  # Stalker

        # Calculate confidence based on data availability
        confidence = min(len(early_positions) / 5.0, 1.0)  # Max confidence with 5+ races

        # Calculate versatility (how consistent the style is)
        if len(early_positions) >= 2:
            import statistics
            variance = statistics.variance(early_positions)
            versatility = max(0.0, min(1.0, variance / 10.0))  # Normalize to 0-1
        else:
            versatility = 0.5

        metrics = {
            'confidence': confidence,
            'avg_early': avg_early,
            'avg_stretch': avg_stretch,
            'avg_finish': avg_finish,
            'avg_change': avg_change,
            'versatility': versatility
        }

        return style, metrics

    def _extract_career_stats(self, horse_elem: ET.Element) -> Dict:
        """Extract career statistics from RaceSummary elements."""
        stats = {
            'starts': 0,
            'wins': 0,
            'seconds': 0,
            'thirds': 0,
            'earnings': 0.0
        }

        # Sum up all race summaries
        for summary_elem in horse_elem.findall('.//RaceSummary'):
            stats['starts'] += int(summary_elem.findtext('NumberOfStarts', '0'))
            stats['wins'] += int(summary_elem.findtext('NumberOfWins', '0'))
            stats['seconds'] += int(summary_elem.findtext('NumberOfSeconds', '0'))
            stats['thirds'] += int(summary_elem.findtext('NumberOfThirds', '0'))

            earnings_text = summary_elem.findtext('EarningsUSA', '0')
            try:
                stats['earnings'] += float(earnings_text)
            except:
                pass

        return stats

    def _extract_track_from_filename(self, xml_path: str) -> str:
        """Extract track code from SIMD filename."""
        # Format: SIMD20230101AQU_USA.xml
        import os
        filename = os.path.basename(xml_path)
        match = re.search(r'SIMD\d{8}([A-Z]+)_', filename)
        if match:
            return match.group(1)
        return 'UNK'

    def _extract_date_from_filename(self, xml_path: str) -> str:
        """Extract date from SIMD filename."""
        # Format: SIMD20230101AQU_USA.xml
        import os
        filename = os.path.basename(xml_path)
        match = re.search(r'SIMD(\d{8})', filename)
        if match:
            date_str = match.group(1)
            # Convert YYYYMMDD to YYYY-MM-DD
            return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
        return '2023-01-01'


# Test function
def test_simd_parser():
    """Test the SIMD parser on a sample file."""
    import sys

    if len(sys.argv) > 1:
        xml_file = sys.argv[1]
    else:
        xml_file = "equibase 2023 data/2023 PPs/SIMD20230101AQU_USA.xml"

    print(f"Testing SIMD parser on: {xml_file}")
    print("=" * 80)

    parser = SIMDXMLParser(debug=True)
    races = parser.parse_xml_file(xml_file)

    print(f"\n✓ Parsed {len(races)} races")

    if races:
        race = races[0]
        print(f"\nRace 1 details:")
        print(f"  Track: {race.track_code}")
        print(f"  Date: {race.date}")
        print(f"  Distance: {race.distance_text}")
        print(f"  Surface: {race.surface_description}")
        print(f"  Horses: {len(race.horses)}")

        if race.horses:
            horse = race.horses[0]
            print(f"\nFirst horse:")
            print(f"  #{horse.program_number}: {horse.name}")
            print(f"  Jockey: {horse.jockey_name}")
            print(f"  Trainer: {horse.trainer_name}")
            print(f"  Best Beyer: {horse.best_speed_figure}")
            print(f"  Running Style: {horse.running_style} (confidence: {horse.style_confidence:.2f})")
            print(f"  Equipment: Blinkers={horse.today_equipment['blinkers']}, Lasix={horse.today_equipment['lasix']}")
            print(f"  Past Performances: {len(horse.past_performances)}")

            if horse.past_performances:
                pp = horse.past_performances[0]
                print(f"\n  Most recent PP:")
                print(f"    Date: {pp.get('date', 'N/A')}")
                print(f"    Track: {pp.get('track', 'N/A')}")
                print(f"    Distance: {pp.get('distance', 0):.1f}F")
                print(f"    First call: {pp.get('first_call', 0)}")
                print(f"    Second call: {pp.get('second_call', 0)}")
                print(f"    Stretch: {pp.get('stretch', 0)}")
                print(f"    Finish: {pp.get('finish', 0)}")
                print(f"    Speed figure: {pp.get('speed_figure', 0)}")
                print(f"    Trip note: {pp.get('short_comment', 'N/A')}")


if __name__ == '__main__':
    test_simd_parser()
