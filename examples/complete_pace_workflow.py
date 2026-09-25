"""
Complete Workflow: PDF to Pace Analysis
Shows the full pipeline from parsing PDF to generating pace insights
"""

from racing_pdf_parser import RacingPDFParser
from pace_integration import PDFToPaceAnalyzer
from pace_analyzer import PaceAnalyzer, RunningStyle
import json
import csv


def analyze_race_from_pdf(pdf_path: str, race_number: int = 1):
    """
    Complete analysis: PDF → Text → Past Performances → Pace Analysis
    
    Args:
        pdf_path: Path to racing PDF
        race_number: Which race to analyze
    
    Returns:
        Dictionary with complete race analysis
    """
    
    print("=" * 70)
    print(f"🐴 PACE ANALYSIS WORKFLOW - RACE {race_number}")
    print("=" * 70)
    
    # Step 1: Extract text from PDF
    print("\n📄 Step 1: Extracting text from PDF...")
    pdf_parser = RacingPDFParser(pdf_path)
    page_results = pdf_parser.extract_all_pages()
    
    # Combine relevant pages for this race
    race_text = ""
    for page_num, result in page_results.items():
        if f"RACE {race_number}" in result['text'] or page_num == 0:  # Assume race 1 on page 0
            race_text += result['text'] + "\n"
    
    if not race_text:
        print(f"❌ Could not find Race {race_number} in PDF")
        return None
    
    print(f"✅ Extracted {len(race_text)} characters of text")
    
    # Step 2: Parse horses from text
    print("\n🔍 Step 2: Parsing horse entries...")
    horses = parse_horses_from_race_text(race_text)
    print(f"✅ Found {len(horses)} horses")
    
    # Step 3: Analyze pace for each horse
    print("\n📊 Step 3: Analyzing pace for each horse...")
    bridge = PDFToPaceAnalyzer()
    pace_analyses = []
    
    for horse in horses:
        try:
            analysis = bridge.analyze_horse_from_text(
                horse['name'], 
                horse['text']
            )
            pace_analyses.append(analysis)
            
            # Print summary
            style = analysis.get('running_style', '?')
            conf = analysis.get('style_confidence', 0)
            print(f"  {horse['name']:20s} - {style} ({conf:.1%} confidence)")
            
        except Exception as e:
            print(f"  ⚠️ {horse['name']:20s} - Error: {e}")
    
    # Step 4: Analyze overall race pace scenario
    print("\n🏁 Step 4: Analyzing race pace scenario...")
    analyzer = PaceAnalyzer()
    
    # Convert to PaceAnalysis objects for race analysis
    from pace_analyzer import PaceAnalysis
    pace_analysis_objects = []
    
    for analysis in pace_analyses:
        if 'running_style' in analysis:
            pa = PaceAnalysis(
                horse_name=analysis['horse_name'],
                running_style=RunningStyle(analysis['running_style']),
                running_style_confidence=analysis.get('style_confidence', 0),
                avg_early_position=analysis.get('avg_early_position', 0),
                avg_stretch_position=analysis.get('avg_stretch_position', 0),
                avg_finish_position=analysis.get('avg_finish_position', 0),
                avg_position_change=analysis.get('avg_position_change', 0),
                early_speed_points=0,
                closer_points=0,
                pace_versatility=analysis.get('pace_versatility', 0)
            )
            pace_analysis_objects.append(pa)
    
    race_scenario = analyzer.analyze_race_pace(pace_analysis_objects)
    
    # Print race scenario
    print("\n" + "=" * 70)
    print("🎯 RACE PACE SCENARIO")
    print("=" * 70)
    print(f"Pace Type: {race_scenario.pace_scenario}")
    print(f"\nEarly Speed Horses ({len(race_scenario.early_speed_horses)}):")
    for horse in race_scenario.early_speed_horses:
        print(f"  • {horse}")
    
    print(f"\nPressers ({len(race_scenario.pressers)}):")
    for horse in race_scenario.pressers:
        print(f"  • {horse}")
    
    print(f"\nStalkers ({len(race_scenario.stalkers)}):")
    for horse in race_scenario.stalkers:
        print(f"  • {horse}")
    
    print(f"\nClosers ({len(race_scenario.closers)}):")
    for horse in race_scenario.closers:
        print(f"  • {horse}")
    
    print(f"\nProjected Leader: {race_scenario.projected_leader}")
    print(f"\nPace Advantage (horses to bet):")
    for horse in race_scenario.pace_advantage:
        print(f"  🎯 {horse}")
    
    # Step 5: Generate betting insights
    print("\n" + "=" * 70)
    print("💡 BETTING INSIGHTS")
    print("=" * 70)
    
    insights = generate_betting_insights(race_scenario, pace_analyses)
    for insight in insights:
        print(f"  {insight}")
    
    # Package results
    results = {
        'race_number': race_number,
        'num_horses': len(horses),
        'pace_scenario': race_scenario.pace_scenario,
        'projected_leader': race_scenario.projected_leader,
        'pace_advantage': race_scenario.pace_advantage,
        'horse_analyses': pace_analyses,
        'betting_insights': insights
    }
    
    return results


