#!/usr/bin/env python3
"""
Debug Race 6 scoring to understand why Chad Brown's winner ranked #4
"""

print("=" * 80)
print(" RACE 6 SCORING ANALYSIS - WHY DID CHAD BROWN'S HORSE LOSE?")
print("=" * 80)
print()

# Data extracted from oct23_predictions_FINAL_TEST.txt
horses = {
    "Bon Temps": {
        "rank": 1,
        "win_prob": 26.8,
        "trainer": "Eoin G Harty",
        "jockey": "Amanda K. Poston",
        "speed": 100.0,
        "form": 29.3,
        "class": 55.8,
        "pace": 58.8,
        "recency": 100.0,
        "progression": 100.0,
        "jockey_score": 24.0,
        "trainer_score": 20.5,
        "post": 64.2,
        "trainer_level": "Above Average (15%)",
        "jockey_level": "Above Average (15%)"
    },
    "Nuanced": {
        "rank": 4,
        "win_prob": 6.5,
        "trainer": "Chad C. Brown (76.92% FTS!)",
        "jockey": "Tyler Gaffalione",
        "speed": 65.0,
        "form": 0.0,  # ZERO! First-time starter or debut
        "class": 15.8,
        "pace": 60.0,
        "recency": 92.9,
        "progression": 50.0,
        "jockey_score": 36.3,
        "trainer_score": 38.0,
        "post": 75.0,
        "trainer_level": "ELITE (25%)",
        "jockey_level": "ELITE (22%)"
    }
}

print("ACTUAL RESULT: #4 Nuanced (Chad Brown) won by 12.5 LENGTHS!")
print("MODEL PREDICTION: #7 Bon Temps (26.8% prob) over #4 Nuanced (6.5% prob)")
print()

print("=" * 80)
print(" SCORE COMPARISON")
print("=" * 80)
print()

# Compare scores
categories = ["speed", "form", "class", "pace", "recency", "progression",
              "jockey_score", "trainer_score", "post"]

print(f"{'Category':<15} {'Bon Temps':<12} {'Nuanced':<12} {'Advantage':<20}")
print("-" * 80)

for cat in categories:
    bon = horses["Bon Temps"][cat]
    nuanced = horses["Nuanced"][cat]
    diff = nuanced - bon

    if diff > 0:
        advantage = f"Nuanced +{diff:.1f}"
    elif diff < 0:
        advantage = f"Bon Temps +{abs(diff):.1f}"
    else:
        advantage = "Tied"

    print(f"{cat:<15} {bon:<12.1f} {nuanced:<12.1f} {advantage:<20}")

print()
print("=" * 80)
print(" KEY FINDINGS")
print("=" * 80)
print()

print("🔍 NUANCED'S ADVANTAGES:")
print(f"   ✅ Trainer Score: 38.0 vs 20.5 (+{38.0-20.5:.1f}) - NEARLY DOUBLE!")
print(f"   ✅ Jockey Score: 36.3 vs 24.0 (+{36.3-24.0:.1f})")
print(f"   ✅ ELITE TRAINER: Chad Brown (76.92% FTS)")
print(f"   ✅ ELITE JOCKEY: Tyler Gaffalione (22% win rate)")
print()

print("❌ NUANCED'S DISADVANTAGES:")
print(f"   ❌ Speed: 65.0 vs 100.0 (-35.0)")
print(f"   ❌ Form: 0.0 vs 29.3 (-29.3) - ZERO FORM!")
print(f"   ❌ Class: 15.8 vs 55.8 (-40.0)")
print(f"   ❌ Recency: 92.9 vs 100.0 (-7.1)")
print(f"   ❌ Progression: 50.0 vs 100.0 (-50.0)")
print()

print("=" * 80)
print(" MAIDEN CLAIMING WEIGHTS (from maiden_weights.py)")
print("=" * 80)
print()

# Maiden claiming weights
weights = {
    "speed": 0.12,
    "form": 0.06,
    "class": 0.05,
    "pace": 0.10,
    "jockey": 0.12,
    "trainer": 0.42,  # HIGHEST!
    "recency": 0.02,
    "progression": 0.05,
    "post": 0.06
}

print("Weight Distribution:")
for factor, weight in weights.items():
    print(f"  {factor:<15} {weight:.2%}")
print()

print("=" * 80)
print(" WEIGHTED SCORE CALCULATION")
print("=" * 80)
print()

# Calculate weighted scores
bon_weighted = (
    horses["Bon Temps"]["speed"] * weights["speed"] +
    horses["Bon Temps"]["form"] * weights["form"] +
    horses["Bon Temps"]["class"] * weights["class"] +
    horses["Bon Temps"]["pace"] * weights["pace"] +
    horses["Bon Temps"]["jockey_score"] * weights["jockey"] +
    horses["Bon Temps"]["trainer_score"] * weights["trainer"] +
    horses["Bon Temps"]["recency"] * weights["recency"] +
    horses["Bon Temps"]["progression"] * weights["progression"] +
    horses["Bon Temps"]["post"] * weights["post"]
)

nuanced_weighted = (
    horses["Nuanced"]["speed"] * weights["speed"] +
    horses["Nuanced"]["form"] * weights["form"] +
    horses["Nuanced"]["class"] * weights["class"] +
    horses["Nuanced"]["pace"] * weights["pace"] +
    horses["Nuanced"]["jockey_score"] * weights["jockey"] +
    horses["Nuanced"]["trainer_score"] * weights["trainer"] +
    horses["Nuanced"]["recency"] * weights["recency"] +
    horses["Nuanced"]["progression"] * weights["progression"] +
    horses["Nuanced"]["post"] * weights["post"]
)

