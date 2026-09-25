"""
Enhanced Trainer Specialization Analyzer - Conditional Multipliers
Addresses critical finding from Oct 22 post-mortem: Trainer patterns underweighted
"""

from dataclasses import dataclass
from typing import Dict, Tuple, List


@dataclass
class TrainerAnalysis:
    """Results from enhanced trainer analysis"""
    base_score: float  # Base trainer score (win % * 100)
    multiplier: float  # Conditional multiplier based on specialty
    bonus_points: float  # Absolute bonus points
    total_score: float  # Final adjusted score
    analysis_notes: list  # Explanation of adjustments


class TrainerSpecializationAnalyzer:
    """
    Enhanced trainer analysis with specialty pattern recognition

    Key Findings from Oct 22 Post-Mortem:
    - Steven Asmussen won 2 races (Races 3, 8) - claiming and maiden specialist
    - Wesley Ward 2YO turf angle - didn't fire but logic was sound
    - Elite trainers have predictable patterns that create edges
    - Trainer specialization was a key component of manual handicapping success
    """

    # Elite trainer thresholds
    ELITE_WIN_RATE = 0.20  # 20%+ win rate = elite
    GOOD_WIN_RATE = 0.15   # 15%+ win rate = above average
    POOR_WIN_RATE = 0.08   # <8% win rate = avoid

    def __init__(self):
        """Initialize trainer specialization analyzer"""
        # Known elite trainers with specializations
        self.trainer_specializations = {
            # Steven Asmussen - Elite all-around, especially strong in claiming
            'Steven Asmussen': {
                'win_rate': 0.22,
                'specialties': ['claiming', 'maiden', 'sprint'],
                'strengths': {
                    'claiming': 1.40,      # +40% in claiming
                    'maiden': 1.25,        # +25% in maiden
                    'sprint': 1.15,        # +15% in sprints
                    'dirt': 1.10,          # +10% on dirt
                }
            },
            'Steve Asmussen': {  # Alternative spelling
                'win_rate': 0.22,
                'specialties': ['claiming', 'maiden', 'sprint'],
                'strengths': {
                    'claiming': 1.40,
                    'maiden': 1.25,
                    'sprint': 1.15,
                    'dirt': 1.10,
                }
            },
            'Steven M Asmussen': {  # With middle initial
                'win_rate': 0.22,
                'specialties': ['claiming', 'maiden', 'sprint'],
                'strengths': {
                    'claiming': 1.40,
                    'maiden': 1.25,
                    'sprint': 1.15,
                    'dirt': 1.10,
                }
            },
            'Steven M. Asmussen': {  # With middle initial and period
                'win_rate': 0.22,
                'specialties': ['claiming', 'maiden', 'sprint'],
                'strengths': {
                    'claiming': 1.40,
                    'maiden': 1.25,
                    'sprint': 1.15,
                    'dirt': 1.10,
                }
            },

            # Wesley Ward - 2YO specialist, especially turf
            'Wesley Ward': {
                'win_rate': 0.25,
                'specialties': ['2yo', 'turf', 'sprint', 'maiden'],
                'strengths': {
                    '2yo': 1.50,           # +50% with 2YOs
                    'turf': 1.35,          # +35% on turf
                    '2yo_turf': 1.75,      # +75% with 2YO on turf (combo)
                    'maiden': 1.30,        # +30% in maidens
                    'sprint': 1.20,        # +20% in sprints
                }
            },

            # Brad Cox - Elite stakes trainer
            'Brad Cox': {
                'win_rate': 0.24,
                'specialties': ['stakes', 'allowance', 'route'],
                'strengths': {
                    'stakes': 1.45,        # +45% in stakes
                    'graded_stakes': 1.60, # +60% in graded stakes
                    'allowance': 1.30,     # +30% in allowance
                    'route': 1.20,         # +20% in routes
                }
            },
            'Bradley Cox': {  # Alternative name
                'win_rate': 0.24,
                'specialties': ['stakes', 'allowance', 'route'],
                'strengths': {
                    'stakes': 1.45,
                    'graded_stakes': 1.60,
                    'allowance': 1.30,
                    'route': 1.20,
                }
            },
            'Brad H Cox': {  # With middle initial
                'win_rate': 0.24,
                'specialties': ['stakes', 'allowance', 'route', 'maiden', 'fts'],
                'strengths': {
                    'stakes': 1.45,
                    'graded_stakes': 1.60,
                    'allowance': 1.30,
                    'route': 1.20,
                    'maiden': 1.50,  # 43.48% FTS (increased from 1.35)
                    'fts': 1.55,     # 43.48% FTS (increased from 1.30)
                }
            },
            'Brad H. Cox': {  # With middle initial and period
                'win_rate': 0.24,
                'specialties': ['stakes', 'allowance', 'route', 'maiden', 'fts'],
                'strengths': {
                    'stakes': 1.45,
                    'graded_stakes': 1.60,
                    'allowance': 1.30,
                    'route': 1.20,
                    'maiden': 1.50,  # 43.48% FTS (increased from 1.35)
                    'fts': 1.55,     # 43.48% FTS (increased from 1.30)
                }
            },

            # Chad Brown - Turf specialist, stakes
            'Chad Brown': {
                'win_rate': 0.23,
                'specialties': ['turf', 'stakes', 'route'],
                'strengths': {
                    'turf': 1.50,          # +50% on turf
                    'stakes': 1.40,        # +40% in stakes
                    'turf_stakes': 1.70,   # +70% in turf stakes (combo)
                    'route': 1.25,         # +25% in routes
                }
            },
            'Chad C. Brown': {  # Alternative name
                'win_rate': 0.23,
                'specialties': ['turf', 'stakes', 'route'],
                'strengths': {
                    'turf': 1.50,
                    'stakes': 1.40,
                    'turf_stakes': 1.70,
                    'route': 1.25,
                }
            },
            'Chad C Brown': {  # Without period
                'win_rate': 0.23,
                'specialties': ['turf', 'stakes', 'route', 'maiden', 'fts'],
                'strengths': {
                    'turf': 1.50,
                    'stakes': 1.40,
                    'turf_stakes': 1.70,
                    'route': 1.25,
                    'maiden': 1.60,  # 76.92% FTS rate! (increased from 1.45)
                    'fts': 1.75,     # 76.92% FTS - nearly automatic (increased from 1.50)
                }
            },

            # Todd Pletcher - Elite all-around, maiden specialist
            'Todd Pletcher': {
                'win_rate': 0.21,
                'specialties': ['maiden', 'stakes', 'fts'],
                'strengths': {
                    'maiden': 1.40,        # +40% in maidens
                    'fts': 1.35,           # +35% with first-time starters
                    'stakes': 1.30,        # +30% in stakes
                    '2yo': 1.25,           # +25% with 2YOs
                }
            },
            'Todd A. Pletcher': {  # Alternative name
                'win_rate': 0.21,
                'specialties': ['maiden', 'stakes', 'fts'],
                'strengths': {
                    'maiden': 1.40,
                    'fts': 1.35,
                    'stakes': 1.30,
                    '2yo': 1.25,
                }
            },
            'Todd A Pletcher': {  # Without period
                'win_rate': 0.21,
                'specialties': ['maiden', 'stakes', 'fts'],
                'strengths': {
                    'maiden': 1.55,  # 69.23% FTS (increased from 1.40)
                    'fts': 1.70,     # 69.23% FTS (increased from 1.35)
                    'stakes': 1.30,
                    '2yo': 1.25,
                }
            },

            # Bob Baffert - Stakes specialist
            'Bob Baffert': {
                'win_rate': 0.22,
                'specialties': ['stakes', '3yo', 'dirt'],
                'strengths': {
                    'stakes': 1.50,        # +50% in stakes
                    'graded_stakes': 1.65, # +65% in graded stakes
                    '3yo': 1.30,           # +30% with 3YOs
                    'dirt': 1.20,          # +20% on dirt
                }
            },

            # Michael Maker - Turf specialist, claiming
            'Michael Maker': {
                'win_rate': 0.18,
                'specialties': ['turf', 'claiming'],
                'strengths': {
                    'turf': 1.35,          # +35% on turf
                    'claiming': 1.25,      # +25% in claiming
                    'route': 1.15,         # +15% in routes
                }
            },
            'Michael J Maker': {  # Alternative name
                'win_rate': 0.18,
                'specialties': ['turf', 'claiming'],
                'strengths': {
                    'turf': 1.35,
                    'claiming': 1.25,
                    'route': 1.15,
                }
            },
            'Michael J. Maker': {  # With period
                'win_rate': 0.18,
                'specialties': ['turf', 'claiming'],
                'strengths': {
                    'turf': 1.35,
                    'claiming': 1.25,
                    'route': 1.15,
                }
            },

            # Bill Mott - Route specialist, older horses
            'Bill Mott': {
                'win_rate': 0.20,
                'specialties': ['route', 'stakes', 'turf'],
                'strengths': {
                    'route': 1.40,         # +40% in routes
                    'stakes': 1.30,        # +30% in stakes
                    'turf': 1.25,          # +25% on turf
                }
            },
            'William Mott': {  # Alternative name
                'win_rate': 0.20,
                'specialties': ['route', 'stakes', 'turf'],
                'strengths': {
                    'route': 1.40,
                    'stakes': 1.30,
                    'turf': 1.25,
                }
            },
            'William I Mott': {  # With middle initial
                'win_rate': 0.20,
                'specialties': ['route', 'stakes', 'turf'],
                'strengths': {
                    'route': 1.40,
                    'stakes': 1.30,
                    'turf': 1.25,
                }
            },
            'William I. Mott': {  # With middle initial and period
                'win_rate': 0.20,
                'specialties': ['route', 'stakes', 'turf'],
                'strengths': {
                    'route': 1.40,
                    'stakes': 1.30,
                    'turf': 1.25,
                }
            },

            # Brendan Walsh - Elite FTS specialist (65.63% FTS rate!)
            'Brendan Walsh': {
                'win_rate': 0.22,
                'specialties': ['maiden', 'fts', 'turf'],
                'strengths': {
                    'maiden': 1.50,        # +50% in maidens
                    'fts': 1.55,           # +55% with first-time starters (65.63%!)
                    'turf': 1.30,          # +30% on turf
                    '2yo': 1.35,           # +35% with 2YOs
                }
            },
            'Brendan P Walsh': {  # With middle initial
                'win_rate': 0.22,
                'specialties': ['maiden', 'fts', 'turf'],
                'strengths': {
                    'maiden': 1.60,  # 65.63% FTS (increased from 1.50)
                    'fts': 1.70,     # 65.63% FTS! (increased from 1.55)
                    'turf': 1.30,
                    '2yo': 1.35,
                }
            },
            'Brendan P. Walsh': {  # With middle initial and period
                'win_rate': 0.22,
                'specialties': ['maiden', 'fts', 'turf'],
                'strengths': {
                    'maiden': 1.50,
                    'fts': 1.55,
                    'turf': 1.30,
                    '2yo': 1.35,
                }
            },

            # George Weaver - Strong trainer (50.51% win rate with specific horses)
            'George Weaver': {
                'win_rate': 0.19,
                'specialties': ['allowance', 'stakes', 'turf'],
                'strengths': {
                    'allowance': 1.35,     # +35% in allowance
                    'stakes': 1.30,        # +30% in stakes
                    'turf': 1.25,          # +25% on turf
                    'route': 1.20,         # +20% in routes
                }
            },

            # William Walden - FTS specialist (70.00% FTS rate!)
            'William Walden': {
                'win_rate': 0.18,
                'specialties': ['maiden', 'fts'],
                'strengths': {
                    'maiden': 1.65,        # 70% FTS! (increased from 1.55)
                    'fts': 1.75,           # 70% FTS! (increased from 1.60)
                    '2yo': 1.40,           # +40% with 2YOs
                }
            },

            # Michael W McCarthy - FTS specialist (66.67% FTS rate!)
            'Michael W McCarthy': {
                'win_rate': 0.17,
                'specialties': ['maiden', 'fts'],
                'strengths': {
                    'maiden': 1.50,        # +50% in maidens
                    'fts': 1.55,           # +55% with first-time starters (66.67%!)
                }
            },
            'Michael McCarthy': {  # Short form
                'win_rate': 0.17,
                'specialties': ['maiden', 'fts'],
                'strengths': {
                    'maiden': 1.50,
                    'fts': 1.55,
                }
            },
        }

    def analyze_trainer(
        self,
        trainer_name: str,
        win_rate: float,
        race_type: str = None,
        surface: str = 'dirt',
        distance_furlongs: float = 6.0,
        horse_age: int = 3,
        is_fts: bool = False
    ) -> TrainerAnalysis:
        """
        Analyze trainer with specialty pattern recognition

        Args:
            trainer_name: Trainer's name
            win_rate: Trainer win percentage (0.0 to 1.0)
            race_type: 'maiden', 'claiming', 'allowance', 'stakes', 'graded stakes', etc.
            surface: 'dirt', 'turf', 'synthetic'
            distance_furlongs: Race distance in furlongs
            horse_age: Horse's age (2, 3, 4+)
            is_fts: Is this a first-time starter?

        Returns:
            TrainerAnalysis with multiplier and bonuses
        """
        # Base score: win_rate * 100 (0-100 scale)
        base_score = win_rate * 100

        # Start with neutral multiplier
        multiplier = 1.0
        bonus_points = 0.0
        notes = []

        # Check if trainer is in specialization database
        trainer_data = self.trainer_specializations.get(trainer_name)

        # Normalize race type
        race_type_normalized = race_type.lower() if race_type else ''
        surface_normalized = surface.lower()

        # Determine distance category
        is_sprint = distance_furlongs <= 7.0
        is_route = distance_furlongs >= 9.0

        # === ELITE TRAINER BONUSES ===

        # Base tier assessment
        if win_rate >= self.ELITE_WIN_RATE:
            multiplier += 0.20  # +20% base for elite
            bonus_points += 8   # +8 points
            notes.append(f"🌟 ELITE TRAINER (Win: {win_rate*100:.1f}%)")
        elif win_rate >= self.GOOD_WIN_RATE:
            multiplier += 0.10  # +10% for good trainers
            bonus_points += 4   # +4 points
            notes.append(f"✓ Above Average Trainer (Win: {win_rate*100:.1f}%)")
        elif win_rate < self.POOR_WIN_RATE:
            multiplier -= 0.20  # -20% penalty
            bonus_points -= 6   # -6 points
            notes.append(f"⚠️ Weak Trainer Stats (Win: {win_rate*100:.1f}%)")

        # === SPECIALTY PATTERN BONUSES ===

        if trainer_data:
            specialties = trainer_data.get('specialties', [])
            strengths = trainer_data.get('strengths', {})

            # Track applied bonuses
            applied_multiplier = 1.0

            # Check for combo bonuses first (higher priority)

            # 2YO on turf (Wesley Ward special)
            if horse_age == 2 and surface_normalized == 'turf' and '2yo_turf' in strengths:
                applied_multiplier = max(applied_multiplier, strengths['2yo_turf'])
                bonus_points += 15
                notes.append(f"🎯 2YO TURF SPECIALIST (Ward angle!)")

            # Turf stakes (Chad Brown special)
            elif surface_normalized == 'turf' and 'stakes' in race_type_normalized and 'turf_stakes' in strengths:
                applied_multiplier = max(applied_multiplier, strengths['turf_stakes'])
                bonus_points += 12
                notes.append(f"🎯 TURF STAKES SPECIALIST")

            # Otherwise check individual specialties
            else:
                # Race type bonuses
                if 'graded' in race_type_normalized and 'stake' in race_type_normalized and 'graded_stakes' in strengths:
                    applied_multiplier = max(applied_multiplier, strengths['graded_stakes'])
                    bonus_points += 12
                    notes.append(f"⭐ GRADED STAKES SPECIALIST")
                elif 'stake' in race_type_normalized and 'stakes' in strengths:
                    applied_multiplier = max(applied_multiplier, strengths['stakes'])
                    bonus_points += 10
                    notes.append(f"✓ Stakes specialist")
                elif 'claiming' in race_type_normalized and 'claiming' in strengths:
                    applied_multiplier = max(applied_multiplier, strengths['claiming'])
                    bonus_points += 8
                    notes.append(f"✓ Claiming specialist")
                elif 'maiden' in race_type_normalized and 'maiden' in strengths:
                    applied_multiplier = max(applied_multiplier, strengths['maiden'])
                    bonus_points += 8
                    notes.append(f"✓ Maiden specialist")
                elif 'allowance' in race_type_normalized and 'allowance' in strengths:
                    applied_multiplier = max(applied_multiplier, strengths['allowance'])
                    bonus_points += 6
                    notes.append(f"✓ Allowance specialist")

                # Surface bonuses (additive if not already applied)
                if surface_normalized == 'turf' and 'turf' in strengths:
                    turf_mult = strengths['turf']
                    if applied_multiplier == 1.0:
                        applied_multiplier = turf_mult
                    else:
                        applied_multiplier *= (1.0 + (turf_mult - 1.0) * 0.5)  # 50% of turf bonus
                    bonus_points += 5
                    notes.append(f"✓ Turf specialist")

                # Distance bonuses (additive)
                if is_sprint and 'sprint' in strengths:
                    sprint_mult = strengths['sprint']
                    if applied_multiplier == 1.0:
                        applied_multiplier = sprint_mult
                    else:
                        applied_multiplier *= (1.0 + (sprint_mult - 1.0) * 0.5)
                    bonus_points += 3
                    notes.append(f"✓ Sprint specialist")
                elif is_route and 'route' in strengths:
                    route_mult = strengths['route']
                    if applied_multiplier == 1.0:
                        applied_multiplier = route_mult
                    else:
                        applied_multiplier *= (1.0 + (route_mult - 1.0) * 0.5)
                    bonus_points += 3
                    notes.append(f"✓ Route specialist")

                # Age bonuses
                if horse_age == 2 and '2yo' in strengths:
                    two_yo_mult = strengths['2yo']
                    if applied_multiplier == 1.0:
                        applied_multiplier = two_yo_mult
                    else:
                        applied_multiplier *= (1.0 + (two_yo_mult - 1.0) * 0.5)
                    bonus_points += 5
                    notes.append(f"✓ 2YO specialist")
                elif horse_age == 3 and '3yo' in strengths:
                    three_yo_mult = strengths['3yo']
                    if applied_multiplier == 1.0:
                        applied_multiplier = three_yo_mult
                    else:
                        applied_multiplier *= (1.0 + (three_yo_mult - 1.0) * 0.5)
                    bonus_points += 4
                    notes.append(f"✓ 3YO specialist")

                # First-time starter bonus (INCREASED BASED ON RACE RESULTS)
                if is_fts and 'fts' in strengths:
                    fts_mult = strengths['fts']

                    # CRITICAL: Use actual FTS multiplier, not dampened
                    # Race 6 proved Chad Brown 76.92% FTS is nearly automatic
                    if applied_multiplier == 1.0:
                        applied_multiplier = fts_mult
                    else:
                        # Still apply combo but with higher weight (75% vs 50%)
                        applied_multiplier *= (1.0 + (fts_mult - 1.0) * 0.75)

                    # Higher bonus points for elite FTS specialists
                    if fts_mult >= 1.50:  # 70%+ FTS rate
                        bonus_points += 15  # Was 6
                        notes.append(f"🎯 ELITE FTS SPECIALIST (near-automatic!)")
                    elif fts_mult >= 1.40:  # 60-69% FTS rate
                        bonus_points += 12  # Was 6
                        notes.append(f"⭐ STRONG FTS SPECIALIST")
                    else:
                        bonus_points += 8   # Was 6
                        notes.append(f"✓ FTS specialist")

            # Apply specialty multiplier (combine with base multiplier)
            multiplier *= applied_multiplier

        # === CALCULATE FINAL SCORE ===

        # Apply multiplier to base score
        multiplied_score = base_score * multiplier

        # Add absolute bonus points
        total_score = multiplied_score + bonus_points

        # Cap at reasonable bounds (0-150 to allow for strong specialists)
        total_score = max(0.0, min(150.0, total_score))

        return TrainerAnalysis(
            base_score=base_score,
            multiplier=multiplier,
            bonus_points=bonus_points,
            total_score=total_score,
            analysis_notes=notes
        )

    def format_analysis(self, analysis: TrainerAnalysis) -> str:
        """Format trainer analysis for display"""
        lines = []
        lines.append(f"Trainer Analysis:")
        lines.append(f"  Base Score: {analysis.base_score:.1f}")
        lines.append(f"  Multiplier: {analysis.multiplier:.2f}x")
        lines.append(f"  Bonus Points: {analysis.bonus_points:+.1f}")
        lines.append(f"  Final Score: {analysis.total_score:.1f}")

        if analysis.analysis_notes:
            lines.append(f"  Notes:")
            for note in analysis.analysis_notes:
                lines.append(f"    - {note}")

        return "\n".join(lines)


