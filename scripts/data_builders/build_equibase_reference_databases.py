#!/usr/bin/env python3
"""
Build Comprehensive Reference Databases from Equibase Data

Parses the Equibase directory file to create comprehensive reference databases for:
1. Trainers (current meet + all-time top 100)
2. Jockeys (current meet + all-time top 200)
3. Horses (current meet + all-time top 200)
4. Owners (current meet)

Also extracts statistics for elite validation.
"""

import json
import re
from typing import Dict, List, Set
from dataclasses import dataclass, asdict


@dataclass
class Trainer:
    name: str
    full_name: str
    variations: List[str]
    starts: int = 0
    wins: int = 0
    earnings: int = 0
    win_pct: float = 0.0
    is_elite: bool = False
    is_current_meet: bool = False
    all_time_rank: int = 0


@dataclass
class Jockey:
    name: str
    full_name: str
    variations: List[str]
    starts: int = 0
    wins: int = 0
    earnings: int = 0
    win_pct: float = 0.0
    is_elite: bool = False
    is_current_meet: bool = False
    all_time_rank: int = 0


@dataclass
class Horse:
    name: str
    sire_name: str = ''
    starts: int = 0
    wins: int = 0
    earnings: int = 0
    is_current_meet: bool = False


@dataclass
class Owner:
    name: str
    full_name: str
    variations: List[str]
    starts: int = 0
    wins: int = 0
    earnings: int = 0


def normalize_name(name: str) -> str:
    """Normalize a name for comparison"""
    return name.strip().lower().replace('.', '').replace(',', '').replace('  ', ' ')


def generate_name_variations(name: str) -> List[str]:
    """Generate common variations of a name"""
    variations = [name]

    # Add version without periods
    no_periods = name.replace('.', '')
    if no_periods != name:
        variations.append(no_periods)

    # Add version without middle initials
    parts = name.split()
    if len(parts) > 2:
        # Try removing middle names/initials
        first_last = f"{parts[0]} {parts[-1]}"
        if first_last not in variations:
            variations.append(first_last)

    # For names like "Kenneth G. McPeek", add "Ken McPeek", "Kenny McPeek"
    if parts:
        first = parts[0]
        if first == "Kenneth":
            variations.extend([
                name.replace("Kenneth", "Ken"),
                name.replace("Kenneth", "Kenny")
            ])
        elif first == "William":
            variations.extend([
                name.replace("William", "Bill"),
                name.replace("William", "Billy")
            ])
        elif first == "Robert":
            variations.extend([
                name.replace("Robert", "Bob"),
                name.replace("Robert", "Bobby")
            ])
        elif first == "Bradley" or first == "Brad":
            variations.extend([
                name.replace("Bradley", "Brad"),
                name.replace("Brad", "Bradley")
            ])

    return list(set(variations))


def parse_currency(value_str: str) -> int:
    """Parse currency string to integer"""
    if not value_str or value_str == '--':
        return 0
    return int(value_str.replace('$', '').replace(',', ''))


def parse_percentage(value_str: str) -> float:
    """Parse percentage string to float"""
    if not value_str or value_str == '--':
        return 0.0
    return float(value_str.replace('%', ''))


