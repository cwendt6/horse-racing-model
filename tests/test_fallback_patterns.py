import re

# Test line from PDF
test_line = 'ShanyfeltStables,Inc.(DouglasE.Shanyfelt)Owner: 84.16 Life: 30 8 3 4 $220,446 Dirt: 26 8 3 4 $219,0711'

print('Testing fallback patterns:')
print('='*80)
print(f'Test line: ...{test_line[-70:]}')
print()

# Pattern 1: Main pattern (currently has wrong escaping)
pattern1 = r'\\$\d+,\d{3}(\d{1,2}[A-Z]?)(?:\s+[\d\-/]+)?$'
match1 = re.search(pattern1, test_line)
print(f'Pattern 1 (main, WRONG escaping): r\'\\\\$...\'')
if match1:
    print(f'  ✓ Match: "{match1.group(0)}"')
    print(f'    Captured: "{match1.group(1)}"')
else:
    print(f'  ✗ No match (expected, since escaping is wrong)')
print()

# Pattern 2: First fallback
pattern2 = r'(\d{1,2}[A-Z]?)\s+[\d\-/]+$'
match2 = re.search(pattern2, test_line)
print(f'Pattern 2 (fallback 1): r\'(\\d{{1,2}}[A-Z]?)\\s+[\\d\\-/]+$\'')
if match2:
    print(f'  ✓ Match: "{match2.group(0)}"')
    print(f'    Captured: "{match2.group(1)}"')
else:
    print(f'  ✗ No match')
print()

# Pattern 3: Second fallback
pattern3 = r'[^\d](\d{1,2}[A-Z]?)$'
match3 = re.search(pattern3, test_line)
print(f'Pattern 3 (fallback 2): r\'[^\\d](\\d{{1,2}}[A-Z]?)$\'')
if match3:
    print(f'  ✓ Match: "{match3.group(0)}"')
    print(f'    Captured: "{match3.group(1)}"')
else:
    print(f'  ✗ No match')
print()

print('='*80)
print('So with WRONG main pattern, it falls to Pattern 3 which captures:')
print(f'  The last 1-2 digits at end of line = "{match3.group(1) if match3 else "N/A"}"')
print()
print('The line ends with "$219,0711" so Pattern 3 matches "711" and captures "11"')
print('But we want "1" not "11"!')
