"""
Results Validation Framework
Parses actual race results and compares to model predictions

This framework:
1. Parses results PDFs to extract actual winners
2. Compares predictions to actual outcomes
3. Calculates accuracy metrics (win rate, top-3 rate, ROI)
4. Generates detailed performance reports
"""

import os
import re
import json
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
import pdfplumber


@dataclass
class RaceResult:
    """Actual race result from results PDF"""
    date: str
    track: str
    race_number: int
    winner_pgm: str
    winner_name: str
    winner_jockey: str
    winner_trainer: str
    win_payoff: Optional[float] = None

    # Top finishers
    second_place: Optional[str] = None
    third_place: Optional[str] = None

    # Exacta/Trifecta payoffs
    exacta_payoff: Optional[float] = None
    trifecta_payoff: Optional[float] = None


@dataclass
class PredictionResult:
    """Comparison of prediction to actual result"""
    date: str
    race_number: int

    # Predicted top 5
    predicted_winner: str
    predicted_winner_pgm: str
    predicted_top_5: List[Tuple[str, str]]  # [(pgm, name), ...]

    # Actual result
    actual_winner: str
    actual_winner_pgm: str

    # Hit metrics
    win_hit: bool
    top_3_hit: bool
    top_5_hit: bool

    # Winner info
    winner_rank: Optional[int]  # Where winner was in our predictions
    winner_probability: Optional[float]  # Our win probability for winner

    # Payoffs (if available)
    win_payoff: Optional[float] = None
    our_odds: Optional[float] = None  # Our predicted fair odds
    edge: Optional[float] = None  # Our edge on the winner


