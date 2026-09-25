"""
Enhanced Jockey Analyzer - Conditional Multipliers
Addresses critical finding from Oct 22 post-mortem: Elite jockeys are underweighted
"""

from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass
class JockeyAnalysis:
    """Results from enhanced jockey analysis"""
    base_score: float  # Base jockey score (win % * 100)
    multiplier: float  # Conditional multiplier based on context
    bonus_points: float  # Absolute bonus points
    total_score: float  # Final adjusted score
    analysis_notes: list  # Explanation of adjustments


class EnhancedJockeyAnalyzer:
    """
    Enhanced jockey analysis with conditional multipliers

    Key Findings from Oct 22 Post-Mortem:
    - Elite jockeys (Gaffalione, Ortiz Jr.) were critical to manual handicapping success
    - Jockey angle produced 3/7 winners (42.9% win rate)
    - Model severely underweights jockey impact
    - Especially critical in maiden races where rider skill matters most
    """

    # Elite jockey thresholds
    ELITE_WIN_RATE = 0.18  # 18%+ win rate = elite
    GOOD_WIN_RATE = 0.12   # 12%+ win rate = above average
    POOR_WIN_RATE = 0.05   # <5% win rate = avoid

    # ITM thresholds (In The Money = 1st, 2nd, or 3rd)
    ELITE_ITM_RATE = 0.50  # 50%+ ITM = elite
    GOOD_ITM_RATE = 0.35   # 35%+ ITM = above average

    def __init__(self):
        """Initialize enhanced jockey analyzer"""
        # Known elite jockeys from Oct 22 analysis
        self.known_elite = {
            'Irad Ortiz, Jr': {'win_rate': 0.24, 'itm_rate': 0.58},
            'Tyler Gaffalione': {'win_rate': 0.22, 'itm_rate': 0.55},
            'Luis Saez': {'win_rate': 0.20, 'itm_rate': 0.52},
            'Javier Castellano': {'win_rate': 0.18, 'itm_rate': 0.50},
            'Joel Rosario': {'win_rate': 0.19, 'itm_rate': 0.51},
        }

    def analyze_jockey(
        self,
        jockey_name: str,
        win_rate: float,
        itm_rate: float = None,
        race_type: str = None,
        horse_experience_level: str = 'experienced'  # or 'maiden', 'fts'
    ) -> JockeyAnalysis:
        """
        Analyze jockey with conditional multipliers

        Args:
            jockey_name: Jockey's name
            win_rate: Jockey win percentage (0.0 to 1.0)
            itm_rate: In The Money rate (optional but recommended)
            race_type: 'maiden', 'stakes', 'allowance', 'claiming', etc.
            horse_experience_level: 'fts' (first time starter), 'maiden', 'experienced'

        Returns:
            JockeyAnalysis with multiplier and bonuses
        """
        # Base score: win_rate * 100 (0-100 scale)
        base_score = win_rate * 100

        # Start with neutral multiplier
        multiplier = 1.0
        bonus_points = 0.0
        notes = []

        # Check if jockey is in elite database
        is_known_elite = jockey_name in self.known_elite
        if is_known_elite:
            stats = self.known_elite[jockey_name]
            win_rate = max(win_rate, stats['win_rate'])  # Use higher of two
            if itm_rate is None:
                itm_rate = stats['itm_rate']

        # === ELITE JOCKEY BONUSES ===

        # Tier 1: ELITE jockeys (18%+ win rate)
        if win_rate >= self.ELITE_WIN_RATE:
            multiplier += 0.35  # +35% boost
            bonus_points += 12  # +12 absolute points
            notes.append(f"🌟 ELITE JOCKEY (Win: {win_rate*100:.1f}%)")

            # Extra boost if ITM rate is also elite
            if itm_rate and itm_rate >= self.ELITE_ITM_RATE:
                multiplier += 0.15  # Additional +15%
                bonus_points += 5  # Additional +5 points
                notes.append(f"⭐ ELITE ITM RATE ({itm_rate*100:.1f}%)")

        # Tier 2: GOOD jockeys (12-18% win rate)
        elif win_rate >= self.GOOD_WIN_RATE:
            multiplier += 0.20  # +20% boost
            bonus_points += 6  # +6 absolute points
            notes.append(f"✓ Above Average Jockey (Win: {win_rate*100:.1f}%)")

        # Tier 3: POOR jockeys (<5% win rate)
        elif win_rate < self.POOR_WIN_RATE:
            multiplier -= 0.30  # -30% penalty
            bonus_points -= 8  # -8 absolute points
            notes.append(f"⚠️ Poor Jockey Stats (Win: {win_rate*100:.1f}%)")

        # === RACE TYPE BONUSES ===

        # MAIDEN RACES: Jockey skill is CRITICAL (rider can overcome inexperience)
        if race_type and 'maiden' in race_type.lower():
            if win_rate >= self.ELITE_WIN_RATE:
                multiplier += 0.25  # Additional +25% in maidens
                bonus_points += 10  # Additional +10 points
                notes.append("🎯 ELITE JOCKEY IN MAIDEN (huge edge!)")
            elif win_rate >= self.GOOD_WIN_RATE:
                multiplier += 0.15  # Additional +15% in maidens
                bonus_points += 5  # Additional +5 points
                notes.append("✓ Good jockey in maiden race")
            else:
                # Poor jockey in maiden is extra bad
                multiplier -= 0.15  # Additional -15% penalty
                bonus_points -= 5  # Additional -5 points
                notes.append("❌ Weak jockey hurts in maiden")

        # STAKES RACES: Elite jockeys get mounts on best horses
        if race_type and 'stakes' in race_type.lower():
            if win_rate >= self.ELITE_WIN_RATE:
                multiplier += 0.10  # +10% in stakes
                notes.append("Stakes-quality rider")

        # === HORSE EXPERIENCE BONUSES ===

        # FIRST TIME STARTERS: Elite jockey can make huge difference
        if horse_experience_level == 'fts':
            if win_rate >= self.ELITE_WIN_RATE:
                multiplier += 0.20  # +20% for FTS with elite jockey
                bonus_points += 8  # +8 points
                notes.append("🌟 Elite jockey on FTS (trainer confidence!)")
            elif win_rate < self.GOOD_WIN_RATE:
                multiplier -= 0.20  # -20% for FTS with poor jockey
                bonus_points -= 6  # -6 points
                notes.append("⚠️ Weak jockey on FTS (red flag)")

        # === CALCULATE FINAL SCORE ===

        # Apply multiplier to base score
        multiplied_score = base_score * multiplier

        # Add absolute bonus points
        total_score = multiplied_score + bonus_points

        # Cap at reasonable bounds (0-120)
        total_score = max(0.0, min(120.0, total_score))

        return JockeyAnalysis(
            base_score=base_score,
            multiplier=multiplier,
            bonus_points=bonus_points,
            total_score=total_score,
            analysis_notes=notes
        )

    def format_analysis(self, analysis: JockeyAnalysis) -> str:
        """Format jockey analysis for display"""
        lines = []
        lines.append(f"Jockey Analysis:")
        lines.append(f"  Base Score: {analysis.base_score:.1f}")
        lines.append(f"  Multiplier: {analysis.multiplier:.2f}x")
        lines.append(f"  Bonus Points: {analysis.bonus_points:+.1f}")
        lines.append(f"  Final Score: {analysis.total_score:.1f}")

        if analysis.analysis_notes:
            lines.append(f"  Notes:")
            for note in analysis.analysis_notes:
                lines.append(f"    - {note}")

        return "\n".join(lines)


