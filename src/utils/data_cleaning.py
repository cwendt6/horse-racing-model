#!/usr/bin/env python3
"""
Data Cleaning and Validation

Fixes data quality issues in racing predictions:
1. Corrupted trainer/jockey fields (embedded race statistics)
2. Invalid program numbers (duplicates, zeros)
3. Missing/generic horse names
4. Missing Beyer figures (especially in maiden races)

Based on PREDICTOR_FIX_SPECIFICATION.md
"""

import re
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple


def clean_trainer_field(trainer_str):
    """
    Extract clean trainer name from field with embedded stats.

    Examples of corrupted input:
        "Clm Prc Danilo Grisales Rave Kee Dirt: 0 0 0 0 $0 Turf: 1 0 0 0 $1,165..."
        "Keith J.Asmussen Kee Dirt: 0 0 0 0 $0..."
        "Jaime A.Torres Kee Turf: 2 1 0 0 $57,825..."
        "Irad Ortiz,Jr.Clm Prc Kee Dirt: 2 0 0 1 $9,680 Turf: 1 0 0 0"  # Jockey in trainer field!
        "Luis Saez Kee Dirt: 0 0 0 0 $0 Turf: 8 1 2 1 $92,400 KOrange"  # Jockey in trainer field!
        "Owner"

    Args:
        trainer_str: Raw trainer field from data

    Returns:
        Clean trainer name or "Unknown"
    """
    if not trainer_str or pd.isna(trainer_str):
        return "Unknown"

    trainer_str = str(trainer_str).strip()

    # Special case: literal "Owner" is valid - owner is training their own horse
    if trainer_str == "Owner":
        return "Owner"

    # NEW: Detect jockey names in trainer field (they have embedded track stats immediately after name)
    # Pattern: "FirstName LastName Kee Dirt:" or "FirstName LastName,Jr. Kee Dirt:"
    # Common jockeys: Irad Ortiz, Luis Saez, Tyler Gaffalione, etc.
    jockey_in_trainer_pattern = r'^([A-Z][a-z]+\s+[A-Z][a-z]+(?:,[A-Z][a-z]+\.?)?)\s+Kee\s+(?:Dirt|Turf):'
    if re.match(jockey_in_trainer_pattern, trainer_str):
        # This is a jockey name, not a trainer - field is corrupted beyond repair
        return "Unknown"

    # Remove "Clm Prc" prefix
    if trainer_str.startswith('Clm Prc '):
        trainer_str = trainer_str[8:].strip()

    # Remove embedded track statistics (everything from "Kee" onwards)
    trainer_str = re.sub(r'\s+Kee\s+(?:Dirt|Turf):.*$', '', trainer_str)
    trainer_str = re.sub(r'\s+Wet\s+Dirt:.*$', '', trainer_str)

    # Remove color codes at end (KOrange, KPurple, etc.)
    trainer_str = re.sub(r'\s*K[A-Z][a-z]+$', '', trainer_str)

    # Now try to extract proper name
    patterns = [
        # Three-word name: "John P. Smith"
        r'^([A-Z][a-z]+\s+[A-Z][a-z]+\s+[A-Z][a-z]+)',
        # Proper name with middle initial: "Keith J.Asmussen" or "Keith J. Asmussen"
        r'^([A-Z][a-z]+\s+[A-Z]\.\s*[A-Z][a-z]+)',
        # Proper name with middle name: "Danilo Grisales"
        r'^([A-Z][a-z]+\s+[A-Z][a-z]+)',
    ]

    for pattern in patterns:
        match = re.search(pattern, trainer_str)
        if match:
            name = match.group(1).strip()
            # Make sure it doesn't include track codes (all caps short words)
            words = name.split()
            clean_words = []
            for word in words:
                # Skip if it's a track code (3-4 uppercase letters)
                if len(word) <= 4 and word.isupper():
                    break
                clean_words.append(word)

            if len(clean_words) >= 2:
                return ' '.join(clean_words)

    # If no pattern matches, take first 2-4 words (typical name length)
    words = trainer_str.split()
    if len(words) > 0:
        # Skip obvious non-name words
        cleaned_words = [w for w in words[:4] if not w in ['Clm', 'Prc', 'Kee', 'Dirt:', 'Turf:', 'Owner']]
        if len(cleaned_words) >= 2:
            return ' '.join(cleaned_words)

    return "Unknown"


