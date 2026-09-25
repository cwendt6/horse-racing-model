import re

# Test line from PDF
test_line = 'Owner: 84.16 Life: 30 8 3 4 $220,446 Dirt: 26 8 3 4 $219,0711'

print('Testing regex patterns for dollar sign matching:')
print('='*80)
print(f'Test line: {test_line}')
print()

# Test different escaping methods
patterns = [
    (r'\$\d+,\d{3}', 'Raw string r\'\\$...\''),
    (r'\\$\d+,\d{3}', 'Raw string r\'\\\\$...\''),
    ('\$\d+,\d{3}', 'Normal string \'\\$...\''),
    ('\\$\d+,\d{3}', 'Normal string \'\\\\$...\''),
]

for pattern, desc in patterns:
    print(f'{desc}:')
    print(f'  Pattern string: {repr(pattern)}')

    matches = re.findall(pattern, test_line)
    if matches:
        print(f'  ✓ Found {len(matches)} matches: {matches}')
    else:
        print(f'  ✗ No matches')
    print()

# Test the full pattern
print('='*80)
print('Testing FULL pattern with program number capture:')
print()

full_pattern = r'\\$\d+,\d{3}(\d{1,2}[A-Z]?)(?:\s+[\d\-/]+)?$'
match = re.search(full_pattern, test_line)
if match:
    print(f'✓ Match: "{match.group(0)}"')
    print(f'  Captured program #: "{match.group(1)}"')
else:
    print('✗ No match')
