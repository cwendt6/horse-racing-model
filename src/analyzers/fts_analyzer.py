"""
First-Time Starter (FTS) Analyzer
Adjusts predictions for horses with no prior starts using trainer and sire statistics
"""

import json
from typing import Dict, Optional, Tuple


class FTSAnalyzer:
    """
    Analyzes first-time starters and applies adjustments based on:
    - Trainer FTS statistics
    - Sire FTS statistics
    - Workout quality (future enhancement)
    """

    def __init__(self, trainer_stats_file: str, sire_stats_file: str):
        """
        Initialize FTS analyzer with statistics files

        Args:
            trainer_stats_file: Path to FTS trainer statistics JSON
            sire_stats_file: Path to FTS sire statistics JSON
        """
        # Load trainer statistics
        with open(trainer_stats_file, 'r') as f:
            self.trainer_stats = json.load(f)

        # Load sire statistics
        with open(sire_stats_file, 'r') as f:
            self.sire_stats = json.load(f)

        # Build lowercase lookups for easier matching
        self.trainer_lookup = {k.lower().strip(): v for k, v in self.trainer_stats.items()}
        self.sire_lookup = {k.lower().strip(): v for k, v in self.sire_stats.items()}

        # Define elite trainer threshold
        self.ELITE_FTS_THRESHOLD = 25.0  # 25%+ win rate

        # Define hot sire threshold
        self.HOT_SIRE_THRESHOLD = 20.0  # 20%+ win rate

        print(f"FTS Analyzer initialized:")
        print(f"  • {len(self.trainer_stats)} trainers with FTS stats")
        print(f"  • {len(self.sire_stats)} sires with FTS stats")

    def is_first_time_starter(self, career_starts: int) -> bool:
        """Check if horse is a first-time starter"""
        return career_starts == 0

    def get_trainer_fts_stats(self, trainer_name: str) -> Optional[Dict]:
        """
        Get FTS statistics for a trainer

        Returns:
            Dict with fts_win_pct, fts_itm_pct, etc. or None if not found
        """
        trainer_key = trainer_name.lower().strip()
        return self.trainer_lookup.get(trainer_key)

    def get_sire_fts_stats(self, sire_name: str) -> Optional[Dict]:
        """
        Get FTS statistics for a sire

        Returns:
            Dict with fts_win_pct, fts_itm_pct, fts_bonus or None if not found
        """
        sire_key = sire_name.lower().strip()
        return self.sire_lookup.get(sire_key)

    def is_elite_fts_trainer(self, trainer_name: str) -> bool:
        """
        Check if trainer is elite with first-time starters

        Elite = 25%+ FTS win rate with 5+ starts
        """
        stats = self.get_trainer_fts_stats(trainer_name)
        if stats:
            return (stats['fts_win_pct'] >= self.ELITE_FTS_THRESHOLD and
                    stats['fts_starts'] >= 5)
        return False

    def is_hot_sire(self, sire_name: str) -> bool:
        """
        Check if sire is hot with first-time starters

        Hot = 20%+ FTS win rate with 10+ starts
        """
        stats = self.get_sire_fts_stats(sire_name)
        if stats:
            return (stats['fts_win_pct'] >= self.HOT_SIRE_THRESHOLD and
                    stats['fts_starts'] >= 10)
        return False

    def calculate_fts_multiplier(self, trainer_name: str, sire_name: str,
                                  has_bullet_workout: bool = False) -> Tuple[float, str]:
        """
        Calculate FTS adjustment multiplier

        Args:
            trainer_name: Trainer name
            sire_name: Sire name
            has_bullet_workout: Whether horse has bullet workout (future)

        Returns:
            Tuple of (multiplier, explanation)
        """
        multiplier = 0.50  # Default FTS penalty: 50% of normal probability
        explanation_parts = []

        # Get trainer stats
        trainer_stats = self.get_trainer_fts_stats(trainer_name)

        if trainer_stats:
            fts_win_pct = trainer_stats['fts_win_pct']

            # Elite FTS trainer (25%+)
            if fts_win_pct >= 30.0:
                multiplier = 0.90  # Only 10% penalty
                explanation_parts.append(f"Elite FTS trainer ({fts_win_pct:.1f}%): +40% boost")
            elif fts_win_pct >= 25.0:
                multiplier = 0.85  # Only 15% penalty
                explanation_parts.append(f"Strong FTS trainer ({fts_win_pct:.1f}%): +35% boost")
            elif fts_win_pct >= 15.0:
                multiplier = 0.70  # 30% penalty
                explanation_parts.append(f"Above-avg FTS trainer ({fts_win_pct:.1f}%): +20% boost")
            else:
                explanation_parts.append(f"Known FTS trainer ({fts_win_pct:.1f}%)")
        else:
            explanation_parts.append("Unknown FTS trainer: -50% penalty")

        # Get sire stats and apply bonus
        sire_stats = self.get_sire_fts_stats(sire_name)

        if sire_stats:
            sire_bonus = sire_stats.get('fts_bonus', 1.0)
            sire_win_pct = sire_stats['fts_win_pct']

            if sire_bonus > 1.0:
                multiplier *= sire_bonus
                explanation_parts.append(f"Hot sire {sire_name} ({sire_win_pct:.1f}%): +{(sire_bonus-1)*100:.0f}% boost")

        # Workout bonus (future enhancement)
        if has_bullet_workout:
            multiplier *= 1.10
            explanation_parts.append("Bullet workout: +10% boost")

        explanation = "; ".join(explanation_parts)

        return multiplier, explanation

    def get_fts_analysis(self, trainer_name: str, sire_name: str,
                        career_starts: int) -> Dict:
        """
        Get complete FTS analysis for a horse

        Returns:
            Dict with:
                - is_fts: bool
                - multiplier: float
                - explanation: str
                - trainer_stats: dict or None
                - sire_stats: dict or None
        """
        is_fts = self.is_first_time_starter(career_starts)

        if not is_fts:
            return {
                'is_fts': False,
                'multiplier': 1.0,
                'explanation': 'Experienced horse',
                'trainer_stats': None,
                'sire_stats': None
            }

        # Calculate FTS multiplier
        multiplier, explanation = self.calculate_fts_multiplier(trainer_name, sire_name)

        return {
            'is_fts': True,
            'multiplier': multiplier,
            'explanation': explanation,
            'trainer_stats': self.get_trainer_fts_stats(trainer_name),
            'sire_stats': self.get_sire_fts_stats(sire_name),
            'is_elite_trainer': self.is_elite_fts_trainer(trainer_name),
            'is_hot_sire': self.is_hot_sire(sire_name)
        }

    def get_summary_stats(self) -> Dict:
        """Get summary statistics"""
        elite_trainers = [name for name in self.trainer_stats.keys()
                         if self.is_elite_fts_trainer(name)]

        hot_sires = [name for name in self.sire_stats.keys()
                    if self.is_hot_sire(name)]

        return {
            'total_trainers': len(self.trainer_stats),
            'elite_trainers': elite_trainers,
            'elite_trainer_count': len(elite_trainers),
            'total_sires': len(self.sire_stats),
            'hot_sires': hot_sires,
            'hot_sire_count': len(hot_sires)
        }


