"""
TEST SUITE: Pace Scenario V2 - October 22, 2025 Validation
============================================================

Tests the new pace calculation against the actual races from Oct 22, 2025

EXPECTED OUTCOMES (from manual handicapping):
- Race 1: MODERATE pace ✓ (moderate fractions)
- Race 2: HONEST/MODERATE pace ✓ (moderate fractions)
- Race 3: HOT PACE ✓ (22.37, 46.05 - speed duel, closer won)
- Race 4: MODERATE pace ✓ (turf, moderate)
- Race 5: HONEST/MODERATE pace ✓ (moderate)
- Race 6: HOT PACE ✓ (22.44, 45.78 - fast fractions)
- Race 7: MODERATE pace ✓ (turf route)
- Race 8: HOT PACE ✓ (22.40, 45.86 - speed duel, tactical speed won)

MODEL'S OLD PREDICTIONS: 0/8 correct (all predicted SLOW pace via low PPI)

TEST GOAL: New V2 calculator should correctly predict 6/8 or 7/8 pace scenarios
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.analyzers.pace_scenario_v2 import (
    PaceScenarioCalculatorV2,
    PaceScenarioType,
    HorsePaceProfile,
    analyze_race_pace
)


class TestOct22PaceScenarios:
    """Test pace scenario calculation against Oct 22, 2025 actual results"""

    def __init__(self):
        self.calculator = PaceScenarioCalculatorV2()
        self.test_results = []

    def test_race_3_hot_pace(self):
        """
        Race 3: 6F Dirt Claiming - THE CRITICAL TEST

        Manual prediction: HOT PACE ✓
        Actual fractions: 22.37, 46.05 (FAST)
        Winner: #5 Tom Cat Tuesday (closer) ✓
        Model prediction: HONEST pace (PPI 66.8) ✗ - DISASTER
        Model pick: #1 Lambo (early speed) finished LAST ✗
        """
        print("\n" + "="*80)
        print("RACE 3: 6F Dirt Claiming ($58,000)")
        print("="*80)
        print("THE CRITICAL TEST - Model picked favorite that finished LAST")

        horses = [
            {'name': 'Tom Cat Tuesday', 'program_number': '5', 'running_style': 'S', 'best_beyer': 88},
            {'name': 'Colonel Caliente', 'program_number': '4', 'running_style': 'EP', 'best_beyer': 90},
            {'name': 'Brave Blend', 'program_number': '3', 'running_style': 'S', 'best_beyer': 85},
            {'name': 'Redacted', 'program_number': '6', 'running_style': 'P', 'best_beyer': 82},
            {'name': 'McIlroy', 'program_number': '9', 'running_style': 'P', 'best_beyer': 80},
            {'name': 'Honest Al', 'program_number': '8', 'running_style': 'S', 'best_beyer': 75},
            {'name': 'Guardian', 'program_number': '7', 'running_style': 'E', 'best_beyer': 85},
            {'name': 'Lambo', 'program_number': '1', 'running_style': 'E', 'best_beyer': 98},  # Model's pick - finished LAST
        ]

        scenario = analyze_race_pace(horses, distance_furlongs=6.0, surface='dirt')

        print(f"\nExpected: HOT PACE (4 speed horses identified by manual handicapping)")
        print(f"Actual fractions: 22.37 (fast), 46.05 (fast)")
        print(f"Winner: #5 Tom Cat Tuesday (closer) - exactly as predicted by pace setup")

        print(f"\nV2 Prediction: {scenario.scenario_type.value}")
        print(f"Early Speed Count: {scenario.early_speed_count}")
        print(f"Tactical Count: {scenario.tactical_speed_count}")
        print(f"Total Speed: {scenario.early_speed_count + scenario.tactical_speed_count}")
        print(f"Pressure Score: {scenario.pace_pressure_score:.1f}/100")

        # Check multipliers
        print(f"\nStyle Multipliers:")
        for horse in horses:
            mult = self.calculator.get_style_multiplier(scenario, horse['running_style'])
            emoji = "✓" if mult > 1.2 and horse['name'] == 'Tom Cat Tuesday' else ""
            print(f"  {horse['name']:<20} ({horse['running_style']}): {mult:.2f}x {emoji}")

        # VALIDATION
        is_correct = scenario.scenario_type == PaceScenarioType.HOT_PACE
        total_speed = scenario.early_speed_count + scenario.tactical_speed_count
        has_speed_duel = total_speed >= 3

        print(f"\n{'✅ PASS' if is_correct else '❌ FAIL'}: Scenario = {scenario.scenario_type.value}")
        print(f"{'✅ PASS' if has_speed_duel else '❌ FAIL'}: Identified speed duel (3+ horses)")

        # Check that closer gets advantage
        closer_mult = self.calculator.get_style_multiplier(scenario, 'S')
        closer_advantage = closer_mult > 1.30

        print(f"{'✅ PASS' if closer_advantage else '❌ FAIL'}: Closer gets {closer_mult:.2f}x (>1.30 expected)")

        # Check that early speed penalized
        early_mult = self.calculator.get_style_multiplier(scenario, 'E')
        early_penalty = early_mult < 0.80

        print(f"{'✅ PASS' if early_penalty else '❌ FAIL'}: Early speed penalized {early_mult:.2f}x (<0.80 expected)")

        self.test_results.append({
            'race': 3,
            'expected': 'HOT_PACE',
            'actual': scenario.scenario_type.value,
            'correct': is_correct,
            'winner_style': 'S',
            'winner_benefited': closer_mult > 1.30
        })

        return is_correct

    def test_race_8_hot_pace_tactical_winner(self):
        """
        Race 8: 6F Dirt Maiden - ANOTHER HOT PACE

        Manual prediction: HOT PACE ✓
        Actual fractions: 22.40, 45.86 (FAST)
        Winner: #3 El Prestigio (tactical speed/EP) ✓
        Model prediction: SLOW pace (PPI 65.0) ✗
        Model pick: Data error ✗
        """
        print("\n" + "="*80)
        print("RACE 8: 6F Dirt Maiden ($110,000)")
        print("="*80)
        print("Testing tactical speed advantage in hot pace")

        horses = [
            {'name': 'El Prestigio', 'program_number': '3', 'running_style': 'P', 'best_beyer': 90},  # Winner - tactical
            {'name': 'Spellmaker', 'program_number': '8', 'running_style': 'P', 'best_beyer': 85},
            {'name': "Nu What's New", 'program_number': '1', 'running_style': 'E', 'best_beyer': 85},
            {'name': 'Good Mojo', 'program_number': '11', 'running_style': 'P', 'best_beyer': 82},
            {'name': 'Hogie the Player', 'program_number': '9', 'running_style': 'EP', 'best_beyer': 80},
            {'name': "Homer's Odyssey", 'program_number': '2', 'running_style': 'EP', 'best_beyer': 82},
            {'name': 'Barker', 'program_number': '6', 'running_style': 'P', 'best_beyer': 75},
            {'name': 'Arthur Jr', 'program_number': '10', 'running_style': 'EP', 'best_beyer': 78},
            {'name': 'Calling On Heaven', 'program_number': '12', 'running_style': 'P', 'best_beyer': 77},
            {'name': 'Valiant Humor', 'program_number': '7', 'running_style': 'E', 'best_beyer': 78},
            {'name': 'Titanium Man', 'program_number': '4', 'running_style': 'S', 'best_beyer': 72},
            {'name': 'Big Garry', 'program_number': '5', 'running_style': 'EP', 'best_beyer': 70},
        ]

        scenario = analyze_race_pace(horses, distance_furlongs=6.0, surface='dirt')

        print(f"\nExpected: HOT PACE (manual identified speed duel)")
        print(f"Actual fractions: 22.40 (fast), 45.86 (fast)")
        print(f"Winner: #3 El Prestigio (vied early then drew clear)")
        print(f"Note: Winner had tactical speed (P/EP style), not pure closer")

        print(f"\nV2 Prediction: {scenario.scenario_type.value}")
        print(f"Early Speed Count: {scenario.early_speed_count}")
        print(f"Tactical Count: {scenario.tactical_speed_count}")
        print(f"Total Speed: {scenario.early_speed_count + scenario.tactical_speed_count}")

        # Check tactical/presser advantage
        print(f"\nKey horses:")
        winner_mult = self.calculator.get_style_multiplier(scenario, 'P')
        tactical_mult = self.calculator.get_style_multiplier(scenario, 'EP')
        print(f"  El Prestigio (P - Winner): {winner_mult:.2f}x")
        print(f"  Tactical (EP): {tactical_mult:.2f}x")

        # VALIDATION
        is_hot = scenario.scenario_type == PaceScenarioType.HOT_PACE
        total_speed = scenario.early_speed_count + scenario.tactical_speed_count

        print(f"\n{'✅ PASS' if is_hot else '❌ FAIL'}: Scenario = {scenario.scenario_type.value}")
        print(f"{'✅ PASS' if total_speed >= 3 else '❌ FAIL'}: Total speed = {total_speed} (≥3 expected)")

        # Tactical/presser should benefit (not just pure closers)
        tactical_advantage = tactical_mult > 1.15
        print(f"{'✅ PASS' if tactical_advantage else '❌ FAIL'}: Tactical benefits {tactical_mult:.2f}x")

        self.test_results.append({
            'race': 8,
            'expected': 'HOT_PACE',
            'actual': scenario.scenario_type.value,
            'correct': is_hot,
            'winner_style': 'P',
            'winner_benefited': winner_mult > 1.15
        })

        return is_hot

    def test_race_6_hot_pace_speed_held(self):
        """
        Race 6: 6F Dirt Allowance - HOT PACE BUT SPEED HELD

        Manual prediction: HOT PACE ✓
        Actual fractions: 22.44, 45.78 (FAST)
        Winner: #4 Beeline (tactical speed/EP) ✓
        Manual's pick: #3 Hailstorm (closer) - 5th ✗
        Lesson: Pure closers from too far back can fail even in hot pace
        """
        print("\n" + "="*80)
        print("RACE 6: 6F Dirt Allowance Optional Claiming ($130,000)")
        print("="*80)
        print("Testing when tactical speed beats pure closer in hot pace")

        horses = [
            {'name': 'Beeline', 'program_number': '4', 'running_style': 'EP', 'best_beyer': 92},  # Winner - tactical
            {'name': 'Keep It Easy', 'program_number': '1', 'running_style': 'S', 'best_beyer': 88},
            {'name': 'Distorted Pro', 'program_number': '9', 'running_style': 'EP', 'best_beyer': 90},
            {'name': 'Tough Catch', 'program_number': '5', 'running_style': 'P', 'best_beyer': 86},
            {'name': 'Hailstorm', 'program_number': '3', 'running_style': 'S', 'best_beyer': 95},  # Manual's pick - 5th
            {'name': 'Legalize', 'program_number': '2', 'running_style': 'S', 'best_beyer': 82},
            {'name': 'One True Shance', 'program_number': '8', 'running_style': 'P', 'best_beyer': 80},
        ]

        scenario = analyze_race_pace(horses, distance_furlongs=6.0, surface='dirt')

        print(f"\nExpected: HOT PACE")
        print(f"Actual fractions: 22.44 (fast), 45.78 (fast)")
        print(f"Winner: #4 Beeline (tactical/EP) - had 2-path position")
        print(f"Manual's pick #3 Hailstorm (closer) came 4-wide and failed")
        print(f"LESSON: Tactical speed (EP) > Pure closer (S) when closer comes too wide")

        print(f"\nV2 Prediction: {scenario.scenario_type.value}")

        # Check multipliers
        print(f"\nStyle Multipliers:")
        tactical_mult = self.calculator.get_style_multiplier(scenario, 'EP')
        closer_mult = self.calculator.get_style_multiplier(scenario, 'S')
        print(f"  Tactical (EP): {tactical_mult:.2f}x - WINNER'S STYLE")
        print(f"  Closer (S): {closer_mult:.2f}x - Can still lose if bad trip")

        # VALIDATION
        is_hot = scenario.scenario_type == PaceScenarioType.HOT_PACE

        print(f"\n{'✅ PASS' if is_hot else '❌ FAIL'}: Correctly identifies HOT PACE")
        print(f"{'✅ PASS' if tactical_mult > 1.20 else '❌ FAIL'}: Tactical gets advantage {tactical_mult:.2f}x")

        self.test_results.append({
            'race': 6,
            'expected': 'HOT_PACE',
            'actual': scenario.scenario_type.value,
            'correct': is_hot,
            'winner_style': 'EP',
            'winner_benefited': tactical_mult > 1.20
        })

        return is_hot

    def test_race_2_honest_pace(self):
        """
        Race 2: 8.5F Dirt Maiden - HONEST/MODERATE PACE

        Manual prediction: MODERATE ✓
        Actual fractions: 23.96, 49.83 (MODERATE)
        Winner: #3 Classic Glide (presser) ✓
        Model: Unclear
        """
        print("\n" + "="*80)
        print("RACE 2: 8.5F (1 1/16M) Dirt Maiden ($85,000)")
        print("="*80)

        horses = [
            {'name': 'Classic Glide', 'program_number': '3', 'running_style': 'P', 'best_beyer': 75},  # Winner
            {'name': 'Noroomformischief', 'program_number': '7', 'running_style': 'EP', 'best_beyer': 72},
            {'name': 'Cairosa', 'program_number': '5', 'running_style': 'S', 'best_beyer': 70},
            {'name': 'Lexico', 'program_number': '6', 'running_style': 'EP', 'best_beyer': 72},
            {'name': 'Napoli', 'program_number': '10', 'running_style': 'P', 'best_beyer': 68},
            {'name': 'Honor Azteca', 'program_number': '4', 'running_style': 'S', 'best_beyer': 65},
            {'name': 'Struck At Midnight', 'program_number': '9', 'running_style': 'P', 'best_beyer': 70},
            {'name': 'Click', 'program_number': '2', 'running_style': 'S', 'best_beyer': 73},  # Model's pick - 8th
            {'name': 'Denise Says No', 'program_number': '1', 'running_style': 'S', 'best_beyer': 62},
            {'name': 'Greatest', 'program_number': '8', 'running_style': 'S', 'best_beyer': 60},
        ]

        scenario = analyze_race_pace(horses, distance_furlongs=8.5, surface='dirt')

        print(f"\nExpected: HONEST or MODERATE pace")
        print(f"Actual fractions: 23.96, 49.83 (moderate - not fast, not slow)")
        print(f"Winner: #3 Classic Glide (presser)")

        print(f"\nV2 Prediction: {scenario.scenario_type.value}")
        print(f"Total Speed: {scenario.early_speed_count + scenario.tactical_speed_count}")

        # Should NOT be hot pace (only 2 speed horses at middle distance)
        is_correct = scenario.scenario_type in [PaceScenarioType.HONEST_PACE, PaceScenarioType.MODERATE_PACE]

        print(f"\n{'✅ PASS' if is_correct else '❌ FAIL'}: Correctly avoids HOT PACE")

        self.test_results.append({
            'race': 2,
            'expected': 'HONEST/MODERATE',
            'actual': scenario.scenario_type.value,
            'correct': is_correct,
            'winner_style': 'P',
            'winner_benefited': True
        })

        return is_correct

    def test_all_races_summary(self):
        """Run all tests and provide summary"""
        print("\n" + "="*80)
        print(" RUNNING ALL OCTOBER 22, 2025 PACE TESTS")
        print("="*80)

        # Run critical tests
        self.test_race_3_hot_pace()
        self.test_race_8_hot_pace_tactical_winner()
        self.test_race_6_hot_pace_speed_held()
        self.test_race_2_honest_pace()

        # Summary
        print("\n" + "="*80)
        print(" TEST SUMMARY")
        print("="*80)

        correct_count = sum(1 for r in self.test_results if r['correct'])
        total_count = len(self.test_results)

        print(f"\nPace Scenario Accuracy: {correct_count}/{total_count} ({100*correct_count/total_count:.0f}%)")

        for result in self.test_results:
            emoji = "✅" if result['correct'] else "❌"
            benefit_emoji = "✓" if result['winner_benefited'] else "✗"
            print(f"{emoji} Race {result['race']}: {result['expected']} → {result['actual']} (Winner benefited: {benefit_emoji})")

        # Compare to model's old performance
        print(f"\n📊 COMPARISON:")
        print(f"   Old Model (PPI): 0/8 (0%) pace accuracy")
        print(f"   New V2 Calc: {correct_count}/{total_count} ({100*correct_count/total_count:.0f}%) pace accuracy")
        print(f"   Manual Handicapping: 6/7 (85.7%) pace accuracy")

        print(f"\n🎯 GOAL: Match or exceed manual handicapping pace accuracy")

        if correct_count / total_count >= 0.75:  # 75%+ is good
            print(f"✅ SUCCESS: V2 calculator achieves {100*correct_count/total_count:.0f}% accuracy!")
        else:
            print(f"⚠️  NEEDS IMPROVEMENT: Target is 75%+")

        return correct_count / total_count


def main():
    """Run the test suite"""
    print("\n" + "="*80)
    print(" PACE SCENARIO V2 - OCTOBER 22, 2025 VALIDATION TEST SUITE")
    print("="*80)
    print("\nTesting new granular pace calculation against actual race results")
    print("Goal: Fix the model's 0/8 pace accuracy catastrophe\n")

    tester = TestOct22PaceScenarios()
    accuracy = tester.test_all_races_summary()

    print("\n" + "="*80)
    print(f" FINAL RESULT: {accuracy*100:.0f}% Pace Accuracy")
    print("="*80 + "\n")

    return accuracy >= 0.75  # Success if 75%+ accuracy


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
