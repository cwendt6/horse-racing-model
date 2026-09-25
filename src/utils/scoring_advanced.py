#!/usr/bin/env python3
"""
Advanced Scoring Functions

Implements improved scoring logic from PREDICTOR_FIX_SPECIFICATION.md:
1. Elite jockey/trainer tiers
2. Dynamic form/progression calculation
3. Pace advantage bonuses
4. Better probability compression

Based on RoadMap specifications.
"""

import pandas as pd
import numpy as np
import re
from typing import Dict, List, Tuple


# Elite jockey and trainer definitions
ELITE_JOCKEYS = {
    'tier1': [
        'Irad Ortiz, Jr.', 'Irad Ortiz Jr.', 'Irad Ortiz', 'Irad Ortiz Jr',
        'Flavien Prat', 'Joel Rosario', 'Luis Saez', 'Jose Ortiz', 'Jose L Ortiz', 'Jose L. Ortiz'
    ],
    'tier2': [
        'Tyler Gaffalione', 'John Velazquez', 'Ricardo Santana Jr.', 'Ricardo Santana Jr',
        'Florent Geroux', 'Manny Franco', 'Javier Castellano'
    ]
}

# Expanded ELITE_TRAINERS with all name variations and missing trainers
ELITE_TRAINERS = {
    'turf': [
        'Chad C.Brown', 'Chad Brown', 'Chad C Brown',
        'William I.Mott', 'William I Mott', 'William Mott',
        'Graham Motion', 'H Graham Motion',
        'Michael Maker', 'Michael J Maker', 'Michael J. Maker',
        'Brendan P Walsh', 'Brendan Walsh', 'Brendan P. Walsh'
    ],
    'dirt': [
        'Todd A.Pletcher', 'Todd Pletcher', 'Todd A Pletcher',
        'Steve Asmussen', 'Steven Asmussen', 'Steven M Asmussen', 'Steven M. Asmussen',
        'Brad Cox', 'Brad H Cox', 'Brad H. Cox',
        'Bob Baffert',
        'Brendan P Walsh', 'Brendan Walsh', 'Brendan P. Walsh'
    ],
    'general': [
        'Chad C.Brown', 'Chad Brown', 'Chad C Brown',
        'Todd A.Pletcher', 'Todd Pletcher', 'Todd A Pletcher',
        'William I.Mott', 'William I Mott', 'William Mott',
        'Steve Asmussen', 'Steven Asmussen', 'Steven M Asmussen', 'Steven M. Asmussen',
        'Brad Cox', 'Brad H Cox', 'Brad H. Cox',
        'Bob Baffert',
        'Brendan P Walsh', 'Brendan Walsh', 'Brendan P. Walsh',
        'George Weaver',
        'William Walden',
        'Michael Maker', 'Michael J Maker', 'Michael J. Maker',
        'Michael W McCarthy', 'Michael McCarthy'
    ]
}


def normalize_name(name: str) -> str:
    """
    Normalize trainer/jockey name for matching
    - Remove periods
    - Normalize spaces
    - Handle middle initials

    Args:
        name: Original name

    Returns:
        Normalized name for matching
    """
    if not name or name in ["Unknown", "Owner"]:
        return name

    # Remove periods
    name = name.replace('.', '')
    # Normalize multiple spaces to single space
    name = re.sub(r'\s+', ' ', name)
    # Strip whitespace
    name = name.strip()

    return name


def calculate_form_score(last_beyer: float, best_beyer: float, recency_days: int = 30) -> float:
    """
    Calculate form score based on recent performance.

    Args:
        last_beyer: Most recent Beyer speed figure
        best_beyer: Best career Beyer speed figure
        recency_days: Days since last race

    Returns:
        Form score (0-100)
    """
    if pd.isna(last_beyer) or pd.isna(best_beyer) or best_beyer == 0:
        return 35.0  # Penalty for missing data

    # Compare last race to best race
    form_ratio = (last_beyer / best_beyer)

    # Base score on ratio
    if form_ratio >= 0.95:
        form_score = 95.0  # Peak form
    elif form_ratio >= 0.85:
        form_score = 80.0  # Good form
    elif form_ratio >= 0.75:
        form_score = 65.0  # Acceptable form
    elif form_ratio >= 0.65:
        form_score = 50.0  # Declining
    else:
        form_score = 35.0  # Poor form

    # Adjust for recency
    if recency_days <= 14:
        form_score *= 1.0  # Fresh
    elif recency_days <= 30:
        form_score *= 0.95
    elif recency_days <= 60:
        form_score *= 0.85
    else:
        form_score *= 0.70  # Layoff concern

    return min(100.0, form_score)


