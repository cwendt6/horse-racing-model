"""
Elite Jockey-Trainer Combination Bonuses

Based on October 23, 2025 race results analysis:
- Race 5: Brad Cox + Irad Ortiz Jr. = Winner
- Race 7: Brad Cox + Irad Ortiz Jr. = Winner
- Race 8: Paulo Lobo + Irad Ortiz Jr. = Winner
- Race 6: Chad Brown + Tyler Gaffalione = Winner (12.5 lengths!)

Elite combinations deliver consistently and deserve stacking bonuses.
"""

from typing import Dict, Tuple


class JockeyTrainerComboAnalyzer:
    """
    Analyzes jockey-trainer combinations and applies bonuses for elite pairings.

    Based on actual race results showing elite combinations win at high rates.
    """

    # Elite jockey-trainer combinations with proven success
    # Format: (trainer_name, jockey_name): bonus_points
    ELITE_COMBOS = {
        # TIER 1: Proven elite combinations (Race results validated)
        ('Brad Cox', 'Irad Ortiz Jr'): 20,
        ('Brad H Cox', 'Irad Ortiz Jr'): 20,
        ('Brad H. Cox', 'Irad Ortiz Jr'): 20,
        ('Chad Brown', 'Irad Ortiz Jr'): 20,
        ('Chad C Brown', 'Irad Ortiz Jr'): 20,
        ('Chad C. Brown', 'Irad Ortiz Jr'): 20,
        ('Chad Brown', 'Tyler Gaffalione'): 18,  # Race 6 winner - 12.5 lengths!
        ('Chad C Brown', 'Tyler Gaffalione'): 18,
        ('Chad C. Brown', 'Tyler Gaffalione'): 18,
        ('Brad Cox', 'Tyler Gaffalione'): 15,
        ('Brad H Cox', 'Tyler Gaffalione'): 15,
        ('Brad H. Cox', 'Tyler Gaffalione'): 15,

        # TIER 2: Strong combinations
        ('Steven Asmussen', 'Luis Saez'): 15,
        ('Steven M Asmussen', 'Luis Saez'): 15,
        ('Steven M. Asmussen', 'Luis Saez'): 15,
        ('Steve Asmussen', 'Luis Saez'): 15,
        ('Steven Asmussen', 'Jose Ortiz'): 15,
        ('Steven M Asmussen', 'Jose Ortiz'): 15,
        ('Steven M. Asmussen', 'Jose Ortiz'): 15,
        ('Steve Asmussen', 'Jose Ortiz'): 15,
        ('Todd Pletcher', 'Irad Ortiz Jr'): 18,
        ('Todd A Pletcher', 'Irad Ortiz Jr'): 18,
        ('Todd A. Pletcher', 'Irad Ortiz Jr'): 18,
        ('Brendan Walsh', 'Tyler Gaffalione'): 15,
        ('Brendan P Walsh', 'Tyler Gaffalione'): 15,
        ('Brendan P. Walsh', 'Tyler Gaffalione'): 15,

        # Other strong combinations
        ('William Mott', 'Irad Ortiz Jr'): 15,
        ('William I Mott', 'Irad Ortiz Jr'): 15,
        ('William I. Mott', 'Irad Ortiz Jr'): 15,
        ('Michael Maker', 'Tyler Gaffalione'): 12,
        ('Michael J Maker', 'Tyler Gaffalione'): 12,
        ('Michael J. Maker', 'Tyler Gaffalione'): 12,
    }

    def __init__(self):
        """Initialize combo analyzer"""
        pass

    def get_combo_bonus(self, trainer_name: str, jockey_name: str) -> Tuple[float, str]:
        """
        Get bonus points for jockey-trainer combination.

        Args:
            trainer_name: Trainer's name
            jockey_name: Jockey's name

        Returns:
            Tuple of (bonus_points, description)
        """
        # Normalize names for matching
        trainer_normalized = trainer_name.strip()
        jockey_normalized = jockey_name.strip()

        # Check for elite combo
        combo_key = (trainer_normalized, jockey_normalized)

        if combo_key in self.ELITE_COMBOS:
            bonus = self.ELITE_COMBOS[combo_key]

            if bonus >= 20:
                return (bonus, f"🔥 ELITE COMBO: {trainer_name} + {jockey_name} (+{bonus})")
            elif bonus >= 15:
                return (bonus, f"⭐ STRONG COMBO: {trainer_name} + {jockey_name} (+{bonus})")
            else:
                return (bonus, f"✓ Good combo: {trainer_name} + {jockey_name} (+{bonus})")

        return (0.0, "")

    def is_elite_combo(self, trainer_name: str, jockey_name: str) -> bool:
        """
        Check if this is an elite jockey-trainer combination.

        Args:
            trainer_name: Trainer's name
            jockey_name: Jockey's name

        Returns:
            True if elite combo
        """
        trainer_normalized = trainer_name.strip()
        jockey_normalized = jockey_name.strip()
        combo_key = (trainer_normalized, jockey_normalized)

        return combo_key in self.ELITE_COMBOS and self.ELITE_COMBOS[combo_key] >= 15


# Export
__all__ = ['JockeyTrainerComboAnalyzer']


if __name__ == '__main__':
    # Test combo analyzer
    analyzer = JockeyTrainerComboAnalyzer()

    print("=" * 80)
    print(" JOCKEY-TRAINER COMBO ANALYZER TEST")
    print("=" * 80)
    print()

    # Test elite combos from actual race results
    test_combos = [
        ('Brad H Cox', 'Irad Ortiz Jr'),      # Race 5, 7 winners
        ('Chad Brown', 'Tyler Gaffalione'),   # Race 6 winner (12.5 lengths!)
        ('Steven M. Asmussen', 'Luis Saez'),  # Strong combo
        ('Todd Pletcher', 'Irad Ortiz Jr'),   # Elite combo
        ('Unknown Trainer', 'Unknown Jockey') # No bonus
    ]

    for trainer, jockey in test_combos:
        bonus, description = analyzer.get_combo_bonus(trainer, jockey)
        print(f"{trainer} + {jockey}:")
        if bonus > 0:
            print(f"  {description}")
        else:
            print(f"  No combo bonus")
        print()

    print("=" * 80)
    print("✓ Combo analyzer test complete")
    print("=" * 80)
