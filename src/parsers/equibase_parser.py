"""
Equibase XML Parser
Parses SIMD (results) and TCH (past performance) XML files
"""

import xml.etree.ElementTree as ET
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime
import re


@dataclass
class Horse:
    """Horse data from race"""
    name: str
    program_number: str
    post_position: int
    jockey_name: str
    jockey_key: str
    trainer_name: str
    trainer_key: str
    owner: str
    weight: int
    age: int
    sex: str
    medication: str
    equipment: str
    morning_line_odds: float
    
    # Performance data
    speed_rating: Optional[int] = None
    final_position: Optional[int] = None
    finish_lengths: Optional[float] = None
    running_positions: Dict[str, int] = None
    comment: Optional[str] = None
    
    # Payoffs
    win_payoff: float = 0.0
    place_payoff: float = 0.0
    show_payoff: float = 0.0


@dataclass
class Race:
    """Race data"""
    race_number: int
    date: str
    track_code: str
    track_name: str
    
    # Race conditions
    distance: int  # In furlongs (e.g., 450 = 4.5F)
    distance_unit: str
    distance_text: str
    surface: str
    surface_description: str
    track_condition: str
    
    # Race type
    race_type: str
    race_type_description: str
    age_restriction: str
    sex_restriction: str
    
    # Purse
    purse: float
    
    # Race info
    post_time: str
    class_rating: Optional[int] = None
    
    # Results
    fractions: List[float] = None
    final_time: float = 0.0
    par_time: Optional[float] = None
    
    # Horses
    horses: List[Horse] = None
    
    # Payoffs
    win_payoff: Optional[Dict[str, float]] = None
    exacta_payoff: Optional[Dict[str, any]] = None
    trifecta_payoff: Optional[Dict[str, any]] = None
    superfecta_payoff: Optional[Dict[str, any]] = None