def analyze_jockey_quick(
    jockey_name: str,
    win_rate: float,
    race_type: str = None,
    is_maiden_horse: bool = False,
    is_fts: bool = False
) -> Tuple[float, str]:
    """
    Quick jockey analysis for integration into prediction pipeline

    Args:
        jockey_name: Jockey's name
        win_rate: Win percentage (0.0 to 1.0)
        race_type: Type of race
        is_maiden_horse: Is this a maiden (inexperienced) horse?
        is_fts: Is this a first time starter?

    Returns:
        Tuple of (adjusted_score, description)
    """
    analyzer = EnhancedJockeyAnalyzer()

    # Determine experience level
    if is_fts:
        experience = 'fts'
    elif is_maiden_horse:
        experience = 'maiden'
    else:
        experience = 'experienced'

    # Analyze
    analysis = analyzer.analyze_jockey(
        jockey_name=jockey_name,
        win_rate=win_rate,
        itm_rate=None,  # Use database if available
        race_type=race_type,
        horse_experience_level=experience
    )

    # Create description
    if analysis.analysis_notes:
        description = " | ".join(analysis.analysis_notes)
    else:
        description = f"Jockey: {win_rate*100:.1f}% win rate"

    return analysis.total_score, description


# Example usage
if __name__ == '__main__':
    analyzer = EnhancedJockeyAnalyzer()

    # Test Case 1: Elite jockey (Gaffalione) in maiden race
    print("Test 1: Gaffalione in Maiden Race")
    analysis = analyzer.analyze_jockey(
        jockey_name='Tyler Gaffalione',
        win_rate=0.22,
        itm_rate=0.55,
        race_type='maiden',
        horse_experience_level='maiden'
    )
    print(analyzer.format_analysis(analysis))
    print()

    # Test Case 2: Poor jockey in maiden race
    print("Test 2: Poor Jockey (8% win rate) in Maiden Race")
    analysis = analyzer.analyze_jockey(
        jockey_name='Unknown Jockey',
        win_rate=0.08,
        itm_rate=0.25,
        race_type='maiden',
        horse_experience_level='maiden'
    )
    print(analyzer.format_analysis(analysis))
    print()

    # Test Case 3: Elite jockey on FTS
    print("Test 3: Ortiz Jr. on First Time Starter")
    analysis = analyzer.analyze_jockey(
        jockey_name='Irad Ortiz, Jr',
        win_rate=0.24,
        itm_rate=0.58,
        race_type='maiden',
        horse_experience_level='fts'
    )
    print(analyzer.format_analysis(analysis))