def parse_horses_from_race_text(race_text: str) -> list:
    """
    Parse individual horse entries from race text
    This is a simplified parser - you'd want to make this more robust
    """
    horses = []
    
    # Split by horse patterns - look for program numbers and horse names
    # This is highly dependent on your PDF format
    
    # For now, let's use a simple heuristic:
    # Look for patterns like "Owner:" which typically starts each horse block
    import re
    
    # Split on "Owner:" pattern
    horse_blocks = re.split(r'\bOwner:', race_text)
    
    for i, block in enumerate(horse_blocks[1:], 1):  # Skip first empty split
        # Try to extract horse name
        # Look for pattern like "Horse Name (L)" or "Horse Name"
        name_match = re.search(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*\([LM]\)', block)
        if name_match:
            horse_name = name_match.group(1)
        else:
            # Fallback: use program number
            horse_name = f"Horse #{i}"
        
        horses.append({
            'program_number': i,
            'name': horse_name,
            'text': 'Owner:' + block  # Reconstruct with Owner prefix
        })
    
    return horses


def generate_betting_insights(race_scenario, pace_analyses) -> list:
    """
    Generate actionable betting insights based on pace analysis
    """
    insights = []
    
    # Insight 1: Pace scenario interpretation
    if race_scenario.pace_scenario == "VERY HOT" or race_scenario.pace_scenario == "HOT":
        insights.append("🔥 HOT PACE EXPECTED - Early speed horses will battle and tire")
        insights.append(f"   → FOCUS ON: {', '.join(race_scenario.closers[:3])}")
        insights.append("   → AVOID: Front runners (will burn out)")
    
    elif race_scenario.pace_scenario == "SLOW":
        insights.append("🐌 SLOW PACE EXPECTED - No pressure on leaders")
        insights.append(f"   → FOCUS ON: {', '.join(race_scenario.early_speed_horses)}")
        insights.append("   → AVOID: Closers (won't have pace to chase)")
    
    elif race_scenario.pace_scenario == "MODERATE":
        insights.append("⚖️ BALANCED PACE - Fair for all running styles")
        insights.append("   → FOCUS ON: Class and form over pace")
    
    # Insight 2: Lone speed scenario
    if len(race_scenario.early_speed_horses) == 1:
        leader = race_scenario.projected_leader
        insights.append(f"🎯 LONE SPEED ADVANTAGE - {leader} can control pace")
        insights.append(f"   → STRONG BET: {leader} (uncontested lead)")
    
    # Insight 3: Pace collapse setup
    if len(race_scenario.early_speed_horses) >= 4:
        insights.append("💥 PACE COLLAPSE SETUP - Multiple speed horses")
        insights.append("   → VALUE PLAYS: Mid-priced closers")
        if race_scenario.closers:
            insights.append(f"   → TOP CLOSER: {race_scenario.closers[0]}")
    
    # Insight 4: Horse-specific insights
    for analysis in pace_analyses:
        # Look for high-confidence horses
        if analysis.get('style_confidence', 0) > 0.8:
            style = analysis.get('running_style', '?')
            name = analysis.get('horse_name', '')
            
            if style == 'E' and race_scenario.pace_scenario == "SLOW":
                insights.append(f"⭐ {name} - Consistent speed in favorable pace")
            
            elif style == 'C' and race_scenario.pace_scenario in ["HOT", "VERY HOT"]:
                insights.append(f"⭐ {name} - Consistent closer in ideal pace scenario")
    
    # Insight 5: Versatile horses
    versatile_horses = [a for a in pace_analyses if a.get('pace_versatility', 0) > 0.7]
    if versatile_horses:
        top_versatile = max(versatile_horses, key=lambda x: x.get('pace_versatility', 0))
        insights.append(f"🔄 {top_versatile['horse_name']} - Most versatile (can win from anywhere)")
    
    return insights if insights else ["No specific pace insights available"]


def export_results(results: dict, output_dir: str = "."):
    """
    Export results to various formats
    """
    race_num = results['race_number']
    
    # Export to JSON
    json_file = f"{output_dir}/race_{race_num}_pace_analysis.json"
    with open(json_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\n💾 Saved: {json_file}")
    
    # Export to CSV
    csv_file = f"{output_dir}/race_{race_num}_horses.csv"
    with open(csv_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'horse_name', 'running_style', 'style_confidence',
            'avg_early_position', 'avg_stretch_position', 'avg_finish_position',
            'avg_position_change', 'pace_versatility', 'num_past_performances'
        ])
        writer.writeheader()
        
        for analysis in results['horse_analyses']:
            if 'horse_name' in analysis:
                writer.writerow({
                    'horse_name': analysis.get('horse_name', ''),
                    'running_style': analysis.get('running_style', '?'),
                    'style_confidence': f"{analysis.get('style_confidence', 0):.2f}",
                    'avg_early_position': f"{analysis.get('avg_early_position', 0):.1f}",
                    'avg_stretch_position': f"{analysis.get('avg_stretch_position', 0):.1f}",
                    'avg_finish_position': f"{analysis.get('avg_finish_position', 0):.1f}",
                    'avg_position_change': f"{analysis.get('avg_position_change', 0):+.1f}",
                    'pace_versatility': f"{analysis.get('pace_versatility', 0):.2f}",
                    'num_past_performances': analysis.get('num_past_performances', 0)
                })
    
    print(f"💾 Saved: {csv_file}")
    
    # Export betting insights to text file
    insights_file = f"{output_dir}/race_{race_num}_insights.txt"
    with open(insights_file, 'w') as f:
        f.write(f"RACE {race_num} - PACE ANALYSIS & BETTING INSIGHTS\n")
        f.write("=" * 70 + "\n\n")
        
        f.write(f"Pace Scenario: {results['pace_scenario']}\n")
        f.write(f"Projected Leader: {results['projected_leader']}\n\n")
        
        f.write("Horses with Pace Advantage:\n")
        for horse in results['pace_advantage']:
            f.write(f"  • {horse}\n")
        
        f.write("\nBetting Insights:\n")
        for insight in results['betting_insights']:
            f.write(f"{insight}\n")
    
    print(f"💾 Saved: {insights_file}")


def main():
    """
    Main workflow - run complete analysis
    """
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python complete_workflow.py <pdf_file> [race_number]")
        print("\nExample:")
        print("  python complete_workflow.py racing_program.pdf 1")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    race_number = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    
    # Run analysis
    results = analyze_race_from_pdf(pdf_path, race_number)
    
    if results:
        # Export results
        export_results(results)
        
        print("\n" + "=" * 70)
        print("✅ ANALYSIS COMPLETE!")
        print("=" * 70)
        print(f"Analyzed {results['num_horses']} horses")
        print(f"Pace scenario: {results['pace_scenario']}")
        print(f"Check output files for detailed results")
    else:
        print("\n❌ Analysis failed - check PDF and race number")


if __name__ == "__main__":
    main()