def clean_jockey_field(jockey_str):
    """
    Extract clean jockey name, removing owner info and claiming data.

    Examples of corrupted input:
        "Luis Saez Owner"
        "Tyler Gaffalione Claimedby Stable"
        "Claimedby Asmussen S"  # Just claiming info, no jockey!
        "Claimedby Sharp Joefrom Birzer"
        "Jimmy D. Roberts Owner"

    Args:
        jockey_str: Raw jockey field from data

    Returns:
        Clean jockey name or "Unknown"
    """
    if not jockey_str or pd.isna(jockey_str):
        return "Unknown"

    jockey_str = str(jockey_str).strip()

    # NEW: If it starts with "Claimedby", it's corrupted beyond repair
    if jockey_str.startswith('Claimedby'):
        # Try to extract jockey name before "Claimedby" if there is one
        # But typically these are just claiming info
        return "Unknown"

    # Remove owner designation
    jockey_str = re.sub(r'\s+Owner$', '', jockey_str, flags=re.IGNORECASE)

    # Remove claiming patterns
    # "Claimedby X from Y" -> ""
    jockey_str = re.sub(r'\s+Claimedby\s+.*?from\s+.*$', '', jockey_str, flags=re.IGNORECASE)
    jockey_str = re.sub(r'\s+Claimedby\s+.*$', '', jockey_str, flags=re.IGNORECASE)

    # Remove claiming/owner names that don't look like jockeys
    invalid_keywords = ['Farm', 'Stable', 'LLC', 'Inc', 'Racing', 'Equine']
    for keyword in invalid_keywords:
        if keyword in jockey_str:
            # If it contains these, likely not a jockey name
            words_before = jockey_str.split(keyword)[0].strip().split()
            if len(words_before) >= 2:
                # Check if these look like proper names
                if all(w[0].isupper() for w in words_before if w):
                    return ' '.join(words_before)
            return "Unknown"

    # Extract proper jockey name (2-3 words typically)
    # Common format: "First Last" or "First Middle Last" or "First Last, Jr."
    words = jockey_str.split()
    if len(words) >= 2:
        # Check if first two words look like names (capitalized)
        if all(word[0].isupper() for word in words[:2] if len(word) > 0):
            # Include up to 3 words (for names like "Irad Ortiz, Jr.")
            return ' '.join(words[:min(3, len(words))])

    # If we got here and still have something reasonable
    if jockey_str and len(jockey_str.split()) <= 4:
        return jockey_str

    return "Unknown"


