#!/usr/bin/env python3
"""
Fuzzy Matching Module for Name Correction

Uses reference databases to correct partial, truncated, or corrupted names
extracted from PDFs. Provides string similarity matching to find best matches
from known valid names.

Usage:
    matcher = FuzzyNameMatcher()

    # Match a corrupted trainer name
    matched_name, confidence = matcher.match_trainer("Kenneth G.Mc")
    # Returns: ("Kenneth G. McPeek", 0.92)

    # Match a partial jockey name
    matched_name, confidence = matcher.match_jockey("Tyler Gaffali")
    # Returns: ("Tyler Gaffalione", 0.88)
"""

import json
import os
from difflib import SequenceMatcher
from typing import Optional, Tuple, List
import re


class FuzzyNameMatcher:
    """Fuzzy string matching for trainer, jockey, horse, sire, and dam names"""

    def __init__(self, reference_dir: str = 'data/reference_databases'):
        """
        Initialize fuzzy matcher with reference databases.

        Args:
            reference_dir: Directory containing *_merged.json reference files
        """
        self.reference_dir = reference_dir

        # Load reference databases (merge old + new Equibase databases)
        self.trainers = self._load_and_merge('trainers_merged.json', 'trainers_equibase.json')
        self.jockeys = self._load_and_merge('jockeys_merged.json', 'jockeys_equibase.json')
        self.horses = self._load_and_merge('horses_merged.json', 'horses_equibase.json')
        self.sires = self._load_reference('sires_merged.json')  # No Equibase version yet
        self.dams = self._load_reference('dams_merged.json')  # No Equibase version yet

        # Create normalized lookup dictionaries for fast exact matching
        self.trainers_normalized = {self._normalize(name): name for name in self.trainers}
        self.jockeys_normalized = {self._normalize(name): name for name in self.jockeys}
        self.horses_normalized = {self._normalize(name): name for name in self.horses}
        self.sires_normalized = {self._normalize(name): name for name in self.sires}
        self.dams_normalized = {self._normalize(name): name for name in self.dams}

        print(f"Loaded reference databases:")
        print(f"  Trainers: {len(self.trainers)}")
        print(f"  Jockeys: {len(self.jockeys)}")
        print(f"  Horses: {len(self.horses)}")
        print(f"  Sires: {len(self.sires)}")
        print(f"  Dams: {len(self.dams)}")

    def _load_reference(self, filename: str) -> List[str]:
        """Load a reference database JSON file"""
        filepath = os.path.join(self.reference_dir, filename)

        if not os.path.exists(filepath):
            print(f"Warning: Reference file not found: {filepath}")
            return []

        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except Exception as e:
            print(f"Error loading {filename}: {str(e)}")
            return []

    def _load_and_merge(self, old_file: str, equibase_file: str) -> List[str]:
        """
        Load and merge old database (list format) and new Equibase database (dict format).

        Equibase format: {
            "Name": {
                "full_name": "Name",
                "variations": ["Name", "N. Name", ...],
                "stats": {...}
            }
        }
        """
        names_set = set()

        # Load old database (simple list)
        old_names = self._load_reference(old_file)
        names_set.update(old_names)

        # Load new Equibase database (dict with variations)
        filepath = os.path.join(self.reference_dir, equibase_file)
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        for name, info in data.items():
                            # Add main name
                            names_set.add(name)
                            # Add all variations
                            if isinstance(info, dict) and 'variations' in info:
                                names_set.update(info['variations'])
            except Exception as e:
                print(f"Error loading {equibase_file}: {str(e)}")

        return list(names_set)

    @staticmethod
    def _normalize(name: str) -> str:
        """
        Normalize a name for comparison.
        Removes spaces, periods, commas, and converts to lowercase.

        Example: "Tyler Gaffalione" -> "tylergaffalione"
        Example: "Irad Ortiz, Jr." -> "iradortizjr"
        """
        if not name:
            return ""

        # Convert to lowercase
        normalized = name.lower()

        # Remove common punctuation and spaces
        normalized = re.sub(r'[.,\s\-]+', '', normalized)

        return normalized

    @staticmethod
    def _similarity_score(str1: str, str2: str) -> float:
        """
        Calculate similarity score between two strings.
        Uses SequenceMatcher ratio (0.0 to 1.0).

        Returns: Float between 0.0 (completely different) and 1.0 (identical)
        """
        if not str1 or not str2:
            return 0.0

        return SequenceMatcher(None, str1.lower(), str2.lower()).ratio()

    def _find_best_match(
        self,
        input_name: str,
        reference_list: List[str],
        normalized_dict: dict,
        min_confidence: float = 0.70
    ) -> Tuple[Optional[str], float]:
        """
        Find the best matching name from a reference list.

        Args:
            input_name: The name to match
            reference_list: List of valid reference names
            normalized_dict: Pre-computed normalized name lookup
            min_confidence: Minimum confidence score to return a match (0.0-1.0)

        Returns:
            (matched_name, confidence_score) or (None, 0.0) if no match above threshold
        """
        if not input_name or not reference_list:
            return None, 0.0

        # Clean the input
        input_cleaned = input_name.strip()

        if not input_cleaned:
            return None, 0.0

        # Strategy 1: Try exact normalized match first (fast)
        input_normalized = self._normalize(input_cleaned)
        if input_normalized in normalized_dict:
            return normalized_dict[input_normalized], 1.0

        # Strategy 2: Check if input is a prefix of any reference name (common for truncated names)
        # This handles cases like "Kenneth G.Mc" -> "Kenneth G. McPeek"
        for ref_name in reference_list:
            ref_normalized = self._normalize(ref_name)

            # If input is a prefix of reference name with high similarity
            if ref_normalized.startswith(input_normalized) and len(input_normalized) >= 5:
                # Calculate confidence based on how much of the name we have
                confidence = len(input_normalized) / len(ref_normalized)
                if confidence >= min_confidence:
                    return ref_name, min(confidence + 0.1, 1.0)  # Boost for prefix match

        # Strategy 3: Full fuzzy matching with similarity scores
        best_match = None
        best_score = 0.0

        for ref_name in reference_list:
            # Calculate similarity score
            score = self._similarity_score(input_cleaned, ref_name)

            if score > best_score:
                best_score = score
                best_match = ref_name

        # Return match if above minimum confidence
        if best_score >= min_confidence:
            return best_match, best_score

        return None, 0.0

    def match_trainer(
        self,
        trainer_name: str,
        min_confidence: float = 0.70
    ) -> Tuple[Optional[str], float]:
        """
        Match a trainer name against the reference database.

        Args:
            trainer_name: Trainer name to match (may be partial/corrupted)
            min_confidence: Minimum confidence score (0.0-1.0)

        Returns:
            (matched_trainer, confidence) or (None, 0.0) if no match

        Examples:
            >>> matcher.match_trainer("Kenneth G.Mc")
            ("Kenneth G. McPeek", 0.92)

            >>> matcher.match_trainer("Brad Cox")
            ("Brad H. Cox", 0.95)
        """
        return self._find_best_match(
            trainer_name,
            self.trainers,
            self.trainers_normalized,
            min_confidence
        )

    def match_jockey(
        self,
        jockey_name: str,
        min_confidence: float = 0.70
    ) -> Tuple[Optional[str], float]:
        """
        Match a jockey name against the reference database.

        Args:
            jockey_name: Jockey name to match (may be partial/corrupted)
            min_confidence: Minimum confidence score (0.0-1.0)

        Returns:
            (matched_jockey, confidence) or (None, 0.0) if no match

        Examples:
            >>> matcher.match_jockey("Tyler Gaffali")
            ("Tyler Gaffalione", 0.88)

            >>> matcher.match_jockey("Irad Ortiz")
            ("Irad Ortiz Jr.", 0.90)
        """
        return self._find_best_match(
            jockey_name,
            self.jockeys,
            self.jockeys_normalized,
            min_confidence
        )

    def match_horse(
        self,
        horse_name: str,
        min_confidence: float = 0.75
    ) -> Tuple[Optional[str], float]:
        """
        Match a horse name against the reference database.

        Note: Horse names are more unique, so we use a slightly higher threshold.

        Args:
            horse_name: Horse name to match
            min_confidence: Minimum confidence score (0.0-1.0)

        Returns:
            (matched_horse, confidence) or (None, 0.0) if no match
        """
        return self._find_best_match(
            horse_name,
            self.horses,
            self.horses_normalized,
            min_confidence
        )

    def match_sire(
        self,
        sire_name: str,
        min_confidence: float = 0.75
    ) -> Tuple[Optional[str], float]:
        """
        Match a sire name against the reference database.

        Args:
            sire_name: Sire name to match
            min_confidence: Minimum confidence score (0.0-1.0)

        Returns:
            (matched_sire, confidence) or (None, 0.0) if no match
        """
        return self._find_best_match(
            sire_name,
            self.sires,
            self.sires_normalized,
            min_confidence
        )

    def match_dam(
        self,
        dam_name: str,
        min_confidence: float = 0.75
    ) -> Tuple[Optional[str], float]:
        """
        Match a dam name against the reference database.

        Args:
            dam_name: Dam name to match
            min_confidence: Minimum confidence score (0.0-1.0)

        Returns:
            (matched_dam, confidence) or (None, 0.0) if no match
        """
        return self._find_best_match(
            dam_name,
            self.dams,
            self.dams_normalized,
            min_confidence
        )

    def correct_extraction(
        self,
        name: str,
        name_type: str,
        min_confidence: float = 0.70
    ) -> Tuple[Optional[str], float]:
        """
        General-purpose name correction.

        Args:
            name: Name to correct
            name_type: Type of name ('trainer', 'jockey', 'horse', 'sire', 'dam')
            min_confidence: Minimum confidence score

        Returns:
            (corrected_name, confidence) or (None, 0.0) if no match
        """
        if name_type == 'trainer':
            return self.match_trainer(name, min_confidence)
        elif name_type == 'jockey':
            return self.match_jockey(name, min_confidence)
        elif name_type == 'horse':
            return self.match_horse(name, min_confidence)
        elif name_type == 'sire':
            return self.match_sire(name, min_confidence)
        elif name_type == 'dam':
            return self.match_dam(name, min_confidence)
        else:
            return None, 0.0


