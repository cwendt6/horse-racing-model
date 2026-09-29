"""
Predict Race from PDF Past Performances
Uses PDF parser to extract data and runs prediction model with optimized weights
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import json
from datetime import datetime

# Import PDF parser (using Hybrid Parser V3 for best quality)
from src.parsers.hybrid_parser_v3 import parse_pdf_hybrid_v3

# Import model components
from src.data_loaders.statistics_loader import StatisticsLoader
from src.analyzers.fts_analyzer import FTSAnalyzer
from src.analyzers.pace_analyzer import PaceAnalyzer
from src.analyzers import racing_statistics as stats

# Import enhanced pace analyzer
from src.analyzers.pace_analyzer_enhanced import EnhancedPaceAnalyzer, format_pace_analysis
from src.analyzers.pace_adapter import (
    convert_pdf_race_to_enhanced,
    apply_pace_adjustments_to_pdf_horses,
    RunningStyle
)

# Import NEW pace scenario V2 (CRITICAL FIX - replaces broken PPI method)
from src.analyzers.pace_scenario_v2 import (
    PaceScenarioCalculatorV2,
    analyze_race_pace,
    get_pace_multiplier
)

# Import enhanced jockey analyzer (CRITICAL FIX #2 - jockey underweighted)
from src.analyzers.jockey_enhanced_analyzer import EnhancedJockeyAnalyzer

# Import trainer specialization analyzer (CRITICAL FIX #3 - trainer patterns)
from src.analyzers.trainer_specialization_analyzer import TrainerSpecializationAnalyzer

# Import betting modules
from src.betting.probability_calibrator import ProbabilityCalibrator
from src.betting.value_detector import ValueDetector

# Import track bias detector
from src.analyzers.track_bias_detector import TrackBiasDetector

# Import exotic betting strategy
from src.betting.exotic_strategy import ExoticStrategy

# Import jockey-trainer combination analyzer
from src.analyzers.jockey_trainer_analyzer import JockeyTrainerAnalyzer

# Import distance/surface analyzer
from src.analyzers.distance_surface_analyzer import DistanceSurfaceAnalyzer

# Import equipment analyzer (CRITICAL for accuracy)
from src.analyzers.equipment_analyzer import EquipmentAnalyzer

# Import trip notes analyzer (bounce-back detection)
from src.analyzers.trip_notes_analyzer import TripNotesAnalyzer

# Import workout analyzer (fitness assessment)
from src.analyzers.workout_analyzer import WorkoutAnalyzer

# Import trainer pattern detector (specialist detection)
from src.analyzers.trainer_pattern_detector import TrainerPatternDetector

# Import maiden-specific weights (CRITICAL FIX #4 - October 23 validation)
from src.utils.maiden_weights import get_weights_for_race, is_maiden_race

# Import jockey-trainer combo analyzer (CRITICAL FIX #5 - elite combinations)
from src.analyzers.jockey_trainer_combos import JockeyTrainerComboAnalyzer


def calculate_expected_value(win_probability, ml_odds, bet_amount=2.0):
    """
    Calculate expected value (EV) of a bet.

    EV = (win_probability × payout) - (loss_probability × bet_amount)

    Args:
        win_probability: Model's win probability (0.0 to 1.0)
        ml_odds: Morning line odds (fractional, e.g., 5.0 for 5-1)
        bet_amount: Amount to bet (default $2)

    Returns:
        Tuple of (ev_percentage, ev_dollars)
        - ev_percentage: EV as percentage of bet amount
        - ev_dollars: EV in dollars

    Examples:
        >>> calculate_expected_value(0.30, 5.0, 2.0)
        (80.0, 1.60)  # +80% EV, +$1.60 expected profit

        >>> calculate_expected_value(0.30, 2.0, 2.0)
        (-10.0, -0.20)  # -10% EV, -$0.20 expected loss
    """
    # Convert fractional odds to decimal (payout multiplier)
    # 5-1 odds = 5.0 fractional = 6.0 decimal (bet $1, get back $6 if win)
    decimal_odds = ml_odds + 1.0

    # Calculate expected return
    payout_if_win = decimal_odds * bet_amount
    expected_return = win_probability * payout_if_win

    # Calculate EV
    ev_dollars = expected_return - bet_amount
    ev_percentage = (ev_dollars / bet_amount) * 100

    return ev_percentage, ev_dollars


def load_optimized_weights(surface='dirt', race_type='', race_class=''):
    """
    Load optimized weights for the specified surface and race type.

    CRITICAL UPDATE (Oct 23, 2025): Uses maiden-specific weights when applicable.
    Based on race results showing 100% of maiden races won by elite FTS trainers.
    """
    # Check if this is a maiden race
    if is_maiden_race(race_type, race_class):
        # Use maiden-specific weights (trainer 35-42% vs standard 18.22%)
        maiden_weights = get_weights_for_race(race_type, race_class)
        print(f"🎯 MAIDEN RACE DETECTED - Using maiden-specific weights")
        print(f"   Trainer weight: {maiden_weights['trainer']:.1%} (vs standard 18.22%)")
        return maiden_weights

    # Non-maiden races: try surface-specific weights first
    weight_files = {
        'dirt': 'output/dirt_optimized_weights.json',
        'turf': 'output/turf_optimized_weights.json',
        'default': 'output/optimized_weights_2023_full.json'
    }

    weight_file = weight_files.get(surface.lower(), weight_files['default'])

    # Fall back to default if surface-specific doesn't exist
    if not os.path.exists(weight_file):
        weight_file = weight_files['default']

    try:
        with open(weight_file, 'r') as f:
            weights = json.load(f)
        print(f"✓ Loaded weights from: {weight_file}")
        return weights
    except Exception as e:
        print(f"✗ Could not load weights: {e}")
        # Return default weights
        return {
            'speed': 0.30,
            'form': 0.20,
            'class': 0.15,
            'pace': 0.15,
            'jockey': 0.10,
            'trainer': 0.10
        }


def convert_pdf_horse_to_model_format(pdf_horse, race_data, jockey_stats, trainer_stats, fts_data):
    """Convert PDFHorse to format expected by model"""

    # Parse ML odds to decimal
    ml_odds = pdf_horse.morning_line_odds
    try:
        if '-' in ml_odds:
            num, den = ml_odds.split('-')
            decimal_odds = (float(num) / float(den)) + 1.0
        elif '/' in ml_odds:
            num, den = ml_odds.split('/')
            decimal_odds = (float(num) / float(den)) + 1.0
        else:
            decimal_odds = float(ml_odds)
    except:
        decimal_odds = 6.0  # Default

    # Extract recent finishes from past performances for form score calculation
    recent_finishes = []
    if pdf_horse.past_performances:
        # Past performances have format: {'early': (call1, call2), 'stretch': X, 'finish': Y}
        # Extract finish positions (most recent first, limit to 5 races)
        recent_finishes = [pp['finish'] for pp in pdf_horse.past_performances[:5] if 'finish' in pp]

    # Parse program number to integer for post position
    try:
        post_position = int(pdf_horse.program_number)
    except (ValueError, TypeError):
        post_position = 5  # Default middle post

    # Calculate days since last race
    days_since_last = 999  # Default for no data
    if pdf_horse.last_race_date and race_data.get('date'):
        try:
            from datetime import datetime
            race_date = datetime.strptime(race_data['date'], '%Y-%m-%d')
            last_race = datetime.strptime(pdf_horse.last_race_date, '%Y-%m-%d')
            days_since_last = (race_date - last_race).days
        except:
            pass  # Keep default

    horse_data = {
        'name': pdf_horse.name,
        'program_number': pdf_horse.program_number,
        'jockey_name': pdf_horse.jockey_name,
        'trainer_name': pdf_horse.trainer_name,
        'morning_line_odds': decimal_odds,

        # Post position
        'post': post_position,

        # Speed figures
        'best_beyer': pdf_horse.best_speed_figure if pdf_horse.best_speed_figure > 0 else 70,
        'last_beyer': pdf_horse.last_speed_figure if pdf_horse.last_speed_figure > 0 else 70,
        'avg_beyer': pdf_horse.avg_speed_figure if pdf_horse.avg_speed_figure > 0 else 70,

        # Career stats
        'career_starts': pdf_horse.career_starts if pdf_horse.career_starts > 0 else 10,
        'career_wins': pdf_horse.career_wins,
        'career_earnings': pdf_horse.career_earnings if pdf_horse.career_earnings > 0 else 50000,

        # Recent form
        'recent_finishes': recent_finishes,
        'days_since_last_race': days_since_last,
        'past_performances': pdf_horse.past_performances if pdf_horse.past_performances else [],

        # Jockey/Trainer stats
        'jockey_win_pct': jockey_stats.win_percentage / 100.0 if jockey_stats else 0.15,
        'trainer_win_pct': trainer_stats.win_percentage / 100.0 if trainer_stats else 0.15,

        # Running style (from parser)
        'running_style': pdf_horse.running_style,

        # FTS
        'is_fts': fts_data.get('is_fts', False),
        'fts_advantage': fts_data.get('advantage', 0.0),
    }

    return horse_data


def predict_race(pdf_race, stats_loader, fts_analyzer, pace_analyzer, enhanced_pace_analyzer, track_bias_detector, jockey_trainer_analyzer, distance_surface_analyzer, equipment_analyzer, trip_notes_analyzer, workout_analyzer, trainer_pattern_detector, enhanced_jockey_analyzer, trainer_specialization_analyzer, jt_combo_analyzer, weights):
    """Generate predictions for a PDF race with elite combo bonuses"""

    print(f"\n{'='*80}")
    print(f" RACE {pdf_race.race_number}: {pdf_race.track_name}")
    print(f"{'='*80}")
    print(f"Date: {pdf_race.date}")
    print(f"Distance: {pdf_race.distance_text}")
    print(f"Surface: {pdf_race.surface_description}")
    print(f"Type: {pdf_race.race_type}")
    print(f"Purse: ${pdf_race.purse:,.0f}")
    print(f"Horses: {len(pdf_race.horses)}")

    if len(pdf_race.horses) == 0:
        print("✗ No horses found in race")
        return None

    # Build race data
    race_data = {
        'date': pdf_race.date,
        'distance': pdf_race.distance_text,
        'surface': pdf_race.surface_description.lower(),
        'track_condition': pdf_race.track_condition,
        'purse': pdf_race.purse if pdf_race.purse > 0 else 50000,  # Default purse if not found
        'field_size': len(pdf_race.horses),
        'avg_beyer': 70,  # Would calculate from horses if we had more data
    }

    # OLD PACE ANALYSIS (basic - keep for comparison)
    # PaceAnalyzer expects list of horse dicts with 'running_style' and 'name' keys
    horse_pace_data = [{'running_style': h.running_style, 'name': h.name} for h in pdf_race.horses]
    distance_furlongs = pdf_race.distance / 100.0  # Convert from 850 to 8.5
    pace_scenario = pace_analyzer.analyze_pace(horse_pace_data, distance_furlongs)
    race_data['pace_scenario'] = pace_scenario.scenario_type

    print(f"\nOld Pace Scenario: {pace_scenario.scenario_type.replace('_', ' ').title()}")

    # ENHANCED PACE ANALYSIS (RE-ENABLED after fixing PP extraction)
    # The pace_adapter.py handles conversion of PP dictionaries to objects
    try:
        # Convert race to enhanced format (this creates new Horse objects with PastPerformance objects)
        enhanced_race = convert_pdf_race_to_enhanced(pdf_race)

        # Get track bias if available
        track_bias = None
        try:
            track_bias = track_bias_detector.get_bias(
                pdf_race.track_code,
                pdf_race.date,
                pdf_race.surface
            )
        except:
            pass  # No bias available, continue without it

        # Analyze pace with enhanced system
        pace_analysis = enhanced_pace_analyzer.analyze_race_pace(
            enhanced_race,
            track_bias=track_bias
        )

        # Print enhanced analysis
        print("\n" + "="*80)
        print(format_pace_analysis(pace_analysis, enhanced_race))
        print("="*80)

        # Apply pace adjustments to horses
        apply_pace_adjustments_to_pdf_horses(enhanced_race.horses, pdf_race.horses, pace_analysis)

        print(f"\n✓ Enhanced pace analysis complete!")
        print(f"  PPI: {pace_analysis.pace_pressure_index:.1f}")
        print(f"  Scenario: {pace_analysis.scenario}")

    except Exception as e:
        print(f"\n⚠️  Enhanced pace analysis failed: {e}")
        print("   Continuing with basic pace only...")
        # Set default pace adjustments
        for horse in pdf_race.horses:
            horse.pace_adjustment = 0.0
            horse.pace_figures = None

    # PACE SCENARIO V2 - CRITICAL FIX (replaces broken PPI method)
    print(f"\n{'='*80}")
    print(f"PACE SCENARIO V2 - Granular Speed Horse Counting")
    print(f"{'='*80}")

    try:
        # Build horse data for V2 pace analysis
        horses_pace_data = []
        for horse in pdf_race.horses:
            horses_pace_data.append({
                'name': horse.name,
                'program_number': horse.program_number,
                'running_style': horse.running_style,  # E, EP, P, S
                'best_beyer': horse.best_speed_figure if horse.best_speed_figure > 0 else 70,
                'avg_early_position': horse.avg_early_position if hasattr(horse, 'avg_early_position') else 5.0
            })

        # Calculate pace scenario V2
        pace_scenario_v2 = analyze_race_pace(
            horses_pace_data,
            distance_furlongs,
            surface=pdf_race.surface_description.lower()
        )

        # Print V2 analysis report
        calculator_v2 = PaceScenarioCalculatorV2()
        print(calculator_v2.format_scenario_report(pace_scenario_v2))

        print(f"\n✓ Pace Scenario V2 calculation complete!")

    except Exception as e:
        print(f"\n⚠️  Pace Scenario V2 failed: {e}")
        print("   Using default pace multipliers...")
        pace_scenario_v2 = None

    # Score each horse
    predictions = []

    for horse in pdf_race.horses:
        # Get jockey/trainer stats
        jockey_stats = stats_loader.get_jockey_stats(horse.jockey_name)
        trainer_stats = stats_loader.get_trainer_stats(horse.trainer_name)

        # Calculate jockey-trainer combination bonus (existing stats-based)
        jt_bonus = 0.0
        jt_description = ""
        if horse.jockey_name and horse.trainer_name:
            jockey_rate = jockey_stats.win_percentage / 100.0 if jockey_stats else 0.0
            trainer_rate = trainer_stats.win_percentage / 100.0 if trainer_stats else 0.0
            jt_bonus, jt_description, jt_details = jockey_trainer_analyzer.analyze_combination(
                horse.jockey_name,
                horse.trainer_name,
                jockey_rate,
                trainer_rate
            )

        # Calculate ELITE jockey-trainer combo bonus (NEW - October 23 validation)
        elite_combo_bonus = 0.0
        elite_combo_desc = ""
        if horse.jockey_name and horse.trainer_name:
            elite_combo_bonus, elite_combo_desc = jt_combo_analyzer.get_combo_bonus(
                horse.trainer_name,
                horse.jockey_name
            )

        # Calculate distance/surface fit bonus
        ds_bonus = 0.0
        ds_notes = []
        try:
            ds_bonus, ds_notes = distance_surface_analyzer.analyze_horse(
                horse,
                pdf_race.distance_description,  # e.g., "6f", "1m"
                race_data['surface']  # "dirt", "turf", etc.
            )
        except Exception as e:
            # If analysis fails, default to 0 bonus
            ds_bonus = 0.0
            ds_notes = []

        # Calculate equipment changes bonus (CRITICAL)
        equip_bonus = 0.0
        equip_notes = []
        try:
            today_equip = getattr(horse, 'today_equipment', {'blinkers': False, 'lasix': False})
            pps = getattr(horse, 'past_performances', [])
            equip_bonus, equip_notes = equipment_analyzer.analyze_horse(
                horse.name,
                today_equip,
                pps
            )
        except Exception as e:
            # If analysis fails, default to 0 bonus
            equip_bonus = 0.0
            equip_notes = []

        # Calculate trip notes bonus (bounce-back detection)
        trip_bonus = 0.0
        trip_notes = []
        try:
            pps = getattr(horse, 'past_performances', [])
            trip_bonus, trip_notes, trip_analysis = trip_notes_analyzer.analyze_horse(
                horse.name,
                pps
            )
        except Exception as e:
            trip_bonus = 0.0
            trip_notes = []

        # Calculate workout bonus (fitness assessment)
        workout_bonus = 0.0
        workout_notes = []
        try:
            # Workout analyzer needs PDF path for direct extraction
            # Pass None for now - workouts will be extracted from past_performances if available
            from datetime import datetime
            race_date = datetime.strptime(pdf_race.date, '%Y-%m-%d') if isinstance(pdf_race.date, str) else pdf_race.date
            workout_bonus, workout_notes = workout_analyzer.analyze_horse(
                horse,
                race_date,
                pdf_path=None  # Could pass PDF path here if needed
            )
        except Exception as e:
            workout_bonus = 0.0
            workout_notes = []

        # Calculate trainer pattern bonus (specialist detection)
        trainer_bonus = 0.0
        trainer_notes = []
        try:
            trainer_bonus, trainer_notes = trainer_pattern_detector.analyze_horse(
                horse,
                pdf_race.distance_text,
                race_data['surface']
            )
        except Exception as e:
            trainer_bonus = 0.0
            trainer_notes = []

        # Check FTS status
        fts_data = {
            'is_fts': horse.career_starts == 0,
            'advantage': 0.0
        }

        if fts_data['is_fts']:
            fts_multiplier, _ = fts_analyzer.calculate_fts_multiplier(
                trainer_name=horse.trainer_name,
                sire_name=horse.sire_name
            )
            fts_data['advantage'] = fts_multiplier - 1.0  # Convert multiplier to advantage

        # Parse ML odds to decimal for betting logic
        ml_odds = horse.morning_line_odds
        try:
            if '-' in ml_odds:
                num, den = ml_odds.split('-')
                decimal_odds = (float(num) / float(den)) + 1.0
            elif '/' in ml_odds:
                num, den = ml_odds.split('/')
                decimal_odds = (float(num) / float(den)) + 1.0
            else:
                decimal_odds = float(ml_odds)
        except:
            decimal_odds = 6.0  # Default

        # Convert to model format
        horse_data = convert_pdf_horse_to_model_format(
            horse, race_data, jockey_stats, trainer_stats, fts_data
        )

        # Calculate score (uses default weights internally)
        score = stats.calculate_comprehensive_score(horse_data, race_data)

        # ENHANCED JOCKEY SCORING (CRITICAL FIX #2)
        # Replace basic jockey score with enhanced version
        jockey_win_rate = jockey_stats.win_percentage / 100.0 if jockey_stats else 0.10
        jockey_itm_rate = jockey_stats.itm_percentage / 100.0 if jockey_stats and hasattr(jockey_stats, 'itm_percentage') else None

        # Determine race type and horse experience
        is_maiden_race = 'maiden' in pdf_race.race_type.lower() if pdf_race.race_type else False

        # ADDITIONAL MAIDEN DETECTION: Check if this is a claiming race with low purse and inexperienced horses
        # This catches "Maiden Claiming" races where parser only extracted "Claiming"
        if not is_maiden_race and pdf_race.race_type and 'claiming' in pdf_race.race_type.lower():
            # Check if it's a low-purse claiming race with mostly inexperienced horses
            if pdf_race.purse > 0 and pdf_race.purse <= 70000:  # Maiden claiming typically $55-70k
                # Count horses with very limited experience
                limited_exp_count = sum(1 for h in pdf_race.horses if h.career_starts <= 3)
                if limited_exp_count >= len(pdf_race.horses) * 0.40:  # 40%+ have <=3 starts
                    is_maiden_race = True
                    print(f"   🔍 DETECTED LIKELY MAIDEN CLAIMING (low purse ${pdf_race.purse:,.0f}, {limited_exp_count}/{len(pdf_race.horses)} horses with <=3 starts)")

        is_fts = horse.career_starts == 0

        # Get enhanced jockey analysis
        jockey_analysis = enhanced_jockey_analyzer.analyze_jockey(
            jockey_name=horse.jockey_name,
            win_rate=jockey_win_rate,
            itm_rate=jockey_itm_rate,
            race_type=pdf_race.race_type,
            horse_experience_level='fts' if is_fts else 'maiden' if is_maiden_race else 'experienced'
        )

        # Replace basic jockey score with enhanced version
        enhanced_jockey_score = jockey_analysis.total_score
        jockey_notes = jockey_analysis.analysis_notes

        # ENHANCED TRAINER SCORING (CRITICAL FIX #3)
        # Replace basic trainer score with specialty-aware version
        trainer_win_rate = trainer_stats.win_percentage / 100.0 if trainer_stats else 0.10

        # Determine horse age (approximate from career starts if not available)
        horse_age = 3  # Default
        if hasattr(horse, 'age'):
            horse_age = horse.age
        elif horse.career_starts == 0:
            horse_age = 2  # FTS likely 2YO
        elif horse.career_starts <= 5:
            horse_age = 3  # Lightly raced likely 3YO

        # Get trainer specialization analysis
        trainer_analysis = trainer_specialization_analyzer.analyze_trainer(
            trainer_name=horse.trainer_name,
            win_rate=trainer_win_rate,
            race_type=pdf_race.race_type,
            surface=pdf_race.surface_description.lower(),
            distance_furlongs=distance_furlongs,
            horse_age=horse_age,
            is_fts=is_fts
        )

        # Replace basic trainer score with enhanced version
        enhanced_trainer_score = trainer_analysis.total_score
        trainer_notes = trainer_analysis.analysis_notes

        # CRITICAL FIX #6 - ELITE TRAINER PROXY SCORING FOR MAIDEN RACES (October 23 validation)
        # Elite trainers (especially FTS specialists) in maiden races know which horses are ready
        # Lack of speed/form history should not penalize horses from elite trainers in maidens
        # This applies to ALL maiden horses with elite trainers, not just FTS
        if is_maiden_race:
            # VALIDATED ELITE FTS TRAINERS (Oct 23 analysis: 100% of maidens won by elite FTS)
            # These rates are from actual race results, not the broken FTS statistics file
            ELITE_FTS_TRAINERS_VALIDATED = {
                'Chad Brown': 0.7692,
                'Chad C Brown': 0.7692,
                'Chad C. Brown': 0.7692,
                'Brendan Walsh': 0.6563,
                'Brendan P Walsh': 0.6563,
                'Brendan P. Walsh': 0.6563,
                'Todd Pletcher': 0.6923,
                'Todd A Pletcher': 0.6923,
                'Todd A. Pletcher': 0.6923,
                'Brad Cox': 0.4348,
                'Brad H Cox': 0.4348,
                'Brad H. Cox': 0.4348,
                'Steven Asmussen': 0.4872,
                'Steven M Asmussen': 0.4872,
                'Steven M. Asmussen': 0.4872,
                'Steve Asmussen': 0.4872,
                'William Mott': 0.4500,
                'William I Mott': 0.4500,
                'William I. Mott': 0.4500,
            }

            # Get trainer's elite status from trainer_specialization_analyzer
            # (More reliable than FTS database which may be outdated)
            trainer_fts_rate = 0.0
            is_elite_maiden_trainer = False

            # FIRST: Check validated elite FTS trainers list (PRIORITY)
            if horse.trainer_name in ELITE_FTS_TRAINERS_VALIDATED:
                trainer_fts_rate = ELITE_FTS_TRAINERS_VALIDATED[horse.trainer_name]
                is_elite_maiden_trainer = True
                print(f"   ✅ VALIDATED ELITE FTS TRAINER: {horse.trainer_name} ({trainer_fts_rate:.1%} FTS rate)")

            # FALLBACK: Check if trainer has elite status (win rate >= 20% = elite trainer)
            elif trainer_win_rate >= 0.20:
                # Elite trainers (20%+ overall) get strong proxy in maidens
                trainer_fts_rate = 0.70  # Assume strong FTS capability for elite trainers
                is_elite_maiden_trainer = True
            elif trainer_win_rate >= 0.15:
                # Above average trainers get moderate proxy
                trainer_fts_rate = 0.50
                is_elite_maiden_trainer = True

            # Also check if trainer got specialty bonuses (indicates elite status)
            if trainer_analysis and hasattr(trainer_analysis, 'multiplier_applied'):
                if trainer_analysis.multiplier_applied >= 1.50:  # Elite multiplier
                    trainer_fts_rate = max(trainer_fts_rate, 0.70)  # Assume elite FTS capability
                    is_elite_maiden_trainer = True

            # Apply FTS proxy scoring based on trainer quality
            proxy_applied = False

            if is_elite_maiden_trainer and trainer_fts_rate >= 0.50:  # Elite or above-average trainers
                # Determine proxy level based on trainer quality
                if trainer_fts_rate >= 0.70:
                    proxy_level = "ELITE"
                    form_proxy = 75.0
                    speed_proxy = 75.0
                else:
                    proxy_level = "STRONG"
                    form_proxy = 65.0
                    speed_proxy = 70.0

                # Apply form proxy for horses with low/zero form
                if score.form <= 10.0:
                    original_form = score.form
                    score.form = form_proxy
                    print(f"   🎯 FTS PROXY ({proxy_level}): Form {original_form:.1f} → {score.form:.1f} (Trainer: {horse.trainer_name})")
                    proxy_applied = True

                # Apply speed proxy for horses with low speed figures
                if score.speed < 70.0:
                    original_speed = score.speed
                    score.speed = speed_proxy
                    print(f"   🎯 FTS PROXY ({proxy_level}): Speed {original_speed:.1f} → {score.speed:.1f}")
                    proxy_applied = True

            elif trainer_fts_rate >= 0.40:  # 40-59% FTS success rate
                # Above average FTS trainers - assign moderate proxy scores
                if score.form == 0.0:
                    score.form = 55.0  # Moderate proxy
                    print(f"   🎯 FTS PROXY (MODERATE): Form 0.0 → 55.0 (Trainer FTS: {trainer_fts_rate:.1%})")
                    proxy_applied = True

                if score.speed < 60.0:
                    original_speed = score.speed
                    score.speed = 65.0  # Moderate proxy
                    print(f"   🎯 FTS PROXY (MODERATE): Speed {original_speed:.1f} → 65.0")
                    proxy_applied = True

            if proxy_applied:
                print(f"   ✅ Applied FTS proxy scoring for {horse.trainer_name} (FTS rate: {trainer_fts_rate:.1%})")

        # Apply track bias adjustments
        surface = race_data['surface'].lower()
        distance_class = 'sprint' if pdf_race.distance < 800 else 'mile' if pdf_race.distance <= 900 else 'route'

        # Adjust post score based on track bias
        try:
            post_pos = int(horse.program_number)
        except (ValueError, AttributeError):
            post_pos = 5  # Default to middle post if can't parse

        adjusted_post_score = track_bias_detector.apply_post_bias_adjustment(
            score.post,
            post_pos,
            surface,
            distance_class
        )

        # Adjust pace score based on running style bias
        adjusted_pace_score = track_bias_detector.apply_pace_bias_adjustment(
            score.pace,
            horse.running_style,
            surface
        )

        # Apply Pace Scenario V2 multiplier (CRITICAL FIX)
        pace_multiplier = 1.0  # Default if V2 calculation failed
        if pace_scenario_v2:
            try:
                pace_multiplier = get_pace_multiplier(pace_scenario_v2, horse.running_style)
            except Exception as e:
                pace_multiplier = 1.0  # Fallback to neutral if error

        # Apply V2 multiplier to pace score
        final_pace_score = adjusted_pace_score * pace_multiplier

        # Recalculate total with optimized weights (October 2025 optimization)
        # RESTORED: Using basic pace score while enhanced pace is being debugged
        # NOW: With track bias + jockey-trainer combo + distance/surface bonuses
        # CRITICAL FIX: Apply bonus scales (were optimized but not being used!)
        # NEW OCT 2025: Apply Pace Scenario V2 multipliers (fixes 0% pace accuracy)
        # NEW OCT 2025: Apply Enhanced Jockey Scoring (fixes jockey underweighting)
        # NEW OCT 2025: Apply Trainer Specialization (fixes trainer pattern misses)
        # NEW OCT 23 2025: Apply Elite Combo Bonuses (validated by race results)
        # NEW OCT 23 2025: Apply Maiden-Specific Weights (100% maiden win rate validation)
        final_score = (
            score.speed * weights.get('speed', 0.2292) +
            score.form * weights.get('form', 0.1458) +
            score.class_rating * weights.get('class_rating', 0.1250) +
            final_pace_score * weights.get('pace', 0.1042) +  # V2 multiplier + track bias
            score.recency * weights.get('recency', 0.0833) +
            score.progression * weights.get('progression', 0.0938) +
            enhanced_jockey_score * weights.get('jockey', 0.500) +  # ENHANCED with conditional multipliers
            enhanced_trainer_score * weights.get('trainer', 0.1822) +  # ENHANCED with specialty patterns (35-42% in maidens!)
            adjusted_post_score * weights.get('post_position', 0.0521) +  # Track bias adjusted
            jt_bonus * weights.get('jt_combo_scale', 1.0) +  # Jockey-trainer combination bonus (-4 to +9)
            elite_combo_bonus +  # ELITE combo bonus (0 to +20) - NEW!
            ds_bonus * weights.get('distance_surface_scale', 1.0) +  # Distance/surface fit bonus (-13 to +10)
            equip_bonus * weights.get('equipment_scale', 1.0) +  # Equipment changes bonus (-3 to +7) CRITICAL
            trip_bonus * weights.get('trip_notes_scale', 1.0) +  # Trip trouble/bounce-back bonus (0 to +15)
            workout_bonus * weights.get('workout_scale', 1.0) +  # Workout fitness bonus (-5 to +15)
            trainer_bonus * weights.get('trainer_pattern_scale', 1.0)  # Trainer pattern bonus (0 to +10)
        )

        # Store pace advantage for display (from basic pace analyzer)
        pace_advantage = score.pace

        predictions.append({
            'program_number': horse.program_number,
            'horse_name': horse.name,
            'name': horse.name,  # For ValueDetector compatibility
            'jockey_name': horse.jockey_name,
            'trainer_name': horse.trainer_name,
            'ml_odds': decimal_odds,  # Store decimal version for betting logic
            'ml_odds_display': horse.morning_line_odds,  # Keep original for display
            'best_beyer': horse.best_speed_figure,
            'running_style': horse.running_style,  # E, P, S, or C
            'style_confidence': horse.style_confidence,  # Confidence in classification
            'avg_early_position': horse.avg_early_position,
            'avg_stretch_position': horse.avg_stretch_position,
            'avg_finish_position': horse.avg_finish_position,
            'avg_position_change': horse.avg_position_change,
            'versatility': horse.versatility,
            'score': final_score,
            'speed_score': score.speed,
            'form_score': score.form,
            'class_score': score.class_rating,
            'pace_score': score.pace,
            'pace_multiplier': pace_multiplier,  # V2 pace multiplier (0.70 to 1.45)
            'jockey_score': enhanced_jockey_score,  # Enhanced jockey score with conditional multipliers
            'jockey_notes': jockey_notes,  # Jockey analysis notes for display
            'trainer_score': enhanced_trainer_score,  # Enhanced trainer score with specialty patterns
            'trainer_notes': trainer_notes,  # Trainer analysis notes for display
            'post_score': score.post,
            'recency_score': score.recency,
            'progression_score': score.progression,
            'is_fts': fts_data['is_fts'],
            'pace_advantage': pace_advantage,
            'jt_combo_bonus': jt_bonus,
            'jt_combo_description': jt_description,
            'ds_bonus': ds_bonus,
            'ds_notes': ds_notes,
            'equip_bonus': equip_bonus,
            'equip_notes': equip_notes,
            'trip_bonus': trip_bonus,
            'trip_notes': trip_notes,
            'workout_bonus': workout_bonus,
            'workout_notes': workout_notes,
            'trainer_bonus': trainer_bonus,
            'trainer_notes': trainer_notes,
            # Enhanced pace figures
            'early_pace_figure': getattr(horse, 'early_pace_figure', None),
            'late_pace_figure': getattr(horse, 'late_pace_figure', None),
            'pace_confidence': getattr(horse, 'pace_confidence', None),
            'pace_method': getattr(horse, 'pace_method', None),
        })

    # Sort by score
    predictions.sort(key=lambda x: x['score'], reverse=True)

    # SEPARATE ALSO ELIGIBLE HORSES (they may not run, so exclude from top picks)
    regular_horses = []
    ae_horses = []

    for pred in predictions:
        pgm = pred['program_number']
        if isinstance(pgm, str) and pgm.startswith('AE'):
            ae_horses.append(pred)
        else:
            regular_horses.append(pred)

    # Add ranks to regular horses only
    for i, pred in enumerate(regular_horses, 1):
        pred['rank'] = i

    # Add ranks to AE horses (separate numbering)
    for i, pred in enumerate(ae_horses, 1):
        pred['rank'] = i
        pred['is_also_eligible'] = True  # Flag for display

    # Use ProbabilityCalibrator ONLY on regular horses (AE horses excluded from probabilities)
    calibrator = ProbabilityCalibrator()
    regular_horses = calibrator.calibrate_race_probabilities(regular_horses)

    # AE horses get default low probability (they may not race)
    for pred in ae_horses:
        pred['probability'] = 0.05  # 5% baseline
        pred['fair_odds'] = 19.0  # 19-1 default

    # Use ValueDetector to identify overlay opportunities (ONLY on regular horses)
    value_detector = ValueDetector(
        min_edge=0.15,  # 15% minimum edge
        min_probability=0.10,  # Don't bet horses < 10% win prob
        max_odds=20.0  # Don't bet extreme longshots > 20-1
    )

    # Update regular horses with morning line odds for value detection
    for pred in regular_horses:
        pred['morning_line_odds'] = pred['ml_odds']  # Value detector expects this key

    # Identify value bets (ONLY from regular horses - don't bet AE horses)
    value_bets = value_detector.identify_value_bets(regular_horses)

    # Calculate Expected Value (EV) for all horses
    for pred in regular_horses:
        pred['expected_value'], pred['ev_dollars'] = calculate_expected_value(
            win_probability=pred['probability'],
            ml_odds=pred['ml_odds'],
            bet_amount=2.0
        )

    # Add value bet flags to regular horses
    for pred in regular_horses:
        # Find if this horse is a value bet
        is_value = any(vb.program_number == pred['program_number'] for vb in value_bets)
        pred['bet_recommended'] = is_value

        # Add edge info
        if is_value:
            vb = next(vb for vb in value_bets if vb.program_number == pred['program_number'])
            pred['value_edge'] = vb.edge * 100  # Convert to percentage
        else:
            pred['value_edge'] = 0.0

    # AE horses not recommended for betting
    for pred in ae_horses:
        pred['bet_recommended'] = False
        pred['value_edge'] = 0.0
        pred['expected_value'] = 0.0
        pred['ev_dollars'] = -2.0  # Expected loss on $2 bet

    return regular_horses, ae_horses, pace_scenario, value_bets


def print_predictions(predictions, ae_horses, pace_scenario, value_bets=None, race_type='', race_class=''):
    """
    Print formatted predictions with value betting opportunities

    Args:
        predictions: List of regular horse predictions (sorted by rank)
        ae_horses: List of ALSO ELIGIBLE horse predictions
        pace_scenario: Pace analysis result
        value_bets: List of value betting opportunities
        race_type: Type of race (for maiden detection)
        race_class: Class of race (for maiden detection)
    """

    # CRITICAL ALERT: Maiden races with elite FTS trainers
    if is_maiden_race(race_type, race_class):
        # Find elite FTS trainers in this race
        elite_fts_threats = []

        # Define elite FTS trainers with their stats
        ELITE_FTS_TRAINERS = {
            'Chad Brown': {'fts_rate': 0.7692, 'tier': 'ELITE'},
            'Chad C Brown': {'fts_rate': 0.7692, 'tier': 'ELITE'},
            'Chad C. Brown': {'fts_rate': 0.7692, 'tier': 'ELITE'},
            'Brendan Walsh': {'fts_rate': 0.6563, 'tier': 'ELITE'},
            'Brendan P Walsh': {'fts_rate': 0.6563, 'tier': 'ELITE'},
            'Brendan P. Walsh': {'fts_rate': 0.6563, 'tier': 'ELITE'},
            'Todd Pletcher': {'fts_rate': 0.6923, 'tier': 'ELITE'},
            'Todd A Pletcher': {'fts_rate': 0.6923, 'tier': 'ELITE'},
            'Todd A. Pletcher': {'fts_rate': 0.6923, 'tier': 'ELITE'},
            'Brad Cox': {'fts_rate': 0.4348, 'tier': 'STRONG'},
            'Brad H Cox': {'fts_rate': 0.4348, 'tier': 'STRONG'},
            'Brad H. Cox': {'fts_rate': 0.4348, 'tier': 'STRONG'},
            'Steven Asmussen': {'fts_rate': 0.4872, 'tier': 'STRONG'},
            'Steven M Asmussen': {'fts_rate': 0.4872, 'tier': 'STRONG'},
            'Steven M. Asmussen': {'fts_rate': 0.4872, 'tier': 'STRONG'},
            'Steve Asmussen': {'fts_rate': 0.4872, 'tier': 'STRONG'},
        }

        ELITE_JOCKEYS = [
            'Irad Ortiz Jr', 'Irad Ortiz, Jr', 'Irad Ortiz, Jr.',
            'Tyler Gaffalione', 'Luis Saez', 'Joel Rosario',
            'Javier Castellano', 'Jose Ortiz', 'Flavien Prat'
        ]

        for pred in predictions:
            trainer = pred.get('trainer_name', '')
            jockey = pred.get('jockey_name', '')

            if trainer in ELITE_FTS_TRAINERS:
                trainer_info = ELITE_FTS_TRAINERS[trainer]
                is_elite_jockey = any(ej.lower() in jockey.lower() for ej in ELITE_JOCKEYS)

                threat_level = '🚨 CRITICAL' if (trainer_info['tier'] == 'ELITE' and is_elite_jockey) else '⚠️ HIGH' if trainer_info['tier'] == 'ELITE' else '⚡ MODERATE'

                elite_fts_threats.append({
                    'horse': pred['horse_name'],
                    'program_number': pred['program_number'],
                    'trainer': trainer,
                    'jockey': jockey,
                    'fts_rate': trainer_info['fts_rate'],
                    'tier': trainer_info['tier'],
                    'is_elite_jockey': is_elite_jockey,
                    'threat_level': threat_level,
                    'model_rank': pred['rank'],
                    'win_prob': pred['probability']
                })

        # Display elite FTS threats if any found
        if elite_fts_threats:
            print(f"\n{'='*80}")
            print(f"🎯 MAIDEN RACE ALERT - ELITE FTS TRAINER THREATS")
            print(f"{'='*80}")
            print(f"\n⚠️  HISTORICAL VALIDATION: 100% of Oct 23 maiden races won by elite FTS trainers!")
            print(f"    Chad Brown (76.92% FTS), Brad Cox (43.48%), Asmussen (48.72%), Walsh (65.63%)")
            print(f"\n🔍 Elite FTS trainers in THIS race:\n")

            for threat in sorted(elite_fts_threats, key=lambda x: x['fts_rate'], reverse=True):
                print(f"{threat['threat_level']} THREAT: #{threat['program_number']} {threat['horse']}")
                print(f"    Trainer: {threat['trainer']} ({threat['fts_rate']:.1%} FTS rate - {threat['tier']})")
                print(f"    Jockey: {threat['jockey']}{' ⭐ ELITE JOCKEY' if threat['is_elite_jockey'] else ''}")
                print(f"    Model Rank: #{threat['model_rank']} ({threat['win_prob']*100:.1f}% win probability)")

                if threat['tier'] == 'ELITE' and threat['is_elite_jockey'] and threat['model_rank'] > 2:
                    print(f"    🚨 WARNING: Model ranked #{threat['model_rank']} but elite combo suggests TOP 2!")

                print()

            print(f"{'='*80}\n")

    # OLD PACE ANALYSIS DISPLAY - Commented out, using Enhanced Pace Analysis instead
    # print(f"\n{'-'*80}")
    # print(f"PACE ANALYSIS (Basic)")
    # print(f"{'-'*80}")
    # print(f"Pace Scenario: {pace_scenario.scenario_type.replace('_', ' ').title()}")
    # print(f"Early Speed: {pace_scenario.early_speed_count}  |  Pressers: {pace_scenario.presser_count}  |  Closers: {pace_scenario.closer_count}")
    # print(f"\n{pace_scenario.pace_description}")
    # if pace_scenario.advantage_horses:
    #     print(f"\n✨ Pace Advantage: {', '.join(pace_scenario.advantage_horses)}")

    print(f"\n{'-'*80}")
    print(f"TOP 5 PREDICTIONS")
    print(f"{'-'*80}")

    for pred in predictions[:5]:
        # Get running style label and confidence
        style_label = pred.get('running_style', 'P')
        style_confidence = pred.get('style_confidence', 0.0)
        style_names = {
            'E': 'Early Speed',
            'P': 'Presser',
            'S': 'Stalker',
            'C': 'Closer'
        }
        style_name = style_names.get(style_label, 'Presser')

        # Show confidence if available and significant
        confidence_text = f" ({style_confidence:.0%})" if style_confidence > 0.6 else ""

        print(f"\n{pred['rank']}. #{pred['program_number']} {pred['horse_name']} [{style_label}]")
        print(f"   Win Probability: {pred['probability']*100:.1f}%")
        print(f"   Fair Odds: {pred['fair_odds']:.1f}-1  |  ML Odds: {pred['ml_odds_display']}")

        # Show Expected Value (EV)
        ev_pct = pred.get('expected_value', 0.0)
        ev_dollars = pred.get('ev_dollars', 0.0)
        if ev_pct > 20:
            print(f"   📈 Expected Value: {ev_pct:+.1f}% (${ev_dollars:+.2f} per $2 bet) 🔥 STRONG VALUE")
        elif ev_pct > 0:
            print(f"   📈 Expected Value: {ev_pct:+.1f}% (${ev_dollars:+.2f} per $2 bet)")
        elif ev_pct > -10:
            print(f"   📉 Expected Value: {ev_pct:+.1f}% (${ev_dollars:+.2f} per $2 bet) ⚠️ MARGINAL")
        else:
            print(f"   📉 Expected Value: {ev_pct:+.1f}% (${ev_dollars:+.2f} per $2 bet) ❌ NEGATIVE")

        # Show betting recommendation
        if pred['bet_recommended']:
            print(f"   💰 BET RECOMMENDED (Value Edge: {pred['value_edge']:+.1f}%)")
        elif pred['value_edge'] > 0:
            print(f"   ⚠️  MARGINAL VALUE (Edge: {pred['value_edge']:+.1f}%)")
        else:
            print(f"   ❌ NO VALUE (Edge: {pred['value_edge']:+.1f}%)")

        print(f"   Running Style: {style_name}{confidence_text}")
        print(f"   Jockey: {pred['jockey_name']}")
        print(f"   Trainer: {pred['trainer_name']}")
        print(f"   Best Beyer: {pred['best_beyer']}")

        if pred['is_fts']:
            print(f"   ⭐ FIRST TIME STARTER")

        if abs(pred['pace_advantage']) > 0.05:
            # Pace score is already 0-100, display as-is (not multiplied)
            pace_mult = pred.get('pace_multiplier', 1.0)
            if pace_mult != 1.0:
                mult_emoji = "🔥" if pace_mult > 1.2 else "⚡" if pace_mult > 1.0 else "⚠️"
                print(f"   📊 Pace Score: {pred['pace_advantage']:+.1f} points × {pace_mult:.2f} {mult_emoji}")
            else:
                print(f"   📊 Pace Score: {pred['pace_advantage']:+.1f} points")

        # Show enhanced jockey analysis if significant
        jockey_notes = pred.get('jockey_notes', [])
        if jockey_notes:
            for note in jockey_notes:
                if '🌟' in note or '⭐' in note or '✓' in note or '⚠️' in note or '❌' in note:
                    print(f"   {note}")

        # Show enhanced trainer analysis if significant
        trainer_notes = pred.get('trainer_notes', [])
        if trainer_notes:
            for note in trainer_notes:
                if '🌟' in note or '⭐' in note or '🎯' in note or '✓' in note or '⚠️' in note or '❌' in note:
                    print(f"   {note}")

        # Show jockey-trainer combo if significant
        if abs(pred['jt_combo_bonus']) > 1.0:
            print(f"   {pred['jt_combo_description']}")

        # Show distance/surface notes if significant
        if abs(pred['ds_bonus']) > 2.0 and pred['ds_notes']:
            for note in pred['ds_notes']:
                if '✓' in note or '⚠️' in note or '❌' in note:  # Only show important notes
                    print(f"   {note}")

        # Show equipment notes if significant (CRITICAL)
        if abs(pred.get('equip_bonus', 0)) > 1.0 and pred.get('equip_notes'):
            for note in pred['equip_notes']:
                if '🎯' in note or '✓' in note or '⚠️' in note:  # Only show important equipment changes
                    print(f"   {note}")

        print(f"   Score Breakdown:")
        print(f"     Speed: {pred['speed_score']:.1f}  |  Form: {pred['form_score']:.1f}  |  Class: {pred['class_score']:.1f}  |  Pace: {pred['pace_advantage']:.1f}")
        print(f"     Recency: {pred['recency_score']:.1f}  |  Progression: {pred['progression_score']:.1f}  |  Jockey: {pred['jockey_score']:.1f}  |  Trainer: {pred['trainer_score']:.1f}  |  Post: {pred['post_score']:.1f}")
        if abs(pred['jt_combo_bonus']) > 0.5:
            print(f"     J-T Combo: {pred['jt_combo_bonus']:+.1f}")
        if abs(pred['ds_bonus']) > 1.0:
            print(f"     Distance/Surface: {pred['ds_bonus']:+.1f}")
        if abs(pred.get('equip_bonus', 0)) > 1.0:
            print(f"     Equipment: {pred['equip_bonus']:+.1f}")

    # ALSO ELIGIBLE HORSES - Show separately with warning
    if ae_horses and len(ae_horses) > 0:
        print(f"\n{'-'*80}")
        print(f"⚠️  ALSO ELIGIBLE HORSES (May not race - NOT included in top picks)")
        print(f"{'-'*80}")
        print(f"\nThese horses are alternates and will only race if there are scratches.")
        print(f"DO NOT bet on these horses unless you confirm they are declared to run.\n")

        for pred in ae_horses:
            style_label = pred.get('running_style', 'P')
            print(f"\n{pred['program_number']} {pred['horse_name']} [{style_label}]")
            print(f"   Model Score: {pred['score']:.1f} (would rank #{pred['rank']} if racing)")
            print(f"   Jockey: {pred['jockey_name']}")
            print(f"   Trainer: {pred['trainer_name']}")
            print(f"   Best Beyer: {pred['best_beyer']}")
            print(f"   ⚠️  ALSO ELIGIBLE - Confirm entry before betting")

    # Exotic wager recommendations - PROFESSIONAL STRATEGY
    print(f"\n{'-'*80}")
    print(f"🎰 EXOTIC BETTING STRATEGY")
    print(f"{'-'*80}")

    # Initialize exotic strategy
    exotic_strategy = ExoticStrategy(base_bet=1.0)

    # Generate exacta recommendations
    exacta_recs = exotic_strategy.generate_exacta_recommendations(
        predictions,
        min_expected_value=-3.0,  # Allow slightly negative EV for coverage
        max_cost=10.0
    )

    # Generate trifecta recommendations
    trifecta_recs = exotic_strategy.generate_trifecta_recommendations(
        predictions,
        min_expected_value=-5.0,
        max_cost=24.0
    )

    # Display exacta recommendations
    if exacta_recs:
        print(f"\n📊 EXACTA RECOMMENDATIONS:\n")
        for i, bet in enumerate(exacta_recs[:3], 1):  # Show top 3
            horses_str = ', '.join(f"#{h}" for h in bet.horses)
            roi_emoji = "🟢" if bet.roi > 20 else "🟡" if bet.roi > 0 else "🔴"

            print(f"{i}. {bet.structure.upper()}: {horses_str}")
            print(f"   Cost: ${bet.cost:.2f}")
            print(f"   Hit Rate: {bet.expected_hit_rate*100:.1f}%")
            print(f"   Est. Payout: ${bet.expected_payout:.2f}")
            print(f"   Expected Value: ${bet.expected_value:+.2f}")
            print(f"   ROI: {bet.roi:+.1f}% {roi_emoji}")

            if bet.expected_value > 0:
                print(f"   ✅ POSITIVE EV - RECOMMENDED")
            print()
    else:
        print(f"\nNo exacta recommendations at current thresholds.")

    # Display trifecta recommendations
    if trifecta_recs:
        print(f"📊 TRIFECTA RECOMMENDATIONS:\n")
        for i, bet in enumerate(trifecta_recs[:2], 1):  # Show top 2
            horses_str = ', '.join(f"#{h}" for h in bet.horses)
            roi_emoji = "🟢" if bet.roi > 20 else "🟡" if bet.roi > 0 else "🔴"

            print(f"{i}. {bet.structure.upper()}: {horses_str}")
            print(f"   Cost: ${bet.cost:.2f}")
            print(f"   Hit Rate: {bet.expected_hit_rate*100:.1f}%")
            print(f"   Est. Payout: ${bet.expected_payout:.2f}")
            print(f"   Expected Value: ${bet.expected_value:+.2f}")
            print(f"   ROI: {bet.roi:+.1f}% {roi_emoji}")

            if bet.expected_value > 0:
                print(f"   ✅ POSITIVE EV - RECOMMENDED")
            print()
    else:
        print(f"\nNo trifecta recommendations at current thresholds.")

    # Key horse recommendations for straight bets
    top_pick = predictions[0]
    if top_pick['probability'] > 0.25:
        print(f"⭐ STRONG TOP PICK FOR WIN BETTING:")
        print(f"   #{top_pick['program_number']} {top_pick['horse_name']} ({top_pick['probability']*100:.1f}% win probability)")
        print(f"   Fair Odds: {top_pick['fair_odds']:.1f}-1 | ML Odds: {top_pick['ml_odds_display']}")

        if top_pick['bet_recommended']:
            print(f"   💰 VALUE BET - Overlay detected!")
        else:
            print(f"   Consider WIN bet if odds stay at {top_pick['fair_odds']:.1f}-1 or better")

    # Value Betting Opportunities
    if value_bets:
        print(f"\n{'-'*80}")
        print(f"💰 VALUE BETTING OPPORTUNITIES")
        print(f"{'-'*80}")
        print(f"\n{len(value_bets)} OVERLAY(S) IDENTIFIED:\n")

        for i, vb in enumerate(value_bets, 1):
            # Confidence emoji
            conf_emoji = "⭐⭐⭐" if vb.confidence == 'HIGH' else "⭐⭐" if vb.confidence == 'MEDIUM' else "⭐"

            print(f"{i}. #{vb.program_number} {vb.name} [{vb.confidence}] {conf_emoji}")
            print(f"   Rank: {vb.rank}  |  Model Probability: {vb.probability*100:.1f}%")
            print(f"   Fair Odds: {vb.fair_odds:.1f}-1  |  Morning Line: {vb.morning_line_odds:.1f}-1")
            print(f"   Edge: {vb.edge*100:+.1f}%  |  Expected Value: ${vb.expected_value:+.2f} per $1 bet")
            print(f"   ✅ RECOMMENDED BET\n")

        total_ev = sum(vb.expected_value for vb in value_bets)
        print(f"Combined EV (betting $1 each): ${total_ev:+.2f}")
    else:
        print(f"\n{'-'*80}")
        print(f"💰 VALUE BETTING")
        print(f"{'-'*80}")
        print(f"\nNo overlays identified in this race.")
        print(f"(Minimum edge threshold: 15%)")


def write_json_output(pdf_path, all_results):
    """
    Write predictions to JSON for validation

    Args:
        pdf_path: Path to PP PDF file
        all_results: List of prediction results

    Returns:
        Path to created JSON file
    """
    import json
    import os
    from datetime import datetime

    # Extract date from filename (e.g., "10-3-25" from "10-3-25-kee-ppspdf.pdf")
    filename = os.path.basename(pdf_path)
    date_str = filename.split('-kee')[0]

    # Create output JSON structure
    output = {
        'date': date_str,
        'generated_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'pdf_file': pdf_path,
        'races': []
    }

    for result in all_results:
        race = result['race']
        predictions = result['predictions']
        ae_horses = result.get('ae_horses', [])
        pace_scenario = result['pace_scenario']
        value_bets = result.get('value_bets', [])

        race_data = {
            'race_number': race.race_number,
            'track': race.track_name,
            'distance': race.distance_text,
            'surface': race.surface_description,
            'race_type': race.race_type,
            'purse': race.purse,
            'pace_scenario': pace_scenario.scenario_type,
            'predictions': []
        }

        # Add predictions (only regular horses)
        for pred in predictions:
            race_data['predictions'].append({
                'program_number': pred['program_number'],
                'horse_name': pred['horse_name'],
                'jockey_name': pred['jockey_name'],
                'trainer_name': pred['trainer_name'],
                'probability': pred['probability'],
                'fair_odds': pred['fair_odds'],
                'ml_odds': pred['ml_odds_display'],
                'best_beyer': pred['best_beyer'],
                'running_style': pred.get('running_style', 'P'),
                'score': pred['score'],
                'rank': pred.get('rank', 0),
                # COMPONENT SCORES (for weight optimization)
                'speed_score': pred.get('speed_score', 0),
                'form_score': pred.get('form_score', 0),
                'class_score': pred.get('class_score', 0),
                'pace_score': pred.get('pace_score', 0),
                'recency_score': pred.get('recency_score', 0),
                'progression_score': pred.get('progression_score', 0),
                'jockey_score': pred.get('jockey_score', 0),
                'trainer_score': pred.get('trainer_score', 0),
                'post_score': pred.get('post_score', 0),
                # BONUS SCORES
                'jt_combo_bonus': pred.get('jt_combo_bonus', 0),
                'ds_bonus': pred.get('ds_bonus', 0),
                'equip_bonus': pred.get('equip_bonus', 0),
                'trip_bonus': pred.get('trip_bonus', 0),
                'workout_bonus': pred.get('workout_bonus', 0),
                'trainer_bonus': pred.get('trainer_bonus', 0)
            })

        # Add AE horses if any
        if ae_horses:
            race_data['ae_horses'] = []
            for ae in ae_horses:
                race_data['ae_horses'].append({
                    'program_number': ae['program_number'],
                    'horse_name': ae['horse_name'],
                    'jockey_name': ae['jockey_name'],
                    'trainer_name': ae['trainer_name']
                })

        output['races'].append(race_data)

    # Write JSON file
    json_filename = f"output/predictions_{date_str}.json"
    with open(json_filename, 'w') as f:
        json.dump(output, f, indent=2)

    return json_filename


def write_output_files(pdf_path, all_results):
    """Write picks.txt and race_analysis.txt files"""

    from datetime import datetime
    import os

    # Extract date from filename (e.g., "10-3-25" from "10-3-25-kee-ppspdf.pdf")
    filename = os.path.basename(pdf_path)
    date_str = filename.split('-kee')[0]

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Write picks.txt - Simple format
    with open('output/picks.txt', 'w') as f:
        f.write(f"KEENELAND RACING PICKS\n")
        f.write(f"Date: {date_str}\n")
        f.write(f"Generated: {timestamp}\n")
        f.write(f"{'='*60}\n\n")

        for result in all_results:
            race = result['race']
            predictions = result['predictions']
            top_pick = predictions[0]

            f.write(f"RACE {race.race_number} - {race.distance_text} {race.surface_description}\n")
            f.write(f"  TOP PICK: #{top_pick['program_number']} {top_pick['horse_name']}\n")
            f.write(f"  Win Probability: {top_pick['probability']*100:.1f}%\n")
            f.write(f"  Fair Odds: {top_pick['fair_odds']:.1f}-1 | ML Odds: {top_pick['ml_odds_display']}\n")
            f.write(f"  Jockey: {top_pick['jockey_name']}\n")

            if top_pick['best_beyer'] > 0:
                f.write(f"  Best Beyer: {top_pick['best_beyer']}\n")

            # Add exacta box recommendation
            if len(predictions) >= 3:
                top_3 = predictions[:3]
                exacta = " - ".join([f"#{p['program_number']}" for p in top_3])
                f.write(f"  Exacta Box: {exacta}\n")

            f.write(f"\n")

    # Write race_analysis.txt - Detailed format
    with open('output/race_analysis.txt', 'w') as f:
        f.write(f"KEENELAND RACING ANALYSIS\n")
        f.write(f"Date: {date_str}\n")
        f.write(f"Generated: {timestamp}\n")
        f.write(f"{'='*80}\n\n")

        for result in all_results:
            race = result['race']
            predictions = result['predictions']
            pace_scenario = result['pace_scenario']

            f.write(f"\n{'='*80}\n")
            f.write(f"RACE {race.race_number}: {race.track_name}\n")
            f.write(f"{'='*80}\n")
            f.write(f"Distance: {race.distance_text}\n")
            f.write(f"Surface: {race.surface_description}\n")
            f.write(f"Type: {race.race_type}\n")
            f.write(f"Purse: ${race.purse:,.0f}\n")
            f.write(f"Horses: {len(race.horses)}\n")

            f.write(f"\n{'-'*80}\n")
            f.write(f"PACE ANALYSIS\n")
            f.write(f"{'-'*80}\n")
            f.write(f"Pace Scenario: {pace_scenario.scenario_type.replace('_', ' ').title()}\n")
            f.write(f"Early Speed: {pace_scenario.early_speed_count}  |  Pressers: {pace_scenario.presser_count}  |  Closers: {pace_scenario.closer_count}\n")
            f.write(f"\n{pace_scenario.pace_description}\n")

            if pace_scenario.advantage_horses:
                f.write(f"\nPace Advantage: {', '.join(pace_scenario.advantage_horses)}\n")

            f.write(f"\n{'-'*80}\n")
            f.write(f"TOP 5 PREDICTIONS\n")
            f.write(f"{'-'*80}\n\n")

            for i, pred in enumerate(predictions[:5], 1):
                # Get running style label
                style_label = pred.get('running_style', 'P')
                style_name = {'E': 'Early Speed', 'P': 'Presser', 'S': 'Closer'}.get(style_label, 'Presser')

                f.write(f"{i}. #{pred['program_number']} {pred['horse_name']} [{style_label}]\n")
                f.write(f"   Win Probability: {pred['probability']*100:.1f}%\n")
                f.write(f"   Model Odds: {pred['fair_odds']:.1f}  |  ML Odds: {pred['ml_odds_display']}\n")
                f.write(f"   Running Style: {style_name}\n")
                f.write(f"   Jockey: {pred['jockey_name']}\n")
                f.write(f"   Trainer: {pred['trainer_name']}\n")

                if pred['best_beyer'] > 0:
                    f.write(f"   Best Beyer: {pred['best_beyer']}\n")

                if pred['is_fts']:
                    f.write(f"   ⭐ FIRST TIME STARTER\n")

                f.write(f"   Score Breakdown:\n")
                f.write(f"     Speed: {pred['speed_score']:.1f}  |  Form: {pred['form_score']:.1f}  |  Class: {pred['class_score']:.1f}  |  Pace: {pred['pace_score']:.1f}\n")
                f.write(f"     Recency: {pred['recency_score']:.1f}  |  Progression: {pred['progression_score']:.1f}  |  Jockey: {pred['jockey_score']:.1f}  |  Trainer: {pred['trainer_score']:.1f}  |  Post: {pred['post_score']:.1f}\n")
                f.write(f"\n")

            # Exotic recommendations
            f.write(f"{'-'*80}\n")
            f.write(f"EXOTIC WAGER RECOMMENDATIONS\n")
            f.write(f"{'-'*80}\n\n")

            if len(predictions) >= 3:
                top_3 = predictions[:3]
                exacta_horses = " - ".join([f"#{p['program_number']}" for p in top_3])
                exacta_cost = len(top_3) * (len(top_3) - 1)
                combined_prob = sum(p['probability'] for p in top_3)

                f.write(f"Exacta Box (Top 3): {exacta_horses}\n")
                f.write(f"  Cost: ${exacta_cost} ($1 base)\n")
                f.write(f"  Combined Win Probability: {combined_prob*100:.1f}%\n\n")

            if len(predictions) >= 4:
                top_4 = predictions[:4]
                trifecta_horses = " - ".join([f"#{p['program_number']}" for p in top_4])
                trifecta_cost = len(top_4) * (len(top_4) - 1) * (len(top_4) - 2)
                combined_prob = sum(p['probability'] for p in top_4)

                f.write(f"Trifecta Box (Top 4): {trifecta_horses}\n")
                f.write(f"  Cost: ${trifecta_cost} ($1 base)\n")
                f.write(f"  Combined Win Probability: {combined_prob*100:.1f}%\n\n")

            # Strong pick indicator
            top_pick = predictions[0]
            if top_pick['probability'] > 0.25:
                f.write(f"⭐ STRONG TOP PICK:\n")
                f.write(f"   #{top_pick['program_number']} {top_pick['horse_name']} ({top_pick['probability']*100:.1f}% win probability)\n")
                f.write(f"   Consider WIN bet if odds are {top_pick['fair_odds']:.1f} or better\n\n")


def main():
    """Main prediction script"""

    if len(sys.argv) < 2:
        print("Usage: python predict_from_pdf.py <pdf_file> [race_number]")
        print("\nExample:")
        print("  python predict_from_pdf.py 'Keeneland October PPs/10-3-25-kee-ppspdf.pdf' 1")
        return

    pdf_path = sys.argv[1]
    race_number = int(sys.argv[2]) if len(sys.argv) > 2 else None

    print(f"\n{'='*80}")
    print(f" HORSE RACING PREDICTION MODEL")
    print(f" Model Version: With FTS Proxy Scoring + Maiden Weights + Elite Combo Bonuses")
    print(f"{'='*80}")

    # Load statistics
    print(f"\nLoading statistics and analyzers...")
    stats_loader = StatisticsLoader(
        jockey_file='data/stats/jockey_statistics_comprehensive.json',
        trainer_file='data/stats/trainer_statistics_comprehensive.json'
    )

    fts_analyzer = FTSAnalyzer(
        trainer_stats_file='data/stats/fts_trainer_statistics.json',
        sire_stats_file='data/stats/fts_sire_statistics.json'
    )

    pace_analyzer = PaceAnalyzer()

    # NEW: Initialize enhanced pace analyzer
    enhanced_pace_analyzer = EnhancedPaceAnalyzer(
        track_variants_file='data/track_variants.json'
    )

    # Initialize track bias detector
    track_bias_detector = TrackBiasDetector()

    # Initialize jockey-trainer combination analyzer (existing stats-based)
    jockey_trainer_analyzer = JockeyTrainerAnalyzer()

    # Initialize elite jockey-trainer combo analyzer (NEW - October 23 validation)
    jt_combo_analyzer = JockeyTrainerComboAnalyzer()

    # Initialize distance/surface analyzer
    distance_surface_analyzer = DistanceSurfaceAnalyzer()

    # Initialize equipment analyzer (CRITICAL)
    equipment_analyzer = EquipmentAnalyzer()

    # Initialize trip notes analyzer
    trip_notes_analyzer = TripNotesAnalyzer()

    # Initialize workout analyzer
    workout_analyzer = WorkoutAnalyzer()

    # Initialize trainer pattern detector
    trainer_pattern_detector = TrainerPatternDetector()

    # Initialize enhanced jockey analyzer (CRITICAL FIX #2)
    enhanced_jockey_analyzer = EnhancedJockeyAnalyzer()

    # Initialize trainer specialization analyzer (CRITICAL FIX #3)
    trainer_specialization_analyzer = TrainerSpecializationAnalyzer()

    print(f"✓ Statistics loaded")
    print(f"✓ Enhanced pace analyzer initialized")
    print(f"✓ Track bias detector initialized")
    print(f"✓ Jockey-trainer analyzer initialized")
    print(f"✓ Distance/surface analyzer initialized")
    print(f"✓ Equipment analyzer initialized")
    print(f"✓ Trip notes analyzer initialized")
    print(f"✓ Workout analyzer initialized")
    print(f"✓ Trainer pattern detector initialized")
    print(f"✓ Enhanced jockey analyzer initialized")
    print(f"✓ Trainer specialization analyzer initialized")

    # Parse PDF (using Hybrid Parser V3)
    print(f"\nParsing PDF with Hybrid Parser V3: {pdf_path}")
    races = parse_pdf_hybrid_v3(pdf_path)

    if not races:
        print(f"✗ No races found in PDF")
        return

    print(f"✓ Found {len(races)} race(s)")

    # Filter to specific race if requested
    if race_number:
        races = [r for r in races if r.race_number == race_number]
        if not races:
            print(f"✗ Race {race_number} not found")
            return

    # Process each race and collect results
    all_results = []

    for race in races:
        # Load optimized weights for this surface AND race type (maiden-specific weights)
        weights = load_optimized_weights(
            surface=race.surface_description,
            race_type=race.race_type,
            race_class=getattr(race, 'race_class', '')
        )

        # Generate predictions
        result = predict_race(race, stats_loader, fts_analyzer, pace_analyzer, enhanced_pace_analyzer, track_bias_detector, jockey_trainer_analyzer, distance_surface_analyzer, equipment_analyzer, trip_notes_analyzer, workout_analyzer, trainer_pattern_detector, enhanced_jockey_analyzer, trainer_specialization_analyzer, jt_combo_analyzer, weights)

        if result:
            regular_horses, ae_horses, pace_scenario, value_bets = result
            print_predictions(regular_horses, ae_horses, pace_scenario, value_bets,
                            race_type=race.race_type,
                            race_class=getattr(race, 'race_class', ''))

            # Store results for output files
            all_results.append({
                'race': race,
                'predictions': regular_horses,  # Only regular horses in predictions
                'ae_horses': ae_horses,  # Store AE horses separately
                'pace_scenario': pace_scenario,
                'value_bets': value_bets
            })

    print(f"\n{'='*80}")
    print(f" PREDICTION COMPLETE")
    print(f"{'='*80}\n")

    # Write output files
    if all_results and not race_number:  # Only write files if processing all races
        write_output_files(pdf_path, all_results)
        print(f"\n✓ Picks saved to: output/picks.txt")
        print(f"✓ Analysis saved to: output/race_analysis.txt")

        # Write JSON output for validation
        json_file = write_json_output(pdf_path, all_results)
        print(f"✓ JSON saved to: {json_file}\n")


if __name__ == '__main__':
    main()