class EquibaseXMLParser:
    """Parser for Equibase XML files"""
    
    def __init__(self):
        pass
    
    def parse_tch_file(self, file_path: str) -> List[Race]:
        """
        Parse TCH (Track Chart) XML file with past performances and results
        
        Args:
            file_path: Path to TCH XML file
            
        Returns:
            List of Race objects
        """
        tree = ET.parse(file_path)
        root = tree.getroot()
        
        races = []
        
        # Get track info
        track_elem = root.find('.//TRACK')
        track_code = track_elem.find('CODE').text if track_elem.find('CODE') is not None else 'UNK'
        track_name = track_elem.find('n').text if track_elem.find('n') is not None else 'Unknown'
        
        race_date = root.get('RACE_DATE', 'Unknown')
        
        # Parse each race
        for race_elem in root.findall('.//RACE'):
            race = self._parse_tch_race(race_elem, track_code, track_name, race_date)
            races.append(race)
        
        return races
    
    def _parse_tch_race(self, race_elem: ET.Element, track_code: str, 
                        track_name: str, race_date: str) -> Race:
        """Parse individual race from TCH file"""
        
        # Basic race info
        race_number = int(race_elem.get('NUMBER', 0))
        
        # Distance
        distance = int(race_elem.find('DISTANCE').text) if race_elem.find('DISTANCE') is not None else 0
        distance_unit = race_elem.find('DIST_UNIT').text if race_elem.find('DIST_UNIT') is not None else 'F'
        
        # Construct distance text
        if distance_unit == 'F':
            distance_text = f"{distance / 100:.1f}F".replace('.0F', 'F')
        else:
            distance_text = f"{distance}{distance_unit}"
        
        # Surface
        surface = race_elem.find('SURFACE').text if race_elem.find('SURFACE') is not None else 'D'
        course_desc = race_elem.find('COURSE_DESC').text if race_elem.find('COURSE_DESC') is not None else 'Dirt'
        
        # Track condition
        track_condition = race_elem.find('TRK_COND').text if race_elem.find('TRK_COND') is not None else 'FT'
        
        # Race type
        race_type = race_elem.find('TYPE').text if race_elem.find('TYPE') is not None else 'Unknown'
        
        # Purse
        purse = float(race_elem.find('PURSE').text) if race_elem.find('PURSE') is not None else 0.0
        
        # Class rating
        class_rating_elem = race_elem.find('CLASS_RATING')
        class_rating = int(class_rating_elem.text) if class_rating_elem is not None and class_rating_elem.text else None
        
        # Age/sex restrictions
        age_restriction = race_elem.find('AGE_RESTRICTIONS').text if race_elem.find('AGE_RESTRICTIONS') is not None else ''
        
        # Post time
        post_time = race_elem.find('POST_TIME').text if race_elem.find('POST_TIME') is not None else ''
        
        # Fractions
        fractions = []
        for i in range(1, 6):
            frac_elem = race_elem.find(f'FRACTION_{i}')
            if frac_elem is not None and frac_elem.text:
                frac = float(frac_elem.text)
                if frac > 0:
                    fractions.append(frac)
        
        # Final time
        final_time_elem = race_elem.find('WIN_TIME')
        final_time = float(final_time_elem.text) if final_time_elem is not None and final_time_elem.text else 0.0
        
        # Par time
        par_time_elem = race_elem.find('PAR_TIME')
        par_time = float(par_time_elem.text) if par_time_elem is not None and par_time_elem.text else None
        
        # Parse horses
        horses = []
        for entry_elem in race_elem.findall('.//ENTRY'):
            horse = self._parse_tch_horse(entry_elem)
            if horse:
                horses.append(horse)
        
        # Parse exotic payoffs
        exacta_payoff = None
        trifecta_payoff = None
        superfecta_payoff = None
        
        exotic_wagers = race_elem.find('EXOTIC_WAGERS')
        if exotic_wagers is not None:
            for wager_elem in exotic_wagers.findall('WAGER'):
                wager_type = wager_elem.find('WAGER_TYPE').text
                winners = wager_elem.find('WINNERS').text.strip()
                payoff = float(wager_elem.find('PAYOFF').text)
                
                if wager_type == 'Exacta':
                    exacta_payoff = {'winners': winners, 'payoff': payoff}
                elif wager_type == 'Trifecta':
                    trifecta_payoff = {'winners': winners, 'payoff': payoff}
                elif wager_type == 'Superfecta':
                    superfecta_payoff = {'winners': winners, 'payoff': payoff}
        
        # Get win payoffs from horses
        win_payoff = {}
        for horse in horses:
            if horse.final_position == 1 and horse.win_payoff > 0:
                win_payoff[horse.program_number] = horse.win_payoff
        
        return Race(
            race_number=race_number,
            date=race_date,
            track_code=track_code,
            track_name=track_name,
            distance=distance,
            distance_unit=distance_unit,
            distance_text=distance_text,
            surface=surface,
            surface_description=course_desc,
            track_condition=track_condition,
            race_type='Unknown',
            race_type_description=race_type,
            age_restriction=age_restriction,
            sex_restriction='',
            purse=purse,
            post_time=post_time,
            class_rating=class_rating,
            fractions=fractions,
            final_time=final_time,
            par_time=par_time,
            horses=horses,
            win_payoff=win_payoff,
            exacta_payoff=exacta_payoff,
            trifecta_payoff=trifecta_payoff,
            superfecta_payoff=superfecta_payoff
        )
    
    def _parse_tch_horse(self, entry_elem: ET.Element) -> Optional[Horse]:
        """Parse individual horse from TCH entry"""

        # Horse name
        name_elem = entry_elem.find('NAME')
        if name_elem is None or not name_elem.text:
            return None
        name = name_elem.text.strip()
        
        # Program number
        program_num = entry_elem.find('PROGRAM_NUM').text if entry_elem.find('PROGRAM_NUM') is not None else '0'
        
        # Post position
        post_pos_elem = entry_elem.find('POST_POS')
        post_pos = int(post_pos_elem.text) if post_pos_elem is not None and post_pos_elem.text else 0
        
        # Jockey
        jockey_elem = entry_elem.find('JOCKEY')
        if jockey_elem is not None:
            jockey_first = jockey_elem.find('FIRST_NAME').text or ''
            jockey_last = jockey_elem.find('LAST_NAME').text or ''
            jockey_name = f"{jockey_first} {jockey_last}".strip()
            jockey_key = jockey_elem.find('KEY').text or ''
        else:
            jockey_name = 'Unknown'
            jockey_key = ''
        
        # Trainer
        trainer_elem = entry_elem.find('TRAINER')
        if trainer_elem is not None:
            trainer_first = trainer_elem.find('FIRST_NAME').text or ''
            trainer_last = trainer_elem.find('LAST_NAME').text or ''
            trainer_name = f"{trainer_first} {trainer_last}".strip()
            trainer_key = trainer_elem.find('KEY').text or ''
        else:
            trainer_name = 'Unknown'
            trainer_key = ''
        
        # Owner
        owner_elem = entry_elem.find('OWNER')
        owner = owner_elem.text if owner_elem is not None and owner_elem.text else 'Unknown'
        
        # Weight
        weight_elem = entry_elem.find('WEIGHT')
        weight = int(weight_elem.text) if weight_elem is not None and weight_elem.text else 0
        
        # Age
        age_elem = entry_elem.find('AGE')
        age = int(age_elem.text) if age_elem is not None and age_elem.text else 0
        
        # Sex
        sex_elem = entry_elem.find('SEX/CODE')
        sex = sex_elem.text if sex_elem is not None and sex_elem.text else 'U'
        
        # Medication
        meds_elem = entry_elem.find('MEDS')
        medication = meds_elem.text if meds_elem is not None and meds_elem.text else ''
        
        # Equipment
        equip_elem = entry_elem.find('EQUIP')
        equipment = equip_elem.text if equip_elem is not None and equip_elem.text else ''
        
        # Morning line odds
        odds_elem = entry_elem.find('DOLLAR_ODDS')
        ml_odds = float(odds_elem.text) if odds_elem is not None and odds_elem.text else 99.0
        
        # Speed rating
        speed_elem = entry_elem.find('SPEED_RATING')
        speed_rating = int(speed_elem.text) if speed_elem is not None and speed_elem.text else None
        
        # Final position
        final_pos_elem = entry_elem.find('OFFICIAL_FIN')
        final_position = int(final_pos_elem.text) if final_pos_elem is not None and final_pos_elem.text else None
        
        # Running positions
        running_positions = {}
        for poc_elem in entry_elem.findall('POINT_OF_CALL'):
            which = poc_elem.get('WHICH')
            pos_elem = poc_elem.find('POSITION')
            if pos_elem is not None and pos_elem.text:
                pos = int(pos_elem.text)
                if pos > 0:  # Only store valid positions
                    running_positions[which] = pos
        
        # Finish lengths
        final_poc = entry_elem.find('POINT_OF_CALL[@WHICH="FINAL"]')
        finish_lengths = None
        if final_poc is not None:
            lengths_elem = final_poc.find('LENGTHS')
            if lengths_elem is not None and lengths_elem.text:
                finish_lengths = float(lengths_elem.text)
        
        # Comment
        comment_elem = entry_elem.find('COMMENT')
        comment = comment_elem.text if comment_elem is not None and comment_elem.text else None
        
        # Payoffs
        win_payoff_elem = entry_elem.find('WIN_PAYOFF')
        win_payoff = float(win_payoff_elem.text) if win_payoff_elem is not None and win_payoff_elem.text else 0.0
        
        place_payoff_elem = entry_elem.find('PLACE_PAYOFF')
        place_payoff = float(place_payoff_elem.text) if place_payoff_elem is not None and place_payoff_elem.text else 0.0
        
        show_payoff_elem = entry_elem.find('SHOW_PAYOFF')
        show_payoff = float(show_payoff_elem.text) if show_payoff_elem is not None and show_payoff_elem.text else 0.0
        
        return Horse(
            name=name,
            program_number=program_num,
            post_position=post_pos,
            jockey_name=jockey_name,
            jockey_key=jockey_key,
            trainer_name=trainer_name,
            trainer_key=trainer_key,
            owner=owner,
            weight=weight,
            age=age,
            sex=sex,
            medication=medication,
            equipment=equipment,
            morning_line_odds=ml_odds,
            speed_rating=speed_rating,
            final_position=final_position,
            finish_lengths=finish_lengths,
            running_positions=running_positions,
            comment=comment,
            win_payoff=win_payoff,
            place_payoff=place_payoff,
            show_payoff=show_payoff
        )


def parse_equibase_files(tch_file: str) -> List[Race]:
    """
    Convenience function to parse Equibase files
    
    Args:
        tch_file: Path to TCH file
        
    Returns:
        List of Race objects
    """
    parser = EquibaseXMLParser()
    races = parser.parse_tch_file(tch_file)
    return races


if __name__ == '__main__':
    # Test parsing
    import sys
    
    if len(sys.argv) > 1:
        tch_file = sys.argv[1]
        races = parse_equibase_files(tch_file)
        
        print(f"Parsed {len(races)} races")
        for race in races[:3]:  # Show first 3
            print(f"\nRace {race.race_number}: {race.distance_text} {race.surface_description}")
            print(f"  Purse: ${race.purse:,.0f}")
            print(f"  Horses: {len(race.horses)}")
            print(f"  Winner: {race.horses[0].name if race.horses else 'N/A'}")
