import os
"""
Interactive Race Dashboard
Visualizes race predictions with focus on exotic wagers
"""

import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec
import numpy as np
from typing import List, Dict, Tuple
from datetime import datetime

from src.parsers.equibase_parser import Race, Horse


class RaceDashboard:
    """Creates interactive visualizations for race predictions"""

    def __init__(self, figsize=(16, 12)):
        """
        Initialize dashboard

        Args:
            figsize: Figure size (width, height) in inches
        """
        self.figsize = figsize
        self.colors = {
            'favorite': '#FFD700',      # Gold
            'contender': '#C0C0C0',     # Silver
            'longshot': '#CD7F32',      # Bronze
            'overlay': '#00FF00',       # Green
            'underlay': '#FF0000',      # Red
            'pace_advantage': '#4169E1', # Royal Blue
        }

    def create_race_dashboard(self, race: Race, predictions: List[Dict],
                            pace_scenario: Dict = None,
                            save_path: str = None) -> None:
        """
        Create comprehensive race dashboard

        Args:
            race: Race object
            predictions: List of prediction dicts with horse data
            pace_scenario: Pace scenario analysis
            save_path: Optional path to save figure
        """
        fig = plt.figure(figsize=self.figsize)
        race_date_str = race.date if hasattr(race, 'date') else 'Unknown Date'
        track_name = race.track_name if hasattr(race, 'track_name') else 'Unknown Track'
        fig.suptitle(f"{track_name} - Race {race.race_number} - {race_date_str}",
                    fontsize=16, fontweight='bold')

        # Create grid layout
        gs = GridSpec(3, 3, figure=fig, hspace=0.3, wspace=0.3)

        # 1. Win Probability Chart (top left)
        ax1 = fig.add_subplot(gs[0, 0])
        self._plot_win_probabilities(ax1, predictions)

        # 2. Odds Comparison (top middle)
        ax2 = fig.add_subplot(gs[0, 1])
        self._plot_odds_comparison(ax2, predictions)

        # 3. Pace Scenario (top right)
        ax3 = fig.add_subplot(gs[0, 2])
        self._plot_pace_scenario(ax3, predictions, pace_scenario)

        # 4. Factor Breakdown (middle left)
        ax4 = fig.add_subplot(gs[1, 0])
        self._plot_factor_breakdown(ax4, predictions)

        # 5. Exotic Wager Recommendations (middle center - spans 2 columns)
        ax5 = fig.add_subplot(gs[1, 1:])
        self._plot_exotic_recommendations(ax5, predictions, race)

        # 6. Top Contenders Table (bottom - spans all columns)
        ax6 = fig.add_subplot(gs[2, :])
        self._plot_contenders_table(ax6, predictions)

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            print(f"\n✓ Dashboard saved to: {save_path}")
        else:
            plt.show()

    def _plot_win_probabilities(self, ax, predictions: List[Dict]) -> None:
        """Plot win probability bar chart"""
        # Sort by rank
        sorted_preds = sorted(predictions, key=lambda x: x['rank'])[:8]

        horses = [f"#{p['program_number']} {p['horse_name'][:12]}"
                 for p in sorted_preds]
        probs = [p['win_probability'] * 100 for p in sorted_preds]

        # Color based on rank
        colors = []
        for p in sorted_preds:
            if p['rank'] == 1:
                colors.append(self.colors['favorite'])
            elif p['rank'] <= 3:
                colors.append(self.colors['contender'])
            else:
                colors.append(self.colors['longshot'])

        bars = ax.barh(horses, probs, color=colors, edgecolor='black', linewidth=1.5)

        # Add probability labels
        for i, (bar, prob) in enumerate(zip(bars, probs)):
            ax.text(prob + 1, i, f"{prob:.1f}%", va='center', fontweight='bold')

        ax.set_xlabel('Win Probability (%)', fontweight='bold')
        ax.set_title('Top Contenders Win Probability', fontweight='bold', fontsize=12)
        ax.set_xlim(0, max(probs) * 1.2)
        ax.grid(axis='x', alpha=0.3)

    def _plot_odds_comparison(self, ax, predictions: List[Dict]) -> None:
        """Plot model odds vs morning line odds"""
        sorted_preds = sorted(predictions, key=lambda x: x['rank'])[:8]

        horses = [f"#{p['program_number']}" for p in sorted_preds]
        model_odds = [p.get('model_odds', 0) for p in sorted_preds]
        ml_odds = [p.get('morning_line_odds', 0) for p in sorted_preds]

        x = np.arange(len(horses))
        width = 0.35

        # Bars
        ax.bar(x - width/2, model_odds, width, label='Model Odds',
               color=self.colors['pace_advantage'], alpha=0.8)
        ax.bar(x + width/2, ml_odds, width, label='Morning Line',
               color='gray', alpha=0.6)

        ax.set_xlabel('Horse', fontweight='bold')
        ax.set_ylabel('Decimal Odds', fontweight='bold')
        ax.set_title('Odds Comparison (Lower = More Favored)', fontweight='bold', fontsize=12)
        ax.set_xticks(x)
        ax.set_xticklabels(horses)
        ax.legend()
        ax.grid(axis='y', alpha=0.3)

    def _plot_pace_scenario(self, ax, predictions: List[Dict],
                           pace_scenario: Dict = None) -> None:
        """Visualize pace scenario"""
        if not pace_scenario:
            ax.text(0.5, 0.5, 'Pace Analysis\nNot Available',
                   ha='center', va='center', fontsize=12)
            ax.axis('off')
            return

        # Count running styles
        style_counts = {'E': 0, 'P': 0, 'S': 0}
        for pred in predictions:
            style = pred.get('running_style', 'P')
            if style in style_counts:
                style_counts[style] += 1

        # Create pie chart
        labels = [f"Early ({style_counts['E']})",
                 f"Presser ({style_counts['P']})",
                 f"Closer ({style_counts['S']})"]
        sizes = [style_counts['E'], style_counts['P'], style_counts['S']]
        colors_pie = ['#FF6B6B', '#4ECDC4', '#45B7D1']

        wedges, texts, autotexts = ax.pie(sizes, labels=labels, colors=colors_pie,
                                          autopct='%1.0f%%', startangle=90)

        # Scenario text
        scenario_type = pace_scenario.get('scenario_type', 'UNKNOWN')
        scenario_text = scenario_type.replace('_', ' ')

        ax.set_title(f'Pace Scenario\n{scenario_text}',
                    fontweight='bold', fontsize=12)

        # Add advantage horses
        if 'advantage_horses' in pace_scenario and pace_scenario['advantage_horses']:
            advantage_text = "Advantage: " + ", ".join(
                [f"#{h}" for h in pace_scenario['advantage_horses'][:3]]
            )
            ax.text(0, -1.3, advantage_text, ha='center', fontsize=9,
                   style='italic', color=self.colors['pace_advantage'])

    def _plot_factor_breakdown(self, ax, predictions: List[Dict]) -> None:
        """Show factor breakdown for top 3 horses"""
        top_3 = sorted(predictions, key=lambda x: x['rank'])[:3]

        factors = ['Speed', 'Form', 'Class', 'Pace', 'Jockey', 'Trainer']
        x = np.arange(len(factors))
        width = 0.25

        for i, pred in enumerate(top_3):
            factor_scores = pred.get('factor_scores', {})
            scores = [
                factor_scores.get('speed', 0),
                factor_scores.get('form', 0),
                factor_scores.get('class', 0),
                factor_scores.get('pace', 0),
                factor_scores.get('jockey', 0),
                factor_scores.get('trainer', 0),
            ]

            label = f"#{pred['program_number']} {pred['horse_name'][:8]}"
            ax.bar(x + i*width, scores, width, label=label, alpha=0.8)

        ax.set_xlabel('Factor', fontweight='bold')
        ax.set_ylabel('Score', fontweight='bold')
        ax.set_title('Factor Breakdown - Top 3', fontweight='bold', fontsize=12)
        ax.set_xticks(x + width)
        ax.set_xticklabels(factors, rotation=45, ha='right')
        ax.legend(fontsize=8)
        ax.grid(axis='y', alpha=0.3)

    def _plot_exotic_recommendations(self, ax, predictions: List[Dict],
                                    race: Race) -> None:
        """Display exotic wager recommendations"""
        ax.axis('off')

        # Get top horses
        sorted_preds = sorted(predictions, key=lambda x: x['rank'])
        top_3 = sorted_preds[:3]
        top_4 = sorted_preds[:4]

        # Calculate confidence metrics
        top_1_prob = top_3[0]['win_probability']
        top_3_prob_sum = sum(p['win_probability'] for p in top_3)

        # Determine bet strength
        if top_1_prob > 0.30:
            confidence = "HIGH"
            conf_color = self.colors['overlay']
        elif top_1_prob > 0.20:
            confidence = "MEDIUM"
            conf_color = 'orange'
        else:
            confidence = "LOW"
            conf_color = self.colors['underlay']

        # Create recommendation text
        y_pos = 0.9
        line_height = 0.12

        # Title
        ax.text(0.5, y_pos, 'EXOTIC WAGER RECOMMENDATIONS',
               ha='center', fontsize=14, fontweight='bold',
               bbox=dict(boxstyle='round', facecolor='lightgray', alpha=0.8))
        y_pos -= line_height * 1.5

        # Confidence
        ax.text(0.5, y_pos, f'Model Confidence: {confidence}',
               ha='center', fontsize=12, fontweight='bold', color=conf_color)
        y_pos -= line_height * 1.2

        # Exacta Box
        exacta_horses = " - ".join([f"#{p['program_number']} {p['horse_name']}"
                                    for p in top_3])
        ax.text(0.1, y_pos, '🎯 EXACTA BOX (Top 3):', fontsize=11, fontweight='bold')
        y_pos -= line_height * 0.8
        ax.text(0.1, y_pos, f"   {exacta_horses}", fontsize=10)
        y_pos -= line_height * 0.7
        exacta_cost = len(top_3) * (len(top_3) - 1)
        ax.text(0.1, y_pos, f"   Cost: ${exacta_cost} ($1 base)",
               fontsize=9, style='italic', color='gray')
        y_pos -= line_height * 1.2

        # Trifecta Box
        trifecta_horses = " - ".join([f"#{p['program_number']} {p['horse_name']}"
                                      for p in top_4])
        ax.text(0.1, y_pos, '🎯 TRIFECTA BOX (Top 4):', fontsize=11, fontweight='bold')
        y_pos -= line_height * 0.8
        ax.text(0.1, y_pos, f"   {trifecta_horses}", fontsize=10)
        y_pos -= line_height * 0.7
        trifecta_cost = len(top_4) * (len(top_4) - 1) * (len(top_4) - 2)
        ax.text(0.1, y_pos, f"   Cost: ${trifecta_cost} ($1 base)",
               fontsize=9, style='italic', color='gray')
        y_pos -= line_height * 1.2

        # Key horses for straight bets
        if top_1_prob > 0.25:  # Only recommend if strong favorite
            ax.text(0.1, y_pos, '⚠️  STRAIGHT BET (Use Caution):',
                   fontsize=11, fontweight='bold')
            y_pos -= line_height * 0.8
            ax.text(0.1, y_pos,
                   f"   #{top_3[0]['program_number']} {top_3[0]['horse_name']} "
                   f"({top_1_prob*100:.1f}% prob)",
                   fontsize=10)

        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)

    def _plot_contenders_table(self, ax, predictions: List[Dict]) -> None:
        """Display detailed table of top contenders"""
        ax.axis('off')

        # Get top 6 horses
        sorted_preds = sorted(predictions, key=lambda x: x['rank'])[:6]

        # Table headers
        headers = ['Rank', 'Pgm', 'Horse', 'Win%', 'Odds', 'Jockey',
                  'Trainer', 'Speed', 'FTS', 'Pace']

        # Table data
        table_data = []
        for pred in sorted_preds:
            row = [
                str(pred['rank']),
                f"#{pred['program_number']}",
                pred['horse_name'][:15],
                f"{pred['win_probability']*100:.1f}%",
                f"{pred.get('model_odds', 0):.1f}",
                pred.get('jockey_name', '')[:12],
                pred.get('trainer_name', '')[:12],
                str(pred.get('speed_figure', '-')),
                '✓' if pred.get('is_fts', False) else '',
                pred.get('pace_advantage', '')[:8],
            ]
            table_data.append(row)

        # Create table
        table = ax.table(cellText=table_data, colLabels=headers,
                        cellLoc='center', loc='center',
                        bbox=[0, 0, 1, 1])

        table.auto_set_font_size(False)
        table.set_fontsize(9)
        table.scale(1, 2)

        # Style header
        for i in range(len(headers)):
            cell = table[(0, i)]
            cell.set_facecolor('#4169E1')
            cell.set_text_props(weight='bold', color='white')

        # Style rank column
        for i in range(1, len(table_data) + 1):
            rank = int(table_data[i-1][0])
            if rank == 1:
                table[(i, 0)].set_facecolor(self.colors['favorite'])
            elif rank <= 3:
                table[(i, 0)].set_facecolor(self.colors['contender'])

        ax.set_title('Top Contenders Detail', fontweight='bold',
                    fontsize=12, pad=20)


def create_race_visualization(race: Race, predictions: List[Dict],
                              pace_scenario: Dict = None,
                              output_file: str = None) -> None:
    """
    Convenience function to create race dashboard

    Args:
        race: Race object
        predictions: List of prediction dictionaries
        pace_scenario: Optional pace scenario analysis
        output_file: Optional path to save figure
    """
    dashboard = RaceDashboard(figsize=(16, 12))
    dashboard.create_race_dashboard(race, predictions, pace_scenario, output_file)


if __name__ == '__main__':
    print("Race Dashboard module loaded.")
    print("Use create_race_visualization() to generate dashboards.")
