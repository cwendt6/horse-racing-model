#!/usr/bin/env python3
"""
Race Type Classifier

Automatically classifies races by type and selects appropriate weight sets
for optimal prediction accuracy.

Race Types:
- Maiden: Horses with no career wins
- Claiming: Horses for sale at specific price
- Allowance: Mid-level conditions races
- Stakes: High-class competition

Usage:
    classifier = RaceClassifier()
    race_type = classifier.classify_race(race_data)
    weights = classifier.get_weights_for_race(race_data)
"""

import json
import os
from typing import Dict, Tuple
from pathlib import Path


class RaceClassifier:
    """
    Classifies races by type and provides specialized weights.
    """

    def __init__(self, weights_file: str = None):
        """
        Initialize race classifier.

        Args:
            weights_file: Path to optimized weights JSON file.
                         Defaults to output/optimized_weights_by_race_type.json
        """
        if weights_file is None:
            # Default to optimized weights file
            base_dir = Path(__file__).parent.parent.parent
            weights_file = base_dir / 'output' / 'optimized_weights_by_race_type.json'

        self.weights_file = str(weights_file)
        self.specialized_weights = {}
        self.default_weights = {
            'speed': 0.24,
            'form': 0.14,
            'class': 0.12,
            'pace': 0.14,
            'recency': 0.13,
            'progression': 0.05,
            'jockey': 0.07,
            'trainer': 0.07,
            'post': 0.04
        }

        self._load_weights()

    def _load_weights(self):
        """Load specialized weights from file if available."""
        if os.path.exists(self.weights_file):
            try:
                with open(self.weights_file, 'r') as f:
                    self.specialized_weights = json.load(f)
                print(f"✓ Loaded specialized weights from {self.weights_file}")
            except Exception as e:
                print(f"⚠️  Could not load weights: {e}")
                print(f"   Using default weights")
        else:
            print(f"⚠️  Weights file not found: {self.weights_file}")
            print(f"   Using default weights")

    def classify_race(self, race_data: Dict) -> str:
        """
        Classify race by type.

        Args:
            race_data: Dictionary with race information including:
                - race_name: Name of the race
                - race_type: Type descriptor
                - purse: Purse amount
                - race_conditions: Optional conditions text

        Returns:
            One of: 'maiden', 'claiming', 'allowance', 'stakes'
        """
        # Extract race attributes
        race_name = str(race_data.get('race_name', '')).lower()
        race_type = str(race_data.get('race_type', '')).lower()
        purse = race_data.get('purse', 0)
        conditions = str(race_data.get('race_conditions', '')).lower()

        # Combine all text fields for checking
        combined_text = f"{race_name} {race_type} {conditions}"

        # Check for maiden
        if 'maiden' in combined_text:
            return 'maiden'

        # Check for stakes (before claiming check - takes precedence)
        if any(keyword in combined_text for keyword in [
            'stakes', 'handicap', 'cup', 'derby', 'oaks',
            'classic', 'championship', 'grade', 'listed'
        ]):
            return 'stakes'

        # High purse indicates stakes even without keyword
        if purse > 150000:
            return 'stakes'

        # Check for allowance (before claiming - "Allowance Optional Claiming" is allowance)
        if 'allowance' in combined_text or 'alw' in combined_text:
            return 'allowance'

        # Check for claiming
        if any(keyword in combined_text for keyword in ['claiming', 'clm', 'claimer']):
            return 'claiming'

        # Default to allowance
        return 'allowance'

    def get_surface_type(self, race_data: Dict) -> str:
        """
        Get surface type from race data.

        Args:
            race_data: Race information

        Returns:
            'dirt' or 'turf'
        """
        surface = str(race_data.get('surface', '')).lower()
        surface_desc = str(race_data.get('surface_description', '')).lower()

        if 'turf' in surface or 'turf' in surface_desc:
            return 'turf'
        return 'dirt'

    def get_distance_class(self, race_data: Dict) -> str:
        """
        Classify race distance.

        Args:
            race_data: Race information with 'distance' in furlongs (e.g., 800 = 8F)

        Returns:
            'sprint', 'mile', or 'route'
        """
        distance = race_data.get('distance', 0)

        # Convert from Equibase format (e.g., 800 = 8 furlongs)
        distance_furlongs = distance / 100.0

        if distance_furlongs < 7.0:
            return 'sprint'
        elif distance_furlongs < 9.0:
            return 'mile'
        else:
            return 'route'

    def get_weights_for_race(self, race_data: Dict) -> Dict[str, float]:
        """
        Get specialized weights for a specific race.

        Args:
            race_data: Race information

        Returns:
            Dictionary of factor weights
        """
        race_type = self.classify_race(race_data)

        # Check if we have specialized weights for this race type
        if race_type in self.specialized_weights:
            weights = self.specialized_weights[race_type]
            return weights
        else:
            # Fall back to default weights
            return self.default_weights.copy()

    def get_race_characteristics(self, race_data: Dict) -> Dict[str, str]:
        """
        Get full race characteristics for analysis.

        Args:
            race_data: Race information

        Returns:
            Dictionary with race_type, surface, distance_class
        """
        return {
            'race_type': self.classify_race(race_data),
            'surface': self.get_surface_type(race_data),
            'distance_class': self.get_distance_class(race_data)
        }

    def explain_classification(self, race_data: Dict) -> str:
        """
        Provide human-readable explanation of classification.

        Args:
            race_data: Race information

        Returns:
            Explanation string
        """
        chars = self.get_race_characteristics(race_data)
        race_type = chars['race_type']
        surface = chars['surface']
        distance_class = chars['distance_class']

        # Build explanation
        explanation = f"Race Type: {race_type.title()}\n"
        explanation += f"Surface: {surface.title()}\n"
        explanation += f"Distance: {distance_class.title()}\n\n"

        # Add type-specific notes
        if race_type == 'maiden':
            explanation += "Notes: Maiden race - Emphasize trainer/jockey quality and connections\n"
            explanation += "       Limited past performance data available\n"
        elif race_type == 'claiming':
            explanation += "Notes: Claiming race - Emphasize recent form and pace\n"
            explanation += "       Class less important than current condition\n"
        elif race_type == 'stakes':
            explanation += "Notes: Stakes race - Emphasize class and speed figures\n"
            explanation += "       Quality matters more than recent form\n"
        else:  # allowance
            explanation += "Notes: Allowance race - Balanced approach\n"
            explanation += "       Class and form both important\n"

        # Show top factors for this race type
        weights = self.get_weights_for_race(race_data)
        sorted_weights = sorted(weights.items(), key=lambda x: x[1], reverse=True)

        explanation += f"\nTop factors for {race_type} races:\n"
        for i, (factor, weight) in enumerate(sorted_weights[:3], 1):
            explanation += f"  {i}. {factor.title()}: {weight*100:.1f}%\n"

        return explanation


