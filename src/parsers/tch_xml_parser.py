#!/usr/bin/env python3
"""
TCH XML Parser - Equibase Track Chart Format
Parses race results from 2023 TCH XML files for backtest validation.

This parser is SEPARATE from the production PDF parser and is used
exclusively for historical data validation.
"""

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import List, Optional, Dict
from pathlib import Path


@dataclass
class HorseResult:
    """Individual horse result from a race"""
    program_number: str
    name: str
    official_finish: int
    win_payoff: float
    place_payoff: float
    show_payoff: float
    dollar_odds: float
    jockey_name: str
    trainer_name: str
    post_position: int
    weight: int
    comment: str = ""

    # Position calls (optional, for analysis)
    position_calls: Dict[str, int] = None

    def __post_init__(self):
        if self.position_calls is None:
            self.position_calls = {}


@dataclass
class ExoticWagerResult:
    """Exotic wager outcome"""
    wager_type: str
    winners: str  # e.g., "5-4-6" for trifecta
    payoff: float
    pool_total: int = 0


@dataclass
class RaceResult:
    """Complete race result"""
    track_code: str
    race_date: str
    race_number: int

    # Race conditions
    distance: int
    surface: str
    track_condition: str
    race_type: str
    purse: int

    # Race times
    winning_time: float
    fractional_times: List[float]

    # Results
    horses: List[HorseResult]
    exotic_wagers: List[ExoticWagerResult]

    # Metadata
    post_time: str = ""
    weather: str = ""

    @property
    def winner(self) -> Optional[HorseResult]:
        """Get the race winner"""
        for horse in self.horses:
            if horse.official_finish == 1:
                return horse
        return None

    @property
    def winner_program_number(self) -> Optional[str]:
        """Get winner's program number"""
        winner = self.winner
        return winner.program_number if winner else None

    @property
    def winner_name(self) -> Optional[str]:
        """Get winner's name"""
        winner = self.winner
        return winner.name if winner else None


