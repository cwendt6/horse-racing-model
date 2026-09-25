#!/usr/bin/env python3
"""
Parser Data Extraction Completeness Assessment

Measures what percentage of available data is being extracted from PP PDFs.
Target: 100% extraction of critical fields.

Critical Fields:
- Horse name
- Program number
- Jockey name
- Trainer name
- Morning line odds
- Speed figures (best Beyer)
- Past performances (with calls, times, distances)
- Running style
- Equipment (blinkers, lasix)
- Workouts

Usage:
    python3 scripts/analysis/performance/parser_accuracy_assessment.py
"""

import sys
import os
sys.path.insert(0, 'src')
sys.path.insert(0, '.')

from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Any
import json

from src.parsers.hybrid_parser_v3 import parse_pdf_hybrid_v3


@dataclass
class FieldExtraction:
    """Track extraction success for a field"""
    field_name: str
    total_horses: int = 0
    extracted: int = 0
    missing: int = 0
    partial: int = 0

    @property
    def extraction_rate(self) -> float:
        if self.total_horses == 0:
            return 0.0
        return (self.extracted / self.total_horses) * 100

    @property
    def completeness_rate(self) -> float:
        """Including partial extractions"""
        if self.total_horses == 0:
            return 0.0
        return ((self.extracted + self.partial) / self.total_horses) * 100