def parse_equibase_file(file_path: str):
    """Parse the Equibase directory file"""

    with open(file_path, 'r') as f:
        lines = f.readlines()

    trainers = {}
    jockeys = {}
    horses = {}
    owners = {}

    current_section = None
    header_line = None

    for i, line in enumerate(lines):
        line = line.strip()

        # Skip empty lines
        if not line:
            continue

        # Detect section headers
        if "Keeneland Trainers" in line:
            current_section = "trainers_meet"
            print(f"Found: {line}")
            header_line = None
            continue
        elif "Keeneland Owners" in line:
            current_section = "owners_meet"
            print(f"Found: {line}")
            header_line = None
            continue
        elif "Keeneland Jockeys" in line:
            current_section = "jockeys_meet"
            print(f"Found: {line}")
            header_line = None
            continue
        elif "Keeneland Horses" in line:
            current_section = "horses_meet"
            print(f"Found: {line}")
            header_line = None
            continue
        elif line.startswith("Rank\tJockey Name\tStarts\t1st") and i > 2000:  # All-time jockeys
            current_section = "jockeys_alltime"
            print(f"Found all-time jockeys at line {i}")
            header_line = None
            continue
        elif line.startswith("Rank\tTrainer Name\tStarts\t1st") and i > 2500:  # All-time trainers
            current_section = "trainers_alltime"
            print(f"Found all-time trainers at line {i}")
            header_line = None
            continue

        # Skip header lines (Rank\tTrainer Name\t...)
        if line.startswith("Rank\t"):
            header_line = line
            continue

        # Skip duplicate header lines
        if header_line and line == header_line:
            continue

        # Parse data based on current section
        parts = line.split('\t')

        if current_section == "trainers_meet" and len(parts) >= 8:
            try:
                rank = parts[0]
                name = parts[1].strip()
                starts = int(parts[2].replace(',', '')) if parts[2] != '--' else 0
                wins = int(parts[4].replace(',', '')) if parts[4] != '--' else 0
                earnings = parse_currency(parts[7])
                win_pct = parse_percentage(parts[8]) if len(parts) > 8 else 0.0

                key = normalize_name(name)
                if key not in trainers:
                    trainers[key] = Trainer(
                        name=name,
                        full_name=name,
                        variations=generate_name_variations(name),
                        starts=starts,
                        wins=wins,
                        earnings=earnings,
                        win_pct=win_pct,
                        is_current_meet=True
                    )
            except (ValueError, IndexError):
                pass

        elif current_section == "trainers_alltime" and len(parts) >= 7:
            try:
                rank_str = parts[0].replace('*', '').strip()
                rank = int(rank_str) if rank_str.isdigit() else 0
                if rank == 0 or rank > 100:  # Only top 100
                    continue

                name = parts[1].strip()
                starts = int(parts[2].replace(',', '')) if parts[2] != '--' else 0
                wins = int(parts[3].replace(',', '')) if parts[3] != '--' else 0
                earnings = parse_currency(parts[6])
                win_pct = parse_percentage(parts[7]) if len(parts) > 7 else 0.0

                key = normalize_name(name)
                if key in trainers:
                    # Update existing with all-time stats (preserve current meet stats)
                    trainers[key].all_time_rank = rank
                    trainers[key].is_elite = True
                    # Keep current meet stats for starts/wins, add all-time earnings
                    if trainers[key].earnings < earnings:
                        trainers[key].earnings = earnings  # Use lifetime earnings if higher
                else:
                    # Create new entry for elite trainer not in current meet
                    trainers[key] = Trainer(
                        name=name,
                        full_name=name,
                        variations=generate_name_variations(name),
                        starts=starts,
                        wins=wins,
                        earnings=earnings,
                        win_pct=win_pct,
                        is_elite=True,
                        is_current_meet=False,
                        all_time_rank=rank
                    )
            except (ValueError, IndexError):
                pass

        elif current_section == "jockeys_meet" and len(parts) >= 8:
            try:
                rank = parts[0]
                name = parts[1].strip()
                starts = int(parts[2].replace(',', '')) if parts[2] != '--' else 0
                wins = int(parts[3].replace(',', '')) if parts[3] != '--' else 0
                earnings = parse_currency(parts[6])
                win_pct = parse_percentage(parts[7]) if len(parts) > 7 else 0.0

                key = normalize_name(name)
                if key not in jockeys:
                    jockeys[key] = Jockey(
                        name=name,
                        full_name=name,
                        variations=generate_name_variations(name),
                        starts=starts,
                        wins=wins,
                        earnings=earnings,
                        win_pct=win_pct,
                        is_current_meet=True
                    )
            except (ValueError, IndexError):
                pass

        elif current_section == "jockeys_alltime" and len(parts) >= 7:
            try:
                rank_str = parts[0].replace('*', '').strip()
                rank = int(rank_str) if rank_str.isdigit() else 0
                if rank == 0 or rank > 200:  # Only top 200
                    continue

                name = parts[1].strip()
                starts = int(parts[2].replace(',', '')) if parts[2] != '--' else 0
                wins = int(parts[3].replace(',', '')) if parts[3] != '--' else 0
                earnings = parse_currency(parts[6])
                win_pct = parse_percentage(parts[7]) if len(parts) > 7 else 0.0

                key = normalize_name(name)
                if key in jockeys:
                    # Update existing with all-time stats (preserve current meet stats)
                    jockeys[key].all_time_rank = rank
                    jockeys[key].is_elite = True
                    # Keep current meet stats for starts/wins, add all-time earnings
                    if jockeys[key].earnings < earnings:
                        jockeys[key].earnings = earnings  # Use lifetime earnings if higher
                else:
                    # Create new entry for elite jockey not in current meet
                    jockeys[key] = Jockey(
                        name=name,
                        full_name=name,
                        variations=generate_name_variations(name),
                        starts=starts,
                        wins=wins,
                        earnings=earnings,
                        win_pct=win_pct,
                        is_elite=True,
                        is_current_meet=False,
                        all_time_rank=rank
                    )
            except (ValueError, IndexError) as e:
                pass

        elif current_section == "horses_meet" and len(parts) >= 8:
            try:
                rank = parts[0]
                name = parts[1].strip()
                sire = parts[2].strip() if len(parts) > 2 else ''
                starts = int(parts[3]) if len(parts) > 3 and parts[3] != '--' else 0
                wins = int(parts[4]) if len(parts) > 4 and parts[4] != '--' else 0
                earnings = parse_currency(parts[7]) if len(parts) > 7 else 0

                key = normalize_name(name)
                if key not in horses:
                    horses[key] = Horse(
                        name=name,
                        sire_name=sire,
                        starts=starts,
                        wins=wins,
                        earnings=earnings,
                        is_current_meet=True
                    )
            except (ValueError, IndexError):
                pass

        elif current_section == "owners_meet" and len(parts) >= 8:
            try:
                rank = parts[0]
                name = parts[1].strip()
                starts = int(parts[2]) if parts[2] != '--' else 0
                wins = int(parts[3]) if parts[3] != '--' else 0
                earnings = parse_currency(parts[6])

                key = normalize_name(name)
                if key not in owners:
                    owners[key] = Owner(
                        name=name,
                        full_name=name,
                        variations=[name],  # Owners have complex partnership names
                        starts=starts,
                        wins=wins,
                        earnings=earnings
                    )
            except (ValueError, IndexError):
                pass

    return trainers, jockeys, horses, owners


