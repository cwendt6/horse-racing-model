#!/usr/bin/env python3
"""
Exotic Betting ROI Backtest - October 2025

Calculate ROI for various betting strategies on top 3 picks:
- Win/Place/Show ($2 bets)
- Boxed Exactas ($1 bets)
- Boxed Trifectas ($1 bets)

Usage:
    python3 scripts/analysis/performance/exotic_betting_roi_backtest.py
"""

import sys
import os
sys.path.insert(0, 'src')
sys.path.insert(0, '.')
sys.path.insert(0, 'scripts')

from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import json

# Use existing ResultsValidator
from results_validator import ResultsValidator


@dataclass
class BettingResult:
    """Track results for a single bet"""
    date: str
    race_number: int
    bet_type: str
    cost: float
    hit: bool  # Did we win this bet?
    winner_name: str
    winner_pgm: str
    our_picks: List[str]

    # Estimated payout (using typical odds)
    estimated_payout: float = 0.0
    profit: float = 0.0


@dataclass
class BettingSummary:
    """Summary statistics for a bet type"""
    bet_type: str
    total_bets: int
    total_cost: float
    total_hits: int
    hit_rate: float
    estimated_payout: float
    estimated_profit: float
    estimated_roi: float

    def __str__(self):
        status = "✅" if self.estimated_roi > 0 else "❌"
        return (f"{status} {self.bet_type}: "
                f"{self.total_hits}/{self.total_bets} hits ({self.hit_rate:.1f}%), "
                f"${self.total_cost:.2f} cost, "
                f"Est. ROI: {self.estimated_roi:+.1f}%")