def calculate_progression_score(career_record: str) -> float:
    """
    Calculate progression based on career record trend.

    Args:
        career_record: String like "12 3-2-1" (starts wins-places-shows)

    Returns:
        Progression score (0-100)
    """
    if pd.isna(career_record) or career_record == "":
        return 35.0  # Penalty for missing data

    try:
        parts = str(career_record).split()
        starts = int(parts[0])
        wps = parts[1].split('-')
        wins = int(wps[0])
        places = int(wps[1]) if len(wps) > 1 else 0
        shows = int(wps[2]) if len(wps) > 2 else 0

        if starts == 0:
            return 40.0  # First-time starter

        # Win percentage
        win_pct = (wins / starts) * 100

        # In-the-money percentage
        itm_pct = ((wins + places + shows) / starts) * 100

        # Score based on performance
        if win_pct >= 33:
            return 90.0
        elif win_pct >= 25:
            return 80.0
        elif win_pct >= 20:
            return 70.0
        elif win_pct >= 15:
            return 60.0
        elif itm_pct >= 50:
            return 55.0
        elif itm_pct >= 33:
            return 45.0
        else:
            return 35.0

    except:
        return 35.0


def get_jockey_score(jockey_name: str, jockey_win_pct: float = None, race_avg: float = 15.0) -> float:
    """
    Calculate jockey score with elite tier handling.

    Args:
        jockey_name: Jockey name
        jockey_win_pct: Jockey's win percentage (if available)
        race_avg: Average jockey score for race (for unknowns)

    Returns:
        Jockey score (10-28)
    """
    if jockey_name == "Unknown" or pd.isna(jockey_name):
        return race_avg if race_avg > 0 else 12.0

    # Normalize jockey name for matching
    normalized_jockey = normalize_name(jockey_name)

    # Normalize elite jockey lists for matching
    normalized_tier1 = [normalize_name(j) for j in ELITE_JOCKEYS['tier1']]
    normalized_tier2 = [normalize_name(j) for j in ELITE_JOCKEYS['tier2']]

    # Check elite tiers with normalized names
    if normalized_jockey in normalized_tier1:
        return 28.0
    elif normalized_jockey in normalized_tier2:
        return 22.0

    # Use actual win percentage if available
    if pd.notna(jockey_win_pct):
        try:
            win_pct = float(jockey_win_pct)
            if win_pct >= 20:
                return 26.0
            elif win_pct >= 15:
                return 20.0
            elif win_pct >= 10:
                return 16.0
            else:
                return 12.0
        except:
            pass

    return 15.0  # Default for known jockey without stats


