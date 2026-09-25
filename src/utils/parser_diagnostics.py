"""
Diagnostic Tool for Racing Analysis Issues
Identifies and fixes common parsing problems
"""

import re
from typing import Dict, List, Tuple, Optional
import json


class ParsingDiagnostics:
    """Diagnose and fix common parsing issues"""
    
    def __init__(self):
        self.issues = []
        self.fixes_applied = []
    
    def diagnose_horse_data(self, horse_dict: Dict) -> Dict:
        """
        Diagnose issues with a single horse's data
        Returns dict of issues and suggested fixes
        """
        issues = {}
        
        # Check 1: Horse name
        if not horse_dict.get('Horse') or horse_dict['Horse'].startswith('Horse '):
            issues['horse_name'] = {
                'problem': f"Generic name: {horse_dict.get('Horse', 'MISSING')}",
                'fix': 'Extract from PDF text using pattern: [A-Z][a-z]+(?:\\s+[A-Z][a-z]+)* \\([LM]\\)'
            }
        
        # Check 2: Program number
        prog_num = horse_dict.get('Program#', 0)
        if prog_num == 0 or prog_num > 20:
            issues['program_number'] = {
                'problem': f"Invalid program number: {prog_num}",
                'fix': 'Should be 1-20, check extraction from left margin of PDF'
            }
        
        # Check 3: Trainer name
        trainer = horse_dict.get('Trainer', '')
        if trainer == 'Unknown' or trainer == 'Owner' or not trainer:
            issues['trainer'] = {
                'problem': f"Trainer: {trainer}",
                'fix': 'Extract from "Trainer: Name ([record])" pattern'
            }
        
        # Check 4: Running style
        style = horse_dict.get('Running_Style', '')
        if not style or style not in ['E', 'P', 'S', 'C']:
            issues['running_style'] = {
                'problem': f"Invalid or missing running style: {style}",
                'fix': 'Calculate from past performance position patterns'
            }
        
        # Check 5: Jockey
        jockey = horse_dict.get('Jockey', '')
        if jockey == 'Unknown' or not jockey:
            issues['jockey'] = {
                'problem': 'Missing jockey name',
                'fix': 'Extract jockey name from line above claiming price/weight'
            }
        
        # Check 6: Best Beyer
        beyer = horse_dict.get('Best_Beyer')
        if beyer is None or beyer == 0:
            issues['beyer'] = {
                'problem': 'Missing Beyer speed figure',
                'severity': 'warning',  # This is optional
                'fix': 'Extract from past performance comments or stats box'
            }
        
        return issues
    
    def diagnose_race_pace(self, race_data: Dict) -> Dict:
        """
        Diagnose pace analysis issues for a race
        """
        issues = {}
        
        # Get running style distribution
        horses = race_data.get('horses', [])
        if not horses:
            return {'no_horses': 'No horse data found'}
        
        styles = [h.get('Running_Style', '') for h in horses]
        style_counts = {
            'E': styles.count('E'),
            'P': styles.count('P'),
            'S': styles.count('S'),
            'C': styles.count('C'),
            'Unknown': styles.count('') + styles.count(None)
        }
        
        total_horses = len(horses)
        
        # Check for unrealistic distributions
        if style_counts['P'] > total_horses * 0.7:
            issues['too_many_pressers'] = {
                'problem': f"{style_counts['P']}/{total_horses} horses classified as Pressers",
                'fix': 'Review running style classification logic - position thresholds may be wrong'
            }
        
        if style_counts['E'] == 0 and total_horses > 5:
            issues['no_early_speed'] = {
                'problem': 'No early speed horses identified',
                'fix': 'Check if early position (first call) is being extracted correctly'
            }
        
        if style_counts['C'] == 0 and style_counts['S'] == 0 and total_horses > 6:
            issues['no_closers'] = {
                'problem': 'No closers or stalkers identified',
                'fix': 'Check position change calculation (early pos - finish pos)'
            }
        
        if style_counts['Unknown'] > total_horses * 0.3:
            issues['many_unknown'] = {
                'problem': f"{style_counts['Unknown']} horses with unknown style",
                'fix': 'Past performances may not be parsing correctly'
            }
        
        # Check pace scores
        pace_scores = [h.get('pace_score', 0) for h in horses if h.get('pace_score')]
        if pace_scores and len(set(pace_scores)) == 1:
            issues['identical_pace_scores'] = {
                'problem': f'All horses have same pace score: {pace_scores[0]}',
                'fix': 'Pace advantage calculation not working - should vary by running style and scenario'
            }
        
        return issues
    
    def check_pdf_extraction_quality(self, extracted_text: str, horse_name: str) -> Dict:
        """
        Check if PDF extraction captured the key data for a horse
        """
        issues = {}
        
        # Check 1: Can we find the horse name in text?
        if horse_name not in extracted_text and not horse_name.startswith('Horse '):
            issues['horse_name_missing'] = 'Horse name not found in extracted text'
        
        # Check 2: Are there past performance lines?
        pp_pattern = r'\d{1,2}[A-Za-z]{3}\d{2}'  # Date pattern like 11Sep25
        pp_matches = re.findall(pp_pattern, extracted_text)
        if len(pp_matches) < 3:
            issues['insufficient_pps'] = f'Only found {len(pp_matches)} past performance dates'
        
        # Check 3: Are there position calls?
        # Look for sequences of numbers that could be positions
        position_pattern = r'\b([1-9]|1[0-2])\s+([1-9]|1[0-2])[²³⁴⁵⁶⁷⁸⁹⁰]*'
        position_sequences = re.findall(position_pattern, extracted_text)
        if len(position_sequences) < 3:
            issues['insufficient_positions'] = 'Cannot find position call sequences'
        
        # Check 4: Are there fractional times?
        time_pattern = r':?\d{2}[¹²³⁴⁵⁶⁷⁸⁹⁰]+'
        time_matches = re.findall(time_pattern, extracted_text)
        if len(time_matches) < 3:
            issues['insufficient_times'] = 'Cannot find fractional times'
        
        # Check 5: Is there trainer info?
        if 'Trainer:' not in extracted_text:
            issues['trainer_missing'] = 'Trainer line not found'
        
        # Check 6: Is there owner info?
        if 'Owner:' not in extracted_text:
            issues['owner_missing'] = 'Owner line not found'
        
        return issues
    
    def suggest_fixes(self, horse_dict: Dict, extracted_text: str = None) -> Dict:
        """
        Suggest specific fixes for a horse's data issues
        """
        fixes = {}
        
        # Fix 1: Extract horse name
        if horse_dict.get('Horse', '').startswith('Horse ') and extracted_text:
            name_match = re.search(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*\(([LM])\)', extracted_text)
            if name_match:
                fixes['horse_name'] = name_match.group(1)
                fixes['sex'] = 'F' if name_match.group(2) == 'L' else 'M'
        
        # Fix 2: Extract trainer
        if horse_dict.get('Trainer') in ['Unknown', 'Owner', ''] and extracted_text:
            trainer_match = re.search(r'Trainer:\s*([^(]+)\s*\(', extracted_text)
            if trainer_match:
                trainer_name = trainer_match.group(1).strip()
                # Clean up trainer name
                trainer_name = re.sub(r'\s+', ' ', trainer_name)
                fixes['trainer'] = trainer_name
        
        # Fix 3: Extract jockey
        if horse_dict.get('Jockey') in ['Unknown', ''] and extracted_text:
            # Jockey usually appears on its own line before horse name or ClmPrc
            jockey_pattern = r'([A-Z][a-z]+\s+[A-Z]\.?\s+[A-Z][a-z]+|[A-Z][a-z]+\s+[A-Z][a-z]+)\s+(?:Kee|Clm)'
            jockey_match = re.search(jockey_pattern, extracted_text)
            if jockey_match:
                fixes['jockey'] = jockey_match.group(1).strip()
        
        # Fix 4: Extract program number
        # Program number is typically a large number on the left margin
        if horse_dict.get('Program#', 0) == 0 and extracted_text:
            # Look for pattern at start of line
            prog_match = re.search(r'^(\d{1,2})\s+\d+-\d+', extracted_text, re.MULTILINE)
            if prog_match:
                fixes['program_number'] = int(prog_match.group(1))
        
        return fixes
    
    def generate_report(self, all_horses: List[Dict], race_data: Dict = None) -> str:
        """
        Generate comprehensive diagnostic report
        """
        report = []
        report.append("=" * 70)
        report.append("RACING PARSER DIAGNOSTIC REPORT")
        report.append("=" * 70)
        report.append("")
        
        # Overall statistics
        total_horses = len(all_horses)
        horses_with_names = sum(1 for h in all_horses if not h.get('Horse', '').startswith('Horse '))
        horses_with_trainers = sum(1 for h in all_horses if h.get('Trainer') not in ['Unknown', 'Owner', '', None])
        horses_with_styles = sum(1 for h in all_horses if h.get('Running_Style') in ['E', 'P', 'S', 'C'])
        
        report.append("OVERALL STATISTICS:")
        report.append(f"  Total Horses: {total_horses}")
        report.append(f"  With Valid Names: {horses_with_names} ({horses_with_names/total_horses*100:.1f}%)")
        report.append(f"  With Trainers: {horses_with_trainers} ({horses_with_trainers/total_horses*100:.1f}%)")
        report.append(f"  With Running Styles: {horses_with_styles} ({horses_with_styles/total_horses*100:.1f}%)")
        report.append("")
        
        # Running style distribution
        if horses_with_styles > 0:
            styles = [h.get('Running_Style', '') for h in all_horses]
            style_counts = {
                'E': styles.count('E'),
                'P': styles.count('P'),
                'S': styles.count('S'),
                'C': styles.count('C')
            }
            
            report.append("RUNNING STYLE DISTRIBUTION:")
            report.append(f"  Early Speed (E): {style_counts['E']} ({style_counts['E']/horses_with_styles*100:.1f}%)")
            report.append(f"  Presser (P): {style_counts['P']} ({style_counts['P']/horses_with_styles*100:.1f}%)")
            report.append(f"  Stalker (S): {style_counts['S']} ({style_counts['S']/horses_with_styles*100:.1f}%)")
            report.append(f"  Closer (C): {style_counts['C']} ({style_counts['C']/horses_with_styles*100:.1f}%)")
            report.append("")
            
            # Flag unrealistic distributions
            if style_counts['P'] > horses_with_styles * 0.7:
                report.append("  ⚠️ WARNING: Too many pressers - check position thresholds")
            if style_counts['E'] == 0:
                report.append("  ⚠️ WARNING: No early speed horses - check early position extraction")
            if style_counts['C'] == 0 and style_counts['S'] == 0:
                report.append("  ⚠️ WARNING: No closers or stalkers - check position change calculation")
            report.append("")
        
        # Individual horse issues
        report.append("INDIVIDUAL HORSE ISSUES:")
        report.append("")
        
        issues_by_horse = {}
        for horse in all_horses[:10]:  # Show first 10
            horse_issues = self.diagnose_horse_data(horse)
            if horse_issues:
                horse_name = horse.get('Horse', 'Unknown')
                prog_num = horse.get('Program#', '?')
                report.append(f"  Horse #{prog_num} ({horse_name}):")
                for issue_type, issue_data in horse_issues.items():
                    report.append(f"    ❌ {issue_type}: {issue_data['problem']}")
                    report.append(f"       Fix: {issue_data['fix']}")
                report.append("")
        
        # Race-level issues
        if race_data:
            report.append("RACE-LEVEL ISSUES:")
            race_issues = self.diagnose_race_pace(race_data)
            for issue_type, issue_data in race_issues.items():
                if isinstance(issue_data, dict):
                    report.append(f"  ❌ {issue_type}: {issue_data['problem']}")
                    report.append(f"     Fix: {issue_data['fix']}")
                else:
                    report.append(f"  ❌ {issue_type}: {issue_data}")
            report.append("")
        
        # Priority fixes
        report.append("=" * 70)
        report.append("PRIORITY FIXES:")
        report.append("=" * 70)
        
        priority = []
        if horses_with_names < total_horses * 0.5:
            priority.append("1. FIX HORSE NAME EXTRACTION")
            priority.append("   - Pattern: [A-Z][a-z]+(?:\\s+[A-Z][a-z]+)* \\([LM]\\)")
            priority.append("   - Location: After claiming price and color line")
            priority.append("")
        
        if horses_with_trainers < total_horses * 0.5:
            priority.append("2. FIX TRAINER EXTRACTION")
            priority.append("   - Pattern: Trainer:\\s*([^(]+)\\s*\\(")
            priority.append("   - Location: After silks description")
            priority.append("")
        
        if horses_with_styles < total_horses * 0.7:
            priority.append("3. FIX RUNNING STYLE CLASSIFICATION")
            priority.append("   - Need to extract position calls from past performances")
            priority.append("   - Pattern: sequence of 4-6 numbers with superscripts")
            priority.append("   - Calculate: early position vs finish position")
            priority.append("")
        
        styles = [h.get('Running_Style', '') for h in all_horses if h.get('Running_Style')]
        if styles and len(set(styles)) <= 2:
            priority.append("4. FIX RUNNING STYLE THRESHOLDS")
            priority.append("   - Current distribution is unrealistic")
            priority.append("   - Adjust position thresholds for E/P/S/C classification")
            priority.append("   - Typical distribution: 20% E, 30% P, 25% S, 25% C")
            priority.append("")
        
        report.extend(priority)
        
        return "\n".join(report)


def main():
    """
    Example usage with your data
    """
    # Example horse data (from your output)
    example_horses = [
        {
            'Program#': 2,
            'Horse': 'Just an Opinion',
            'Trainer': 'MarcelinoSalas',
            'Jockey': 'Edgar Morales',
            'Running_Style': 'P',
            'Best_Beyer': 75
        },
        {
            'Program#': 1,
            'Horse': 'Horse 1',  # Problem
            'Trainer': 'Owner',  # Problem
            'Jockey': 'Tyler Gaffalione',
            'Running_Style': 'P',
            'Best_Beyer': 54
        },
        {
            'Program#': 4,
            'Horse': 'Horse 4',  # Problem
            'Trainer': 'Unknown',  # Problem
            'Jockey': 'Luan Machado',
            'Running_Style': 'P',
            'Best_Beyer': 79
        }
    ]
    
    race_data = {
        'horses': example_horses
    }
    
    diagnostics = ParsingDiagnostics()
    report = diagnostics.generate_report(example_horses, race_data)
    
    print(report)
    
    # Save report
    with open('parsing_diagnostic_report.txt', 'w') as f:
        f.write(report)
    
    print("\n💾 Report saved to: parsing_diagnostic_report.txt")


if __name__ == "__main__":
    main()
