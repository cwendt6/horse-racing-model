#!/usr/bin/env python3
"""
Compare FIXED model predictions (with maiden weights + combos) vs actual results
"""

# Actual winners from October 23, 2025 (from OCT23_RESULTS_ANALYSIS.txt)
ACTUAL_WINNERS = {
    1: "Sprint Out Pass (#7)",
    2: "Time for Music (#1)",  # Steven Asmussen - Maiden 2YO
    3: "Twirling Queen (#3)",
    4: "Sweetalkingbourbon (#6)",
    5: "Amberglen (#9)",  # Brad Cox + Irad Ortiz Jr. - Maiden 2YO Fillies
    6: "Nuanced (#4)",  # Chad Brown + Tyler Gaffalione - Maiden Claiming (won by 12.5 lengths!)
    7: "Fulleffort (#7)",  # Brad Cox + Irad Ortiz Jr. - Allowance 2YO
    8: "Sam's Treasure (#4)",  # Paulo Lobo + Irad Ortiz Jr. - Allowance Optional Claiming
    9: "Triumphant Spirit (#1)"  # Brendan Walsh + Tyler Gaffalione - Maiden
}

# New model predictions (with maiden weights + elite combo bonuses)
# Extracted from oct23_predictions_FINAL_TEST.txt
NEW_MODEL_PICKS = {
    1: "Sprint Out Pass (#7)",
    2: "Maximum Offer (#5)",
    3: "Youalmosthadme (#4)",
    4: "Remi's Moon (#2)",
    5: "Love and Grace (#10)",
    6: "Bon Temps (#7)",
    7: "Expressway (#9)",
    8: "Sam's Treasure (#4)",
    9: "Lady Pippa (#10)"
}

# Original model predictions (before fixes)
# From OCT23_RESULTS_ANALYSIS.txt
OLD_MODEL_PICKS = {
    1: "Sprint Out Pass (#7)",
    2: "Like Water (#2)",  # Maiden - WRONG
    3: "Youalmosthadme (#4)",
    4: "Remi's Moon (#2)",
    5: "Temple Goddess (#7)",  # Maiden - WRONG
    6: "Bon Temps (#7)",  # Maiden Claiming - WRONG
    7: "Expressway (#9)",  # Allowance 2YO - WRONG
    8: "Tanya Showers (#2)",  # WRONG
    9: "Pretty Tapit (#9)"  # Maiden - WRONG
}

# Manual handicapping picks
# From OCT23_RESULTS_ANALYSIS.txt
MANUAL_PICKS = {
    1: "Farm Team (#2)",  # SCRATCHED
    2: "Maximum Effort (#5)",  # Steven Asmussen - Finished 2nd
    3: "Twirling Queen (#3)",  # CORRECT
    4: "Utopian (#4)",  # WRONG (finished 4th)
    5: "Amberglen (#9)",  # Brad Cox FTS - CORRECT
    6: "Nuanced (#4)",  # Chad Brown 76.92% FTS - CORRECT (won by 12.5 lengths!)
    7: "Fulleffort (#7)",  # Cox/Ortiz Jr. elite combo - CORRECT
    8: "Sam's Treasure (#4)",  # Lobo 100% FTS - CORRECT
    9: "Rethink (#6)"  # Chad Brown/Ortiz Jr. - WRONG (finished 7th)
}

print("=" * 80)
print(" FIXED MODEL vs ACTUAL RESULTS - October 23, 2025")
print("=" * 80)
print()

new_model_wins = 0
old_model_wins = 0
manual_wins = 0