class ParserAccuracyAssessment:
    def __init__(self, pp_directory: str = "Keeneland October PPs"):
        self.pp_directory = Path(pp_directory)
        self.field_stats = {}
        self.race_results = []

    def assess_all_pdfs(self):
        """Assess all October PDFs"""
        pdf_files = sorted(self.pp_directory.glob("*-kee-ppspdf.pdf"))

        print("=" * 80)
        print(" PARSER DATA EXTRACTION COMPLETENESS ASSESSMENT")
        print("=" * 80)
        print()
        print(f"Analyzing {len(pdf_files)} PDF files...")
        print()

        for pdf_file in pdf_files:
            date = pdf_file.stem.split('-kee-')[0]
            print(f"Processing {date}...", end=' ')

            try:
                races = parse_pdf_hybrid_v3(str(pdf_file), debug=False)
                self._assess_races(races, date)
                print(f"✓ {len(races)} races, {sum(len(r.horses) for r in races)} horses")
            except Exception as e:
                print(f"✗ Error: {str(e)}")

        self._generate_report()

    def _assess_races(self, races: List[Any], date: str):
        """Assess data extraction for all races"""
        for race in races:
            race_result = {
                'date': date,
                'race_number': race.race_number,
                'horses': len(race.horses),
                'field_completeness': {}
            }

            for horse in race.horses:
                self._assess_horse(horse)

            self.race_results.append(race_result)

    def _assess_horse(self, horse: Any):
        """Assess data extraction for a single horse"""
        # Core identification fields
        self._check_field('horse_name', horse.name, required=True,
                         valid_check=lambda x: x and not x.startswith('Horse '))
        self._check_field('program_number', horse.program_number, required=True,
                         valid_check=lambda x: x and x.strip())

        # Personnel fields
        self._check_field('jockey_name', horse.jockey_name, required=True,
                         valid_check=lambda x: x and x != 'Unknown')
        self._check_field('trainer_name', horse.trainer_name, required=True,
                         valid_check=lambda x: x and x != 'Unknown')

        # Odds and ratings
        ml_odds = getattr(horse, 'morning_line_odds', getattr(horse, 'ml_odds', None))
        def is_valid_odds(x):
            if x is None:
                return False
            # Handle numeric values
            if isinstance(x, (int, float)):
                return x > 0
            # Handle string values (e.g., "5-2", "3.50")
            if isinstance(x, str):
                return x.strip() and x != 'Unknown'
            return False
        self._check_field('morning_line_odds', ml_odds, required=True, valid_check=is_valid_odds)

        # Speed figures
        best_beyer = getattr(horse, 'best_speed_figure', getattr(horse, 'best_beyer', None))
        def is_valid_beyer(x):
            if x is None:
                return False
            # Handle numeric values
            if isinstance(x, (int, float)):
                return x > 0
            # Handle string values
            if isinstance(x, str):
                try:
                    return float(x) > 0
                except (ValueError, TypeError):
                    return False
            return False
        self._check_field('best_beyer', best_beyer, required=True, valid_check=is_valid_beyer)

        # Running style
        style = getattr(horse, 'running_style', None)
        self._check_field('running_style', style, required=True,
                         valid_check=lambda x: x and x in ['E', 'P', 'S', 'C'])

        # Past performances
        pps = getattr(horse, 'past_performances', [])
        self._check_field('past_performances_count', len(pps), required=True,
                         valid_check=lambda x: x >= 3)  # At least 3 PPs expected

        # If we have PPs, check their completeness
        if pps and len(pps) > 0:
            self._assess_past_performances(pps)

        # Equipment
        today_equip = getattr(horse, 'today_equipment', None)
        self._check_field('today_equipment', today_equip, required=False,
                         valid_check=lambda x: x is not None and isinstance(x, dict))

        # Workouts
        workouts = getattr(horse, 'workouts', getattr(horse, 'recent_workouts', None))
        self._check_field('workouts', workouts, required=False,
                         valid_check=lambda x: x is not None)

    def _assess_past_performances(self, pps: List[Any]):
        """Assess PP data completeness"""
        if not pps:
            return

        # Check first PP for detailed data
        pp = pps[0]

        if isinstance(pp, dict):
            # Check for call positions (critical for pace analysis)
            self._check_field('pp_first_call', pp.get('first_call'), required=True,
                             valid_check=lambda x: x is not None)
            self._check_field('pp_second_call', pp.get('second_call'), required=True,
                             valid_check=lambda x: x is not None)
            self._check_field('pp_stretch', pp.get('stretch'), required=True,
                             valid_check=lambda x: x is not None)
            self._check_field('pp_finish', pp.get('finish'), required=True,
                             valid_check=lambda x: x is not None)

            # Check for fractional times (critical for pace analysis)
            frac_times = pp.get('fractional_times', [])
            self._check_field('pp_fractional_times', frac_times, required=True,
                             valid_check=lambda x: x and len(x) > 0)

            # Check for speed figure in PP
            speed_fig = pp.get('speed_figure', pp.get('beyer'))
            def is_valid_pp_beyer(x):
                if x is None:
                    return False
                if isinstance(x, (int, float)):
                    return x > 0
                if isinstance(x, str):
                    try:
                        return float(x) > 0
                    except (ValueError, TypeError):
                        return False
                return False
            self._check_field('pp_speed_figure', speed_fig, required=True, valid_check=is_valid_pp_beyer)

            # Check for distance and surface
            self._check_field('pp_distance', pp.get('distance'), required=True,
                             valid_check=lambda x: x is not None and x.strip())
            self._check_field('pp_surface', pp.get('surface'), required=True,
                             valid_check=lambda x: x is not None and x.strip())

    def _check_field(self, field_name: str, value: Any, required: bool, valid_check=None):
        """Check if a field was extracted and is valid"""
        if field_name not in self.field_stats:
            self.field_stats[field_name] = FieldExtraction(field_name)

        stats = self.field_stats[field_name]
        stats.total_horses += 1

        # Check if extracted
        if value is None or (isinstance(value, str) and not value.strip()):
            stats.missing += 1
        elif valid_check:
            try:
                if not valid_check(value):
                    stats.partial += 1
                else:
                    stats.extracted += 1
            except (TypeError, ValueError):
                # If validation fails due to type mismatch, mark as partial
                stats.partial += 1
        else:
            stats.extracted += 1

    def _generate_report(self):
        """Generate comprehensive extraction report"""
        print()
        print("=" * 80)
        print(" DATA EXTRACTION COMPLETENESS REPORT")
        print("=" * 80)
        print()

        # Group fields by category
        core_fields = ['horse_name', 'program_number', 'jockey_name', 'trainer_name', 'morning_line_odds']
        rating_fields = ['best_beyer', 'running_style']
        pp_fields = ['past_performances_count', 'pp_first_call', 'pp_second_call',
                     'pp_stretch', 'pp_finish', 'pp_fractional_times', 'pp_speed_figure',
                     'pp_distance', 'pp_surface']
        optional_fields = ['today_equipment', 'workouts']

        total_horses = max([stats.total_horses for stats in self.field_stats.values()], default=0)

        print(f"📊 Total Horses Analyzed: {total_horses}")
        print()

        # Core fields (must be 100%)
        print("🔴 CRITICAL FIELDS (Target: 100%)")
        print("-" * 80)
        for field in core_fields:
            if field in self.field_stats:
                stats = self.field_stats[field]
                status = "✅" if stats.extraction_rate >= 95 else "⚠️" if stats.extraction_rate >= 80 else "❌"
                print(f"{status} {field:25s}: {stats.extraction_rate:5.1f}% ({stats.extracted}/{stats.total_horses})")
        print()

        # Rating fields (should be >90%)
        print("🟡 RATING FIELDS (Target: 90%+)")
        print("-" * 80)
        for field in rating_fields:
            if field in self.field_stats:
                stats = self.field_stats[field]
                status = "✅" if stats.extraction_rate >= 90 else "⚠️" if stats.extraction_rate >= 70 else "❌"
                print(f"{status} {field:25s}: {stats.extraction_rate:5.1f}% ({stats.extracted}/{stats.total_horses})")
        print()

        # PP fields (critical for pace analysis)
        print("🔵 PAST PERFORMANCE FIELDS (Target: 90%+)")
        print("-" * 80)
        for field in pp_fields:
            if field in self.field_stats:
                stats = self.field_stats[field]
                comp_rate = stats.completeness_rate if stats.partial > 0 else stats.extraction_rate
                status = "✅" if comp_rate >= 90 else "⚠️" if comp_rate >= 70 else "❌"

                if stats.partial > 0:
                    print(f"{status} {field:25s}: {comp_rate:5.1f}% ({stats.extracted}+{stats.partial}/{stats.total_horses})")
                else:
                    print(f"{status} {field:25s}: {stats.extraction_rate:5.1f}% ({stats.extracted}/{stats.total_horses})")
        print()

        # Optional fields
        print("🟢 OPTIONAL FIELDS")
        print("-" * 80)
        for field in optional_fields:
            if field in self.field_stats:
                stats = self.field_stats[field]
                print(f"   {field:25s}: {stats.extraction_rate:5.1f}% ({stats.extracted}/{stats.total_horses})")
        print()

        # Overall assessment
        critical_fields = core_fields + rating_fields + pp_fields
        critical_stats = [self.field_stats[f] for f in critical_fields if f in self.field_stats]

        if critical_stats:
            avg_extraction = sum(s.extraction_rate for s in critical_stats) / len(critical_stats)
            avg_completeness = sum(s.completeness_rate for s in critical_stats) / len(critical_stats)

            print("=" * 80)
            print(" OVERALL ASSESSMENT")
            print("=" * 80)
            print()
            print(f"Average Extraction Rate: {avg_extraction:.1f}%")
            print(f"Average Completeness Rate (inc. partial): {avg_completeness:.1f}%")
            print()

            if avg_extraction >= 95:
                print("✅ EXCELLENT - Parser extracting 95%+ of critical data")
            elif avg_extraction >= 90:
                print("✅ GOOD - Parser extracting 90%+ of critical data")
            elif avg_extraction >= 80:
                print("⚠️  FAIR - Parser extracting 80%+ but needs improvement")
            else:
                print("❌ POOR - Parser extracting <80% of critical data")

            print()

            # Identify problem areas
            problem_fields = [s for s in critical_stats if s.extraction_rate < 90]
            if problem_fields:
                print("⚠️  FIELDS NEEDING IMPROVEMENT:")
                for stats in sorted(problem_fields, key=lambda x: x.extraction_rate):
                    print(f"   • {stats.field_name}: {stats.extraction_rate:.1f}% extraction")
            else:
                print("🎯 All critical fields extracting at 90%+!")

        print()
        print("=" * 80)

        # Save detailed report
        report_data = {
            'total_horses': total_horses,
            'field_stats': {
                name: {
                    'total': stats.total_horses,
                    'extracted': stats.extracted,
                    'partial': stats.partial,
                    'missing': stats.missing,
                    'extraction_rate': stats.extraction_rate,
                    'completeness_rate': stats.completeness_rate
                }
                for name, stats in self.field_stats.items()
            },
            'overall': {
                'avg_extraction_rate': avg_extraction if critical_stats else 0,
                'avg_completeness_rate': avg_completeness if critical_stats else 0
            }
        }

        output_file = 'output/parser_accuracy_report.json'
        with open(output_file, 'w') as f:
            json.dump(report_data, f, indent=2)

        print(f"📄 Detailed report saved to: {output_file}")
        print()


if __name__ == '__main__':
    assessor = ParserAccuracyAssessment()
    assessor.assess_all_pdfs()