# Convenience function for quick testing
def test_fuzzy_matching():
    """Test the fuzzy matching module with common examples"""
    print("="*80)
    print(" TESTING FUZZY MATCHING MODULE")
    print("="*80)
    print()

    matcher = FuzzyNameMatcher()
    print()

    # Test cases
    test_cases = [
        # (input, type, expected_output)
        ("Kenneth G.Mc", "trainer", "Kenneth G. McPeek"),
        ("Tyler Gaffali", "jockey", "Tyler Gaffalione"),
        ("Irad Ortiz", "jockey", "Irad Ortiz Jr."),
        ("Brad Cox", "trainer", "Brad H. Cox"),
        ("Luis Saez", "jockey", "Luis Saez"),
    ]

    print("TEST CASES:")
    print("-"*80)

    for input_name, name_type, expected in test_cases:
        matched, confidence = matcher.correct_extraction(input_name, name_type)

        if matched:
            status = "✓" if matched == expected else "⚠"
            print(f"{status} {name_type.title()}: \"{input_name}\" → \"{matched}\" (confidence: {confidence:.2f})")
            if matched != expected and expected:
                print(f"    Expected: \"{expected}\"")
        else:
            print(f"✗ {name_type.title()}: \"{input_name}\" → NO MATCH")
        print()


if __name__ == '__main__':
    test_fuzzy_matching()
