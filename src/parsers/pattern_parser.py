#!/usr/bin/env python3
"""
Pattern-Based Parser (Parser 4) - Full PDF Extraction + Pattern Matching

Strategy:
1. Extract complete PDF text at once
2. Identify race sections using patterns
3. Within each race, find horse blocks based on known structure
4. Extract fields using regex patterns learned from October PPs

Advantages over Parser 1 & 3:
- More flexible than coordinates (works across format variations)
- Better than line-by-line (can see full context)
- Can handle multi-line names and complex layouts
"""

import re
import pdfplumber
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass


@dataclass
class PatternHorse:
    """Horse data extracted using pattern matching"""
    program_number: str
    name: str
    jockey_name: str
    trainer_name: str
    ml_odds: str
    weight: int
    age: int
    sex: str
    sire_name: str
    dam_name: str
    best_beyer: int
    career_record: str

    # Confidence scores
    name_confidence: float = 0.0
    jockey_confidence: float = 0.0
    trainer_confidence: float = 0.0


@dataclass
class PatternRace:
    """Race data extracted using pattern matching"""
    race_number: int
    distance_text: str
    surface: str
    race_type: str
    purse: int
    horses: List[PatternHorse]


class PatternBasedParser:
    """Extract racing data using full-text pattern matching"""

    def __init__(self):
        """Initialize pattern-based parser with known patterns"""

        # Race header patterns - matches "Race1", "RACE1", or standalone race number
        self.race_header_pattern = r'(?:RACE|Race)\s*(\d+)|^[\s]*(\d{1,2})[\s]+\d+\-\d+\s+Owner:'
        self.race_label_pattern = r'\d{1,2}/\d{1,2}/\d{4}Race(\d+)'  # Format like "10/18/2025Race1"
        self.distance_pattern = r'((?:One|Two|Three|Four|Five|Six|Seven|Eight|Nine|Ten|Eleven|Twelve)\s+(?:And\s+)?(?:One|Two|Three|Four|Five|Six|Seven|Eight|Nine|Ten|Eleven|Twelve|A)?\s*(?:Half|Quarter|Sixteenth)?\s*Mile(?:s)?(?:\s+And\s+\w+)?)'
        self.purse_pattern = r'Purse\$[\d,]+(?:\.\d{2})?'

        # Horse entry patterns
        # Pattern: "Pgm# ML_Odds Owner: [name]"
        # Note: Program number can be right-aligned with spaces before it
        self.horse_entry_pattern = r'^\s*(\d{1,2}[A-Z]?)\s+([\d\-/]+)\s+Owner:'

        # Name extraction patterns
        # Horse names often appear after "Owner:" before trainer/jockey info
        self.horse_name_pattern = r'Owner:\s*([A-Za-z\s\'.&-]+?)(?:\s+Trainer:|\s+\d+\.\d+|\s+Life:)'

        # Trainer pattern: "Trainer: Name (record)"
        self.trainer_pattern = r'Trainer:\s*([^(]+?)\s*\('

        # Jockey pattern:
        # Primary: Extract from most recent race line (format: "LastnameFirstInitial" like "GaffalioneT")
        self.jockey_from_pp_pattern = r'[A-Z][a-z]{2,}[A-Z]{1,2}\s+\d{3}'  # Format: GaffalioneT 121
        # Fallback: After post color or "ClmPrc"
        self.jockey_pattern = r'(?:Red|Blue|White|Black|Green|Yellow|Orange|Pink|Gray|Purple|Brown)\s+([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+(?:\s+Jr\.?)?)'
        self.jockey_alt_pattern = r'(?:ClmPrc|Clm\s+Prc)\s+([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+(?:\s+Jr\.?)?)'

        # Beyer speed figure pattern
        self.beyer_pattern = r'Best\s+Beyer:\s*(\d+)'

        # Sire/Dam patterns
        self.sire_pattern = r'Sire:\s*([A-Za-z\s\'.&-]+?)(?:\s+Dam:|\s+\()'
        self.dam_pattern = r'Dam:\s*([A-Za-z\s\'.&-]+?)(?:\s+\(|\s+DamSire:)'

    def extract_complete_text(self, pdf_path: str) -> str:
        """
        Extract all text from PDF at once.

        Returns: Complete PDF text as single string
        """
        full_text = []

        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                # Extract text preserving layout
                page_text = page.extract_text(layout=True)
                if page_text:
                    full_text.append(page_text)

        return '\n'.join(full_text)

    def split_into_races(self, full_text: str) -> List[Tuple[int, str]]:
        """
        Split complete text into race sections.

        Returns: List of (race_number, race_text) tuples
        """
        # PRIMARY STRATEGY: Look for program #1 entries (most reliable race boundary)
        # Race labels like "10/18/2025Race1" can appear mid-race, but program #1 marks the start
        return self._split_by_horse_entries(full_text)

    def _split_by_horse_entries(self, full_text: str) -> List[Tuple[int, str]]:
        """
        Fallback method: Split races by looking for program #1 entries.
        Assumes each race starts with program #1.
        """
        # Find all "1 [odds] Owner:" patterns (start of race)
        pgm1_pattern = r'^\s*1\s+[\d\-/]+\s+Owner:'
        splits = list(re.finditer(pgm1_pattern, full_text, re.MULTILINE))

        races = []
        for i, match in enumerate(splits):
            race_num = i + 1  # Infer race number from order
            start_pos = match.start()

            if i + 1 < len(splits):
                end_pos = splits[i + 1].start()
            else:
                end_pos = len(full_text)

            race_text = full_text[start_pos:end_pos]
            races.append((race_num, race_text))

        return races

    def extract_race_metadata(self, race_text: str) -> Dict:
        """Extract race-level metadata (distance, surface, purse)"""
        metadata = {
            'distance': '',
            'surface': 'Dirt',  # Default
            'purse': 0
        }

        # Extract distance
        distance_match = re.search(self.distance_pattern, race_text, re.IGNORECASE)
        if distance_match:
            metadata['distance'] = distance_match.group(1)

        # Determine surface
        if 'Turf' in race_text or 'turf' in race_text or 'Haggin' in race_text:
            metadata['surface'] = 'Turf'

        # Extract purse
        purse_matches = re.findall(self.purse_pattern, race_text)
        if purse_matches:
            # Usually the first large dollar amount is the purse
            for purse_str in purse_matches:
                # Remove "Purse", "$", and commas, then extract number
                purse_clean = purse_str.replace('Purse', '').replace('$', '').replace(',', '').split('.')[0]
                try:
                    purse_val = int(purse_clean)
                    if purse_val >= 50000:  # Reasonable purse minimum
                        metadata['purse'] = purse_val
                        break
                except ValueError:
                    continue

        return metadata

    def find_horse_sections(self, race_text: str) -> List[str]:
        """
        Find individual horse sections within a race.

        Returns: List of text blocks, one per horse
        """
        # Find all horse entry markers (program number + owner line)
        entry_matches = list(re.finditer(self.horse_entry_pattern, race_text, re.MULTILINE))

        horse_sections = []
        for i, match in enumerate(entry_matches):
            start_pos = match.start()

            # Find end position (start of next horse or end of race)
            if i + 1 < len(entry_matches):
                end_pos = entry_matches[i + 1].start()
            else:
                # End of race - look for next race header or end of text
                next_race = re.search(r'\nRACE\s+\d+', race_text[start_pos:])
                if next_race:
                    end_pos = start_pos + next_race.start()
                else:
                    end_pos = len(race_text)

            horse_text = race_text[start_pos:end_pos]
            horse_sections.append(horse_text)

        return horse_sections

    def extract_horse_from_section(self, horse_text: str, program_number: str) -> Optional[PatternHorse]:
        """
        Extract horse data from a text section.

        Args:
            horse_text: Text block for one horse
            program_number: Already extracted program number

        Returns: PatternHorse object or None if extraction fails
        """
        horse = PatternHorse(
            program_number=program_number,
            name='Unknown',
            jockey_name='Unknown',
            trainer_name='Unknown',
            ml_odds='',
            weight=0,
            age=0,
            sex='',
            sire_name='Unknown',
            dam_name='Unknown',
            best_beyer=0,
            career_record=''
        )

        # Extract horse name
        name_match = re.search(self.horse_name_pattern, horse_text)
        if name_match:
            horse.name = name_match.group(1).strip()
            horse.name_confidence = 0.90
        else:
            # Fallback: Look for capitalized name after Owner:
            owner_line = horse_text.split('\n')[0]  # First line has Owner:
            # Extract text between "Owner:" and next keyword
            fallback_match = re.search(r'Owner:\s*([A-Za-z\s\'.&-]+)', owner_line)
            if fallback_match:
                horse.name = fallback_match.group(1).strip()
                horse.name_confidence = 0.70

        # Extract trainer
        trainer_match = re.search(self.trainer_pattern, horse_text)
        if trainer_match:
            trainer = trainer_match.group(1).strip()
            # Clean up spacing
            trainer = re.sub(r'([a-z])([A-Z])', r'\1 \2', trainer)
            horse.trainer_name = trainer
            horse.trainer_confidence = 0.90

        # Extract jockey - try multiple methods in priority order
        jockey = None  # Initialize to avoid errors

        # METHOD 1: Extract from garbled current jockey/trainer line
        # This line appears between "Silks:" and breeding info, contains weight + jockey name
        # Pattern: Look for weight (3 digits) followed by name like "KeithJ" or "TylerG"
        # in the section between Silks and breeding (before "by" keyword)
        current_jockey_match = re.search(r'\d{3}\s+([A-Z][a-z]+[A-Z](?:[a-z]+)?)\s*\(', horse_text)
        if current_jockey_match:
            jockey_raw = current_jockey_match.group(1)
            # Split like "KeithJ" -> "Keith J" or "TylerG" -> "Tyler G"
            jockey = re.sub(r'([a-z])([A-Z])', r'\1 \2', jockey_raw)
            horse.jockey_name = jockey
            horse.jockey_confidence = 0.90

        # METHOD 2: from most recent race line (fallback)
        if not jockey:
            pp_jockey_matches = re.findall(self.jockey_from_pp_pattern, horse_text)
            if pp_jockey_matches:
                # Take first match (most recent race)
                jockey_raw = pp_jockey_matches[0].split()[0]  # Get just the name part
                # Split LastnameFirstInitial into "Lastname FirstInitial"
                jockey = re.sub(r'([a-z])([A-Z])', r'\1 \2', jockey_raw)
                horse.jockey_name = jockey
                horse.jockey_confidence = 0.75  # Lower confidence - past jockey may have changed

        # METHOD 3: Try to extract from post color line
        if not jockey:
            jockey_match = re.search(self.jockey_pattern, horse_text, re.IGNORECASE)
            if not jockey_match:
                jockey_match = re.search(self.jockey_alt_pattern, horse_text)

            if jockey_match:
                jockey = jockey_match.group(1).strip()
                # Clean up spacing
                jockey = re.sub(r'([a-z])([A-Z])', r'\1 \2', jockey)
                jockey = re.sub(r'\.([A-Z])', r'. \1', jockey)
                jockey = re.sub(r',([A-Z])', r', \1', jockey)
                horse.jockey_name = jockey
                horse.jockey_confidence = 0.75

        # If still no jockey found, set Unknown
        if not jockey:
            horse.jockey_name = 'Unknown'
            horse.jockey_confidence = 0.0

        # Extract Beyer
        beyer_match = re.search(self.beyer_pattern, horse_text)
        if beyer_match:
            horse.best_beyer = int(beyer_match.group(1))

        # Extract sire
        sire_match = re.search(self.sire_pattern, horse_text)
        if sire_match:
            horse.sire_name = sire_match.group(1).strip()

        # Extract dam
        dam_match = re.search(self.dam_pattern, horse_text)
        if dam_match:
            horse.dam_name = dam_match.group(1).strip()

        return horse

    def parse_race(self, race_number: int, race_text: str) -> Optional[PatternRace]:
        """
        Parse a single race from text.

        Returns: PatternRace object or None if parsing fails
        """
        # Extract metadata
        metadata = self.extract_race_metadata(race_text)

        # Find horse sections
        horse_sections = self.find_horse_sections(race_text)

        if not horse_sections:
            return None

        # Extract each horse
        horses = []
        for horse_text in horse_sections:
            # Extract program number from first line
            entry_match = re.search(self.horse_entry_pattern, horse_text, re.MULTILINE)
            if not entry_match:
                continue

            program_number = entry_match.group(1)
            ml_odds = entry_match.group(2)

            # Extract horse data
            horse = self.extract_horse_from_section(horse_text, program_number)
            if horse:
                horse.ml_odds = ml_odds
                horses.append(horse)

        if not horses:
            return None

        race = PatternRace(
            race_number=race_number,
            distance_text=metadata['distance'],
            surface=metadata['surface'],
            race_type='',  # Would need more pattern analysis
            purse=metadata['purse'],
            horses=horses
        )

        return race

    def parse(self, pdf_path: str, debug: bool = False) -> List[PatternRace]:
        """
        Parse PDF using pattern-based approach.

        Args:
            pdf_path: Path to PDF file
            debug: Print debug information

        Returns: List of PatternRace objects
        """
        if debug:
            print("="*80)
            print(" PATTERN-BASED PARSER (Parser 4)")
            print("="*80)
            print()

        # Step 1: Extract complete text
        if debug:
            print("Step 1: Extracting complete PDF text...")
        full_text = self.extract_complete_text(pdf_path)
        if debug:
            print(f"  Extracted {len(full_text)} characters")
            print()

        # Step 2: Split into races
        if debug:
            print("Step 2: Splitting into race sections...")
        race_sections = self.split_into_races(full_text)
        if debug:
            print(f"  Found {len(race_sections)} races")
            print()

        # Step 3: Parse each race
        if debug:
            print("Step 3: Parsing each race...")
        races = []
        for race_num, race_text in race_sections:
            race = self.parse_race(race_num, race_text)
            if race:
                races.append(race)
                if debug:
                    print(f"  Race {race_num}: {len(race.horses)} horses")

        if debug:
            print()
            print(f"Parsed {len(races)} races, {sum(len(r.horses) for r in races)} total horses")
            print()

        return races


