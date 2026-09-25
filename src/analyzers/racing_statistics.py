"""
Horse Racing Statistical Analysis Module
Provides advanced statistical functions for handicapping and probability calculations
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

# Import pace figure calculator
try:
    from ..parsers.fractional_time_parser import calculate_pace_figures
except ImportError:
    # Fallback for when running as script
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from parsers.fractional_time_parser import calculate_pace_figures


@dataclass
class HorseScore:
    """Container for a horse's component scores"""
    speed: float
    form: float
    class_rating: float
    pace: float
    jockey: float
    trainer: float
    post: float
    recency: float = 50.0  # Default neutral score
    progression: float = 50.0  # Form progression (improving/declining)
    total: float = 0.0


def normalize_probabilities(scores: np.ndarray) -> np.ndarray:
    """
    Normalize scores to probabilities that sum to 1.0
    
    Uses softmax-like transformation to convert scores to probabilities
    
    Args:
        scores: Array of horse scores
        
    Returns:
        Array of win probabilities summing to 1.0
    """
    if len(scores) == 0:
        return np.array([])
    
    # Ensure no negative scores
    min_score = np.min(scores)
    if min_score < 0:
        scores = scores - min_score
    
    # Apply exponential scaling (higher scores get exponentially more weight)
    exp_scores = np.exp(scores / 10)  # Divide by 10 to prevent overflow
    
    # Normalize to sum to 1
    probabilities = exp_scores / np.sum(exp_scores)
    
    return probabilities