def main():
    """Test the race classifier."""
    print("="*80)
    print(" RACE CLASSIFIER TEST")
    print("="*80)
    print()

    classifier = RaceClassifier()

    # Test cases
    test_races = [
        {
            'name': 'Race 1 - Maiden Special Weight',
            'race_name': 'Maiden Special Weight',
            'race_type': 'MSW',
            'purse': 80000,
            'surface_description': 'Dirt',
            'distance': 600
        },
        {
            'name': 'Race 2 - Claiming',
            'race_name': 'Claiming',
            'race_type': 'CLM',
            'purse': 30000,
            'surface_description': 'Dirt',
            'distance': 650
        },
        {
            'name': 'Race 3 - Allowance Optional Claiming',
            'race_name': 'Allowance Optional Claiming',
            'race_type': 'AOC',
            'purse': 100000,
            'surface_description': 'Turf',
            'distance': 800
        },
        {
            'name': 'Race 4 - Grade 2 Stakes',
            'race_name': 'Lexington Stakes (Grade 2)',
            'race_type': 'STK',
            'purse': 400000,
            'surface_description': 'Dirt',
            'distance': 900
        }
    ]

    for test_race in test_races:
        print(f"\n{test_race['name']}")
        print("-"*80)

        # Classify
        race_type = classifier.classify_race(test_race)
        chars = classifier.get_race_characteristics(test_race)

        print(f"Classification: {race_type.upper()}")
        print(f"Surface: {chars['surface'].title()}")
        print(f"Distance: {chars['distance_class'].title()}")

        # Get weights
        weights = classifier.get_weights_for_race(test_race)

        print(f"\nWeight Distribution:")
        sorted_weights = sorted(weights.items(), key=lambda x: x[1], reverse=True)
        for factor, weight in sorted_weights:
            bar = '█' * int(weight * 100)
            print(f"  {factor:12s}: {weight*100:5.1f}% {bar}")

        print()

    print("="*80)
    print("✓ Race classifier test complete")
    print("="*80)


if __name__ == '__main__':
    main()