def calculate_trainer_score(trainer_name: str, trainer_win_pct: float = None,
                           race_type: str = "", surface: str = "") -> float:
    """
    Calculate trainer score with elite tier handling and specialization.

    Args:
        trainer_name: Trainer name
        trainer_win_pct: Trainer's win percentage (if available)
        race_type: Type of race (maiden, claiming, etc.)
        surface: Surface type (dirt/turf)

    Returns:
        Trainer score (10-35)
    """
    if trainer_name in ["Unknown", "Owner"]:
        return 10.0

    # Normalize trainer name for matching
    normalized_trainer = normalize_name(trainer_name)

    # Normalize elite trainer lists for matching
    normalized_elite_turf = [normalize_name(t) for t in ELITE_TRAINERS.get('turf', [])]
    normalized_elite_dirt = [normalize_name(t) for t in ELITE_TRAINERS.get('dirt', [])]
    normalized_elite_general = [normalize_name(t) for t in ELITE_TRAINERS.get('general', [])]

    # Check elite status with surface bonus
    is_elite = False
    surface_bonus = 0

    surface_lower = surface.lower()
    if surface_lower == 'turf' and normalized_trainer in normalized_elite_turf:
        is_elite = True
        surface_bonus = 5.0
    elif surface_lower == 'dirt' and normalized_trainer in normalized_elite_dirt:
        is_elite = True
        surface_bonus = 5.0
    elif normalized_trainer in normalized_elite_general:
        is_elite = True

    # Base score from win percentage
    base_score = 15.0

    if trainer_win_pct and trainer_win_pct != 'Owner':
        try:
            win_pct = float(str(trainer_win_pct).rstrip('%'))

            if win_pct >= 25:
                base_score = 28.0
            elif win_pct >= 20:
                base_score = 24.0
            elif win_pct >= 15:
                base_score = 20.0
            elif win_pct >= 10:
                base_score = 16.0
        except:
            pass

    # Apply elite bonus
    if is_elite:
        base_score = max(base_score, 25.0)

    return min(35.0, base_score + surface_bonus)


def calculate_pace_advantage(race_df: pd.DataFrame) -> Tuple[pd.DataFrame, str]:
    """
    Identify horses with pace advantage and add boost.

    Pace scenarios:
    - Lone Speed (1 early speed): +25 to lone speed, +10 to pressers
    - Speed Duel (3+ early speed): +20 to closers, +12 to pressers, -10 to early speed
    - Honest Pace (2 early speed): +5 to all
    - No Speed (0 early speed): +15 to pressers

    Args:
        race_df: DataFrame with Running_Style column

    Returns:
        Tuple of (updated DataFrame with pace_advantage_boost, scenario description)
    """
    race_df = race_df.copy()

    # Count running styles
    early_speed_count = len(race_df[race_df['Running_Style'] == 'Early Speed'])
    pressers_count = len(race_df[race_df['Running_Style'] == 'Presser'])
    closers_count = len(race_df[race_df['Running_Style'].isin(['Closer', 'Stalker'])])

    # Initialize boost column
    race_df['pace_advantage_boost'] = 0.0
    pace_scenario = "Honest Pace"

    # LONE SPEED scenario (1 E vs many P/C)
    if early_speed_count == 1 and (pressers_count + closers_count) >= 6:
        race_df.loc[race_df['Running_Style'] == 'Early Speed', 'pace_advantage_boost'] = 25.0
        race_df.loc[race_df['Running_Style'] == 'Presser', 'pace_advantage_boost'] = 10.0
        pace_scenario = "LONE SPEED - Huge advantage to early speed"

    # SPEED DUEL scenario (3+ E)
    elif early_speed_count >= 3:
        race_df.loc[race_df['Running_Style'].isin(['Closer', 'Stalker']), 'pace_advantage_boost'] = 20.0
        race_df.loc[race_df['Running_Style'] == 'Presser', 'pace_advantage_boost'] = 12.0
        race_df.loc[race_df['Running_Style'] == 'Early Speed', 'pace_advantage_boost'] = -10.0
        pace_scenario = "SPEED DUEL - Closers benefit from hot pace"

    # HONEST PACE scenario (2 E)
    elif early_speed_count == 2:
        race_df['pace_advantage_boost'] = 5.0
        pace_scenario = "Honest Pace - Fair for all styles"

    # NO SPEED scenario (0 E)
    elif early_speed_count == 0:
        race_df.loc[race_df['Running_Style'] == 'Presser', 'pace_advantage_boost'] = 15.0
        pace_scenario = "NO SPEED - Pressers can control pace"

    return race_df, pace_scenario