def build_fuzzy_matching_databases(trainers, jockeys, horses, owners, output_dir):
    """Build fuzzy matching JSON files compatible with existing system"""

    print("\nBuilding fuzzy matching databases...")

    # Trainers database
    trainer_db = {}
    for trainer in trainers.values():
        trainer_db[trainer.name] = {
            'full_name': trainer.full_name,
            'variations': trainer.variations,
            'stats': {
                'starts': trainer.starts,
                'wins': trainer.wins,
                'earnings': trainer.earnings,
                'win_pct': trainer.win_pct,
                'is_elite': trainer.is_elite,
                'all_time_rank': trainer.all_time_rank
            }
        }

    with open(f'{output_dir}/trainers_equibase.json', 'w') as f:
        json.dump(trainer_db, f, indent=2)
    print(f"✓ Trainers: {len(trainer_db)} entries")

    # Jockeys database
    jockey_db = {}
    for jockey in jockeys.values():
        jockey_db[jockey.name] = {
            'full_name': jockey.full_name,
            'variations': jockey.variations,
            'stats': {
                'starts': jockey.starts,
                'wins': jockey.wins,
                'earnings': jockey.earnings,
                'win_pct': jockey.win_pct,
                'is_elite': jockey.is_elite,
                'all_time_rank': jockey.all_time_rank
            }
        }

    with open(f'{output_dir}/jockeys_equibase.json', 'w') as f:
        json.dump(jockey_db, f, indent=2)
    print(f"✓ Jockeys: {len(jockey_db)} entries")

    # Horses database
    horse_db = {}
    for horse in horses.values():
        horse_db[horse.name] = {
            'sire_name': horse.sire_name,
            'stats': {
                'starts': horse.starts,
                'wins': horse.wins,
                'earnings': horse.earnings
            }
        }

    with open(f'{output_dir}/horses_equibase.json', 'w') as f:
        json.dump(horse_db, f, indent=2)
    print(f"✓ Horses: {len(horse_db)} entries")

    # Owners database
    owner_db = {}
    for owner in owners.values():
        owner_db[owner.name] = {
            'full_name': owner.full_name,
            'stats': {
                'starts': owner.starts,
                'wins': owner.wins,
                'earnings': owner.earnings
            }
        }

    with open(f'{output_dir}/owners_equibase.json', 'w') as f:
        json.dump(owner_db, f, indent=2)
    print(f"✓ Owners: {len(owner_db)} entries")

    # Elite statistics for validation
    elite_stats = {
        'elite_trainers': [
            {
                'name': t.name,
                'win_pct': t.win_pct,
                'earnings': t.earnings,
                'all_time_rank': t.all_time_rank
            }
            for t in trainers.values() if t.is_elite
        ],
        'elite_jockeys': [
            {
                'name': j.name,
                'win_pct': j.win_pct,
                'earnings': j.earnings,
                'all_time_rank': j.all_time_rank
            }
            for j in jockeys.values() if j.is_elite
        ]
    }

    with open(f'{output_dir}/elite_statistics.json', 'w') as f:
        json.dump(elite_stats, f, indent=2)
    print(f"✓ Elite statistics: {len(elite_stats['elite_trainers'])} trainers, {len(elite_stats['elite_jockeys'])} jockeys")