def calculate_place_show_probabilities(win_probs: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """
    Calculate place and show probabilities using Harville formula
    
    The Harville formula estimates the probability of a horse finishing
    in a given position based on its win probability.
    
    Args:
        win_probs: Array of win probabilities for all horses
        
    Returns:
        Tuple of (place_probabilities, show_probabilities)
    """
    n = len(win_probs)
    place_probs = np.zeros(n)
    show_probs = np.zeros(n)
    
    for i in range(n):
        p_win_i = win_probs[i]
        
        # Place probability: P(finish 1st or 2nd)
        # = P(win) + P(2nd | didn't win)
        p_place = p_win_i
        
        for j in range(n):
            if i != j:
                # Probability horse i finishes 2nd behind horse j
                p_second = win_probs[j] * (p_win_i / (1 - win_probs[j]))
                p_place += p_second
        
        place_probs[i] = min(p_place, 1.0)  # Cap at 100%
        
        # Show probability: P(finish 1st, 2nd, or 3rd)
        p_show = p_place
        
        for j in range(n):
            for k in range(n):
                if i != j and i != k and j != k:
                    # Probability horse i finishes 3rd behind horses j and k
                    p_third = (win_probs[j] * win_probs[k] * p_win_i / 
                             ((1 - win_probs[j]) * (1 - win_probs[j] - win_probs[k])))
                    p_show += p_third
        
        show_probs[i] = min(p_show, 1.0)  # Cap at 100%
    
    return place_probs, show_probs


def calculate_confidence_interval(probability: float, sample_size: int = 100, 
                                 confidence_level: float = 0.95) -> Tuple[float, float]:
    """
    Calculate confidence interval for a probability estimate
    
    Uses Wilson score interval for binomial proportion
    
    Args:
        probability: The estimated probability (0 to 1)
        sample_size: Effective sample size (based on data quality)
        confidence_level: Confidence level (default 95%)
        
    Returns:
        Tuple of (lower_bound, upper_bound)
    """
    from scipy import stats
    
    # Z-score for confidence level
    z = stats.norm.ppf((1 + confidence_level) / 2)
    
    # Wilson score interval
    denominator = 1 + z**2 / sample_size
    center = (probability + z**2 / (2 * sample_size)) / denominator
    margin = z * np.sqrt((probability * (1 - probability) / sample_size + 
                          z**2 / (4 * sample_size**2))) / denominator
    
    lower = max(0.0, center - margin)
    upper = min(1.0, center + margin)
    
    return lower, upper


def probability_to_odds(probability: float, takeout: float = 0.17, 
                       format: str = 'fractional') -> str:
    """
    Convert win probability to odds format
    
    Args:
        probability: Win probability (0 to 1)
        takeout: Track takeout percentage (default 17%)
        format: 'fractional', 'decimal', or 'american'
        
    Returns:
        Formatted odds string
    """
    if probability <= 0:
        return "999/1"
    
    # Adjust for track takeout to get fair odds
    fair_prob = probability * (1 - takeout)
    
    # Convert to decimal odds
    decimal_odds = 1 / fair_prob
    
    if format == 'decimal':
        return f"{decimal_odds:.2f}"
    
    elif format == 'american':
        if decimal_odds >= 2.0:
            american = (decimal_odds - 1) * 100
            return f"+{int(american)}"
        else:
            american = -100 / (decimal_odds - 1)
            return f"{int(american)}"
    
    else:  # fractional
        fractional = decimal_odds - 1
        
        # Convert to simple fraction
        if fractional < 1:
            # Odds-on (e.g., 1/2)
            denominator = int(1 / fractional)
            return f"1/{denominator}"
        else:
            # Odds-against (e.g., 5/1)
            numerator = int(fractional)
            return f"{numerator}/1"


def odds_to_probability(odds_str: str) -> float:
    """
    Convert odds string to probability
    
    Handles fractional (5/1), decimal (6.0), and American (+500) formats
    
    Args:
        odds_str: Odds in any standard format
        
    Returns:
        Implied probability (0 to 1)
    """
    odds_str = str(odds_str).strip()
    
    try:
        # Fractional odds (5/1 or 5-1)
        if '/' in odds_str or '-' in odds_str:
            separator = '/' if '/' in odds_str else '-'
            numerator, denominator = odds_str.split(separator)
            fraction = float(numerator) / float(denominator)
            return 1 / (fraction + 1)
        
        # American odds (+500 or -200)
        elif '+' in odds_str or odds_str.startswith('-'):
            american = float(odds_str)
            if american > 0:
                return 100 / (american + 100)
            else:
                return abs(american) / (abs(american) + 100)
        
        # Decimal odds (6.0)
        else:
            decimal = float(odds_str)
            return 1 / decimal
            
    except (ValueError, ZeroDivisionError):
        return 0.0


def calculate_overlay_percentage(projected_prob: float, ml_odds: str) -> float:
    """
    Calculate betting overlay/underlay percentage
    
    Positive values indicate overlays (good bets)
    Negative values indicate underlays (bad bets)
    
    Args:
        projected_prob: Model's projected win probability
        ml_odds: Morning line odds string
        
    Returns:
        Overlay percentage (e.g., 25.0 means 25% overlay)
    """
    ml_prob = odds_to_probability(ml_odds)
    
    if ml_prob == 0:
        return 0.0
    
    overlay = ((projected_prob / ml_prob) - 1) * 100
    return overlay


def calculate_expected_value(projected_prob: float, odds: str, bet_amount: float = 1.0) -> float:
    """
    Calculate expected value of a bet
    
    Args:
        projected_prob: Probability of winning
        odds: Payout odds
        bet_amount: Size of bet
        
    Returns:
        Expected value (positive = profitable bet)
    """
    # Convert odds to decimal payout multiplier
    odds_prob = odds_to_probability(odds)
    if odds_prob == 0:
        return -bet_amount
    
    payout_multiplier = 1 / odds_prob
    
    # EV = (probability of win × payout) - (probability of loss × bet amount)
    ev = (projected_prob * payout_multiplier * bet_amount) - bet_amount
    
    return ev


def calculate_speed_score(best_beyer: Optional[float], last_beyer: Optional[float], 
                          race_avg_beyer: float) -> float:
    """
    Calculate speed figure score (0-100)
    
    Args:
        best_beyer: Horse's best Beyer speed figure
        last_beyer: Horse's most recent Beyer
        race_avg_beyer: Average Beyer for this race class
        
    Returns:
        Speed score (0-100)
    """
    if best_beyer is None or best_beyer <= 0:
        return 50.0  # Neutral score for missing data
    
    # Weight best and last figures
    if last_beyer and last_beyer > 0:
        effective_beyer = (best_beyer * 0.6) + (last_beyer * 0.4)
    else:
        effective_beyer = best_beyer
    
    # Scale relative to race average
    if race_avg_beyer > 0:
        differential = effective_beyer - race_avg_beyer
        # Convert to 0-100 scale (±20 points = ±50 points on scale)
        score = 50 + (differential * 2.5)
    else:
        # Absolute scale if no race average
        score = effective_beyer * 0.8
    
    # Clamp to 0-100
    return max(0.0, min(100.0, score))


def calculate_recency_score(days_since_last_race: int) -> float:
    """
    Calculate recency score (0-100) based on days since last race

    Optimal range: 14-45 days
    Acceptable: 7-60 days
    Penalty for long layoffs (>90 days) or very fresh (<7 days)

    Args:
        days_since_last_race: Days since last race

    Returns:
        Recency score (0-100)
    """
    if days_since_last_race < 0:
        return 50.0  # No data

    # Optimal range: 14-45 days
    if 14 <= days_since_last_race <= 45:
        # Peak form - slight curve with best at 21-28 days
        if 21 <= days_since_last_race <= 28:
            return 100.0
        elif 14 <= days_since_last_race <= 21:
            return 90.0 + (days_since_last_race - 14) * (10.0 / 7)
        else:  # 28-45
            return 100.0 - (days_since_last_race - 28) * (10.0 / 17)

    # Too fresh (< 14 days)
    elif days_since_last_race < 14:
        if days_since_last_race >= 7:
            return 75.0  # Acceptable but not ideal
        else:
            return 50.0  # Very fresh, may be tired

    # Moderate layoff (45-90 days)
    elif days_since_last_race <= 90:
        # Linear decline from 90 to 70
        return 90.0 - (days_since_last_race - 45) * (20.0 / 45)

    # Long layoff (90-180 days)
    elif days_since_last_race <= 180:
        # Steeper decline from 70 to 40
        return 70.0 - (days_since_last_race - 90) * (30.0 / 90)

    # Very long layoff (>180 days)
    else:
        # Major penalty
        return max(20.0, 40.0 - (days_since_last_race - 180) * 0.1)


def calculate_form_progression_score(past_performances: List[Dict]) -> float:
    """
    Calculate form progression score (0-100) based on recent trend

    Analyzes whether horse is improving (rising form), declining, or steady.
    Compares last 3 races to previous 3 races.

    Args:
        past_performances: List of past performance dicts with 'finish' key

    Returns:
        Progression score (0-100)
        100 = Strongly improving
        50 = Neutral/steady
        0 = Declining badly
    """
    if not past_performances or len(past_performances) < 2:
        return 50.0  # Neutral for insufficient data

    # Extract finish positions (filter out DNF, DQ, etc)
    finishes = []
    for pp in past_performances[:6]:  # Look at last 6 races max
        finish = pp.get('finish')
        if finish and isinstance(finish, (int, float)) and finish > 0:
            finishes.append(int(finish))

    if len(finishes) < 2:
        return 50.0  # Need at least 2 races

    # For horses with 2-3 races, compare most recent to previous
    if len(finishes) <= 3:
        most_recent = finishes[0]
        previous_avg = sum(finishes[1:]) / len(finishes[1:])

        # Simple comparison for limited data
        improvement = previous_avg - most_recent

        # Scale improvement for 2-3 race sample (less confident)
        if improvement >= 3.0:
            return 70.0  # Strong improvement
        elif improvement >= 1.5:
            return 60.0  # Moderate improvement
        elif improvement >= 0.5:
            return 55.0  # Slight improvement
        elif improvement >= -0.5:
            return 50.0  # Steady
        elif improvement >= -1.5:
            return 45.0  # Slight decline
        elif improvement >= -3.0:
            return 40.0  # Moderate decline
        else:
            return 30.0  # Strong decline

    # Split into recent (last 3) and previous (next 3) for horses with 4+ races
    recent = finishes[:3]
    previous = finishes[3:6] if len(finishes) > 3 else finishes[:3]

    if not recent or not previous:
        return 50.0

    # Calculate average finish position for each group
    recent_avg = sum(recent) / len(recent)
    previous_avg = sum(previous) / len(previous)

    # Improvement = lower recent average (better finishes)
    # Decline = higher recent average (worse finishes)
    improvement = previous_avg - recent_avg

    # Score based on improvement
    # Improvement of -2.0 or more = major decline (score 0-30)
    # Improvement of +2.0 or more = major improvement (score 70-100)
    # Steady (±0.5) = neutral (score 45-55)

    if improvement >= 2.0:
        # Strong improvement
        return min(100.0, 80.0 + improvement * 10)
    elif improvement >= 1.0:
        # Moderate improvement
        return 65.0 + (improvement - 1.0) * 15
    elif improvement >= 0.5:
        # Slight improvement
        return 55.0 + (improvement - 0.5) * 20
    elif improvement >= -0.5:
        # Steady form
        return 50.0 + improvement * 10
    elif improvement >= -1.0:
        # Slight decline
        return 45.0 + (improvement + 0.5) * 20
    elif improvement >= -2.0:
        # Moderate decline
        return 35.0 + (improvement + 1.0) * 10
    else:
        # Major decline
        return max(0.0, 30.0 + (improvement + 2.0) * 15)


def calculate_pace_figures(past_performances: List[Dict], distance_furlongs: float = 8.0) -> Dict[str, float]:
    """
    Calculate average E1, E2, and LP pace figures from past performances

    Uses fractional times from past performances to calculate:
    - E1: Early pace (first fraction velocity)
    - E2: Middle pace (second fraction velocity)
    - LP: Late pace (final fraction velocity)

    Args:
        past_performances: List of PP dicts with 'fractional_times' key
        distance_furlongs: Today's race distance (for context)

    Returns:
        Dict with 'avg_e1', 'avg_e2', 'avg_lp', 'consistency' (0-1)
    """
    e1_figures = []
    e2_figures = []
    lp_figures = []

    for pp in past_performances[:6]:  # Last 6 races
        fractional_times = pp.get('fractional_times', [])
        if not fractional_times or len(fractional_times) < 1:
            continue

        # E1: First call pace (furlongs per second * 100)
        first_call_time = fractional_times[0]
        if first_call_time > 0:
            # Estimate distance: <25s = 2f, 25-50s = 4f
            first_call_distance = 2.0 if first_call_time < 25 else 4.0
            e1_velocity = first_call_distance / first_call_time
            e1_figures.append(e1_velocity * 100)

        # E2: Second call pace (if available)
        if len(fractional_times) >= 2:
            second_call_time = fractional_times[1]
            e2_time = second_call_time - first_call_time
            if e2_time > 0:
                # Second call distance estimation
                second_call_distance = 4.0 if second_call_time < 50 else 6.0
                e2_distance = second_call_distance - first_call_distance
                e2_velocity = e2_distance / e2_time
                e2_figures.append(e2_velocity * 100)

        # LP: Late pace (if we have enough fractions)
        if len(fractional_times) >= 3:
            last_fraction_time = fractional_times[-1]
            second_last_time = fractional_times[-2]
            lp_time = last_fraction_time - second_last_time
            if lp_time > 0:
                # Estimate remaining distance (typically 2f)
                lp_distance = 2.0
                lp_velocity = lp_distance / lp_time
                lp_figures.append(lp_velocity * 100)

    # Calculate averages
    avg_e1 = sum(e1_figures) / len(e1_figures) if e1_figures else 0.0
    avg_e2 = sum(e2_figures) / len(e2_figures) if e2_figures else avg_e1  # Default to E1
    avg_lp = sum(lp_figures) / len(lp_figures) if lp_figures else avg_e2  # Default to E2

    # Calculate consistency (inverse coefficient of variation)
    def calc_consistency(values):
        if len(values) < 2:
            return 0.5
        try:
            import statistics
            mean_val = statistics.mean(values)
            stdev = statistics.stdev(values)
            cv = stdev / mean_val if mean_val > 0 else 1.0
            return max(0.0, min(1.0, 1.0 - (cv / 2)))
        except:
            return 0.5

    consistency = calc_consistency(e1_figures + e2_figures + lp_figures)

    return {
        'avg_e1': round(avg_e1, 1),
        'avg_e2': round(avg_e2, 1),
        'avg_lp': round(avg_lp, 1),
        'consistency': round(consistency, 2),
        'sample_size': len(e1_figures)
    }


def calculate_form_score(recent_finishes: List[int], recent_dates: Optional[List[str]] = None) -> float:
    """
    Calculate form/consistency score (0-100)
    
    Args:
        recent_finishes: List of recent finish positions (most recent first)
        recent_dates: Optional list of race dates for recency weighting
        
    Returns:
        Form score (0-100)
    """
    if not recent_finishes:
        return 50.0  # Neutral for missing data
    
    # Weight recent races more heavily
    weights = [1.0, 0.8, 0.6, 0.4, 0.2][:len(recent_finishes)]
    
    # Score based on finish position (1st = 100, 10th+ = 0)
    position_scores = [max(0, 100 - (pos - 1) * 10) for pos in recent_finishes]
    
    # Weighted average
    weighted_score = sum(s * w for s, w in zip(position_scores, weights)) / sum(weights)
    
    return weighted_score


def calculate_class_score(career_earnings: float, purse: float, 
                         career_starts: int = 10) -> float:
    """
    Calculate class rating score (0-100)
    
    Args:
        career_earnings: Total career earnings
        purse: Current race purse
        career_starts: Number of career starts
        
    Returns:
        Class score (0-100)
    """
    if career_earnings <= 0 or career_starts <= 0:
        return 50.0
    
    # Average earnings per start
    avg_earnings = career_earnings / career_starts
    
    # Compare to current purse
    class_ratio = avg_earnings / (purse / 10)  # Assume 10% to winner
    
    # Scale to 0-100 (ratio of 2.0 = score of 100)
    score = min(100.0, class_ratio * 50)
    
    return score


def calculate_pace_score(running_style: str, pace_scenario: str,
                        position_in_field: int, field_size: int) -> float:
    """
    Calculate pace scenario score (0-100) using multiplier-based system

    Args:
        running_style: 'E', 'P', 'S', or 'C'
        pace_scenario: Pace scenario from analyzer (Speed Duel, Hot Pace, Honest Pace, Lone Speed, No Speed)
        position_in_field: 1-based position in early pace
        field_size: Number of horses in race

    Returns:
        Pace score (0-100)
    """
    # Multiplier-based scoring for better differentiation
    # Multipliers applied to base score of 75.0
    scenario_weights = {
        'SPEED_DUEL': {'E': 0.3, 'P': 0.7, 'S': 0.9, 'C': 1.0},  # Closers benefit most
        'HOT': {'E': 0.5, 'P': 0.8, 'S': 0.9, 'C': 1.0},
        'HONEST': {'E': 0.7, 'P': 0.9, 'S': 0.8, 'C': 0.7},
        'LONE_SPEED': {'E': 0.9, 'P': 0.8, 'S': 0.7, 'C': 0.6},
        'NO_SPEED': {'E': 1.0, 'P': 0.7, 'S': 0.5, 'C': 0.3},  # Early speed benefits most
    }

    # Map various scenario formats
    scenario_key = pace_scenario.upper().replace(' ', '_')
    if 'SPEED' in scenario_key and 'DUEL' in scenario_key:
        scenario_key = 'SPEED_DUEL'
    elif 'HOT' in scenario_key:
        scenario_key = 'HOT'
    elif 'HONEST' in scenario_key or 'CONTENTIOUS' in scenario_key:
        scenario_key = 'HONEST'
    elif 'LONE' in scenario_key:
        scenario_key = 'LONE_SPEED'
    elif 'NO' in scenario_key or 'SLOW' in scenario_key:
        scenario_key = 'NO_SPEED'
    else:
        scenario_key = 'HONEST'  # Default

    # Get multiplier for this style/scenario combination
    weights = scenario_weights.get(scenario_key, {})
    multiplier = weights.get(running_style, 0.75)

    # Apply multiplier to base score
    base_score = 75.0 * multiplier

    # Adjust for position in field (early speed loses value if many others)
    if running_style == 'E' and position_in_field > 3:
        base_score -= (position_in_field - 3) * 3

    return max(0.0, min(100.0, base_score))


def get_track_bias_multipliers(track_condition: str, surface: str) -> dict:
    """
    Calculate track bias multipliers based on condition

    Different track conditions create different biases:
    - Muddy/Sloppy (MY, SL): Favor inside posts and speed
    - Firm turf (FM): Fair to all, slight inside bias
    - Soft turf (SF, GD, YL): Favor closers, outside posts can be better
    - Fast dirt (FT): Neutral

    Args:
        track_condition: Track condition code (FT, FM, GD, MY, SL, etc.)
        surface: 'dirt' or 'turf'

    Returns:
        Dict with multipliers for different factors
    """
    condition = track_condition.upper()

    # Default multipliers (no bias)
    multipliers = {
        'post_inside_boost': 0.0,   # Boost for posts 1-3
        'post_outside_penalty': 0.0, # Penalty for posts 8+
        'speed_bias': 1.0,           # Multiplier for early speed scores
        'closer_bias': 1.0,          # Multiplier for closer scores
    }

    # Muddy/Sloppy dirt - heavily favors inside and speed
    if condition in ['MY', 'SL', 'SY'] and 'turf' not in surface.lower():
        multipliers['post_inside_boost'] = 10.0
        multipliers['post_outside_penalty'] = -15.0
        multipliers['speed_bias'] = 1.15
        multipliers['closer_bias'] = 0.85

    # Fast dirt - neutral with slight inside edge
    elif condition == 'FT' and 'turf' not in surface.lower():
        multipliers['post_inside_boost'] = 2.0
        multipliers['post_outside_penalty'] = -5.0
        multipliers['speed_bias'] = 1.0
        multipliers['closer_bias'] = 1.0

    # Firm turf - fair to all, traditional turf racing
    elif condition == 'FM' and 'turf' in surface.lower():
        multipliers['post_inside_boost'] = 3.0
        multipliers['post_outside_penalty'] = -8.0
        multipliers['speed_bias'] = 1.0
        multipliers['closer_bias'] = 1.0

    # Good/Soft/Yielding turf - favors closers more
    elif condition in ['GD', 'SF', 'YL'] and 'turf' in surface.lower():
        multipliers['post_inside_boost'] = 0.0
        multipliers['post_outside_penalty'] = -5.0
        multipliers['speed_bias'] = 0.95
        multipliers['closer_bias'] = 1.08

    return multipliers


def calculate_post_position_score(post_position: int, field_size: int, surface: str = 'dirt') -> float:
    """
    Calculate post position advantage score (0-100)

    Inside posts (1-3) have significant advantage, especially on turf
    Outside posts (10+) have disadvantage in large fields

    Args:
        post_position: Horse's post position (1-based)
        field_size: Number of horses in race
        surface: 'dirt' or 'turf' (turf has stronger inside bias)

    Returns:
        Post position score (0-100)
    """
    if post_position <= 0 or field_size <= 0:
        return 50.0  # Neutral

    # Base scoring by post position
    if post_position == 1:
        base_score = 85.0  # Rail has slight advantage
    elif post_position == 2:
        base_score = 90.0  # Best post - not pinned on rail, but still inside
    elif post_position == 3:
        base_score = 88.0  # Also excellent
    elif post_position <= 5:
        base_score = 75.0  # Good middle posts
    elif post_position <= 7:
        base_score = 65.0  # Acceptable
    elif post_position <= 10:
        base_score = 50.0  # Neutral to slight disadvantage
    else:
        # Very outside posts - significant disadvantage
        base_score = max(30.0, 50.0 - (post_position - 10) * 5)

    # Turf racing has stronger inside bias
    if 'turf' in surface.lower() or 'grass' in surface.lower():
        if post_position <= 3:
            base_score += 5.0  # Boost inside posts on turf
        elif post_position >= 8:
            base_score -= 5.0  # Penalize outside posts on turf more

    # Adjust for field size - outside posts worse in larger fields
    if post_position > field_size * 0.6:  # Outer 40% of field
        penalty = (post_position - field_size * 0.6) * 2
        base_score -= penalty

    return max(0.0, min(100.0, base_score))


def parse_distance_to_furlongs(distance_text: str) -> float:
    """
    Convert distance to furlongs - handles fractional formats

    Args:
        distance_text: Distance as text (e.g., "6F", "1 1/8", "7 1/2", "440Y")

    Returns:
        Distance in furlongs
    """
    text = distance_text.upper().strip()

    # Handle "6F", "7F", etc.
    if 'F' in text and len(text) <= 3 and '/' not in text:
        try:
            return float(text.replace('F', '').strip())
        except ValueError:
            pass

    # Handle "1M", "1 1/16M", etc. (miles)
    if 'M' in text:
        text = text.replace('M', '').strip()
        if '/' in text:
            parts = text.split()
            try:
                miles = float(parts[0])
                if len(parts) > 1 and '/' in parts[1]:
                    num, denom = parts[1].split('/')
                    miles += float(num) / float(denom)
                return miles * 8.0  # 1 mile = 8 furlongs
            except (ValueError, IndexError, ZeroDivisionError):
                pass
        else:
            try:
                return float(text) * 8.0
            except ValueError:
                pass

    # Handle fractional furlongs like "7 1/2"
    if '/' in text:
        text = text.replace('F', '').strip()
        parts = text.split()
        try:
            furlongs = float(parts[0])
            if len(parts) > 1 and '/' in parts[1]:
                num, denom = parts[1].split('/')
                furlongs += float(num) / float(denom)
            return furlongs
        except (ValueError, IndexError, ZeroDivisionError):
            pass

    # Handle yards like "870Y", "440Y"
    if 'Y' in text:
        try:
            yards = float(text.replace('Y', '').strip())
            return yards / 220.0  # 220 yards = 1 furlong
        except ValueError:
            pass

    # Fallback: try to parse as plain number
    try:
        return float(text)
    except ValueError:
        return 6.0  # Default 6F


def calculate_comprehensive_score(horse_data: Dict, race_data: Dict) -> HorseScore:
    """
    Calculate comprehensive horse score using all factors
    
    Args:
        horse_data: Dictionary containing horse's data
        race_data: Dictionary containing race information
        
    Returns:
        HorseScore object with all component scores and total
    """
    # Component scores
    speed = calculate_speed_score(
        horse_data.get('best_beyer'),
        horse_data.get('last_beyer'),
        race_data.get('avg_beyer', 70)
    )
    
    form = calculate_form_score(
        horse_data.get('recent_finishes', []),
        horse_data.get('recent_dates')
    )
    
    class_rating = calculate_class_score(
        horse_data.get('career_earnings', 0),
        race_data.get('purse', 100000),
        horse_data.get('career_starts', 10)
    )
    
    pace = calculate_pace_score(
        horse_data.get('running_style', 'P'),
        race_data.get('pace_scenario', 'moderate'),
        horse_data.get('early_position', 5),
        race_data.get('field_size', 10)
    )
    
    jockey = horse_data.get('jockey_win_pct', 0.10) * 100
    
    trainer_pct = horse_data.get('trainer_win_pct', '10%')
    if isinstance(trainer_pct, str):
        trainer = float(trainer_pct.replace('%', ''))
    else:
        trainer = trainer_pct * 100 if trainer_pct < 1 else trainer_pct
    
    post = calculate_post_position_score(
        horse_data.get('post', 5),
        race_data.get('field_size', 10),
        race_data.get('surface', 'dirt')
    )

    recency = calculate_recency_score(
        horse_data.get('days_since_last_race', 999)
    )

    # Calculate form progression (improving/declining)
    progression = calculate_form_progression_score(
        horse_data.get('past_performances', [])
    )

    # Apply track bias adjustments
    track_condition = race_data.get('track_condition', 'FT')
    surface = race_data.get('surface', 'dirt')
    bias = get_track_bias_multipliers(track_condition, surface)

    # Adjust pace score based on running style and track bias
    running_style = horse_data.get('running_style', 'P')
    if running_style in ['E', 'P']:  # Speed horses
        pace = pace * bias['speed_bias']
    elif running_style == 'C':  # Closers
        pace = pace * bias['closer_bias']

    # OPTION A: Add pace figure bonus/penalty (±5 points max)
    # Calculate pace figures from fractional times
    past_performances = horse_data.get('past_performances', [])
    if past_performances:
        pace_figs = calculate_pace_figures(past_performances)

        # Only apply bonus if we have sufficient data (2+ races)
        if pace_figs['sample_size'] >= 2:
            avg_e1 = pace_figs['avg_e1']
            avg_e2 = pace_figs['avg_e2']
            avg_lp = pace_figs['avg_lp']
            consistency = pace_figs['consistency']

            # Bonus/penalty based on pace quality and running style fit
            pace_bonus = 0.0

            # Early speed horses benefit from strong E1
            if running_style == 'E':
                if avg_e1 >= 8.8:
                    pace_bonus += 3.0  # Exceptional early speed
                elif avg_e1 >= 8.5:
                    pace_bonus += 1.5  # Good early speed
                elif avg_e1 < 8.0:
                    pace_bonus -= 2.0  # Weak early speed

            # Closers benefit from strong LP
            elif running_style == 'C':
                if avg_lp >= 8.0:
                    pace_bonus += 3.0  # Exceptional late kick
                elif avg_lp >= 7.5:
                    pace_bonus += 1.5  # Good late kick
                elif avg_lp < 6.5:
                    pace_bonus -= 2.0  # Weak late kick

            # Pressers/Stalkers benefit from sustained pace (E2)
            else:  # P or S
                if avg_e2 >= 8.5:
                    pace_bonus += 2.5  # Excellent sustained pace
                elif avg_e2 >= 8.2:
                    pace_bonus += 1.0  # Good sustained pace
                elif avg_e2 < 7.8:
                    pace_bonus -= 1.5  # Weak sustained pace

            # Consistency bonus (reliable pace patterns)
            if consistency >= 0.85:
                pace_bonus += 1.5  # Very consistent
            elif consistency >= 0.75:
                pace_bonus += 0.5  # Reasonably consistent

            # Cap bonus/penalty at ±5
            pace_bonus = max(-5.0, min(5.0, pace_bonus))

            # Apply to pace score
            pace = min(100.0, max(0.0, pace + pace_bonus))

    # Adjust post score based on track bias
    post_pos = horse_data.get('post', 5)
    if post_pos <= 3:  # Inside posts
        post = min(100.0, post + bias['post_inside_boost'])
    elif post_pos >= 8:  # Outside posts
        post = max(0.0, post + bias['post_outside_penalty'])

    # Weighted combination (optimized on October 2025 Keeneland data)
    # Baseline: 28.57% win rate → Optimized: 32.14% win rate (+3.57 pts)
    weights = {
        'speed': 0.2292,        # Reduced from 0.25 (speed less dominant than thought)
        'form': 0.1458,         # Reduced from 0.16
        'class_rating': 0.1250, # Slight increase from 0.12
        'pace': 0.1458,         # Increased from 0.12 (pace more important!)
        'recency': 0.0833,      # Reduced from 0.10
        'progression': 0.0938,  # Increased from 0.07 (form trend highly predictive!)
        'jockey': 0.0625,       # Reduced from 0.07
        'trainer': 0.0625,      # Reduced from 0.07
        'post': 0.0521,         # Increased from 0.04 (post position undervalued)
    }

    total = (speed * weights['speed'] +
             form * weights['form'] +
             class_rating * weights['class_rating'] +
             pace * weights['pace'] +
             recency * weights['recency'] +
             progression * weights['progression'] +
             jockey * weights['jockey'] +
             trainer * weights['trainer'] +
             post * weights['post'])

    return HorseScore(
        speed=speed,
        form=form,
        class_rating=class_rating,
        pace=pace,
        jockey=jockey,
        trainer=trainer,
        post=post,
        recency=recency,
        progression=progression,
        total=total
    )


def calculate_confidence_metrics(horses_data: List[Dict], race_data: Dict) -> Dict[str, any]:
    """
    Calculate confidence metrics for predictions
    
    Args:
        horses_data: List of horse data dictionaries
        race_data: Race information dictionary
        
    Returns:
        Dictionary of confidence metrics
    """
    # Data quality: percentage of non-null values
    total_fields = 0
    non_null_fields = 0
    
    critical_fields = ['best_beyer', 'last_beyer', 'running_style', 'career_earnings']
    
    for horse in horses_data:
        for field in critical_fields:
            total_fields += 1
            value = horse.get(field)
            if value is not None and value not in [0, '', 'nan', 'None']:
                non_null_fields += 1
    
    data_quality = (non_null_fields / total_fields * 100) if total_fields > 0 else 0
    
    # Beyer spread (lower = more certainty)
    beyers = [h.get('best_beyer', 70) for h in horses_data if h.get('best_beyer')]
    beyer_spread = max(beyers) - min(beyers) if beyers else 20
    
    # Field size (8-10 is optimal)
    field_size = len(horses_data)
    size_confidence = 100 - abs(9 - field_size) * 5
    
    # Overall confidence
    if data_quality > 85 and beyer_spread < 12:
        confidence = "HIGH"
    elif data_quality > 70 and beyer_spread < 18:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"
    
    return {
        'level': confidence,
        'data_quality': data_quality,
        'beyer_spread': beyer_spread,
        'field_size': field_size,
        'size_confidence': size_confidence
    }