def calculate_win_probabilities(scores: np.ndarray, compression_factor: float = 2.5) -> np.ndarray:
    """
    Calculate win probabilities with better differentiation.

    Uses exponential transformation to create more separation between top horses
    and reduce over-compression.

    Args:
        scores: Array of raw composite scores
        compression_factor: Higher = more spread (1.0 = linear, 3.0 = strong favorite bias)
                          Recommended: 2.5 for most races

    Returns:
        Array of win probabilities (0-1 range, sums to 1.0)
    """
    # Handle edge cases
    scores = np.array(scores)
    scores = np.maximum(scores, 1)  # Avoid zeros

    # Apply exponential transform to create more separation
    # This makes the difference between top horses more pronounced
    adjusted_scores = np.power(scores, compression_factor)

    # Normalize to probabilities
    probabilities = adjusted_scores / adjusted_scores.sum()

    # Ensure minimum floor (no horse below 0.5%)
    probabilities = np.maximum(probabilities, 0.005)

    # Renormalize after floor
    probabilities = probabilities / probabilities.sum()

    return probabilities


def adjust_probabilities_by_field_size(probabilities: np.ndarray, field_size: int) -> np.ndarray:
    """
    Adjust probabilities for field size.

    Larger fields should have slightly more compression (harder to pick winner).

    Args:
        probabilities: Initial probability array
        field_size: Number of horses in race

    Returns:
        Adjusted probability array
    """
    if field_size <= 8:
        # Small fields: Allow more separation
        return probabilities
    elif field_size <= 12:
        # Medium fields: Slight compression
        adjusted = probabilities ** 0.9
        return adjusted / adjusted.sum()
    else:
        # Large fields: More compression
        adjusted = probabilities ** 0.85
        return adjusted / adjusted.sum()


# Export all functions
__all__ = [
    'calculate_form_score',
    'calculate_progression_score',
    'get_jockey_score',
    'calculate_trainer_score',
    'calculate_pace_advantage',
    'calculate_win_probabilities',
    'adjust_probabilities_by_field_size',
    'ELITE_JOCKEYS',
    'ELITE_TRAINERS'
]


if __name__ == '__main__':
    # Test scoring functions
    print("="*80)
    print(" ADVANCED SCORING MODULE - TEST")
    print("="*80)
    print()

    # Test form score
    print("1. Form Score Test:")
    print(f"   Peak form (last=95, best=100): {calculate_form_score(95, 100, 14):.1f}")
    print(f"   Good form (last=85, best=100): {calculate_form_score(85, 100, 21):.1f}")
    print(f"   Poor form (last=60, best=100): {calculate_form_score(60, 100, 30):.1f}")
    print()

    # Test jockey score
    print("2. Jockey Score Test:")
    print(f"   Elite Tier 1 (Irad Ortiz Jr.): {get_jockey_score('Irad Ortiz Jr.'):.1f}")
    print(f"   Elite Tier 2 (Tyler Gaffalione): {get_jockey_score('Tyler Gaffalione'):.1f}")
    print(f"   Regular jockey (20% win): {get_jockey_score('John Smith', 20.0):.1f}")
    print(f"   Unknown: {get_jockey_score('Unknown'):.1f}")
    print()

    # Test trainer score
    print("3. Trainer Score Test:")
    print(f"   Elite turf (Chad Brown on turf): {calculate_trainer_score('Chad Brown', 25.0, '', 'turf'):.1f}")
    print(f"   Elite dirt (Brad Cox on dirt): {calculate_trainer_score('Brad Cox', 22.0, '', 'dirt'):.1f}")
    print(f"   Regular trainer (15% win): {calculate_trainer_score('Jane Doe', 15.0):.1f}")
    print()

    # Test probability compression
    print("4. Probability Compression Test:")
    print("   Scenario: 5 horses with scores [100, 90, 85, 75, 70]")
    scores = np.array([100, 90, 85, 75, 70])

    # Linear (no compression)
    linear_probs = scores / scores.sum()
    print(f"   Linear (no compression): {[f'{p*100:.1f}%' for p in linear_probs]}")

    # With compression factor 2.5
    compressed_probs = calculate_win_probabilities(scores, compression_factor=2.5)
    print(f"   Compressed (factor=2.5):  {[f'{p*100:.1f}%' for p in compressed_probs]}")

    # With compression factor 3.0
    compressed_probs_3 = calculate_win_probabilities(scores, compression_factor=3.0)
    print(f"   Compressed (factor=3.0):  {[f'{p*100:.1f}%' for p in compressed_probs_3]}")

    print()
    print("="*80)
    print("✓ Advanced scoring module test complete")
    print("="*80)
