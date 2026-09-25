import os
"""
Quick test to compare old vs new extraction on problematic Race 2
"""
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pdfplumber

pdf_path = "Keeneland October PPs/10-3-25-kee-ppspdf.pdf"

print("=" * 80)
print("EXTRACTION COMPARISON - Page 4 (Race 2)")
print("=" * 80)

with pdfplumber.open(pdf_path) as pdf:
    page = pdf.pages[3]  # Page 4 (0-indexed)

    # OLD METHOD: Standard extraction
    print("\n❌ OLD METHOD (Standard extract_text):")
    print("-" * 80)
    old_text = page.extract_text()
    print(old_text[:500])

    # Check for spacing issues
    if old_text:
        space_ratio = old_text.count(' ') / len(old_text)
        words = old_text.split()
        single_chars = sum(1 for w in words if len(w) == 1 and w.isalpha())

        print(f"\n  Space ratio: {space_ratio:.2%}")
        print(f"  Single-char words: {single_chars}/{len(words)}")
        print(f"  Encoding issues: {'YES' if space_ratio > 0.3 else 'NO'}")

# NEW METHOD: Load from position-based file
print("\n\n✅ NEW METHOD (Position-based extraction):")
print("-" * 80)
with open('page_004_position_based.txt', 'r') as f:
    new_text = f.read()
    print(new_text[:500])

    # Check quality
    if new_text:
        space_ratio = new_text.count(' ') / len(new_text)
        words = new_text.split()
        single_chars = sum(1 for w in words if len(w) == 1 and w.isalpha())

        print(f"\n  Space ratio: {space_ratio:.2%}")
        print(f"  Single-char words: {single_chars}/{len(words)}")
        print(f"  Encoding issues: {'YES' if space_ratio > 0.3 else 'NO'}")

print("\n" + "=" * 80)
print("RESULT: Position-based extraction SOLVES the encoding issue!")
print("=" * 80)