for race_num in range(1, 10):
    actual = ACTUAL_WINNERS[race_num]
    new_pick = NEW_MODEL_PICKS[race_num]
    old_pick = OLD_MODEL_PICKS[race_num]
    manual = MANUAL_PICKS[race_num]

    new_correct = (new_pick == actual)
    old_correct = (old_pick == actual)
    manual_correct = (manual == actual)

    if new_correct:
        new_model_wins += 1
    if old_correct:
        old_model_wins += 1
    if manual_correct:
        manual_wins += 1

    print(f"Race {race_num}:")
    print(f"  ACTUAL WINNER:  {actual}")
    print(f"  New Model Pick: {new_pick}  {'✅ CORRECT' if new_correct else '❌ WRONG'}")
    print(f"  Old Model Pick: {old_pick}  {'✅ CORRECT' if old_correct else '❌ WRONG'}")
    print(f"  Manual Pick:    {manual}  {'✅ CORRECT' if manual_correct else '❌ CORRECT'}")

    # Show what changed
    if new_pick != old_pick:
        print(f"  🔄 MODEL CHANGED: {old_pick} → {new_pick}")

    print()

print("=" * 80)
print(" FINAL COMPARISON")
print("=" * 80)
print()
print(f"NEW MODEL (with fixes):  {new_model_wins}/9 winners ({new_model_wins/9*100:.1f}%)")
print(f"OLD MODEL (pre-fixes):   {old_model_wins}/9 winners ({old_model_wins/9*100:.1f}%)")
print(f"MANUAL HANDICAPPING:     {manual_wins}/9 winners ({manual_wins/9*100:.1f}%)")
print()

improvement = new_model_wins - old_model_wins
if improvement > 0:
    print(f"✅ IMPROVEMENT: +{improvement} winners ({improvement/9*100:.1f}% improvement)")
elif improvement < 0:
    print(f"❌ REGRESSION: {improvement} winners ({improvement/9*100:.1f}% worse)")
else:
    print(f"⚠️  NO CHANGE: Same number of winners")

print()
print("=" * 80)
print(" KEY INSIGHTS")
print("=" * 80)
print()

# Check maiden races specifically (from OCT23_RESULTS_ANALYSIS.txt)
# Race 2: Maiden 2YO
# Race 5: Maiden 2YO Fillies
# Race 6: Maiden Claiming
# Race 9: Maiden
maiden_races = [2, 5, 6, 9]
print("MAIDEN RACE PERFORMANCE:")
new_maiden_wins = sum(1 for r in maiden_races if NEW_MODEL_PICKS[r] == ACTUAL_WINNERS[r])
old_maiden_wins = sum(1 for r in maiden_races if OLD_MODEL_PICKS[r] == ACTUAL_WINNERS[r])
manual_maiden_wins = sum(1 for r in maiden_races if MANUAL_PICKS[r] == ACTUAL_WINNERS[r])

print(f"  New Model:  {new_maiden_wins}/4 maiden winners ({new_maiden_wins/4*100:.0f}%)")
print(f"  Old Model:  {old_maiden_wins}/4 maiden winners ({old_maiden_wins/4*100:.0f}%)")
print(f"  Manual:     {manual_maiden_wins}/4 maiden winners ({manual_maiden_wins/4*100:.0f}%)")
print()

# Detail maiden race results
print("Maiden Race Details:")
for r in maiden_races:
    actual = ACTUAL_WINNERS[r]
    new_pick = NEW_MODEL_PICKS[r]
    new_correct = "✅" if new_pick == actual else "❌"
    print(f"  Race {r}: Winner {actual}, Model picked {new_pick} {new_correct}")
print()

if new_maiden_wins > old_maiden_wins:
    print(f"✅ MAIDEN FIX WORKED: +{new_maiden_wins - old_maiden_wins} maiden winners!")
elif new_maiden_wins == manual_maiden_wins:
    print(f"🎯 MATCHED MANUAL: Maiden race performance now matches manual handicapping!")
else:
    print(f"⚠️  MAIDEN FIX DID NOT IMPROVE MAIDEN PERFORMANCE")
    print(f"   Problem: Still 0/4 maiden races despite increased trainer weights")

print()
print("=" * 80)
