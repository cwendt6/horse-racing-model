"""
Equipment Change Analyzer
Detects and scores equipment changes (blinkers, Lasix, etc.)

CRITICAL FEATURE: Equipment changes, especially first-time blinkers and first-time Lasix,
are highly predictive of improved performance.

Expected Impact: +5-8% accuracy improvement
"""

from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass
import re


@dataclass
class EquipmentChange:
    """Represents an equipment change"""
    equipment_type: str  # 'blinkers', 'lasix', 'blinkers_off', 'lasix_off'
    is_first_time: bool
    is_removal: bool
    description: str
    score_impact: float  # Points to add/subtract


class EquipmentAnalyzer:
    """
    Analyzes equipment changes and their impact on performance

    Equipment codes in DRF PPs:
    - b = blinkers on
    - L = Lasix on
    - bL = both on
    - (blank) = neither

    High-value changes:
    - First-time blinkers: +5 to +8 points (wake-up call)
    - First-time Lasix: +3 to +5 points (improves breathing)
    - Blinkers off: -2 to -4 points (losing focus aid)
    - Returning blinkers: +2 to +4 points (back to what works)
    """

    # Scoring weights
    FIRST_TIME_BLINKERS = 7.0  # Strong positive
    FIRST_TIME_LASIX = 4.0     # Moderate positive
    BLINKERS_OFF = -3.0        # Negative (removing what helped)
    LASIX_OFF = -2.0           # Negative (but less common)
    BLINKERS_BACK_ON = 3.0     # Positive (returning to what worked)
    LASIX_BACK_ON = 2.0        # Slight positive

    def __init__(self):
        self.equipment_pattern = re.compile(
            r'\s+(\d{3})\s+([bL]+)?\s+[\d\.\*]',  # weight, optional equipment, odds
            re.IGNORECASE
        )

    def extract_equipment_from_pp_line(self, pp_line: str) -> Dict[str, bool]:
        """
        Extract equipment from a past performance line

        Returns:
            dict with 'blinkers' and 'lasix' boolean flags
        """
        equipment = {'blinkers': False, 'lasix': False}

        # Look for equipment codes after weight
        match = self.equipment_pattern.search(pp_line)

        if match and match.group(2):  # Has equipment code
            equip_code = match.group(2).lower()
            equipment['blinkers'] = 'b' in equip_code
            equipment['lasix'] = 'l' in equip_code

        return equipment

    def extract_equipment_from_pps(self, past_performances: List) -> List[Dict[str, bool]]:
        """
        Extract equipment for all past performances

        Args:
            past_performances: List of PP dicts or objects

        Returns:
            List of equipment dicts (newest to oldest)
        """
        equipment_history = []

        for pp in past_performances:
            # Get the raw PP line if available
            if isinstance(pp, dict):
                pp_line = pp.get('raw_line', '')
            else:
                pp_line = getattr(pp, 'raw_line', '')

            if pp_line:
                equip = self.extract_equipment_from_pp_line(pp_line)
            else:
                # No raw line available, assume no equipment
                equip = {'blinkers': False, 'lasix': False}

            equipment_history.append(equip)

        return equipment_history

    def detect_changes(
        self,
        today_equipment: Dict[str, bool],
        past_equipment: List[Dict[str, bool]]
    ) -> List[EquipmentChange]:
        """
        Detect equipment changes from past to today

        Args:
            today_equipment: Equipment for today's race
            past_equipment: Equipment history from PPs (newest to oldest)

        Returns:
            List of EquipmentChange objects
        """
        changes = []

        # No past data - can't determine changes
        if not past_equipment:
            return changes

        last_race_equipment = past_equipment[0] if past_equipment else {}

        # Check blinkers changes
        today_blinkers = today_equipment.get('blinkers', False)
        last_blinkers = last_race_equipment.get('blinkers', False)

        if today_blinkers and not last_blinkers:
            # Blinkers added

            # Is this first time ever?
            first_time = not any(eq.get('blinkers', False) for eq in past_equipment)

            if first_time:
                changes.append(EquipmentChange(
                    equipment_type='blinkers',
                    is_first_time=True,
                    is_removal=False,
                    description='🎯 FIRST TIME BLINKERS (wake-up call)',
                    score_impact=self.FIRST_TIME_BLINKERS
                ))
            else:
                # Blinkers back on
                changes.append(EquipmentChange(
                    equipment_type='blinkers',
                    is_first_time=False,
                    is_removal=False,
                    description='✓ Blinkers back on (returns to what worked)',
                    score_impact=self.BLINKERS_BACK_ON
                ))

        elif not today_blinkers and last_blinkers:
            # Blinkers removed
            changes.append(EquipmentChange(
                equipment_type='blinkers_off',
                is_first_time=False,
                is_removal=True,
                description='⚠️ Blinkers OFF (removing focus aid)',
                score_impact=self.BLINKERS_OFF
            ))

        # Check Lasix changes
        today_lasix = today_equipment.get('lasix', False)
        last_lasix = last_race_equipment.get('lasix', False)

        if today_lasix and not last_lasix:
            # Lasix added

            # Is this first time ever?
            first_time = not any(eq.get('lasix', False) for eq in past_equipment)

            if first_time:
                changes.append(EquipmentChange(
                    equipment_type='lasix',
                    is_first_time=True,
                    is_removal=False,
                    description='✓ First-time Lasix (breathing aid)',
                    score_impact=self.FIRST_TIME_LASIX
                ))
            else:
                # Lasix back on
                changes.append(EquipmentChange(
                    equipment_type='lasix',
                    is_first_time=False,
                    is_removal=False,
                    description='Lasix back on',
                    score_impact=self.LASIX_BACK_ON
                ))

        elif not today_lasix and last_lasix:
            # Lasix removed
            changes.append(EquipmentChange(
                equipment_type='lasix_off',
                is_first_time=False,
                is_removal=True,
                description='⚠️ Lasix OFF',
                score_impact=self.LASIX_OFF
            ))

        return changes

    def analyze_horse(
        self,
        horse_name: str,
        today_equipment: Dict[str, bool],
        past_performances: List
    ) -> Tuple[float, List[str]]:
        """
        Complete equipment analysis for a horse

        Args:
            horse_name: Horse's name
            today_equipment: Equipment for today
            past_performances: List of past performance data

        Returns:
            (total_score_adjustment, list_of_descriptions)
        """
        # Extract equipment history from PPs
        past_equipment = self.extract_equipment_from_pps(past_performances)

        # Detect changes
        changes = self.detect_changes(today_equipment, past_equipment)

        # Calculate total impact
        total_score = sum(change.score_impact for change in changes)
        descriptions = [change.description for change in changes]

        # If no changes, add current equipment status
        if not changes:
            status_parts = []
            if today_equipment.get('blinkers'):
                status_parts.append('blinkers')
            if today_equipment.get('lasix'):
                status_parts.append('Lasix')

            if status_parts:
                desc = f"Standard equipment: {', '.join(status_parts)}"
            else:
                desc = "No equipment changes"

            descriptions = [desc]

        return total_score, descriptions

    def generate_report(
        self,
        horses: List,
        today_equipment_map: Dict[str, Dict[str, bool]]
    ) -> str:
        """
        Generate equipment analysis report for all horses

        Args:
            horses: List of horse objects with past_performances
            today_equipment_map: Dict mapping horse name to today's equipment

        Returns:
            Formatted report string
        """
        report = [
            "\n" + "=" * 70,
            "EQUIPMENT CHANGE ANALYSIS",
            "=" * 70,
            ""
        ]

        significant_changes = []

        for horse in horses:
            horse_name = getattr(horse, 'name', 'Unknown')
            today_equip = today_equipment_map.get(horse_name, {'blinkers': False, 'lasix': False})
            pps = getattr(horse, 'past_performances', [])

            score, descriptions = self.analyze_horse(horse_name, today_equip, pps)

            # Track significant changes
            if score != 0:
                significant_changes.append((horse_name, score, descriptions))

        # Sort by impact (highest first)
        significant_changes.sort(key=lambda x: x[1], reverse=True)

        if significant_changes:
            report.append("SIGNIFICANT EQUIPMENT CHANGES:")
            report.append("-" * 70)
            for name, score, descs in significant_changes:
                report.append(f"\n{name}: {score:+.1f} points")
                for desc in descs:
                    report.append(f"  • {desc}")
        else:
            report.append("No significant equipment changes detected")

        report.append("\n" + "=" * 70)

        return "\n".join(report)


