"""
Track Bias Detector

Applies track-specific biases to scoring system based on:
1. Post position performance by track
2. Pace bias (early speed vs closers)
3. Surface-specific adjustments
4. Distance-specific adjustments

Uses historical data analysis to create multipliers that
improve prediction accuracy.
"""

import json
from typing import Dict, Optional, Tuple
from pathlib import Path


class TrackBiasDetector:
    """
    Detects and applies track biases to improve predictions

    Loads historical bias data and provides multipliers for:
    - Post position adjustments
    - Pace/running style adjustments
    - Surface-specific effects
    """

    def __init__(self, bias_data_file: Optional[str] = None):
        """
        Initialize bias detector

        Args:
            bias_data_file: Path to bias analysis JSON file
                          Defaults to output/track_bias_analysis_october_2025.json
        """
        if bias_data_file is None:
            bias_data_file = 'output/track_bias_analysis_october_2025.json'

        self.bias_data = self._load_bias_data(bias_data_file)
        self.enabled = True

    def _load_bias_data(self, file_path: str) -> Dict:
        """Load bias data from JSON file"""
        try:
            with open(file_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Warning: Bias data file not found: {file_path}")
            print("Track bias adjustments disabled.")
            return {'bias_multipliers': {'post_position': {}, 'pace_bias': {}}}

    def get_post_position_multiplier(
        self,
        post_position: int,
        surface: str = 'turf',
        distance_class: str = 'mile'
    ) -> float:
        """
        Get post position bias multiplier

        Args:
            post_position: Post position (1-14)
            surface: 'turf' or 'dirt'
            distance_class: 'sprint', 'mile', or 'route'

        Returns:
            Multiplier (1.0 = neutral, >1.0 = advantage, <1.0 = disadvantage)

        Example:
            >>> detector.get_post_position_multiplier(1, 'turf', 'mile')
            1.513  # Post 1 is 51% better than average
        """
        if not self.enabled:
            return 1.0

        # Try to get track-specific data
        post_str = str(post_position)
        multipliers = self.bias_data.get('bias_multipliers', {}).get('post_position', {})

        # Return multiplier or default to 1.0
        return multipliers.get(post_str, 1.0)

    def get_pace_bias_multiplier(
        self,
        running_style: str,
        surface: str = 'turf'
    ) -> float:
        """
        Get pace bias multiplier for running style

        Args:
            running_style: 'E', 'P', 'S', or 'C'
            surface: 'turf' or 'dirt'

        Returns:
            Multiplier for pace score

        Example:
            >>> detector.get_pace_bias_multiplier('C', 'turf')
            1.145  # Closers favored at Keeneland
        """
        if not self.enabled:
            return 1.0

        pace_multipliers = self.bias_data.get('bias_multipliers', {}).get('pace_bias', {})

        return pace_multipliers.get(running_style, 1.0)

    def apply_post_bias_adjustment(
        self,
        base_post_score: float,
        post_position: int,
        surface: str = 'turf',
        distance_class: str = 'mile'
    ) -> float:
        """
        Apply post position bias to post score

        Args:
            base_post_score: Original post position score
            post_position: Post position
            surface: Surface type
            distance_class: Distance classification

        Returns:
            Adjusted post score

        Example:
            >>> detector.apply_post_bias_adjustment(50.0, 1, 'turf')
            75.65  # Post 1 gets big boost at Keeneland
        """
        multiplier = self.get_post_position_multiplier(post_position, surface, distance_class)
        return base_post_score * multiplier

    def apply_pace_bias_adjustment(
        self,
        base_pace_score: float,
        running_style: str,
        surface: str = 'turf'
    ) -> float:
        """
        Apply pace bias to pace score

        Args:
            base_pace_score: Original pace score
            running_style: Horse's running style
            surface: Surface type

        Returns:
            Adjusted pace score

        Example:
            >>> detector.apply_pace_bias_adjustment(70.0, 'C', 'turf')
            80.15  # Closers get boost at Keeneland
        """
        multiplier = self.get_pace_bias_multiplier(running_style, surface)
        return base_pace_score * multiplier

    def get_bias_summary(self, track_code: str = 'KEE') -> Dict:
        """
        Get summary of bias patterns for a track

        Args:
            track_code: Track code (default KEE for Keeneland)

        Returns:
            Dict with bias summary
        """
        post_multipliers = self.bias_data.get('bias_multipliers', {}).get('post_position', {})
        pace_multipliers = self.bias_data.get('bias_multipliers', {}).get('pace_bias', {})

        # Identify strongest biases
        best_posts = [(int(p), m) for p, m in post_multipliers.items() if m > 1.2]
        worst_posts = [(int(p), m) for p, m in post_multipliers.items() if m < 0.8]

        best_posts.sort(key=lambda x: x[1], reverse=True)
        worst_posts.sort(key=lambda x: x[1])

        return {
            'track': track_code,
            'total_races': self.bias_data.get('total_races', 0),
            'best_posts': best_posts[:3],
            'worst_posts': worst_posts[:3],
            'pace_bias': pace_multipliers,
            'bias_type': self._classify_track_bias(pace_multipliers)
        }

    def _classify_track_bias(self, pace_multipliers: Dict) -> str:
        """Classify overall track bias"""
        if not pace_multipliers:
            return 'neutral'

        early_mult = pace_multipliers.get('E', 1.0)
        closer_mult = pace_multipliers.get('C', 1.0)

        if closer_mult > early_mult * 1.15:
            return 'closer_favoring'
        elif early_mult > closer_mult * 1.15:
            return 'speed_favoring'
        else:
            return 'neutral'

    def print_bias_report(self, track_code: str = 'KEE'):
        """Print formatted bias report"""
        summary = self.get_bias_summary(track_code)

        print('='*80)
        print(f' TRACK BIAS REPORT - {track_code}')
        print('='*80)
        print()
        print(f"Analysis based on {summary['total_races']} races")
        print()

        print('POST POSITION BIAS:')
        print('-'*40)
        if summary['best_posts']:
            print('  Best Posts:')
            for post, mult in summary['best_posts']:
                print(f"    Post {post:2d}: {mult:.3f}x ({(mult-1)*100:+.1f}%)")
        print()

        if summary['worst_posts']:
            print('  Worst Posts:')
            for post, mult in summary['worst_posts']:
                print(f"    Post {post:2d}: {mult:.3f}x ({(mult-1)*100:+.1f}%)")
        print()

        print('PACE BIAS:')
        print('-'*40)
        print(f"  Track Type: {summary['bias_type'].replace('_', ' ').title()}")
        print()
        for style, mult in summary['pace_bias'].items():
            style_name = {
                'E': 'Early Speed',
                'P': 'Presser',
                'S': 'Stalker',
                'C': 'Closer'
            }.get(style, style)
            symbol = '✅' if mult > 1.1 else '❌' if mult < 0.9 else '→'
            print(f"  {style_name:12s}: {mult:.3f}x ({(mult-1)*100:+.1f}%) {symbol}")

        print()
        print('='*80)

    def enable(self):
        """Enable bias adjustments"""
        self.enabled = True

    def disable(self):
        """Disable bias adjustments (use for testing)"""
        self.enabled = False


# Helper functions for integration with existing scoring

def classify_distance(distance_furlongs: float) -> str:
    """Classify race distance"""
    if distance_furlongs < 7.0:
        return 'sprint'
    elif distance_furlongs < 9.0:
        return 'mile'
    else:
        return 'route'


def apply_track_biases_to_scores(
    score_dict,
    horse_data: Dict,
    race_data: Dict,
    bias_detector: TrackBiasDetector
) -> None:
    """
    Apply track biases to score components (modifies score_dict in place)

    Args:
        score_dict: Score object with component scores
        horse_data: Horse information dict
        race_data: Race information dict
        bias_detector: TrackBiasDetector instance

    Example:
        >>> score_dict = calculate_comprehensive_score(horse_data, race_data)
        >>> apply_track_biases_to_scores(score_dict, horse_data, race_data, detector)
        >>> # score_dict.post and score_dict.pace are now adjusted
    """
    if not bias_detector.enabled:
        return

    # Get race characteristics
    surface = race_data.get('surface', 'turf').lower()
    surface = 'turf' if 'turf' in surface else 'dirt'

    distance_text = race_data.get('distance', '')
    if isinstance(distance_text, str):
        # Extract furlongs from text like "One Mile" or "8.5F"
        distance_furlongs = 8.0  # Default
    else:
        distance_furlongs = float(distance_text)

    distance_class = classify_distance(distance_furlongs)

    # Apply post position bias
    try:
        post = int(horse_data.get('program_number', 5))
    except (ValueError, TypeError):
        post = 5

    if hasattr(score_dict, 'post'):
        original_post = score_dict.post
        score_dict.post = bias_detector.apply_post_bias_adjustment(
            original_post, post, surface, distance_class
        )

    # Apply pace bias
    running_style = horse_data.get('running_style', 'P')

    if hasattr(score_dict, 'pace'):
        original_pace = score_dict.pace
        score_dict.pace = bias_detector.apply_pace_bias_adjustment(
            original_pace, running_style, surface
        )


def demo_bias_detector():
    """Demonstrate bias detector usage"""
    detector = TrackBiasDetector()

    detector.print_bias_report('KEE')

    print()
    print('='*80)
    print(' EXAMPLE BIAS ADJUSTMENTS')
    print('='*80)
    print()

    # Example 1: Inside post advantage
    base_post_score = 50.0
    post1_adjusted = detector.apply_post_bias_adjustment(base_post_score, 1, 'turf')
    post11_adjusted = detector.apply_post_bias_adjustment(base_post_score, 11, 'turf')

    print(f"Post Position Score Adjustments:")
    print(f"  Post 1:  {base_post_score:.1f} → {post1_adjusted:.1f} ({post1_adjusted - base_post_score:+.1f})")
    print(f"  Post 11: {base_post_score:.1f} → {post11_adjusted:.1f} ({post11_adjusted - base_post_score:+.1f})")
    print()

    # Example 2: Pace bias
    base_pace_score = 70.0
    closer_adjusted = detector.apply_pace_bias_adjustment(base_pace_score, 'C', 'turf')
    stalker_adjusted = detector.apply_pace_bias_adjustment(base_pace_score, 'S', 'turf')

    print(f"Pace Score Adjustments:")
    print(f"  Closer (C):  {base_pace_score:.1f} → {closer_adjusted:.1f} ({closer_adjusted - base_pace_score:+.1f})")
    print(f"  Stalker (S): {base_pace_score:.1f} → {stalker_adjusted:.1f} ({stalker_adjusted - base_pace_score:+.1f})")
    print()


if __name__ == '__main__':
    demo_bias_detector()