def test_pattern_parser():
    """Test the pattern-based parser"""
    import sys

    pdf_path = 'Keeneland October PPs/10-18-25-kee-ppspdf.pdf'
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]

    parser = PatternBasedParser()
    races = parser.parse(pdf_path, debug=True)

    print("="*80)
    print(" QUALITY ANALYSIS")
    print("="*80)
    print()

    total_horses = sum(len(r.horses) for r in races)

    # Check quality
    generic_names = 0
    unknown_jockeys = 0
    unknown_trainers = 0
    high_conf_names = 0
    high_conf_jockeys = 0
    high_conf_trainers = 0

    for race in races:
        for h in race.horses:
            if h.name == 'Unknown' or h.name.startswith('Horse '):
                generic_names += 1
            elif h.name_confidence >= 0.80:
                high_conf_names += 1

            if h.jockey_name == 'Unknown':
                unknown_jockeys += 1
            elif h.jockey_confidence >= 0.80:
                high_conf_jockeys += 1

            if h.trainer_name == 'Unknown':
                unknown_trainers += 1
            elif h.trainer_confidence >= 0.80:
                high_conf_trainers += 1

    name_quality = (total_horses - generic_names) / total_horses * 100 if total_horses > 0 else 0
    jockey_quality = (total_horses - unknown_jockeys) / total_horses * 100 if total_horses > 0 else 0
    trainer_quality = (total_horses - unknown_trainers) / total_horses * 100 if total_horses > 0 else 0
    overall = (name_quality + jockey_quality + trainer_quality) / 3

    print(f"Total Horses: {total_horses}")
    print()
    print(f"Horse Names: {name_quality:.1f}% ({total_horses - generic_names}/{total_horses})")
    print(f"  High confidence (80%+): {high_conf_names}")
    print()
    print(f"Jockeys: {jockey_quality:.1f}% ({total_horses - unknown_jockeys}/{total_horses})")
    print(f"  High confidence (80%+): {high_conf_jockeys}")
    print()
    print(f"Trainers: {trainer_quality:.1f}% ({total_horses - unknown_trainers}/{total_horses})")
    print(f"  High confidence (80%+): {high_conf_trainers}")
    print()
    print(f"Overall Quality: {overall:.1f}%")
    print()


if __name__ == '__main__':
    test_pattern_parser()
