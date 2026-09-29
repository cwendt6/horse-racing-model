"""
Test script for jockey-trainer analyzer
"""

import pytest

from src.analyzers.jockey_trainer_analyzer import JockeyTrainerAnalyzer, seed_initial_data


@pytest.fixture(autouse=True)
def seeded_stats(tmp_path, monkeypatch):
    """Run each test in a temp dir with seeded combos, so nothing touches data/."""
    monkeypatch.chdir(tmp_path)
    seed_initial_data()


def test_basic_functionality():
    """Test basic analyzer functionality"""
    print("\n" + "="*70)
    print("TEST 1: Basic Functionality")
    print("="*70)

    analyzer = JockeyTrainerAnalyzer()

    # Test known combo
    bonus, desc, details = analyzer.analyze_combination(
        "Irad Ortiz Jr",
        "Brad Cox",
        jockey_rate=0.24,
        trainer_rate=0.26
    )

    print(f"\nResult: {desc}")
    print(f"Bonus: {bonus:+.1f}")
    print(f"Details: {details}")

    assert bonus != 0, "Should have non-zero bonus for seeded combo"
    print("\n✓ Test passed!")


def test_top_combinations():
    """Test getting top combinations"""
    print("\n" + "="*70)
    print("TEST 2: Top Combinations")
    print("="*70)

    analyzer = JockeyTrainerAnalyzer()
    top = analyzer.get_top_combinations(min_starts=20, limit=10)

    print(f"\nTop {len(top)} Jockey-Trainer Combinations:\n")

    for i, stat in enumerate(top, 1):
        diff = stat.performance_differential()
        print(f"{i:2d}. {stat.jockey_name} + {stat.trainer_name}")
        print(f"    {stat.starts} starts | {stat.win_rate:.1%} win rate")
        print(f"    Differential: {diff:+.1%}")
        print()

    print("✓ Test passed!")


def test_cold_combo():
    """Test cold combo detection"""
    print("\n" + "="*70)
    print("TEST 3: Cold Combo Detection")
    print("="*70)

    analyzer = JockeyTrainerAnalyzer()

    # Create a poor performing combo
    stat = analyzer.get_or_create_stat("Test Jockey", "Test Trainer", 0.22, 0.24)
    stat.starts = 30
    stat.wins = 3  # 10% win rate (vs expected 23% average)
    stat.win_rate = stat.wins / stat.starts

    analyzer._save_stats()

    bonus, desc, details = analyzer.analyze_combination(
        "Test Jockey",
        "Test Trainer",
        jockey_rate=0.22,
        trainer_rate=0.24
    )

    print(f"\nResult: {desc}")
    print(f"Bonus: {bonus:+.1f} (should be negative)")
    print(f"Details: {details}")

    assert bonus < 0, "Cold combo should have negative bonus"
    print("\n✓ Test passed!")


if __name__ == "__main__":
    # Seed data first time
    print("\n" + "="*70)
    print("SEEDING INITIAL DATA")
    print("="*70)
    seed_initial_data()

    # Run tests
    test_basic_functionality()
    test_top_combinations()
    test_cold_combo()

    print("\n" + "🎉"*20)
    print("ALL TESTS PASSED! Jockey-Trainer Analyzer is ready.")
    print("🎉"*20 + "\n")
