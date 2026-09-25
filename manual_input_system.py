"""
Manual Input System for Race Day Updates
Simple CLI for updating predictions with live data
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
from dataclasses import dataclass


# ============================================================================
# DATA MODELS
# ============================================================================

class UpdateType(Enum):
    """Types of manual updates"""
    LIVE_ODDS = "live_odds"
    SCRATCH = "scratch"
    TRACK_CONDITION = "track_condition"
    JOCKEY_CHANGE = "jockey_change"
    EQUIPMENT_CHANGE = "equipment_change"


@dataclass
class ManualUpdate:
    """Record of a manual update"""
    race_number: int
    horse_name: Optional[str]
    update_type: UpdateType
    old_value: Any
    new_value: Any
    timestamp: datetime
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            'race_number': self.race_number,
            'horse_name': self.horse_name,
            'update_type': self.update_type.value,
            'old_value': str(self.old_value),
            'new_value': str(self.new_value),
            'timestamp': self.timestamp.isoformat(),
            'notes': self.notes
        }


# ============================================================================
# MAIN SYSTEM
# ============================================================================

class ManualInputSystem:
    """
    CLI system for manual updates to predictions
    """

    def __init__(self, predictions_file: str):
        self.predictions_file = Path(predictions_file)

        # Load predictions
        self.predictions = self._load_predictions()
        self.updates: List[ManualUpdate] = []

        # Create outputs directory
        self.output_dir = Path("predictions")
        self.output_dir.mkdir(exist_ok=True)

        self.updates_dir = Path("updates")
        self.updates_dir.mkdir(exist_ok=True)

    def _load_predictions(self) -> dict:
        """Load base predictions from file"""
        if not self.predictions_file.exists():
            raise FileNotFoundError(f"Predictions file not found: {self.predictions_file}")

        with open(self.predictions_file, 'r') as f:
            return json.load(f)

    def _save_predictions(self, filename: str):
        """Save updated predictions"""
        output_path = self.output_dir / filename
        with open(output_path, 'w') as f:
            json.dump(self.predictions, f, indent=2)
        print(f"✓ Saved to {output_path}")

    def _save_updates(self, filename: str):
        """Save update history"""
        updates_path = self.updates_dir / filename
        updates_data = [u.to_dict() for u in self.updates]
        with open(updates_path, 'w') as f:
            json.dump(updates_data, f, indent=2)

    def display_menu(self):
        """Show main menu"""
        print("\n" + "="*70)
        print("MANUAL INPUT SYSTEM")
        print("="*70)
        print("\n1. Update Live Odds")
        print("2. Mark Horse Scratched")
        print("3. Update Track Condition")
        print("4. View Current Predictions")
        print("5. Show Overlays")
        print("6. Save & Exit")
        print("7. Exit Without Saving")
        print("\nEnter choice (1-7): ", end="")

    def update_live_odds(self):
        """Update odds for horses in a race"""
        print("\n" + "="*70)
        print("UPDATE LIVE ODDS")
        print("="*70)

        # Show available races
        races = self.predictions.get('races', [])
        print("\nAvailable races:")
        for race in races:
            print(f"  Race {race['race_number']}: {len(race['predictions'])} horses")

        # Get race number
        race_num = int(input("\nEnter race number: "))
        race_data = next((r for r in races if r['race_number'] == race_num), None)

        if not race_data:
            print(f"❌ Race {race_num} not found")
            return

        print(f"\nRace {race_num} - {len(race_data['predictions'])} horses")
        print("\nCurrent Morning Line Odds:")

        # Show current odds
        for pred in race_data['predictions']:
            horse = pred['name']
            ml_odds = pred.get('ml_odds', pred.get('morning_line_odds', 'N/A'))
            live = pred.get('live_odds', '')
            live_str = f" → Live: {live:.1f}" if live else ""
            print(f"  #{pred['program_number']:2d} {horse:25s} ML: {ml_odds}{live_str}")

        # Get updates
        print("\nEnter live odds (format: program# odds)")
        print("Example: 4 7-2  or  4 3.5")
        print("Enter 'done' when finished")

        while True:
            entry = input("\n> ").strip().lower()

            if entry == 'done':
                break

            try:
                parts = entry.split()
                program_num = int(parts[0])

                # Parse odds (handle 7-2 or 3.5 format)
                odds_str = parts[1]
                if '-' in odds_str:
                    num, denom = map(float, odds_str.split('-'))
                    odds = num / denom
                else:
                    odds = float(odds_str)

                # Find horse
                pred = next((p for p in race_data['predictions'] if p['program_number'] == program_num), None)

                if pred:
                    old_odds = pred.get('live_odds', pred.get('ml_odds', pred.get('morning_line_odds', 'N/A')))
                    pred['live_odds'] = odds

                    # Record update
                    update = ManualUpdate(
                        race_number=race_num,
                        horse_name=pred['name'],
                        update_type=UpdateType.LIVE_ODDS,
                        old_value=old_odds,
                        new_value=odds,
                        timestamp=datetime.now()
                    )
                    self.updates.append(update)

                    print(f"  ✓ Updated #{program_num} {pred['name']}: {old_odds} → {odds:.1f}")
                else:
                    print(f"  ❌ Horse #{program_num} not found")

            except (ValueError, IndexError) as e:
                print(f"  ❌ Invalid format. Use: program# odds (e.g., 4 7-2)")

        # Recalculate overlays
        self._calculate_overlays(race_data)

        print(f"\n✓ Updated {len([u for u in self.updates if u.race_number == race_num])} odds in Race {race_num}")

    def mark_scratch(self):
        """Mark a horse as scratched"""
        print("\n" + "="*70)
        print("MARK HORSE SCRATCHED")
        print("="*70)

        # Get race and horse
        race_num = int(input("\nEnter race number: "))
        races = self.predictions.get('races', [])
        race_data = next((r for r in races if r['race_number'] == race_num), None)

        if not race_data:
            print(f"❌ Race {race_num} not found")
            return

        print(f"\nHorses in Race {race_num}:")
        for pred in race_data['predictions']:
            status = "❌ SCRATCHED" if pred.get('is_scratched') else ""
            print(f"  #{pred['program_number']:2d} {pred['name']} {status}")

        program_num = int(input("\nEnter program number to scratch: "))
        pred = next((p for p in race_data['predictions'] if p['program_number'] == program_num), None)

        if pred:
            pred['is_scratched'] = True

            update = ManualUpdate(
                race_number=race_num,
                horse_name=pred['name'],
                update_type=UpdateType.SCRATCH,
                old_value=False,
                new_value=True,
                timestamp=datetime.now()
            )
            self.updates.append(update)

            print(f"\n✓ Marked #{program_num} {pred['name']} as SCRATCHED")
            print(f"  (This will affect pace calculations and probabilities)")
        else:
            print(f"❌ Horse #{program_num} not found")

    def _calculate_overlays(self, race_data: dict):
        """Calculate overlays for a race"""
        for pred in race_data['predictions']:
            if pred.get('is_scratched'):
                continue

            live_odds = pred.get('live_odds')
            if not live_odds:
                continue

            # Calculate fair odds from win probability
            win_prob = pred.get('probability', pred.get('win_probability', 0))
            if win_prob <= 0:
                continue

            fair_odds = (1.0 / win_prob) - 1  # Convert to odds format

            # Calculate overlay
            overlay_pct = ((live_odds - fair_odds) / fair_odds) * 100

            pred['overlay_percentage'] = round(overlay_pct, 1)
            pred['is_overlay'] = overlay_pct >= 20.0
            pred['fair_odds'] = round(fair_odds, 1)

    def show_overlays(self):
        """Show all overlays across all races"""
        print("\n" + "="*70)
        print("OVERLAY OPPORTUNITIES")
        print("="*70)

        overlays_found = False

        for race_data in self.predictions.get('races', []):
            race_overlays = [p for p in race_data['predictions']
                           if p.get('is_overlay') and not p.get('is_scratched')]

            if race_overlays:
                overlays_found = True
                print(f"\nRace {race_data['race_number']}:")

                for pred in sorted(race_overlays, key=lambda p: p['overlay_percentage'], reverse=True):
                    prob = pred.get('probability', pred.get('win_probability', 0))
                    score = pred.get('total_score', 0)
                    print(f"  #{pred['program_number']:2d} {pred['name']:25s}")
                    print(f"      Live: {pred['live_odds']:.1f}-1 | Fair: {pred['fair_odds']:.1f}-1 | Overlay: {pred['overlay_percentage']:+.1f}%")
                    print(f"      Win Prob: {prob:.1%} | Score: {score:.1f}")

        if not overlays_found:
            print("\nNo overlays found. Update live odds first.")

        print("\n" + "="*70)

    def view_predictions(self):
        """View current predictions for all races"""
        print("\n" + "="*70)
        print("CURRENT PREDICTIONS")
        print("="*70)

        for race_data in self.predictions.get('races', []):
            print(f"\nRace {race_data['race_number']}:")
            print(f"  Distance: {race_data.get('distance', 'N/A')}")
            print(f"  Surface: {race_data.get('surface', 'N/A')}")
            print()

            # Sort by predicted finish
            predictions = sorted(race_data['predictions'],
                               key=lambda p: p.get('predicted_finish', p.get('probability', 0)),
                               reverse=True)

            for i, pred in enumerate(predictions[:5], 1):  # Top 5
                status = "❌" if pred.get('is_scratched') else ""
                overlay = "🎯" if pred.get('is_overlay') else ""
                prob = pred.get('probability', pred.get('win_probability', 0))
                score = pred.get('total_score', 0)

                print(f"  {i:2d}. #{pred['program_number']:2d} {pred['name']:25s} {status} {overlay}")
                print(f"      Score: {score:5.1f} | Win%: {prob:.1%}")

                if pred.get('live_odds'):
                    print(f"      Odds: {pred['live_odds']:.1f}-1")

        print("\n" + "="*70)

    def run(self):
        """Main interactive loop"""
        print("\n🐴 Welcome to Manual Input System! 🐴")
        print(f"Loaded: {self.predictions_file}")

        while True:
            self.display_menu()

            try:
                choice = input().strip()

                if choice == '1':
                    self.update_live_odds()
                elif choice == '2':
                    self.mark_scratch()
                elif choice == '3':
                    print("\n⚠️ Track condition updates coming in next version")
                elif choice == '4':
                    self.view_predictions()
                elif choice == '5':
                    self.show_overlays()
                elif choice == '6':
                    # Save and exit
                    base_name = self.predictions_file.stem
                    self._save_predictions(f"{base_name}_updated.json")
                    self._save_updates(f"{base_name}_updates.json")
                    print("\n✓ All changes saved!")
                    print(f"  Predictions: predictions/{base_name}_updated.json")
                    print(f"  Update log: updates/{base_name}_updates.json")
                    break
                elif choice == '7':
                    # Exit without saving
                    confirm = input("\nAre you sure? Unsaved changes will be lost (y/n): ")
                    if confirm.lower() == 'y':
                        print("\nExiting without saving...")
                        break
                else:
                    print("\n❌ Invalid choice. Please enter 1-7.")

            except KeyboardInterrupt:
                print("\n\n❌ Interrupted. Changes not saved.")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}")
                print("Please try again.")

        print("\n👋 Goodbye! Good luck at the track! 🏇\n")


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def quick_update_odds(predictions_file: str, updates_dict: Dict[int, Dict[int, float]]):
    """
    Quick function to update odds programmatically

    Args:
        predictions_file: Path to predictions JSON
        updates_dict: {race_num: {program_num: odds}}

    Example:
        quick_update_odds('oct25_base.json', {
            1: {4: 7.5, 2: 3.0},  # Race 1: #4 @ 7.5-1, #2 @ 3.0-1
            3: {1: 2.5, 5: 12.0}  # Race 3: #1 @ 2.5-1, #5 @ 12.0-1
        })
    """
    system = ManualInputSystem(predictions_file)

    for race_num, odds_updates in updates_dict.items():
        races = system.predictions.get('races', [])
        race_data = next((r for r in races if r['race_number'] == race_num), None)

        if not race_data:
            print(f"⚠️ Race {race_num} not found")
            continue

        for program_num, odds in odds_updates.items():
            pred = next((p for p in race_data['predictions'] if p['program_number'] == program_num), None)

            if pred:
                old_odds = pred.get('live_odds', pred.get('ml_odds', pred.get('morning_line_odds', 'N/A')))
                pred['live_odds'] = odds

                update = ManualUpdate(
                    race_number=race_num,
                    horse_name=pred['name'],
                    update_type=UpdateType.LIVE_ODDS,
                    old_value=old_odds,
                    new_value=odds,
                    timestamp=datetime.now(),
                    notes="Quick update"
                )
                system.updates.append(update)
                print(f"✓ Race {race_num}, #{program_num}: {old_odds} → {odds:.1f}")

        # Recalculate overlays for this race
        system._calculate_overlays(race_data)

    # Save
    base_name = Path(predictions_file).stem
    system._save_predictions(f"{base_name}_updated.json")
    system._save_updates(f"{base_name}_updates.json")
    print("\n✓ All updates saved!")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python manual_input_system.py <predictions_file>")
        print("Example: python manual_input_system.py predictions/oct25_base.json")
        sys.exit(1)

    system = ManualInputSystem(sys.argv[1])
    system.run()