def test_fts_analyzer():
    """Test the FTS analyzer with sample data"""
    print("\n" + "="*80)
    print(" TESTING FTS ANALYZER")
    print("="*80)

    # Initialize analyzer
    analyzer = FTSAnalyzer(
        trainer_stats_file='data/stats/fts_trainer_statistics.json',
        sire_stats_file='data/stats/fts_sire_statistics.json'
    )

    # Get summary
    summary = analyzer.get_summary_stats()
    print(f"\nSummary:")
    print(f"  Elite FTS trainers: {summary['elite_trainer_count']}")
    print(f"    {', '.join(summary['elite_trainers'])}")
    print(f"  Hot FTS sires: {summary['hot_sire_count']}")

    # Test cases
    test_cases = [
        ("Brad Cox", "Curlin", 0, "Elite trainer + hot sire FTS"),
        ("Wesley Ward", "Into Mischief", 0, "Elite trainer + known sire FTS"),
        ("Todd Pletcher", "Quality Road", 0, "Known trainer FTS"),
        ("Unknown Trainer", "Unknown Sire", 0, "Unknown FTS"),
        ("Brad Cox", "Curlin", 5, "Experienced horse (not FTS)")
    ]

    print(f"\n{'='*80}")
    print(" TEST CASES")
    print(f"{'='*80}\n")

    for trainer, sire, starts, description in test_cases:
        analysis = analyzer.get_fts_analysis(trainer, sire, starts)

        print(f"{description}:")
        print(f"  Trainer: {trainer}, Sire: {sire}, Starts: {starts}")
        print(f"  Is FTS: {analysis['is_fts']}")
        print(f"  Multiplier: {analysis['multiplier']:.2f}")
        print(f"  Explanation: {analysis['explanation']}")

        if analysis['trainer_stats']:
            print(f"  Trainer FTS: {analysis['trainer_stats']['fts_wins']}/{analysis['trainer_stats']['fts_starts']} ({analysis['trainer_stats']['fts_win_pct']}%)")

        if analysis['sire_stats']:
            print(f"  Sire FTS: {analysis['sire_stats']['fts_wins']}/{analysis['sire_stats']['fts_starts']} ({analysis['sire_stats']['fts_win_pct']}%)")

        print()

    print("="*80)
    print()


if __name__ == '__main__':
    test_fts_analyzer()
