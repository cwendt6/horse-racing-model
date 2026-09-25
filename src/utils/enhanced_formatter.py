"""
Enhanced Output Formatter for Horse Racing Analysis
Generates professional, statistically rigorous race reports
"""

from typing import List, Dict, Tuple
import racing_statistics as stats
import numpy as np


class EnhancedRaceFormatter:
    """
    Formats race analysis with comprehensive statistics
    """
    
    def __init__(self, include_confidence_intervals: bool = True,
                 include_exotic_probs: bool = True,
                 takeout: float = 0.17):
        self.include_ci = include_confidence_intervals
        self.include_exotic = include_exotic_probs
        self.takeout = takeout
    
    def format_percentage(self, value: float, decimals: int = 1) -> str:
        """Format probability as percentage"""
        return f"{value * 100:.{decimals}f}%"
    
    def format_confidence_interval(self, lower: float, upper: float) -> str:
        """Format confidence interval"""
        return f"({int(lower * 100)}-{int(upper * 100)}%)"
    
    def get_value_stars(self, overlay_pct: float) -> str:
        """Convert overlay percentage to star rating"""
        if overlay_pct >= 30:
            return "★★★"
        elif overlay_pct >= 15:
            return "★★"
        elif overlay_pct >= 5:
            return "★"
        else:
            return ""
    
    def format_race_header(self, race_data: Dict) -> str:
        """Format race header section"""
        header = f"""
{'='*80}
RACE {race_data['race_number']} - {race_data['distance']} {race_data['surface'].upper()}
{'='*80}
Purse: ${race_data['purse']:,.0f}
Pace Scenario: {race_data.get('pace_scenario', 'Unknown').upper()}
Field Size: {race_data['field_size']} horses
"""
        return header
    
    def format_horse_prediction(self, rank: int, horse_data: Dict, 
                              race_data: Dict, confidence_metrics: Dict) -> str:
        """
        Format individual horse prediction with full statistics
        
        Args:
            rank: Finishing position prediction (1, 2, 3, etc.)
            horse_data: Dictionary with horse information and probabilities
            race_data: Race information
            confidence_metrics: Confidence metrics for the race
            
        Returns:
            Formatted prediction string
        """
        output = []
        
        # Header line with position and horse name
        output.append(f"\n  {rank}. #{horse_data['program_number']} {horse_data['name']:<25}")
        
        # Win probability with confidence interval
        win_prob = horse_data['win_probability']
        output.append(f"     Win: {self.format_percentage(win_prob, 1):<7}", end='')
        
        if self.include_ci and confidence_metrics['level'] in ['MEDIUM', 'HIGH']:
            ci_lower, ci_upper = stats.calculate_confidence_interval(
                win_prob, 
                sample_size=int(confidence_metrics['data_quality'])
            )
            output.append(f" (95% CI: {self.format_confidence_interval(ci_lower, ci_upper)})")
        else:
            output.append("")
        
        # Place and Show probabilities
        if self.include_exotic and horse_data.get('place_probability'):
            output.append(f"     Place: {self.format_percentage(horse_data['place_probability'], 1):<7} "
                        f"Show: {self.format_percentage(horse_data['show_probability'], 1)}")
        
        # Score breakdown
        scores = horse_data.get('scores', {})
        output.append(f"     Score: {horse_data.get('total_score', 0):.1f} "
                    f"(Speed:{scores.get('speed', 0):.0f} | "
                    f"Form:{scores.get('form', 0):.0f} | "
                    f"Class:{scores.get('class_rating', 0):.0f} | "
                    f"Pace:{scores.get('pace', 0):.0f})")
        
        # Odds comparison and value
        ml_odds = horse_data.get('ml_odds', '99/1')
        proj_odds = stats.probability_to_odds(win_prob, self.takeout)
        overlay = horse_data.get('overlay_percentage', 0)
        
        output.append(f"     ML Odds: {ml_odds:<6} → Projected: {proj_odds:<6}")
        
        # Value rating
        if overlay > 5:
            stars = self.get_value_stars(overlay)
            output.append(f"     VALUE: {stars} {overlay:+.0f}% overlay")
        elif overlay < -15:
            output.append(f"     ⚠ UNDERLAY: {overlay:.0f}%")
        
        # Expected value
        ev = horse_data.get('expected_value', 0)
        if ev > 0.1:
            output.append(f"     Expected Value: +${ev:.2f} per $1 bet")
        
        return '\n'.join(output)
    
    def format_field_analysis(self, horses: List[Dict], race_data: Dict, 
                             confidence_metrics: Dict) -> str:
        """Format overall field analysis section"""
        
        # Find favorite
        favorite = min(horses, key=lambda h: h['win_probability'], default=horses[0])
        favorite_odds = stats.probability_to_odds(favorite['win_probability'], self.takeout)
        
        # Calculate total coverage
        total_prob = sum(h['win_probability'] for h in horses)
        
        output = f"""
{'─'*80}
FIELD ANALYSIS:
{'─'*80}
  Total horses: {len(horses)}
  Probability coverage: {self.format_percentage(total_prob, 1)}
  Confidence: {confidence_metrics['level']} 
    • Data quality: {confidence_metrics['data_quality']:.0f}%
    • Beyer spread: {confidence_metrics['beyer_spread']:.0f} points
  
  Projected favorite: #{favorite['program_number']} {favorite['name']} ({favorite_odds})
"""
        return output
    
    def format_betting_strategy(self, horses: List[Dict], race_data: Dict) -> str:
        """Format recommended betting strategies"""
        
        # Find best value plays
        value_plays = sorted([h for h in horses if h.get('overlay_percentage', 0) > 15], 
                           key=lambda h: h['overlay_percentage'], reverse=True)[:3]
        
        # Find high confidence plays (combination of probability and overlay)
        confidence_plays = sorted([h for h in horses if h['win_probability'] > 0.12], 
                                key=lambda h: h['win_probability'], reverse=True)[:2]
        
        # Top exacta combinations
        top_horses = horses[:4]  # Top 4 finishers
        
        output = ["\n" + "─"*80]
        output.append("BETTING STRATEGY:")
        output.append("─"*80)
        
        # High confidence win bets
        if confidence_plays:
            output.append("  High Confidence Win Bets:")
            for horse in confidence_plays:
                ev = horse.get('expected_value', 0)
                output.append(f"    • #{horse['program_number']} {horse['name']:<20} "
                            f"({self.format_percentage(horse['win_probability'])} @ {horse.get('ml_odds', 'N/A')}) "
                            f"[EV: {ev:+.2f}]")
        
        # Value overlay plays
        if value_plays:
            output.append("\n  Value Overlay Plays:")
            for horse in value_plays:
                output.append(f"    • #{horse['program_number']} {horse['name']:<20} "
                            f"({horse['overlay_percentage']:+.0f}% edge)")
        
        # Exacta recommendations
        if len(top_horses) >= 2:
            output.append("\n  Exacta Recommendations:")
            # Top exacta
            combined_prob = top_horses[0]['win_probability'] * top_horses[1]['place_probability']
            output.append(f"    • {top_horses[0]['program_number']}-{top_horses[1]['program_number']} "
                        f"(Combined board probability: {self.format_percentage(combined_prob)})")
            
            # Alternative exacta
            if len(top_horses) >= 3:
                alt_prob = top_horses[0]['win_probability'] * top_horses[2]['place_probability']
                output.append(f"    • {top_horses[0]['program_number']}-{top_horses[2]['program_number']} "
                            f"(Combined board probability: {self.format_percentage(alt_prob)})")
        
        # Trifecta suggestion for bigger payouts
        if len(top_horses) >= 3:
            tri_prob = (top_horses[0]['win_probability'] * 
                       top_horses[1]['place_probability'] * 
                       top_horses[2]['show_probability'])
            if tri_prob > 0.05:  # At least 5% chance
                output.append(f"\n  Trifecta Box: {'-'.join(str(h['program_number']) for h in top_horses[:3])} "
                            f"(Est. probability: {self.format_percentage(tri_prob)})")
        
        return '\n'.join(output)
    
    def format_complete_race(self, race_data: Dict, horses: List[Dict]) -> str:
        """
        Format complete race analysis
        
        Args:
            race_data: Dictionary with race information
            horses: List of horse dictionaries with predictions and scores
            
        Returns:
            Complete formatted race analysis
        """
        # Calculate confidence metrics
        confidence_metrics = stats.calculate_confidence_metrics(horses, race_data)
        
        # Sort horses by predicted finish position
        sorted_horses = sorted(horses, key=lambda h: h.get('finish_position', 99))
        
        # Build output
        output = []
        
        # Header
        output.append(self.format_race_header(race_data))
        
        # Predictions for each horse
        output.append("\nPREDICTED ORDER OF FINISH:")
        output.append("─"*80)
        
        for rank, horse in enumerate(sorted_horses, 1):
            output.append(self.format_horse_prediction(rank, horse, race_data, confidence_metrics))
        
        # Field analysis
        output.append(self.format_field_analysis(sorted_horses, race_data, confidence_metrics))
        
        # Betting strategy
        output.append(self.format_betting_strategy(sorted_horses, race_data))
        
        output.append("\n" + "="*80 + "\n")
        
        return '\n'.join(output)
    
    def format_quick_picks(self, race_data: Dict, horses: List[Dict]) -> str:
        """
        Format condensed quick picks version
        
        Args:
            race_data: Dictionary with race information
            horses: List of horse dictionaries
            
        Returns:
            Condensed picks format
        """
        sorted_horses = sorted(horses, key=lambda h: h.get('finish_position', 99))[:4]
        
        output = []
        output.append(f"\nRACE {race_data['race_number']} - {race_data['distance']} {race_data['surface'].upper()}")
        output.append("─"*80)
        output.append("PICKS:")
        
        for i, horse in enumerate(sorted_horses, 1):
            win_prob = horse['win_probability']
            score = horse.get('total_score', 0)
            overlay = horse.get('overlay_percentage', 0)
            
            value_indicator = ""
            if overlay > 30:
                value_indicator = " 💎 VALUE"
            elif overlay > 15:
                value_indicator = " 💰"
            
            output.append(f"  {i}. #{horse['program_number']} {horse['name']:<25} "
                        f"({self.format_percentage(win_prob)} | Score: {score:.1f}){value_indicator}")
        
        # Best exacta
        if len(sorted_horses) >= 2:
            output.append(f"\n📊 EXACTA: {sorted_horses[0]['name']} / {sorted_horses[1]['name']}")
        
        output.append("")
        
        return '\n'.join(output)


def generate_enhanced_analysis(races_data: List[Dict], output_format: str = 'full') -> str:
    """
    Generate enhanced analysis for all races
    
    Args:
        races_data: List of race dictionaries with predictions
        output_format: 'full' or 'quick' picks
        
    Returns:
        Formatted analysis string
    """
    formatter = EnhancedRaceFormatter()
    
    output = []
    output.append("="*80)
    output.append("ENHANCED STATISTICAL RACE ANALYSIS")
    output.append(f"{races_data[0].get('track', 'Unknown Track')} - {races_data[0].get('date', 'Unknown Date')}")
    output.append("="*80)
    
    for race in races_data:
        if output_format == 'quick':
            output.append(formatter.format_quick_picks(race, race['horses']))
        else:
            output.append(formatter.format_complete_race(race, race['horses']))
    
    return '\n'.join(output)