class ResultsValidator:
    """Validates predictions against actual race results"""

    def __init__(self, results_dir: str = 'data/Results Files'):
        """
        Initialize results validator

        Args:
            results_dir: Directory containing results PDF files
        """
        self.results_dir = results_dir

    def parse_results_pdf(self, pdf_path: str) -> List[RaceResult]:
        """
        Parse a results PDF file to extract race outcomes

        Args:
            pdf_path: Path to results PDF

        Returns:
            List of RaceResult objects
        """
        results = []

        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if not text:
                    continue

                # Extract race results from this page
                page_results = self._extract_results_from_text(text, pdf_path)
                results.extend(page_results)

        return results

    def _extract_results_from_text(self, text: str, pdf_path: str) -> List[RaceResult]:
        """
        Extract race results from PDF text

        Args:
            text: Extracted PDF text
            pdf_path: Path to PDF (for date extraction)

        Returns:
            List of RaceResult objects from this text
        """
        results = []

        # Extract date from filename (e.g., KEE101825USA.pdf -> 10-18-25 -> 2025-10-18)
        filename = os.path.basename(pdf_path)
        date_match = re.search(r'KEE(\d{2})(\d{2})(\d{2})', filename)
        if date_match:
            month, day, year = date_match.groups()
            date_str = f"2025-{month}-{day}"
        else:
            date_str = "2025-10-01"  # Default

        # Split text into lines
        lines = text.split('\n')

        # Find race headers and extract results
        i = 0
        while i < len(lines):
            line = lines[i]

            # Look for race header: "KEENELAND ... Race N"
            race_match = re.search(r'KEENELAND.*?Race\s*(\d+)', line, re.IGNORECASE)

            if race_match:
                race_num = int(race_match.group(1))

                # Extract winner info from subsequent lines
                winner_info = self._extract_winner_from_lines(lines[i:i+50])

                if winner_info:
                    result = RaceResult(
                        date=date_str,
                        track='KEE',
                        race_number=race_num,
                        winner_pgm=winner_info['pgm'],
                        winner_name=winner_info['name'],
                        winner_jockey=winner_info.get('jockey', 'Unknown'),
                        winner_trainer=winner_info.get('trainer', 'Unknown'),
                        win_payoff=winner_info.get('payoff'),
                        second_place=winner_info.get('second'),
                        third_place=winner_info.get('third')
                    )
                    results.append(result)

            i += 1

        return results

    def _extract_winner_from_lines(self, lines: List[str]) -> Optional[Dict]:
        """
        Extract winner information from race result lines

        Args:
            lines: Lines of text from race section

        Returns:
            Dict with winner info, or None if not found
        """
        # Look for "Winner:" line
        for i, line in enumerate(lines[:30]):
            if 'Winner:' in line or 'winner:' in line.lower():
                # Winner format: "Winner: Horse Name, Jockey Name"
                match = re.search(r'Winner:\s+([^,]+),\s*(.+)', line, re.IGNORECASE)
                if match:
                    winner_name = match.group(1).strip()
                    jockey_name = match.group(2).strip()

                    # Try to find program number (usually in results table above)
                    pgm = self._find_program_number(lines[:i], winner_name)

                    return {
                        'name': winner_name,
                        'pgm': pgm or '1',
                        'jockey': jockey_name,
                        'trainer': 'Unknown'
                    }

        # Alternative: Look for results table
        # Format: "Pgm  Horse Name              Jockey              Trainer"
        for i, line in enumerate(lines[:30]):
            if 'Pgm' in line and 'Horse' in line:
                # Next line should be first finisher (winner)
                if i + 1 < len(lines):
                    result_line = lines[i + 1]
                    # Parse: "1    Horse Name             Jockey Name         Trainer Name"
                    parts = result_line.split()
                    if len(parts) >= 2:
                        pgm = parts[0]
                        # Horse name is usually 2-4 words
                        name_parts = []
                        for j in range(1, min(5, len(parts))):
                            if parts[j][0].isupper():
                                name_parts.append(parts[j])
                            else:
                                break

                        if name_parts:
                            return {
                                'name': ' '.join(name_parts),
                                'pgm': pgm,
                                'jockey': 'Unknown',
                                'trainer': 'Unknown'
                            }

        return None

    def _find_program_number(self, lines: List[str], horse_name: str) -> Optional[str]:
        """
        Find program number for a horse in results table

        Args:
            lines: Lines to search
            horse_name: Horse name to find

        Returns:
            Program number string, or None
        """
        for line in lines:
            if horse_name.lower() in line.lower():
                # Try to extract leading number
                match = re.match(r'^\s*(\d+[A-Z]?)\s+', line)
                if match:
                    return match.group(1)

        return None

    def compare_prediction_to_result(
        self,
        prediction: Dict,
        result: RaceResult
    ) -> PredictionResult:
        """
        Compare a prediction to actual race result

        Args:
            prediction: Prediction dict from predict_from_pdf.py
            result: Actual race result

        Returns:
            PredictionResult with comparison metrics
        """
        # Extract our top 5 predictions
        predictions_list = prediction.get('predictions', [])

        if not predictions_list:
            # Return empty result
            return PredictionResult(
                date=result.date,
                race_number=result.race_number,
                predicted_winner='None',
                predicted_winner_pgm='0',
                predicted_top_5=[],
                actual_winner=result.winner_name,
                actual_winner_pgm=result.winner_pgm,
                win_hit=False,
                top_3_hit=False,
                top_5_hit=False,
                winner_rank=None,
                winner_probability=None
            )

        # Get our top pick
        top_pick = predictions_list[0]
        predicted_winner_name = top_pick.get('horse_name', '')
        predicted_winner_pgm = top_pick.get('program_number', '0')

        # Get top 5
        top_5 = []
        for i in range(min(5, len(predictions_list))):
            pred = predictions_list[i]
            top_5.append((
                pred.get('program_number', '0'),
                pred.get('horse_name', '')
            ))

        # Find where actual winner was in our predictions
        winner_rank = None
        winner_probability = None

        for i, pred in enumerate(predictions_list, 1):
            pred_name = pred.get('horse_name', '').lower().strip()
            result_name = result.winner_name.lower().strip()

            # Fuzzy name matching (handle minor differences)
            if self._names_match(pred_name, result_name):
                winner_rank = i
                winner_probability = pred.get('probability', 0.0)
                break

        # Calculate hits
        win_hit = (winner_rank == 1)
        top_3_hit = (winner_rank is not None and winner_rank <= 3)
        top_5_hit = (winner_rank is not None and winner_rank <= 5)

        return PredictionResult(
            date=result.date,
            race_number=result.race_number,
            predicted_winner=predicted_winner_name,
            predicted_winner_pgm=predicted_winner_pgm,
            predicted_top_5=top_5,
            actual_winner=result.winner_name,
            actual_winner_pgm=result.winner_pgm,
            win_hit=win_hit,
            top_3_hit=top_3_hit,
            top_5_hit=top_5_hit,
            winner_rank=winner_rank,
            winner_probability=winner_probability,
            win_payoff=result.win_payoff
        )

    def _names_match(self, name1: str, name2: str) -> bool:
        """
        Check if two horse names match (with fuzzy matching)

        Args:
            name1: First name
            name2: Second name

        Returns:
            True if names match
        """
        # Exact match
        if name1 == name2:
            return True

        # Remove common differences
        clean1 = re.sub(r'[^\w\s]', '', name1).strip()
        clean2 = re.sub(r'[^\w\s]', '', name2).strip()

        if clean1 == clean2:
            return True

        # Remove all whitespace and compare (handles "Golden Irish" vs "GoldenIrish")
        no_space1 = clean1.replace(' ', '').lower()
        no_space2 = clean2.replace(' ', '').lower()

        if no_space1 == no_space2:
            return True

        # Check if one is substring of other (handles "Indy Magic" vs "Indy Magic (L)")
        if clean1 in clean2 or clean2 in clean1:
            return True

        # Word-based matching (at least 2 words match)
        words1 = set(clean1.split())
        words2 = set(clean2.split())

        if len(words1) >= 2 and len(words2) >= 2:
            overlap = len(words1 & words2)
            if overlap >= 2:
                return True

        return False

    def generate_validation_report(
        self,
        comparisons: List[PredictionResult]
    ) -> Dict:
        """
        Generate validation report from comparisons

        Args:
            comparisons: List of prediction vs result comparisons

        Returns:
            Report dict with accuracy metrics
        """
        total_races = len(comparisons)

        if total_races == 0:
            return {
                'total_races': 0,
                'win_rate': 0.0,
                'top_3_rate': 0.0,
                'top_5_rate': 0.0,
                'average_winner_rank': 0.0,
                'comparisons': []
            }

        # Calculate metrics
        wins = sum(1 for c in comparisons if c.win_hit)
        top_3 = sum(1 for c in comparisons if c.top_3_hit)
        top_5 = sum(1 for c in comparisons if c.top_5_hit)

        # Average winner rank (only for races where we had winner)
        winner_ranks = [c.winner_rank for c in comparisons if c.winner_rank is not None]
        avg_winner_rank = sum(winner_ranks) / len(winner_ranks) if winner_ranks else 99.0

        # Calculate ROI (if payoffs available)
        total_bet = total_races * 2.0  # $2 per race
        total_return = 0.0
        roi_races = 0

        for c in comparisons:
            if c.win_hit and c.win_payoff:
                total_return += c.win_payoff
                roi_races += 1

        roi = ((total_return - (roi_races * 2.0)) / (roi_races * 2.0) * 100) if roi_races > 0 else 0.0

        return {
            'total_races': total_races,
            'win_rate': wins / total_races * 100,
            'top_3_rate': top_3 / total_races * 100,
            'top_5_rate': top_5 / total_races * 100,
            'average_winner_rank': avg_winner_rank,
            'roi': roi,
            'roi_races': roi_races,
            'total_bet': total_bet,
            'total_return': total_return,
            'comparisons': [asdict(c) for c in comparisons]
        }

    def print_report(self, report: Dict):
        """
        Print formatted validation report

        Args:
            report: Report dict from generate_validation_report
        """
        print("\n" + "="*80)
        print(" PREDICTION VALIDATION REPORT")
        print("="*80)
        print()

        print(f"Total Races Analyzed: {report['total_races']}")
        print()

        print("ACCURACY METRICS:")
        print("-"*80)
        print(f"  Win Rate (Top Pick):  {report['win_rate']:.1f}%")
        print(f"  Top-3 Hit Rate:       {report['top_3_rate']:.1f}%")
        print(f"  Top-5 Hit Rate:       {report['top_5_rate']:.1f}%")
        print(f"  Average Winner Rank:  {report['average_winner_rank']:.1f}")
        print()

        if report['roi_races'] > 0:
            print("ROI ANALYSIS (Win Bets Only):")
            print("-"*80)
            print(f"  Races with Payoff Data: {report['roi_races']}")
            print(f"  Total Bet:  ${report['total_bet']:.2f}")
            print(f"  Total Return: ${report['total_return']:.2f}")
            print(f"  ROI: {report['roi']:+.1f}%")
            print()

        # Show individual race results
        print("DETAILED RESULTS:")
        print("-"*80)

        for comp in report['comparisons']:
            status = "✓ WIN" if comp['win_hit'] else "✗ MISS"
            if not comp['win_hit'] and comp['top_3_hit']:
                status = "△ TOP-3"
            elif not comp['win_hit'] and comp['top_5_hit']:
                status = "○ TOP-5"

            print(f"{comp['date']} Race {comp['race_number']:2d}: {status}")
            print(f"  Predicted: #{comp['predicted_winner_pgm']} {comp['predicted_winner']}")
            print(f"  Actual:    #{comp['actual_winner_pgm']} {comp['actual_winner']}")

            if comp['winner_rank']:
                print(f"  Winner was our #{comp['winner_rank']} pick ({comp['winner_probability']*100:.1f}% probability)")
            else:
                print(f"  Winner not in our predictions")

            print()

        print("="*80)


# Quick test
if __name__ == "__main__":
    print("Testing Results Validator...")
    print("="*70)

    validator = ResultsValidator()

    # Test parsing a results file
    results_file = 'data/Results Files/KEE101825USA.pdf'

    if os.path.exists(results_file):
        print(f"\nParsing: {results_file}")
        results = validator.parse_results_pdf(results_file)

        print(f"\nExtracted {len(results)} race results:")
        for result in results[:3]:  # Show first 3
            print(f"  Race {result.race_number}: #{result.winner_pgm} {result.winner_name}")
    else:
        print(f"\n✗ Results file not found: {results_file}")

    print("\n✓ Results Validator ready for use!")
    print("="*70)
