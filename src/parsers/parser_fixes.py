"""
Fixes for Racing Parser Issues
Corrects horse name extraction, running style classification, and pace analysis
"""

import re
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass


class HorseNameExtractor:
    """Fix horse name extraction from PDF text"""
    
    @staticmethod
    def extract_horse_name_from_block(text_block: str) -> Optional[str]:
        """
        Extract horse name from a horse's text block

        Horse name typically appears in one of these patterns:
        0. Name with (L/M) followed by stats: "St. Albans Raid (L) (0-0-0-0)"
        1. After claiming price: "$50,000 Zucchero 119"
        2. On its own line: "Miss Ellary (L) 122"
        3. After color: "Red $50,000 Zucchero 119"
        """

        # Pattern 0: Horse name with (L) or (M) followed by race stats
        # Example: "St. Albans Raid (L) (0-0-0-0)" or "Horse Name (M) (1-2-3-4)"
        pattern0 = r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*\(([LM])\)\s*\(\d+-\d+-\d+-\d+\)'
        match = re.search(pattern0, text_block)
        if match:
            return match.group(1).strip()

        # Pattern 1: Horse name with (L) or (M) and weight
        # Example: "Miss Ellary (L) 122" or "Zucchero 119"
        pattern1 = r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*\(([LM])\)\s+(\d{3})'
        match = re.search(pattern1, text_block)
        if match:
            return match.group(1).strip()
        
        # Pattern 2: After claiming price
        # Example: "$50,000 Zucchero 119"
        pattern2 = r'\$[\d,]+\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+\d{3}'
        match = re.search(pattern2, text_block)
        if match:
            return match.group(1).strip()
        
        # Pattern 3: After color and before weight
        # Example: "Red Zucchero 119" or "White Miss Ellary (L) 122"
        pattern3 = r'(?:Red|White|Blue|Green|Yellow|Black|Pink|Orange|Purple|Grey|Gray)\s+(?:\$[\d,]+\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:\([LM]\)\s+)?\d{3}'
        match = re.search(pattern3, text_block, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        
        # Pattern 4: Look for capitalized name pattern near weight
        # Must be 2-4 words, all capitalized
        pattern4 = r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\s+(?:\([LM]\)\s+)?\d{3}\b'
        match = re.search(pattern4, text_block)
        if match:
            name = match.group(1).strip()
            # Filter out common non-names
            if name not in ['Owner', 'Trainer', 'Silks', 'Clm Prc', 'Kee Dirt', 'Wet Dirt', 'Workout']:
                return name
        
        return None
    
    @staticmethod
    def extract_program_number(text_block: str) -> Optional[int]:
        """
        Extract program number from text block
        Usually appears as large number on left, followed by ML odds
        Example: "1  9-2" or "3  15-1"
        """
        
        # Pattern: Program number followed by ML odds at start of line
        pattern = r'^(\d{1,2})\s+\d+-\d+'
        match = re.search(pattern, text_block, re.MULTILINE)
        if match:
            return int(match.group(1))
        
        # Alternative: Look for "Program#" or similar
        pattern2 = r'(?:Program|Prog|#)\s*[:#]?\s*(\d{1,2})'
        match = re.search(pattern2, text_block, re.IGNORECASE)
        if match:
            return int(match.group(1))
        
        return None


class TrainerJockeyExtractor:
    """Fix trainer and jockey extraction"""
    
    @staticmethod
    def extract_trainer(text_block: str) -> Optional[str]:
        """
        Extract trainer name from text block
        Pattern: "Trainer: Name (record)"
        """
        
        # Standard pattern
        pattern = r'Trainer:\s*([^(]+?)\s*\('
        match = re.search(pattern, text_block)
        if match:
            trainer = match.group(1).strip()
            # Clean up spacing issues
            trainer = re.sub(r'([a-z])([A-Z])', r'\1 \2', trainer)  # Add space: "BrianA.Lynch" -> "Brian A. Lynch"
            trainer = re.sub(r'\s+', ' ', trainer)  # Normalize spaces
            return trainer
        
        return None
    
    @staticmethod
    def extract_jockey(text_block: str, claiming_race: bool = False) -> Optional[str]:
        """
        Extract jockey name from text block

        For claiming races: Jockey appears above "Clm Prc"
        For non-claiming races: Jockey appears on line with "Kee Dirt" or similar
        """

        if claiming_race:
            # Pattern for claiming races: Jockey name above "ClmPrc" or "Clm Prc"
            pattern = r'([A-Z][a-z]+(?:\s+[A-Z]\.?\s+)?[A-Z][a-z]+)\s*\n?\s*(?:Clm\s*Prc|ClmPrc)'
            match = re.search(pattern, text_block, re.IGNORECASE)
            if match:
                jockey = match.group(1).strip()
                # Clean up
                jockey = re.sub(r'([a-z])([A-Z])', r'\1 \2', jockey)  # Add spaces
                return jockey

        # NEW PATTERN 1: Modern format - "LastNameInitial weight" in race lines
        # Example: "GaffalioneT 121 L 3.25" or "TorresJA 122 bL 3.83" or "OrtizJL 123 L *1.63"
        # Look for: CapitalLetter + lowercase letters + 1-3 capital letters + space + 3-digit weight + space + optional code + space + number/asterisk
        pattern_race_line = r'\b([A-Z][a-z]{2,12}[A-Z]{1,3})\s+\d{3}\s+[bLfgs]{0,3}\s+[\d\.\*]'
        matches = re.findall(pattern_race_line, text_block)
        if matches:
            # Return the FIRST jockey name (most recent race appears first in text)
            jockey = matches[0].strip()
            # Add space before final capital letters: "GaffalioneT" -> "Gaffalione T"
            jockey = re.sub(r'([a-z])([A-Z]{1,3})$', r'\1 \2', jockey)
            return jockey

        # Standard pattern: Look for name pattern near "Kee" or weight
        # Common jockeys have format: "FirstName LastName" or "FirstName Initial LastName"
        pattern = r'\b([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+(?:\s+Jr\.?)?)\s+(?:Kee|Clm|\d{3}\s+[bL])'
        match = re.search(pattern, text_block)
        if match:
            jockey = match.group(1).strip()
            return jockey

        # Try extracting from explicit jockey line
        pattern2 = r'Jockey:\s*([^\n(]+?)(?:\s*\(|\s*$)'
        match = re.search(pattern2, text_block, re.IGNORECASE)
        if match:
            return match.group(1).strip()

        return None


class RunningStyleClassifier:
    """Fixed running style classification with better thresholds"""
    
    def __init__(self):
        # Adjusted thresholds for more realistic distributions
        # UPDATED OCT 2025: Add EP classification for Pace V2 compatibility
        self.thresholds = {
            'early_speed_max_position': 2.5,      # Avg early pos <= 2.5 = Early Speed (E)
            'early_presser_max_position': 4.0,    # Avg early pos <= 4.0 = Early Presser/Tactical (EP)
            'presser_max_position': 6.0,          # Avg early pos <= 6.0 = Presser (P)
            'stalker_max_position': 8.0,          # Avg early pos <= 8.0 = Stalker (S)
            'min_races_for_confidence': 3,        # Need at least 3 races
            'position_change_closer': 3.0         # Gaining 3+ positions = potential closer
        }
    
    def classify_from_positions(self, 
                                early_positions: List[int], 
                                finish_positions: List[int]) -> Tuple[str, float]:
        """
        Classify running style from position data
        
        Args:
            early_positions: List of positions at first call
            finish_positions: List of positions at finish
        
        Returns:
            Tuple of (style, confidence)
        """
        
        if not early_positions or not finish_positions:
            return '?', 0.0
        
        if len(early_positions) < self.thresholds['min_races_for_confidence']:
            return '?', 0.3  # Low confidence with few races
        
        # Calculate averages
        avg_early = sum(early_positions) / len(early_positions)
        avg_finish = sum(finish_positions) / len(finish_positions)
        
        # Calculate position changes
        position_changes = []
        for i in range(min(len(early_positions), len(finish_positions))):
            change = early_positions[i] - finish_positions[i]  # Positive = gained ground
            position_changes.append(change)
        
        avg_change = sum(position_changes) / len(position_changes) if position_changes else 0
        
        # Calculate consistency (standard deviation)
        if len(early_positions) > 1:
            variance = sum((x - avg_early) ** 2 for x in early_positions) / len(early_positions)
            std_dev = variance ** 0.5
            consistency = 1.0 - min(std_dev / 5.0, 1.0)  # Lower std dev = higher consistency
        else:
            consistency = 0.5
        
        # Classification logic
        style = '?'
        confidence = 0.0
        
        # Early Speed: consistently near the front (pure frontrunners)
        if avg_early <= self.thresholds['early_speed_max_position']:
            style = 'E'
            # Higher confidence if consistently in front (1st or 2nd)
            front_runner_pct = sum(1 for pos in early_positions if pos <= 2) / len(early_positions)
            confidence = 0.7 + (front_runner_pct * 0.3)

        # Early Presser/Tactical: sits just off the pace (2.5-4.0 early)
        elif avg_early <= self.thresholds['early_presser_max_position']:
            style = 'EP'
            # Confidence based on consistency in that range (2nd-4th early)
            ep_pct = sum(1 for pos in early_positions if 2.5 <= pos <= 4.0) / len(early_positions)
            confidence = 0.6 + (ep_pct * 0.3)

        # Closer: starts far back, gains significant ground
        elif avg_change >= self.thresholds['position_change_closer']:
            style = 'S'  # Changed from C to S (Stalker/Closer)
            # Confidence based on consistency of closing
            closer_races = sum(1 for change in position_changes if change >= 3) / len(position_changes)
            confidence = 0.6 + (closer_races * 0.4)

        # Presser: mid-pack (4.0-6.0 early)
        elif avg_early <= self.thresholds['presser_max_position']:
            style = 'P'
            # Confidence based on consistency in that range
            presser_pct = sum(1 for pos in early_positions if 4 <= pos <= 6) / len(early_positions)
            confidence = 0.6 + (presser_pct * 0.3)

        # Stalker: mid-to-back pack (6.0-8.0 early)
        elif avg_early <= self.thresholds['stalker_max_position']:
            style = 'S'
            # Stalkers typically gain 1-2 positions
            stalker_pct = sum(1 for change in position_changes if 1 <= change <= 3) / len(position_changes)
            confidence = 0.5 + (stalker_pct * 0.3)

        # Far back closer
        else:
            style = 'S'
            confidence = 0.5  # Lower confidence for horses that start far back
        
        # Adjust confidence based on overall consistency
        confidence = confidence * (0.7 + consistency * 0.3)
        
        return style, min(confidence, 1.0)
    
    def extract_positions_from_pp_line(self, pp_line: str) -> Tuple[Optional[int], Optional[int]]:
        """
        Extract early position and finish position from a PP line
        
        Returns: (early_position, finish_position)
        """
        
        # Look for sequence of positions (usually 4-6 numbers)
        # Pattern: numbers possibly followed by superscript
        position_pattern = r'\b(\d{1,2})[²³⁴⁵⁶⁷⁸⁹⁰hd]*\b'
        
        # Find all potential positions
        matches = re.findall(position_pattern, pp_line)
        
        if not matches or len(matches) < 4:
            return None, None
        
        # Filter to reasonable position values (1-20)
        positions = [int(m) for m in matches if 1 <= int(m) <= 20]
        
        if len(positions) < 4:
            return None, None
        
        # Typical format: [start, 1st_call, 2nd_call, stretch, finish]
        # We want 1st call (index 1) and finish (last)
        early_pos = positions[1] if len(positions) > 1 else positions[0]
        finish_pos = positions[-1]
        
        return early_pos, finish_pos


class PaceAdvantageCalculator:
    """Calculate proper pace advantage scores"""
    
    def __init__(self):
        self.scenario_weights = {
            'VERY_HOT': {'E': 0.3, 'P': 0.7, 'S': 0.9, 'C': 1.0},  # Closers benefit most
            'HOT': {'E': 0.5, 'P': 0.8, 'S': 0.9, 'C': 1.0},
            'CONTENTIOUS': {'E': 0.7, 'P': 0.9, 'S': 0.8, 'C': 0.7},
            'MODERATE': {'E': 0.9, 'P': 0.8, 'S': 0.7, 'C': 0.6},
            'SLOW': {'E': 1.0, 'P': 0.7, 'S': 0.5, 'C': 0.3},      # Early speed benefits most
        }
    
    def calculate_pace_score(self, 
                            running_style: str, 
                            pace_scenario: str,
                            base_score: float = 75.0) -> float:
        """
        Calculate pace advantage score based on running style and scenario
        
        Args:
            running_style: 'E', 'P', 'S', or 'C'
            pace_scenario: Pace scenario type
            base_score: Base score to modify
        
        Returns:
            Adjusted pace score (0-100)
        """
        
        if running_style not in ['E', 'P', 'S', 'C']:
            return base_score
        
        # Map scenario to weight key
        scenario_key = pace_scenario.upper().replace(' ', '_')
        if 'SPEED DUEL' in scenario_key or 'VERY HOT' in scenario_key:
            scenario_key = 'VERY_HOT'
        elif 'HOT' in scenario_key:
            scenario_key = 'HOT'
        elif 'CONTENTIOUS' in scenario_key or 'HONEST' in scenario_key:
            scenario_key = 'CONTENTIOUS'
        elif 'LONE' in scenario_key:
            scenario_key = 'MODERATE'
        elif 'SLOW' in scenario_key or 'NO SPEED' in scenario_key:
            scenario_key = 'SLOW'
        else:
            scenario_key = 'CONTENTIOUS'  # Default
        
        # Get multiplier
        weights = self.scenario_weights.get(scenario_key, {})
        multiplier = weights.get(running_style, 0.75)
        
        # Calculate score
        pace_score = base_score * multiplier
        
        # Ensure it's in range
        return max(0, min(100, pace_score))
    
    def determine_pace_scenario(self, 
                               early_speed_count: int, 
                               total_horses: int) -> str:
        """
        Determine pace scenario based on early speed horses
        
        Args:
            early_speed_count: Number of horses with early speed
            total_horses: Total horses in race
        
        Returns:
            Pace scenario string
        """
        
        # Calculate ratio
        speed_ratio = early_speed_count / total_horses if total_horses > 0 else 0
        
        if early_speed_count >= 4:
            return "Speed Duel"
        elif early_speed_count == 3:
            return "Hot Pace"
        elif early_speed_count == 2:
            return "Honest Pace"
        elif early_speed_count == 1:
            return "Lone Speed"
        else:
            return "No Speed"


def apply_fixes_to_horse_dict(horse_dict: Dict, text_block: str, is_claiming: bool = False) -> Dict:
    """
    Apply all fixes to a single horse dictionary
    
    Args:
        horse_dict: Original horse data
        text_block: Extracted text for this horse
        is_claiming: Whether this is a claiming race
    
    Returns:
        Fixed horse dictionary
    """
    
    fixed = horse_dict.copy()
    
    # Fix 1: Horse name
    if not horse_dict.get('Horse') or horse_dict['Horse'].startswith('Horse '):
        name = HorseNameExtractor.extract_horse_name_from_block(text_block)
        if name:
            fixed['Horse'] = name
    
    # Fix 2: Program number
    if not horse_dict.get('Program#') or horse_dict['Program#'] == 0:
        prog_num = HorseNameExtractor.extract_program_number(text_block)
        if prog_num:
            fixed['Program#'] = prog_num
    
    # Fix 3: Trainer
    if horse_dict.get('Trainer') in ['Unknown', 'Owner', '', None]:
        trainer = TrainerJockeyExtractor.extract_trainer(text_block)
        if trainer:
            fixed['Trainer'] = trainer
    
    # Fix 4: Jockey
    if horse_dict.get('Jockey') in ['Unknown', '', None]:
        jockey = TrainerJockeyExtractor.extract_jockey(text_block, is_claiming)
        if jockey:
            fixed['Jockey'] = jockey
    
    return fixed


def main_example():
    """Example of applying fixes"""
    
    # Example text block for a horse
    sample_text = """
    1  9-2  Owner: Raroma Stable (Rajendra Maharajh)
    Silks: Red, white emblem, white blocks on sleeves, red cap
    Trainer: Brian A. Lynch (0-0-0-0) 0.00%
    
    Luis Saez
    Clm Prc
    Red    $50,000  Zucchero     119    (0-0-0-0) 0.00%
    
    Gr/ro.c.2 Mendelssohn - Toffen by Cairo Prince
    04Sep25 1 CD ft 1m :46¹⁰ 1:10⁴³ 1:35⁴⁷ 3 3¹ 4² 5³ 6⁴
    """
    
    # Original problematic horse dict
    horse_dict = {
        'Program#': 0,
        'Horse': 'Horse 1',
        'Trainer': 'Unknown',
        'Jockey': 'Unknown',
        'Running_Style': 'P'
    }
    
    # Apply fixes
    fixed_horse = apply_fixes_to_horse_dict(horse_dict, sample_text, is_claiming=True)
    
    print("BEFORE:")
    print(f"  Program#: {horse_dict['Program#']}")
    print(f"  Horse: {horse_dict['Horse']}")
    print(f"  Trainer: {horse_dict['Trainer']}")
    print(f"  Jockey: {horse_dict['Jockey']}")
    print()
    print("AFTER:")
    print(f"  Program#: {fixed_horse['Program#']}")
    print(f"  Horse: {fixed_horse['Horse']}")
    print(f"  Trainer: {fixed_horse['Trainer']}")
    print(f"  Jockey: {fixed_horse['Jockey']}")
    
    # Test running style classification
    print("\n" + "="*50)
    print("RUNNING STYLE CLASSIFICATION TEST")
    print("="*50)
    
    classifier = RunningStyleClassifier()
    
    # Test case 1: Early speed horse
    early_speed_horse = {
        'early_positions': [1, 2, 1, 2, 1],
        'finish_positions': [1, 3, 2, 1, 4]
    }
    style, conf = classifier.classify_from_positions(
        early_speed_horse['early_positions'],
        early_speed_horse['finish_positions']
    )
    print(f"\nEarly Speed Horse: {style} ({conf:.2f} confidence)")
    
    # Test case 2: Closer
    closer_horse = {
        'early_positions': [8, 9, 7, 10, 8],
        'finish_positions': [2, 3, 1, 4, 3]
    }
    style, conf = classifier.classify_from_positions(
        closer_horse['early_positions'],
        closer_horse['finish_positions']
    )
    print(f"Closer Horse: {style} ({conf:.2f} confidence)")
    
    # Test case 3: Presser
    presser_horse = {
        'early_positions': [3, 4, 3, 4, 4],
        'finish_positions': [2, 3, 1, 3, 2]
    }
    style, conf = classifier.classify_from_positions(
        presser_horse['early_positions'],
        presser_horse['finish_positions']
    )
    print(f"Presser Horse: {style} ({conf:.2f} confidence)")


if __name__ == "__main__":
    main_example()