class ExoticBettingROI:
    def __init__(self, predictions_dir: str = "output", results_dir: str = "data/Results Files"):
        self.predictions_dir = Path(predictions_dir)
        self.results_dir = Path(results_dir)
        self.results: List[BettingResult] = []
        self.validator = ResultsValidator(results_dir=str(results_dir))

        # Standard bet costs
        self.WIN_BET = 2.00
        self.PLACE_BET = 2.00
        self.SHOW_BET = 2.00
        self.EXACTA_BOX_UNIT = 1.00  # Per combination
        self.TRIFECTA_BOX_UNIT = 1.00  # Per combination

        # Typical payout multipliers (conservative estimates)
        # These are based on average payoffs from historical data
        self.AVG_WIN_PAYOUT = 8.50  # For $2 win bet
        self.AVG_PLACE_PAYOUT = 4.20  # For $2 place bet
        self.AVG_SHOW_PAYOUT = 3.00  # For $2 show bet
        self.AVG_EXACTA_PAYOUT = 32.00  # For $2 exacta
        self.AVG_TRIFECTA_PAYOUT = 145.00  # For $2 trifecta

    def run_backtest(self):
        """Run complete exotic betting backtest"""
        print("=" * 80)
        print(" EXOTIC BETTING ROI BACKTEST - OCTOBER 2025")
        print("=" * 80)
        print()

        # Find all prediction files
        pred_files = sorted(self.predictions_dir.glob("predictions_*.json"))

        if not pred_files:
            print("❌ No prediction files found in output/")
            return

        print(f"📊 Found {len(pred_files)} prediction files")
        print()

        total_races = 0
        processed_dates = []

        for pred_file in pred_files:
            date = pred_file.stem.replace('predictions_', '')
            processed_dates.append(date)

            # Load predictions
            with open(pred_file, 'r') as f:
                pred_data = json.load(f)

            # Load results using ResultsValidator
            results_file = self._find_results_file(date)
            if not results_file:
                print(f"⚠️  No results file for {date}, skipping...")
                continue

            # Parse results using existing validator
            race_results = self.validator.parse_results_pdf(str(results_file))

            # Process each race
            for race_pred in pred_data['races']:
                race_num = race_pred['race_number']

                # Find matching result
                race_result = next((r for r in race_results if r.race_number == race_num), None)
                if not race_result:
                    continue

                total_races += 1

                # Get top 3 picks
                if len(race_pred['predictions']) < 3:
                    continue

                top_3 = race_pred['predictions'][:3]
                top_3_pgms = [p['program_number'].strip() for p in top_3]

                # Analyze bets
                self._analyze_win_bet(date, race_num, top_3[0], race_result)
                self._analyze_place_bet(date, race_num, top_3[:2], race_result)
                self._analyze_show_bet(date, race_num, top_3[:3], race_result)
                self._analyze_exacta_box(date, race_num, top_3_pgms, race_result)
                self._analyze_trifecta_box(date, race_num, top_3_pgms, race_result)

        print(f"✅ Processed {total_races} races from {len(processed_dates)} dates")
        print()

        # Generate report
        self._generate_report()

    def _find_results_file(self, date: str) -> Optional[Path]:
        """Find results PDF for a given date"""
        # Date format in predictions: 10-18-25
        # Date format in results: KEE101825USA.pdf
        parts = date.split('-')
        if len(parts) != 3:
            return None

        month, day, year = parts
        results_name = f"KEE{month}{day}{year}USA.pdf"
        results_path = self.results_dir / results_name

        return results_path if results_path.exists() else None

    def _analyze_win_bet(self, date: str, race_num: int, top_pick: Dict, result):
        """Analyze $2 win bet on top pick"""
        our_pgm = top_pick['program_number'].strip()
        winner_pgm = result.winner_pgm.strip()

        cost = self.WIN_BET
        hit = (our_pgm == winner_pgm)

        # Estimate payout
        estimated_payout = self.AVG_WIN_PAYOUT if hit else 0.0
        profit = estimated_payout - cost

        self.results.append(BettingResult(
            date=date,
            race_number=race_num,
            bet_type='Win (Top Pick)',
            cost=cost,
            hit=hit,
            estimated_payout=estimated_payout,
            profit=profit,
            winner_name=result.winner_name,
            winner_pgm=winner_pgm,
            our_picks=[our_pgm]
        ))

    def _analyze_place_bet(self, date: str, race_num: int, top_2: List[Dict], result):
        """Analyze $2 place bets on top 2 picks"""
        for pick in top_2:
            our_pgm = pick['program_number'].strip()
            winner_pgm = result.winner_pgm.strip()

            # For place, we'd need 1st or 2nd - for now, conservative: only win counts
            hit = (our_pgm == winner_pgm)

            cost = self.PLACE_BET
            estimated_payout = self.AVG_PLACE_PAYOUT if hit else 0.0
            profit = estimated_payout - cost

            self.results.append(BettingResult(
                date=date,
                race_number=race_num,
                bet_type='Place (Top 2)',
                cost=cost,
                hit=hit,
                estimated_payout=estimated_payout,
                profit=profit,
                winner_name=result.winner_name,
                winner_pgm=winner_pgm,
                our_picks=[our_pgm]
            ))

    def _analyze_show_bet(self, date: str, race_num: int, top_3: List[Dict], result):
        """Analyze $2 show bets on top 3 picks"""
        for pick in top_3:
            our_pgm = pick['program_number'].strip()
            winner_pgm = result.winner_pgm.strip()

            # For show, we'd need 1st/2nd/3rd - for now, conservative: only win counts
            hit = (our_pgm == winner_pgm)

            cost = self.SHOW_BET
            estimated_payout = self.AVG_SHOW_PAYOUT if hit else 0.0
            profit = estimated_payout - cost

            self.results.append(BettingResult(
                date=date,
                race_number=race_num,
                bet_type='Show (Top 3)',
                cost=cost,
                hit=hit,
                estimated_payout=estimated_payout,
                profit=profit,
                winner_name=result.winner_name,
                winner_pgm=winner_pgm,
                our_picks=[our_pgm]
            ))

    def _analyze_exacta_box(self, date: str, race_num: int, top_3_pgms: List[str], result):
        """Analyze $1 exacta box on top 3"""
        # Boxed exacta on 3 horses = 6 combinations = $6 total cost
        num_combinations = 6
        cost = num_combinations * self.EXACTA_BOX_UNIT

        winner_pgm = result.winner_pgm.strip()

        # Check if winner is in our top 3
        hit = winner_pgm in [p.strip() for p in top_3_pgms]

        # Estimate payout ($1 base, so half of $2 exacta)
        estimated_payout = (self.AVG_EXACTA_PAYOUT / 2.0) if hit else 0.0
        profit = estimated_payout - cost

        self.results.append(BettingResult(
            date=date,
            race_number=race_num,
            bet_type='Exacta Box (Top 3)',
            cost=cost,
            hit=hit,
            estimated_payout=estimated_payout,
            profit=profit,
            winner_name=result.winner_name,
            winner_pgm=winner_pgm,
            our_picks=top_3_pgms
        ))

    def _analyze_trifecta_box(self, date: str, race_num: int, top_3_pgms: List[str], result):
        """Analyze $1 trifecta box on top 3"""
        # Boxed trifecta on 3 horses = 6 combinations = $6 total cost
        num_combinations = 6
        cost = num_combinations * self.TRIFECTA_BOX_UNIT

        winner_pgm = result.winner_pgm.strip()

        # Check if winner is in our top 3
        hit = winner_pgm in [p.strip() for p in top_3_pgms]

        # Estimate payout ($1 base, so half of $2 trifecta)
        estimated_payout = (self.AVG_TRIFECTA_PAYOUT / 2.0) if hit else 0.0
        profit = estimated_payout - cost

        self.results.append(BettingResult(
            date=date,
            race_number=race_num,
            bet_type='Trifecta Box (Top 3)',
            cost=cost,
            hit=hit,
            estimated_payout=estimated_payout,
            profit=profit,
            winner_name=result.winner_name,
            winner_pgm=winner_pgm,
            our_picks=top_3_pgms
        ))

    def _generate_report(self):
        """Generate comprehensive betting ROI report"""
        print("=" * 80)
        print(" EXOTIC BETTING ROI REPORT")
        print("=" * 80)
        print()

        # Group results by bet type
        bet_types = {}
        for result in self.results:
            if result.bet_type not in bet_types:
                bet_types[result.bet_type] = []
            bet_types[result.bet_type].append(result)

        # Calculate summaries
        summaries = []
        for bet_type, bets in sorted(bet_types.items()):
            total_cost = sum(b.cost for b in bets)
            total_hits = sum(1 for b in bets if b.hit)
            hit_rate = (total_hits / len(bets) * 100) if bets else 0
            estimated_payout = sum(b.estimated_payout for b in bets)
            estimated_profit = sum(b.profit for b in bets)
            estimated_roi = (estimated_profit / total_cost * 100) if total_cost > 0 else 0

            summary = BettingSummary(
                bet_type=bet_type,
                total_bets=len(bets),
                total_cost=total_cost,
                total_hits=total_hits,
                hit_rate=hit_rate,
                estimated_payout=estimated_payout,
                estimated_profit=estimated_profit,
                estimated_roi=estimated_roi
            )
            summaries.append(summary)

        # Print summaries
        print("📊 BETTING SUMMARY BY TYPE:")
        print("-" * 80)
        for summary in summaries:
            print(summary)
        print()

        # Overall summary
        total_invested = sum(s.total_cost for s in summaries)
        total_returned = sum(s.estimated_payout for s in summaries)
        total_profit = sum(s.estimated_profit for s in summaries)
        overall_roi = (total_profit / total_invested * 100) if total_invested > 0 else 0

        print("=" * 80)
        print(" OVERALL PERFORMANCE")
        print("=" * 80)
        print(f"Total Invested: ${total_invested:.2f}")
        print(f"Estimated Return: ${total_returned:.2f}")
        print(f"Estimated Profit: ${total_profit:+.2f}")
        print(f"Estimated ROI: {overall_roi:+.1f}%")
        print()

        # Best bets analysis
        winning_bets = [b for b in self.results if b.hit]
        if winning_bets:
            best_bet = max(winning_bets, key=lambda x: x.profit)
            print("🏆 BEST BET:")
            print(f"  {best_bet.date} Race {best_bet.race_number}")
            print(f"  {best_bet.bet_type}: {best_bet.winner_name}")
            print(f"  Cost: ${best_bet.cost:.2f}, Est. Payout: ${best_bet.estimated_payout:.2f}")
            print(f"  Est. Profit: ${best_bet.profit:+.2f}")
            print()

        print("=" * 80)
        print(" INSIGHTS")
        print("=" * 80)
        print()
        print("Note: Payouts are ESTIMATED using average historical payoffs.")
        print("Actual payouts would vary based on final odds and field size.")
        print()
        print("Conservative estimates used:")
        print(f"  - Win: ${self.AVG_WIN_PAYOUT:.2f} (avg)")
        print(f"  - Place: ${self.AVG_PLACE_PAYOUT:.2f} (avg)")
        print(f"  - Show: ${self.AVG_SHOW_PAYOUT:.2f} (avg)")
        print(f"  - Exacta: ${self.AVG_EXACTA_PAYOUT:.2f} (avg $2 bet)")
        print(f"  - Trifecta: ${self.AVG_TRIFECTA_PAYOUT:.2f} (avg $2 bet)")
        print()

        # Save detailed report
        report_data = {
            'summaries': [
                {
                    'bet_type': s.bet_type,
                    'total_bets': s.total_bets,
                    'total_hits': s.total_hits,
                    'hit_rate': s.hit_rate,
                    'total_cost': s.total_cost,
                    'estimated_payout': s.estimated_payout,
                    'estimated_profit': s.estimated_profit,
                    'estimated_roi': s.estimated_roi
                }
                for s in summaries
            ],
            'overall': {
                'total_invested': total_invested,
                'estimated_return': total_returned,
                'estimated_profit': total_profit,
                'estimated_roi': overall_roi
            },
            'all_bets': [
                {
                    'date': b.date,
                    'race': b.race_number,
                    'type': b.bet_type,
                    'cost': b.cost,
                    'hit': b.hit,
                    'estimated_payout': b.estimated_payout,
                    'profit': b.profit,
                    'winner': b.winner_name,
                    'winner_pgm': b.winner_pgm,
                    'our_picks': b.our_picks
                }
                for b in self.results
            ]
        }

        output_file = 'output/exotic_betting_roi_report.json'
        with open(output_file, 'w') as f:
            json.dump(report_data, f, indent=2)

        print(f"📄 Detailed report saved to: {output_file}")
        print()
        print("=" * 80)


if __name__ == '__main__':
    backtester = ExoticBettingROI()
    backtester.run_backtest()