def validate_and_fix_program_numbers(df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
    """
    Ensure unique, valid program numbers per race.

    Issues fixed:
    - Program numbers ≤ 0
    - Duplicate program numbers within a race
    - Missing program numbers

    Args:
        df: DataFrame with 'Race' and 'Program#' columns

    Returns:
        Tuple of (cleaned DataFrame, list of issue descriptions)
    """
    issues = []
    df = df.copy()

    for race_num in df['Race'].unique():
        race_mask = df['Race'] == race_num
        race_df = df[race_mask]

        # Check for invalid numbers (0 or less)
        invalid_mask = (df['Program#'] <= 0) & race_mask
        if invalid_mask.any():
            count = invalid_mask.sum()
            issues.append(f"Race {race_num}: {count} invalid program numbers (≤0) - fixed")
            # Reassign to next available number
            max_num = race_df['Program#'].max()
            for idx in df[invalid_mask].index:
                max_num += 1
                df.at[idx, 'Program#'] = max_num

        # Check for duplicates
        race_df = df[race_mask]  # Refresh after changes
        prog_counts = race_df['Program#'].value_counts()
        duplicates = prog_counts[prog_counts > 1]

        if len(duplicates) > 0:
            dup_list = list(duplicates.index)
            issues.append(f"Race {race_num}: Duplicate program numbers {dup_list} - fixed")
            # Reassign duplicates (keep first occurrence)
            for dup_num in duplicates.index:
                dup_mask = (df['Program#'] == dup_num) & race_mask
                dup_indices = df[dup_mask].index[1:]  # Skip first
                max_num = race_df['Program#'].max()
                for idx in dup_indices:
                    max_num += 1
                    df.at[idx, 'Program#'] = max_num

    return df, issues


def validate_horse_names(df: pd.DataFrame) -> pd.DataFrame:
    """
    Check for generic/missing horse names.

    Adds 'name_quality' column: 'generic' or 'valid'

    Args:
        df: DataFrame with 'Horse' column

    Returns:
        DataFrame with name_quality column added
    """
    df = df.copy()

    # Pattern for generic names: "Horse X" where X is a number
    generic_pattern = r'^Horse\s+\d+$'

    df['name_quality'] = df['Horse'].apply(
        lambda x: 'generic' if re.match(generic_pattern, str(x)) else 'valid'
    )

    generic_count = (df['name_quality'] == 'generic').sum()
    if generic_count > 0:
        print(f"⚠️  WARNING: {generic_count} horses have generic names - data quality issue")

    return df


def impute_missing_beyer(row, df: pd.DataFrame):
    """
    Impute Beyer figure for horses without race history.

    Strategy:
    - Maiden races: Estimate based on purse level and trainer quality
    - Other races: Use race average minus penalty

    Args:
        row: DataFrame row
        df: Full DataFrame for race context

    Returns:
        Estimated Beyer figure
    """
    # If we have a valid Beyer, return it
    if pd.notna(row.get('Best_Beyer')) and row['Best_Beyer'] > 0:
        return row['Best_Beyer']

    # For maidens, use pedigree-based estimate
    race_type = str(row.get('Type', '')).lower()

    if 'maiden' in race_type:
        # Estimate based on purse level
        purse = row.get('Purse', 0)

        # Base estimate by purse
        if purse >= 100000:
            base_estimate = 70  # Higher-class maiden
        elif purse >= 50000:
            base_estimate = 60
        else:
            base_estimate = 50

        # Adjust for trainer quality (if available)
        trainer_win_pct = row.get('Trainer_Win%', 0)
        if trainer_win_pct and trainer_win_pct != 'Owner':
            try:
                win_pct = float(str(trainer_win_pct).rstrip('%'))
                if win_pct > 20:
                    base_estimate += 8
                elif win_pct > 15:
                    base_estimate += 4
            except:
                pass

        return base_estimate

    # For non-maidens with missing Beyer, use race average minus penalty
    race_mask = df['Race'] == row['Race']
    race_beyers = df[race_mask]['Best_Beyer']
    race_avg = race_beyers[race_beyers > 0].mean()

    if pd.notna(race_avg) and race_avg > 0:
        return max(40, race_avg - 15)  # Penalty for missing data

    return 50  # Absolute fallback


def clean_dataframe(df: pd.DataFrame, verbose: bool = True) -> Tuple[pd.DataFrame, Dict]:
    """
    Master cleaning function - applies all cleaning operations.

    Args:
        df: Raw DataFrame from data loader
        verbose: Print progress messages

    Returns:
        Tuple of (cleaned DataFrame, quality report dictionary)
    """
    if verbose:
        print("\n" + "="*80)
        print(" DATA CLEANING")
        print("="*80)

    quality_report = {
        'original_rows': len(df),
        'issues': []
    }

    # 1. Clean trainer and jockey fields
    if verbose:
        print("\n1. Cleaning trainer and jockey fields...")

    if 'Trainer' in df.columns:
        df['Trainer'] = df['Trainer'].apply(clean_trainer_field)
        if verbose:
            print("   ✓ Cleaned trainer fields")

    if 'Jockey' in df.columns:
        df['Jockey'] = df['Jockey'].apply(clean_jockey_field)
        if verbose:
            print("   ✓ Cleaned jockey fields")

    # 2. Validate and fix program numbers
    if verbose:
        print("\n2. Validating program numbers...")

    if 'Program#' in df.columns and 'Race' in df.columns:
        df, prog_issues = validate_and_fix_program_numbers(df)
        if prog_issues:
            quality_report['issues'].extend(prog_issues)
            if verbose:
                for issue in prog_issues:
                    print(f"   ⚠️  {issue}")
        else:
            if verbose:
                print("   ✓ All program numbers valid")

    # 3. Validate horse names
    if verbose:
        print("\n3. Validating horse names...")

    if 'Horse' in df.columns:
        df = validate_horse_names(df)
        generic_count = (df['name_quality'] == 'generic').sum()
        if generic_count == 0 and verbose:
            print("   ✓ All horse names appear valid")

    # 4. Impute missing Beyer figures
    if verbose:
        print("\n4. Handling missing Beyer figures...")

    if 'Best_Beyer' in df.columns:
        missing_before = (df['Best_Beyer'].isna() | (df['Best_Beyer'] <= 0)).sum()
        df['Best_Beyer'] = df.apply(lambda row: impute_missing_beyer(row, df), axis=1)

        # Also handle Last_Beyer
        if 'Last_Beyer' in df.columns:
            df['Last_Beyer'] = df.apply(
                lambda row: row['Last_Beyer'] if pd.notna(row['Last_Beyer']) and row['Last_Beyer'] > 0
                else row['Best_Beyer'] * 0.9,
                axis=1
            )

        missing_after = (df['Best_Beyer'].isna() | (df['Best_Beyer'] <= 0)).sum()
        imputed = missing_before - missing_after

        if verbose:
            print(f"   ✓ Imputed {imputed} missing Beyer figures")

    quality_report['cleaned_rows'] = len(df)
    quality_report['imputed_beyers'] = imputed if 'Best_Beyer' in df.columns else 0

    if verbose:
        print("\n" + "="*80)
        print(f" CLEANING COMPLETE - {len(df)} horses processed")
        print("="*80 + "\n")

    return df, quality_report


def validate_race_data(df: pd.DataFrame, race_num: int) -> Dict:
    """
    Comprehensive validation for a single race.

    Args:
        df: Full DataFrame
        race_num: Race number to validate

    Returns:
        Dictionary with:
            - race: Race number
            - quality_score: 0-100 quality score
            - issues: List of issue descriptions
            - quality_level: 'HIGH', 'MEDIUM', or 'LOW'
    """
    race_df = df[df['Race'] == race_num].copy()
    issues = []
    quality_score = 100.0

    # 1. Check program numbers
    if 'Program#' in race_df.columns:
        if len(race_df['Program#'].unique()) != len(race_df):
            issues.append("Duplicate program numbers")
            quality_score -= 20

        if (race_df['Program#'] <= 0).any():
            issues.append("Invalid program numbers (≤0)")
            quality_score -= 15

    # 2. Check horse names
    if 'name_quality' in race_df.columns:
        generic_count = (race_df['name_quality'] == 'generic').sum()
        if generic_count > 0:
            issues.append(f"{generic_count} generic horse name(s)")
            quality_score -= (10 * generic_count)

    # 3. Check for missing critical data
    if 'Best_Beyer' in race_df.columns:
        missing_beyer = (race_df['Best_Beyer'].isna() | (race_df['Best_Beyer'] <= 0)).sum()
        if missing_beyer > 0:
            issues.append(f"{missing_beyer} missing Beyer figures")
            quality_score -= (5 * missing_beyer)

    if 'Jockey' in race_df.columns:
        unknown_jockeys = (race_df['Jockey'] == 'Unknown').sum()
        if unknown_jockeys > 0:
            issues.append(f"{unknown_jockeys} unknown jockey(s)")
            quality_score -= (3 * unknown_jockeys)

    # 4. Check trainer/jockey field corruption
    if 'Trainer' in race_df.columns:
        corrupt_trainers = race_df['Trainer'].apply(
            lambda x: 'Clm Prc' in str(x) or 'Kee Dirt:' in str(x)
        ).sum()
        if corrupt_trainers > 0:
            issues.append(f"{corrupt_trainers} corrupted trainer field(s)")
            quality_score -= (10 * corrupt_trainers)

    # 5. Validate probabilities sum to ~100% (if present)
    if 'Win_Probability' in race_df.columns:
        prob_sum = race_df['Win_Probability'].sum()
        if abs(prob_sum - 100.0) > 1.0:
            issues.append(f"Probabilities sum to {prob_sum:.1f}% (should be ~100%)")
            quality_score -= 10

    quality_score = max(0, quality_score)

    return {
        'race': race_num,
        'quality_score': quality_score,
        'issues': issues,
        'quality_level': 'HIGH' if quality_score >= 80 else 'MEDIUM' if quality_score >= 60 else 'LOW'
    }


# Export all functions
__all__ = [
    'clean_trainer_field',
    'clean_jockey_field',
    'validate_and_fix_program_numbers',
    'validate_horse_names',
    'impute_missing_beyer',
    'clean_dataframe',
    'validate_race_data'
]


if __name__ == '__main__':
    # Test with sample data
    print("Data Cleaning Module - Test")
    print("="*80)

    # Test trainer cleaning
    test_trainers = [
        "Clm Prc Danilo Grisales Rave Kee Dirt: 0 0 0 0 $0 Turf: 1 0 0 0 $1,165",
        "Keith J.Asmussen Kee Dirt: 0 0 0 0 $0",
        "Brad Cox",
        "Unknown"
    ]

    print("\nTrainer Field Cleaning:")
    for trainer in test_trainers:
        cleaned = clean_trainer_field(trainer)
        print(f"  {trainer[:50]:50s} → {cleaned}")

    # Test jockey cleaning
    test_jockeys = [
        "Luis Saez Owner",
        "Tyler Gaffalione",
        "Irad Ortiz, Jr.",
        "Unknown"
    ]

    print("\nJockey Field Cleaning:")
    for jockey in test_jockeys:
        cleaned = clean_jockey_field(jockey)
        print(f"  {jockey:30s} → {cleaned}")

    print("\n" + "="*80)
    print("✓ Data cleaning module test complete")