# Example usage
if __name__ == '__main__':
    analyzer = TrainerSpecializationAnalyzer()

    # Test Case 1: Steven Asmussen in claiming race
    print("Test 1: Steven Asmussen in Claiming Race")
    analysis = analyzer.analyze_trainer(
        trainer_name='Steven Asmussen',
        win_rate=0.22,
        race_type='claiming',
        surface='dirt',
        distance_furlongs=6.0,
        horse_age=4
    )
    print(analyzer.format_analysis(analysis))
    print()

    # Test Case 2: Wesley Ward with 2YO on turf
    print("Test 2: Wesley Ward with 2YO on Turf")
    analysis = analyzer.analyze_trainer(
        trainer_name='Wesley Ward',
        win_rate=0.25,
        race_type='maiden',
        surface='turf',
        distance_furlongs=5.5,
        horse_age=2
    )
    print(analyzer.format_analysis(analysis))
    print()

    # Test Case 3: Chad Brown in turf stakes
    print("Test 3: Chad Brown in Turf Stakes")
    analysis = analyzer.analyze_trainer(
        trainer_name='Chad Brown',
        win_rate=0.23,
        race_type='graded stakes',
        surface='turf',
        distance_furlongs=9.0,
        horse_age=4
    )
    print(analyzer.format_analysis(analysis))