def main():
    """Main execution"""

    print("="*80)
    print(" BUILDING COMPREHENSIVE REFERENCE DATABASES FROM EQUIBASE DATA")
    print("="*80)
    print()

    input_file = "Directory Equibase - Trainers, Owners, Jockeys, Horses.txt"
    output_dir = "data/reference_databases"

    print(f"Input file: {input_file}")
    print(f"Output directory: {output_dir}")
    print()

    # Parse the file
    print("Parsing Equibase directory file...")
    trainers, jockeys, horses, owners = parse_equibase_file(input_file)

    print(f"\n✓ Parsing complete!")
    print(f"  Trainers: {len(trainers)}")
    print(f"  Jockeys: {len(jockeys)}")
    print(f"  Horses: {len(horses)}")
    print(f"  Owners: {len(owners)}")

    # Count elite
    elite_trainers = sum(1 for t in trainers.values() if t.is_elite)
    elite_jockeys = sum(1 for j in jockeys.values() if j.is_elite)

    print(f"\n  Elite trainers (top 100 all-time): {elite_trainers}")
    print(f"  Elite jockeys (top 200 all-time): {elite_jockeys}")

    # Build databases
    build_fuzzy_matching_databases(trainers, jockeys, horses, owners, output_dir)

    print()
    print("="*80)
    print(" SUCCESS! Reference databases built")
    print("="*80)
    print()
    print("Next steps:")
    print("1. Update fuzzy_matching.py to load these new databases")
    print("2. Test hybrid parser with expanded databases")
    print("3. Expect quality improvement: 94.5% → 96-97%+")


if __name__ == '__main__':
    main()