# Quick test
if __name__ == "__main__":
    print("Testing Equipment Analyzer...")
    print("=" * 70)

    analyzer = EquipmentAnalyzer()

    # Test equipment extraction from PP line
    test_line = "21Sep25 2CD sys 6f :22¹» :45¹º 1:10¸¼3g Clm40000 110-101 6 2 2«¬ 1¶ 1¹ 1¸¢ GaffalioneT 121 L 3.25"

    equip = analyzer.extract_equipment_from_pp_line(test_line)
    print(f"\nTest PP line: ...GaffalioneT 121 L 3.25")
    print(f"Extracted equipment: {equip}")
    assert equip['lasix'] == True, "Should detect Lasix"
    assert equip['blinkers'] == False, "Should not detect blinkers"

    # Test blinkers + Lasix
    test_line2 = "20Jul25 4Elp gd 1m :46¶¹1:10º¾ 1:36¿º3g Clm40000-c 79-91 6 4¹ 3¹ 3¸¡ 2¸ 3¹ TorresJA 122 bL 3.83"
    equip2 = analyzer.extract_equipment_from_pp_line(test_line2)
    print(f"\nTest PP line: ...TorresJA 122 bL 3.83")
    print(f"Extracted equipment: {equip2}")
    assert equip2['lasix'] == True, "Should detect Lasix"
    assert equip2['blinkers'] == True, "Should detect blinkers"

    # Test first-time blinkers
    today_equip = {'blinkers': True, 'lasix': False}
    past_equip = [
        {'blinkers': False, 'lasix': False},
        {'blinkers': False, 'lasix': False},
        {'blinkers': False, 'lasix': False}
    ]

    changes = analyzer.detect_changes(today_equip, past_equip)
    print(f"\nTest: First-time blinkers")
    print(f"Changes detected: {len(changes)}")
    for change in changes:
        print(f"  • {change.description} ({change.score_impact:+.1f} points)")

    assert len(changes) == 1, "Should detect one change"
    assert changes[0].is_first_time == True, "Should be first time"
    assert changes[0].score_impact == analyzer.FIRST_TIME_BLINKERS, "Should have high score"

    print("\n✓ All tests passed!")
    print("=" * 70)