def parse_tch_file(xml_path: str) -> List[RaceResult]:
    """
    Parse Equibase TCH XML file (race results)

    Args:
        xml_path: Path to TCH XML file

    Returns:
        List of RaceResult objects (one per race in the file)
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()

    # Get track info
    track_elem = root.find('.//TRACK')
    track_code = track_elem.find('CODE').text if track_elem is not None else 'UNK'

    # Get race date from CHART element
    race_date = root.attrib.get('RACE_DATE', '')

    # Parse all races in the file
    races = []
    for race_elem in root.findall('.//RACE'):
        race_result = parse_race(race_elem, track_code, race_date)
        if race_result:
            races.append(race_result)

    return races


def parse_race(race_elem: ET.Element, track_code: str, race_date: str) -> Optional[RaceResult]:
    """Parse a single race from TCH XML"""
    try:
        # Race number
        race_number = int(race_elem.attrib.get('NUMBER', 0))

        # Race conditions
        distance = int(race_elem.findtext('DISTANCE', '0'))
        surface = race_elem.findtext('SURFACE', 'D')
        track_condition = race_elem.findtext('TRK_COND', 'FT')
        race_type = race_elem.findtext('TYPE', 'Unknown')
        purse = int(race_elem.findtext('PURSE', '0'))

        # Times
        winning_time = float(race_elem.findtext('WIN_TIME', '0.0'))
        fractional_times = []
        for i in range(1, 6):  # Up to 5 fractions
            frac_text = race_elem.findtext(f'FRACTION_{i}')
            if frac_text:
                fractional_times.append(float(frac_text))

        # Metadata
        post_time = race_elem.findtext('POST_TIME', '')
        weather = race_elem.findtext('WEATHER', '')

        # Parse horse entries
        horses = []
        for entry_elem in race_elem.findall('.//ENTRY'):
            horse = parse_horse_entry(entry_elem)
            if horse:
                horses.append(horse)

        # Parse exotic wagers
        exotic_wagers = []
        exotic_elem = race_elem.find('.//EXOTIC_WAGERS')
        if exotic_elem is not None:
            for wager_elem in exotic_elem.findall('.//WAGER'):
                wager = parse_exotic_wager(wager_elem)
                if wager:
                    exotic_wagers.append(wager)

        return RaceResult(
            track_code=track_code,
            race_date=race_date,
            race_number=race_number,
            distance=distance,
            surface=surface,
            track_condition=track_condition,
            race_type=race_type,
            purse=purse,
            winning_time=winning_time,
            fractional_times=fractional_times,
            horses=horses,
            exotic_wagers=exotic_wagers,
            post_time=post_time,
            weather=weather
        )

    except Exception as e:
        print(f"Error parsing race: {str(e)}")
        return None


def parse_horse_entry(entry_elem: ET.Element) -> Optional[HorseResult]:
    """Parse a single horse entry from TCH XML"""
    try:
        # Basic info
        name = entry_elem.findtext('NAME', '').strip()
        program_num = entry_elem.findtext('PROGRAM_NUM', '0')
        official_fin = int(entry_elem.findtext('OFFICIAL_FIN', '0'))

        # Payoffs
        win_payoff = float(entry_elem.findtext('WIN_PAYOFF', '0.0'))
        place_payoff = float(entry_elem.findtext('PLACE_PAYOFF', '0.0'))
        show_payoff = float(entry_elem.findtext('SHOW_PAYOFF', '0.0'))

        # Odds and position
        dollar_odds = float(entry_elem.findtext('DOLLAR_ODDS', '0.0'))
        post_pos = int(entry_elem.findtext('POST_POS', '0'))
        weight = int(entry_elem.findtext('WEIGHT', '0'))

        # Jockey
        jockey_elem = entry_elem.find('.//JOCKEY')
        if jockey_elem is not None:
            jockey_first = jockey_elem.findtext('FIRST_NAME', '')
            jockey_last = jockey_elem.findtext('LAST_NAME', '')
            jockey_name = f"{jockey_first} {jockey_last}".strip()
        else:
            jockey_name = "Unknown"

        # Trainer
        trainer_elem = entry_elem.find('.//TRAINER')
        if trainer_elem is not None:
            trainer_first = trainer_elem.findtext('FIRST_NAME', '')
            trainer_last = trainer_elem.findtext('LAST_NAME', '')
            trainer_name = f"{trainer_first} {trainer_last}".strip()
        else:
            trainer_name = "Unknown"

        # Comment (running line)
        comment = entry_elem.findtext('COMMENT', '').strip()

        # Position calls (optional)
        position_calls = {}
        for call_elem in entry_elem.findall('.//POINT_OF_CALL'):
            which = call_elem.attrib.get('WHICH', '')
            position = int(call_elem.findtext('POSITION', '0'))
            if which and position:
                position_calls[which] = position

        return HorseResult(
            program_number=program_num,
            name=name,
            official_finish=official_fin,
            win_payoff=win_payoff,
            place_payoff=place_payoff,
            show_payoff=show_payoff,
            dollar_odds=dollar_odds,
            jockey_name=jockey_name,
            trainer_name=trainer_name,
            post_position=post_pos,
            weight=weight,
            comment=comment,
            position_calls=position_calls
        )

    except Exception as e:
        print(f"Error parsing horse entry: {str(e)}")
        return None


def parse_exotic_wager(wager_elem: ET.Element) -> Optional[ExoticWagerResult]:
    """Parse exotic wager result from TCH XML"""
    try:
        wager_type = wager_elem.findtext('WAGER_TYPE', '').strip()
        winners = wager_elem.findtext('WINNERS', '').strip()
        payoff = float(wager_elem.findtext('PAYOFF', '0.0'))
        pool_total = int(wager_elem.findtext('POOL_TOTAL', '0'))

        if wager_type and winners:
            return ExoticWagerResult(
                wager_type=wager_type,
                winners=winners,
                payoff=payoff,
                pool_total=pool_total
            )
        return None

    except Exception as e:
        print(f"Error parsing exotic wager: {str(e)}")
        return None


def get_exacta_result(race_result: RaceResult) -> Optional[ExoticWagerResult]:
    """Get exacta result from race"""
    for wager in race_result.exotic_wagers:
        if wager.wager_type.lower() == 'exacta':
            return wager
    return None


def get_trifecta_result(race_result: RaceResult) -> Optional[ExoticWagerResult]:
    """Get trifecta result from race"""
    for wager in race_result.exotic_wagers:
        if wager.wager_type.lower() == 'trifecta':
            return wager
    return None


def get_superfecta_result(race_result: RaceResult) -> Optional[ExoticWagerResult]:
    """Get superfecta result from race"""
    for wager in race_result.exotic_wagers:
        if wager.wager_type.lower() == 'superfecta':
            return wager
    return None


# Example usage and testing
if __name__ == "__main__":
    # Test on sample file
    sample_file = "equibase 2023 data/2023 Result Charts/kee20231007tch.xml"

    if Path(sample_file).exists():
        print(f"Testing TCH parser on: {sample_file}")
        print("=" * 80)

        races = parse_tch_file(sample_file)

        print(f"\n✓ Parsed {len(races)} races from file")

        for race in races[:3]:  # Show first 3 races
            print(f"\n{'='*80}")
            print(f"Race {race.race_number} - {race.track_code} on {race.race_date}")
            print(f"  {race.distance}F {race.surface} - {race.race_type}")
            print(f"  Purse: ${race.purse:,} - Winning time: {race.winning_time}s")
            print(f"  {len(race.horses)} horses")

            # Show winner
            winner = race.winner
            if winner:
                print(f"\n  WINNER: #{winner.program_number} {winner.name}")
                print(f"    Jockey: {winner.jockey_name}")
                print(f"    Trainer: {winner.trainer_name}")
                print(f"    Odds: {winner.dollar_odds}-1")
                print(f"    Payoffs: Win ${winner.win_payoff:.2f}, Place ${winner.place_payoff:.2f}, Show ${winner.show_payoff:.2f}")

            # Show exotic results
            if race.exotic_wagers:
                print(f"\n  EXOTIC WAGERS:")
                for wager in race.exotic_wagers:
                    print(f"    {wager.wager_type}: {wager.winners} - ${wager.payoff:.2f}")

        print(f"\n{'='*80}")
        print("✅ TCH Parser test complete!")
    else:
        print(f"❌ Sample file not found: {sample_file}")
