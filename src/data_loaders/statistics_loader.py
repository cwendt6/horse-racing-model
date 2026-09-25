"""
Statistics Loader
Loads and provides access to jockey and trainer statistics
"""

import json
from typing import Dict, Optional, List
from dataclasses import dataclass


@dataclass
class JockeyStats:
    """Jockey statistics"""
    name: str
    win_percentage: float = 15.0  # Default
    itm_percentage: float = 35.0  # Default
    starts: int = 0
    wins: int = 0
    earnings: float = 0.0


@dataclass
class TrainerStats:
    """Trainer statistics"""
    name: str
    win_percentage: float = 15.0  # Default
    itm_percentage: float = 35.0  # Default
    starts: int = 0
    wins: int = 0
    earnings: float = 0.0


class StatisticsLoader:
    """Loads and provides access to jockey/trainer statistics"""

    def __init__(self, jockey_file: str, trainer_file: str):
        """
        Load statistics files

        Args:
            jockey_file: Path to jockey statistics JSON
            trainer_file: Path to trainer statistics JSON
        """
        with open(jockey_file, 'r') as f:
            self.jockey_data = json.load(f)

        with open(trainer_file, 'r') as f:
            self.trainer_data = json.load(f)

        # Build lookup dictionaries for faster access
        self._build_lookup_tables()

    def _build_lookup_tables(self):
        """Build fast lookup tables for jockeys and trainers"""

        self.jockey_lookup = {}
        for jockey in self.jockey_data.get('jockeys', []):
            name = jockey['name']
            self.jockey_lookup[name.lower()] = jockey

        self.trainer_lookup = {}
        for trainer in self.trainer_data.get('trainers', []):
            name = trainer['name']
            self.trainer_lookup[name.lower()] = trainer

    def get_jockey_stats(self, jockey_name: str, track: str = 'keeneland',
                        meet: str = 'current', year: int = 2023) -> JockeyStats:
        """
        Get jockey statistics

        Args:
            jockey_name: Jockey name (e.g., "Tyler Gaffalione")
            track: Track name (default: 'keeneland')
            meet: Meet period - 'current', 'ytd', 'all_time' (default: 'current')
            year: Year for historical lookups

        Returns:
            JockeyStats object with statistics
        """
        # Normalize name
        name_key = jockey_name.lower()

        # Try to find jockey
        jockey_data = self.jockey_lookup.get(name_key)

        if not jockey_data:
            # Return default stats if not found
            return JockeyStats(name=jockey_name)

        # Determine which category to use
        if meet == 'current' and track.lower() == 'keeneland':
            # Determine season based on date
            # For 2023, fall meet is Oct, spring meet is Apr
            category = f'keeneland_fall_{year}' if year == 2023 and 10 >= 10 else f'keeneland_spring_{year}'
        elif meet == 'ytd':
            category = f'ytd_{year}_all_tracks'
        elif meet == 'all_time':
            category = 'all_time_all_tracks'
        else:
            category = f'{track.lower()}_{meet}_{year}'

        # Get stats from category
        stats = jockey_data.get(category, {})

        if not stats or not isinstance(stats, dict):
            # Try ytd as fallback
            stats = jockey_data.get(f'ytd_{year}_all_tracks', {})

        if not stats or not isinstance(stats, dict):
            # Try all_time as last resort
            stats = jockey_data.get('all_time_all_tracks', {})

        # Extract statistics
        win_pct = stats.get('win_percentage', 15.0)
        itm_pct = stats.get('itm_percentage', 35.0)
        starts = stats.get('starts', 0)
        wins = stats.get('wins', 0)
        earnings = stats.get('earnings', 0.0)

        return JockeyStats(
            name=jockey_name,
            win_percentage=win_pct,
            itm_percentage=itm_pct,
            starts=starts,
            wins=wins,
            earnings=earnings
        )

    def get_trainer_stats(self, trainer_name: str, track: str = 'keeneland',
                         meet: str = 'current', year: int = 2023) -> TrainerStats:
        """
        Get trainer statistics

        Args:
            trainer_name: Trainer name (e.g., "Brad Cox")
            track: Track name (default: 'keeneland')
            meet: Meet period - 'current', 'ytd', 'all_time' (default: 'current')
            year: Year for historical lookups

        Returns:
            TrainerStats object with statistics
        """
        # Normalize name
        name_key = trainer_name.lower()

        # Try to find trainer
        trainer_data = self.trainer_lookup.get(name_key)

        if not trainer_data:
            # Return default stats if not found
            return TrainerStats(name=trainer_name)

        # Determine which category to use
        if meet == 'current' and track.lower() == 'keeneland':
            # Determine season based on date
            category = f'keeneland_fall_{year}' if year == 2023 and 10 >= 10 else f'keeneland_spring_{year}'
        elif meet == 'ytd':
            category = f'ytd_{year}_all_tracks'
        elif meet == 'all_time':
            category = 'all_time_all_tracks'
        else:
            category = f'{track.lower()}_{meet}_{year}'

        # Get stats from category
        stats = trainer_data.get(category, {})

        if not stats or not isinstance(stats, dict):
            # Try ytd as fallback
            stats = trainer_data.get(f'ytd_{year}_all_tracks', {})

        if not stats or not isinstance(stats, dict):
            # Try all_time as last resort
            stats = trainer_data.get('all_time_all_tracks', {})

        # Extract statistics
        win_pct = stats.get('win_percentage', 15.0)
        itm_pct = stats.get('itm_percentage', 35.0)
        starts = stats.get('starts', 0)
        wins = stats.get('wins', 0)
        earnings = stats.get('earnings', 0.0)

        return TrainerStats(
            name=trainer_name,
            win_percentage=win_pct,
            itm_percentage=itm_pct,
            starts=starts,
            wins=wins,
            earnings=earnings
        )


if __name__ == '__main__':
    # Test the loader
    loader = StatisticsLoader(
        'jockey_statistics_comprehensive.json',
        'trainer_statistics_comprehensive.json'
    )

    # Test jockey lookup
    print("Testing jockey statistics:")
    test_jockeys = ["Tyler Gaffalione", "Brian Hernandez, Jr.", "Unknown Jockey"]

    for jockey_name in test_jockeys:
        stats = loader.get_jockey_stats(jockey_name, year=2023)
        print(f"\n{jockey_name}:")
        print(f"  Win %: {stats.win_percentage:.1f}%")
        print(f"  ITM %: {stats.itm_percentage:.1f}%")
        print(f"  Starts: {stats.starts}")
        print(f"  Wins: {stats.wins}")

    # Test trainer lookup
    print("\n\nTesting trainer statistics:")
    test_trainers = ["Brad Cox", "Steve Asmussen", "Unknown Trainer"]

    for trainer_name in test_trainers:
        stats = loader.get_trainer_stats(trainer_name, year=2023)
        print(f"\n{trainer_name}:")
        print(f"  Win %: {stats.win_percentage:.1f}%")
        print(f"  ITM %: {stats.itm_percentage:.1f}%")
        print(f"  Starts: {stats.starts}")
        print(f"  Wins: {stats.wins}")
