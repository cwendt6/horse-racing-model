import os
#!/usr/bin/env python3
"""Test script to verify basic execution"""

import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

print("Script starting...")
print("="*80)
print("TEST")
print("="*80)

from src.data_loaders.statistics_loader import StatisticsLoader

print("\nLoading statistics...")
stats_loader = StatisticsLoader(
    jockey_file='data/stats/jockey_statistics_comprehensive.json',
    trainer_file='data/stats/trainer_statistics_comprehensive.json'
)
print("✓ Statistics loaded")

print("\nScript complete!")
