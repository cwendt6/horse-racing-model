"""
Maiden Race Specific Weight Configuration

Based on October 23, 2025 race results analysis:
- 4/4 maiden races (100%) won by elite FTS trainers
- Manual handicapping (55.6% win rate) used heavy trainer weighting
- Model (11.1% win rate) used standard 18.22% trainer weight

Key insight: Trainer credentials should be PRIMARY factor in maiden races,
not just one factor among many.
"""

# STANDARD WEIGHTS (for non-maiden races)
STANDARD_WEIGHTS = {
    'speed': 0.30,
    'form': 0.225,
    'class_rating': 0.216,
    'pace': 0.073,
    'jockey': 0.052,
    'trainer': 0.1822,  # 18.22%
    'recency': 0.025,
    'progression': 0.025,
    'post_position': 0.02
}

# MAIDEN-SPECIFIC WEIGHTS (validated by actual results)
MAIDEN_WEIGHTS = {
    'speed': 0.15,       # Reduced - maidens have less reliable speed figures
    'form': 0.08,        # Reduced - maidens have limited form
    'class_rating': 0.08,  # Reduced - maiden class is less predictive
    'pace': 0.12,        # Slightly increased - pace matters
    'jockey': 0.15,      # Increased - elite jockeys signal confidence
    'trainer': 0.35,     # MAJOR INCREASE (was 0.1822) - PRIMARY FACTOR
    'recency': 0.02,     # Reduced
    'progression': 0.05, # Maidens with workouts
    'post_position': 0.00  # Minimal in maidens
}

# MAIDEN CLAIMING WEIGHTS (even heavier trainer emphasis)
MAIDEN_CLAIMING_WEIGHTS = {
    'speed': 0.12,
    'form': 0.06,
    'class_rating': 0.05,
    'pace': 0.10,
    'jockey': 0.12,
    'trainer': 0.42,     # EVEN HIGHER - 42% for claiming maidens
    'recency': 0.02,
    'progression': 0.05,
    'post_position': 0.06  # Post matters more in claiming
}

# MAIDEN STAKES WEIGHTS (quality maidens)
MAIDEN_STAKES_WEIGHTS = {
    'speed': 0.18,       # Better works/breeding
    'form': 0.10,
    'class_rating': 0.12,  # Breeding matters
    'pace': 0.12,
    'jockey': 0.16,      # Top jockeys
    'trainer': 0.30,     # Still primary but slightly less
    'recency': 0.02,
    'progression': 0.00,
    'post_position': 0.00
}


def get_weights_for_race(race_type: str, race_class: str = "") -> dict:
    """
    Get appropriate weights based on race type.

    Args:
        race_type: Type of race ('maiden', 'claiming', 'allowance', 'stakes', etc.)
        race_class: Race class ('maiden_claiming', 'maiden_special_weight', etc.)

    Returns:
        Dictionary of weights for this race type
    """
    race_type_lower = race_type.lower()
    race_class_lower = race_class.lower()

    # Maiden races get special weights
    if 'maiden' in race_type_lower or 'maiden' in race_class_lower:

        # Maiden claiming
        if 'claiming' in race_type_lower or 'claiming' in race_class_lower:
            return MAIDEN_CLAIMING_WEIGHTS.copy()

        # Maiden stakes
        elif 'stake' in race_type_lower or 'stake' in race_class_lower:
            return MAIDEN_STAKES_WEIGHTS.copy()

        # Maiden special weight (default maiden)
        else:
            return MAIDEN_WEIGHTS.copy()

    # Non-maiden races use standard weights
    return STANDARD_WEIGHTS.copy()


def is_maiden_race(race_type: str, race_class: str = "") -> bool:
    """
    Determine if a race is a maiden race.

    Args:
        race_type: Type of race
        race_class: Race class

    Returns:
        True if maiden race
    """
    race_type_lower = race_type.lower()
    race_class_lower = race_class.lower()

    return 'maiden' in race_type_lower or 'maiden' in race_class_lower


# Export
__all__ = [
    'STANDARD_WEIGHTS',
    'MAIDEN_WEIGHTS',
    'MAIDEN_CLAIMING_WEIGHTS',
    'MAIDEN_STAKES_WEIGHTS',
    'get_weights_for_race',
    'is_maiden_race'
]


if __name__ == '__main__':
    print("=" * 80)
    print(" MAIDEN WEIGHTS MODULE - TEST")
    print("=" * 80)
    print()

    # Test different race types
    test_races = [
        ('Maiden Special Weight', ''),
        ('Maiden Claiming', ''),
        ('Allowance', ''),
        ('', 'Maiden Special Weight'),
        ('', 'Maiden Claiming'),
        ('Stakes', 'Maiden Stakes')
    ]

    for race_type, race_class in test_races:
        weights = get_weights_for_race(race_type, race_class)
        is_maiden = is_maiden_race(race_type, race_class)

        print(f"Race: {race_type or race_class}")
        print(f"  Is Maiden: {is_maiden}")
        print(f"  Trainer Weight: {weights['trainer']:.1%}")
        print(f"  Jockey Weight: {weights['jockey']:.1%}")
        print(f"  Speed Weight: {weights['speed']:.1%}")
        print()

    print("=" * 80)
    print("KEY VALIDATION from October 23 results:")
    print("  - 4/4 maiden races won by elite FTS trainers")
    print("  - Trainer weight increased from 18.22% to 35-42% in maidens")
    print("  - This matches manual handicapping methodology (55.6% winners)")
    print("=" * 80)