print(f"Bon Temps Weighted Score:  {bon_weighted:.2f}")
print(f"Nuanced Weighted Score:    {nuanced_weighted:.2f}")
print(f"Difference:                {bon_weighted - nuanced_weighted:+.2f} (Bon Temps ahead)")
print()

print("Breakdown:")
print(f"{'Factor':<15} {'Bon Temps':<20} {'Nuanced':<20}")
print("-" * 55)

factors_calc = [
    ("Speed", horses["Bon Temps"]["speed"] * weights["speed"],
     horses["Nuanced"]["speed"] * weights["speed"]),
    ("Form", horses["Bon Temps"]["form"] * weights["form"],
     horses["Nuanced"]["form"] * weights["form"]),
    ("Class", horses["Bon Temps"]["class"] * weights["class"],
     horses["Nuanced"]["class"] * weights["class"]),
    ("Pace", horses["Bon Temps"]["pace"] * weights["pace"],
     horses["Nuanced"]["pace"] * weights["pace"]),
    ("Jockey", horses["Bon Temps"]["jockey_score"] * weights["jockey"],
     horses["Nuanced"]["jockey_score"] * weights["jockey"]),
    ("Trainer", horses["Bon Temps"]["trainer_score"] * weights["trainer"],
     horses["Nuanced"]["trainer_score"] * weights["trainer"]),
    ("Recency", horses["Bon Temps"]["recency"] * weights["recency"],
     horses["Nuanced"]["recency"] * weights["recency"]),
    ("Progression", horses["Bon Temps"]["progression"] * weights["progression"],
     horses["Nuanced"]["progression"] * weights["progression"]),
    ("Post", horses["Bon Temps"]["post"] * weights["post"],
     horses["Nuanced"]["post"] * weights["post"]),
]

for factor, bon_val, nuanced_val in factors_calc:
    print(f"{factor:<15} {bon_val:>8.2f} ({bon_val/bon_weighted*100:>5.1f}%)  "
          f"{nuanced_val:>8.2f} ({nuanced_val/nuanced_weighted*100:>5.1f}%)")

print()
print("=" * 80)
print(" ROOT CAUSE ANALYSIS")
print("=" * 80)
print()

print("🎯 THE PROBLEM:")
print()
print("Even with 42% trainer weight in maiden claiming races, Nuanced's")
print("trainer advantage (38.0 vs 20.5 = +17.5 points) only contributes:")
print(f"  Trainer contribution: {17.5 * weights['trainer']:.2f} points")
print()
print("But Bon Temps has massive advantages in other areas:")
print(f"  Speed advantage: {(100.0-65.0) * weights['speed']:.2f} points (35 point gap)")
print(f"  Form advantage: {(29.3-0.0) * weights['form']:.2f} points (ZERO form!)")
print(f"  Class advantage: {(55.8-15.8) * weights['class']:.2f} points (40 point gap)")
print(f"  Progression advantage: {(100.0-50.0) * weights['progression']:.2f} points")
print()
print("The trainer advantage of +7.35 points is NOT ENOUGH to overcome")
print(f"the combined disadvantage of -{(100.0-65.0)*weights['speed'] + (29.3-0.0)*weights['form'] + (55.8-15.8)*weights['class']:.2f} points")
print()

print("=" * 80)
print(" THE SOLUTION")
print("=" * 80)
print()

print("For maiden races with ELITE FTS trainers (60%+ FTS), horses with")
print("ZERO or low form/speed scores should NOT be penalized.")
print()
print("Instead, assign them a DEFAULT score based on trainer quality:")
print()
print("  If Form = 0 AND trainer FTS >= 70%:")
print("    Form = 75.0  (assume elite FTS trainer brings ready horse)")
print()
print("  If Form = 0 AND trainer FTS >= 60%:")
print("    Form = 65.0")
print()
print("  If Form = 0 AND trainer FTS >= 50%:")
print("    Form = 55.0")
print()
print("Same logic for Speed scores < 70 in maiden races with elite FTS trainers.")
print()

print("=" * 80)
print(" RECALCULATION WITH FIX")
print("=" * 80)
print()

# Adjust Nuanced's scores with the fix
nuanced_adjusted = horses["Nuanced"].copy()

# Chad Brown has 76.92% FTS
if nuanced_adjusted["form"] == 0.0:
    nuanced_adjusted["form"] = 75.0  # Elite FTS proxy
    print("✓ Adjusted Form: 0.0 → 75.0 (Elite FTS proxy)")

if nuanced_adjusted["speed"] < 70:
    nuanced_adjusted["speed"] = 75.0  # Elite FTS proxy
    print("✓ Adjusted Speed: 65.0 → 75.0 (Elite FTS proxy)")

print()

nuanced_adjusted_weighted = (
    nuanced_adjusted["speed"] * weights["speed"] +
    nuanced_adjusted["form"] * weights["form"] +
    nuanced_adjusted["class"] * weights["class"] +
    nuanced_adjusted["pace"] * weights["pace"] +
    nuanced_adjusted["jockey_score"] * weights["jockey"] +
    nuanced_adjusted["trainer_score"] * weights["trainer"] +
    nuanced_adjusted["recency"] * weights["recency"] +
    nuanced_adjusted["progression"] * weights["progression"] +
    nuanced_adjusted["post"] * weights["post"]
)

print(f"Bon Temps Weighted Score:      {bon_weighted:.2f}")
print(f"Nuanced Adjusted Score:        {nuanced_adjusted_weighted:.2f}")
print(f"Difference:                    {nuanced_adjusted_weighted - bon_weighted:+.2f}")
print()

if nuanced_adjusted_weighted > bon_weighted:
    print("✅ WITH FIX: Nuanced would have been ranked HIGHER!")
else:
    print("⚠️  WITH FIX: Still not enough - need more aggressive adjustment")

print()
print("=" * 80)
