"""
Tournament Simulator UI Module
Provides interface for simulating custom tournaments
"""

import streamlit as st


def render(model, default_surface='hard', model_id=None, region=None, show_context=False):
    """
    Render the tournament simulator page
    
    Args:
        model: EloSystem instance
        default_surface: Default surface for tournament
        model_id: Bedrock model ID for AI analysis
        region: AWS region for Bedrock
        show_context: Whether to show the context sent to AI
    """
    st.markdown('<div class="page-title">🏆 Tournament Simulator</div>', unsafe_allow_html=True)
    
    if model is None:
        st.error("❌ Unable to load tournament simulator. Please check your configuration.")
        return
    
    # Initialize session state
    if 'tournament_players' not in st.session_state:
        st.session_state.tournament_players = []
    if 'tournament_surface' not in st.session_state:
        st.session_state.tournament_surface = default_surface
    if 'tournament_results' not in st.session_state:
        st.session_state.tournament_results = None
    
    # Get all players
    all_players = _get_all_players(model)
    
    if not all_players:
        st.warning("No players found in database.")
        return
    
    # Tournament setup
    st.markdown("### 🏆 Create Tournament")
    
    # Surface selection
    surface = st.radio(
        "**Tournament Surface**",
        options=['hard', 'clay', 'grass', 'indoor_hard'],
        format_func=lambda x: x.replace('_', ' ').title(),
        horizontal=True,
        key="tournament_surface_select"
    )
    st.session_state.tournament_surface = surface
    
    st.markdown("---")
    
    # Player selection
    st.markdown("### 👥 Select 16 Players")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        selected_player = st.selectbox(
            "Search and add players",
            options=[""] + [p for p in all_players if p not in st.session_state.tournament_players],
            key="tournament_player_select"
        )
    
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("➕ Add Player", width='stretch', disabled=not selected_player or selected_player == ""):
            if len(st.session_state.tournament_players) < 16:
                st.session_state.tournament_players.append(selected_player)
                st.rerun()
            else:
                st.warning("Tournament is full (16 players)")
    
    # Quick fill options
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("⚡ Fill with Top 16", width='stretch'):
            remaining_slots = 16 - len(st.session_state.tournament_players)
            if remaining_slots > 0:
                # Get top players by Elo
                player_elos = [(p, model.get_player_elo(p, surface)) for p in all_players 
                              if p not in st.session_state.tournament_players]
                player_elos.sort(key=lambda x: x[1], reverse=True)
                st.session_state.tournament_players.extend([p[0] for p in player_elos[:remaining_slots]])
                st.rerun()
    
    with col2:
        if st.button("🎲 Random Fill", width='stretch'):
            import random
            remaining_slots = 16 - len(st.session_state.tournament_players)
            if remaining_slots > 0:
                available = [p for p in all_players if p not in st.session_state.tournament_players]
                random_players = random.sample(available, min(remaining_slots, len(available)))
                st.session_state.tournament_players.extend(random_players)
                st.rerun()
    
    with col3:
        if st.button("🗑️ Clear All", width='stretch'):
            st.session_state.tournament_players = []
            st.session_state.tournament_results = None
            st.rerun()
    
    # Display selected players grid
    st.markdown(f"**Selected: {len(st.session_state.tournament_players)}/16**")
    st.progress(len(st.session_state.tournament_players) / 16)
    
    if st.session_state.tournament_players:
        _display_player_grid(st.session_state.tournament_players)
    
    # Generate bracket button
    st.markdown("<br>", unsafe_allow_html=True)
    can_generate = len(st.session_state.tournament_players) == 16
    
    if not can_generate:
        st.info(f"ℹ️ Add {16 - len(st.session_state.tournament_players)} more player(s) to generate bracket")
    
    if st.button("🏆 Generate Bracket", 
                 disabled=not can_generate,
                 width='stretch',
                 type="primary"):
        with st.spinner("Running tournament analysis..."):
            st.session_state.tournament_results = _simulate_tournament(
                model,
                st.session_state.tournament_players,
                st.session_state.tournament_surface,
                model_id,
                region
            )
    
    # Display tournament results
    if st.session_state.tournament_results:
        _display_tournament_results(st.session_state.tournament_results, show_context)


def _get_all_players(model):
    """Extract all unique players from the model"""
    try:
        # Try to get players from EloSystem method
        if hasattr(model, 'get_all_players'):
            return model.get_all_players()
        # Fallback to accessing players directly
        elif hasattr(model, 'model') and hasattr(model.model, 'players'):
            return sorted(list(model.model.players.keys()))
        else:
            return []
    except Exception as e:
        st.error(f"Error getting players: {e}")
        return []


def _display_player_grid(players):
    """Display selected players in a grid"""
    cols = st.columns(4)
    for i in range(16):
        with cols[i % 4]:
            if i < len(players):
                player = players[i]
                st.markdown(f"""
                <div style='background: linear-gradient(135deg, #0f1629 0%, #1a2332 100%); 
                            border: 1px solid #1a2332; border-radius: 8px; 
                            padding: 1rem; margin-bottom: 0.5rem; text-align: center;'>
                    <div style='color: #00d4ff; font-size: 0.8rem; font-weight: 600;'>#{i+1}</div>
                    <div style='color: #e2e8f0; font-size: 0.9rem; margin-top: 0.25rem;'>{player}</div>
                </div>
                """, unsafe_allow_html=True)
                if st.button("❌", key=f"remove_{i}", width='stretch'):
                    st.session_state.tournament_players.remove(player)
                    st.rerun()
            else:
                st.markdown(f"""
                <div style='background: rgba(255, 255, 255, 0.02); 
                            border: 1px dashed #1a2332; border-radius: 8px; 
                            padding: 1rem; margin-bottom: 0.5rem; text-align: center;'>
                    <div style='color: #64748b; font-size: 0.8rem;'>#{i+1}</div>
                    <div style='color: #475569; font-size: 0.9rem; margin-top: 0.25rem;'>Empty</div>
                </div>
                """, unsafe_allow_html=True)


def _simulate_tournament(model, players, surface, model_id, region):
    """Run tournament analysis for bracket"""
    try:
        import random
        
        bracket = _generate_bracket(model, players, surface)
        
        results = {
            'players': players,
            'surface': surface,
            'champion': bracket['champion'],
            'runner_up': bracket['final']['p1'] if bracket['final']['winner'] == bracket['final']['p2'] else bracket['final']['p2'],
            'bracket': bracket,
            'title_probabilities': _calculate_title_probabilities(model, players, surface),
            'ai_analysis': None
        }
        
        # Generate AI analysis if available
        if model_id and region:
            results['ai_analysis'] = _generate_tournament_brief(results, model_id, region)
        
        return results
        
    except Exception as e:
        st.error(f"Error simulating tournament: {e}")
        return None


def _generate_bracket(model, players, surface):
    """Generate complete tournament bracket"""
    import random
    
    def _simulate_match(p1, p2):
        """Simulate a single match"""
        try:
            if hasattr(model, 'get_match_prediction'):
                prediction_data = model.get_match_prediction(p1, p2, surface)
                prob = prediction_data.get('win_prob_a', 0.5)
            elif hasattr(model, 'model') and hasattr(model.model, 'match_win_prob'):
                prob = model.model.match_win_prob(p1, p2, surface)
            else:
                elo1 = model.get_player_elo(p1, surface)
                elo2 = model.get_player_elo(p2, surface)
                prob = 1 / (1 + 10**((elo2 - elo1) / 400))
        except:
            prob = 0.5
        
        winner = p1 if random.random() < prob else p2
        return {'p1': p1, 'p2': p2, 'winner': winner, 'prob': prob}
    
    bracket = {
        'round1': [],
        'quarterfinals': [],
        'semifinals': [],
        'final': None,
        'champion': None
    }
    
    # Randomize bracket draw - shuffle players for different matchups each time
    current_players = players.copy()
    random.shuffle(current_players)
    
    # Round 1 (16 -> 8)
    for i in range(0, 16, 2):
        match = _simulate_match(current_players[i], current_players[i+1])
        bracket['round1'].append(match)
    
    # Quarterfinals (8 -> 4) - winners advance in bracket order
    qf_players = [match['winner'] for match in bracket['round1']]
    for i in range(0, 8, 2):
        match = _simulate_match(qf_players[i], qf_players[i+1])
        bracket['quarterfinals'].append(match)
    
    # Semifinals (4 -> 2)
    sf_players = [match['winner'] for match in bracket['quarterfinals']]
    for i in range(0, 4, 2):
        match = _simulate_match(sf_players[i], sf_players[i+1])
        bracket['semifinals'].append(match)
    
    # Final (2 -> 1)
    final_players = [match['winner'] for match in bracket['semifinals']]
    if len(final_players) == 2:
        final_match = _simulate_match(final_players[0], final_players[1])
        bracket['final'] = final_match
        bracket['champion'] = final_match['winner']
    
    return bracket


def _calculate_title_probabilities(model, players, surface):
    """Calculate title probabilities for all players"""
    # Simplified calculation
    probs = {}
    total_elo = sum(model.get_player_elo(p, surface) for p in players)
    
    for player in players:
        elo = model.get_player_elo(player, surface)
        probs[player] = (elo / total_elo) * 100 if total_elo > 0 else 0
    
    return dict(sorted(probs.items(), key=lambda x: x[1], reverse=True))


def _generate_tournament_brief(results, model_id, region):
    """Generate comprehensive AI tournament analysis"""
    
    # Enhanced fallback analysis with actual tournament data
    def _create_detailed_brief():
        champion = results['champion']
        runner_up = results['runner_up']
        surface = results['surface'].replace('_', ' ').title()
        
        # Get top contenders
        top_3 = list(results['title_probabilities'].items())[:3]
        dark_horses = list(results['title_probabilities'].items())[8:12]  # Players ranked 9-12
        
        # Analyze bracket results
        bracket = results['bracket']
        upsets = []
        for match in bracket['round1']:
            if match['prob'] < 0.4:  # Underdog won
                upsets.append(f"{match['winner']} defeated {match['p1'] if match['winner'] == match['p2'] else match['p2']}")
        
        # Champion analysis
        champ_prob = results['title_probabilities'].get(champion, 0)
        if champ_prob > 20:
            champ_analysis = "lived up to pre-tournament expectations"
        elif champ_prob > 10:
            champ_analysis = "emerged from the pack of contenders"
        else:
            champ_analysis = "pulled off a stunning upset victory"
        
        return f"""
**TOURNAMENT RECAP**
{champion} has claimed the {surface} Court championship, {champ_analysis} with a {champ_prob:.1f}% pre-tournament probability. The final victory over {runner_up} caps off {'an expected' if champ_prob > 15 else 'a surprising'} tournament run.

**PRE-TOURNAMENT FAVORITES**
• **{top_3[0][0]}** ({top_3[0][1]:.1f}%) - {'Delivered as expected' if top_3[0][0] == champion else 'Failed to capitalize on top seeding'}
• **{top_3[1][0]}** ({top_3[1][1]:.1f}%) - {'Solid performance' if top_3[1][0] in [champion, runner_up] else 'Underperformed expectations'}
• **{top_3[2][0]}** ({top_3[2][1]:.1f}%) - {'Met expectations' if top_3[2][0] in [champion, runner_up] else 'Early exit disappointed'}

**SURFACE ANALYSIS**
{surface} court conditions {'favored the big servers and aggressive players' if surface == 'Grass' else 'rewarded patience and consistency' if surface == 'Clay' else 'produced fast-paced, high-quality tennis' if surface == 'Hard' else 'created controlled, tactical battles'}. The champion's playing style proved perfectly suited to these conditions.

**KEY STORYLINES**
• **Champion's Path**: {champion} navigated {'a challenging draw' if champ_prob < 15 else 'the bracket as expected'}
• **Biggest Upsets**: {upsets[0] if upsets else 'No major upsets in the opening round'}
• **Dark Horse Performance**: {dark_horses[0][0] if dark_horses else 'Lower seeds struggled'} {'exceeded expectations' if dark_horses and dark_horses[0][0] in [champion, runner_up] else 'failed to make an impact'}

**FINAL ANALYSIS**
This {surface.lower()} court tournament {'delivered on its promise' if len(upsets) < 2 else 'provided plenty of surprises'} with {champion} {'confirming their status' if champ_prob > 20 else 'announcing their arrival'} as a major force. The {'predictable' if champ_prob > 20 else 'unpredictable'} nature of the results {'validates' if champ_prob > 20 else 'highlights the competitive depth in'} the current tennis landscape.

**STATISTICAL HIGHLIGHTS**
• Tournament featured {len(results['players'])} elite players
• {len(upsets)} significant upsets in early rounds
• Champion's title probability: {champ_prob:.1f}%
• Surface: {surface} court conditions
        """
    
    try:
        # Try Bedrock API first
        import sys
        sys.path.append('.')
        from app import call_bedrock
        
        # Create simplified prompt to avoid validation errors
        top_players = list(results['title_probabilities'].items())[:5]
        
        prompt = f"""Analyze this tennis tournament:

Champion: {results['champion']}
Runner-up: {results['runner_up']}
Surface: {results['surface'].replace('_', ' ').title()}

Top 5 pre-tournament favorites:
{', '.join([f'{player} ({prob:.1f}%)' for player, prob in top_players])}

Provide comprehensive analysis covering tournament recap, favorites performance, surface impact, key storylines, and statistical insights for tennis fans."""
        
        system_prompt = "You are a tennis expert analyst providing comprehensive tournament coverage and insights."
        response = call_bedrock(system_prompt, prompt, model_id, region)
        
        if response and len(response.strip()) > 100:
            return response
        else:
            return _create_detailed_brief()
            
    except Exception as e:
        return _create_detailed_brief()


def _display_tournament_results(results, show_context):
    """Display tournament results and bracket"""
    st.markdown("---")
    st.markdown("## 🏆 Tournament Results")
    
    # Champion announcement
    st.markdown(f"""
    <div style='background: linear-gradient(135deg, #0f1629 0%, #1a2332 100%); 
                border: 2px solid #00d4ff; border-radius: 16px; padding: 2rem; 
                margin-bottom: 2rem; text-align: center;'>
        <h1 style='color: #39ff14; margin: 0; font-size: 2.5rem;'>🏆</h1>
        <h2 style='color: #e2e8f0; margin: 1rem 0 0.5rem 0;'>CHAMPION</h2>
        <h1 style='background: linear-gradient(135deg, #00d4ff 0%, #39ff14 100%);
                   -webkit-background-clip: text; -webkit-text-fill-color: transparent;
                   margin: 0; font-size: 3rem;'>
            {results['champion']}
        </h1>
        <p style='color: #94a3b8; margin-top: 1rem;'>
            {results['surface'].replace('_', ' ').title()} Court Tournament
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Bracket visualization
    st.markdown("### 🎯 TOURNAMENT BRACKET")
    bracket_viz = _generate_bracket_visualization(results['bracket'])
    st.code(bracket_viz, language=None)
    
    # Upset alerts (top 5 only)
    st.markdown("### 🚨 TOP UPSET ALERTS")
    upsets = _identify_upsets(results['bracket'])
    if upsets:
        for upset in upsets:
            if upset['risk'] == 'HIGH':
                st.warning(f"**{upset['round']}**: {upset['match']} - {upset['description']}")
            elif upset['risk'] == 'MEDIUM':
                st.info(f"**{upset['round']}**: {upset['match']} - {upset['description']}")
    else:
        st.success("No significant upset alerts detected")
    
    # Title probabilities
    st.markdown("### 📊 TITLE PROBABILITIES")
    _display_title_probabilities_chart(results['title_probabilities'], results['champion'])
    
    # AI Analysis
    if results['ai_analysis']:
        st.markdown("### 🤖 AI TOURNAMENT BRIEF")
        with st.expander("View Full Analysis", expanded=True):
            st.markdown(results['ai_analysis'])
    
    # Action buttons
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🔄 New Tournament", width='stretch'):
            st.session_state.tournament_results = None
            st.session_state.tournament_players = []
            st.rerun()
    with col2:
        if st.button("🎲 Re-simulate", width='stretch'):
            st.session_state.tournament_results = None
            st.rerun()
    with col3:
        if st.button("📥 Export", width='stretch'):
            st.info("Export feature coming soon!")


def _generate_bracket_visualization(bracket):
    """Generate clean tournament bracket visualization"""
    
    lines = []
    lines.append("TOURNAMENT BRACKET")
    lines.append("=" * 80)
    lines.append("")
    
    # Round 1
    lines.append("ROUND 1:")
    for i, match in enumerate(bracket['round1'], 1):
        winner = "✓" if match['winner'] == match['p1'] else " "
        loser = " " if match['winner'] == match['p1'] else "✓"
        prob1 = match['prob'] * 100
        prob2 = (1 - match['prob']) * 100
        lines.append(f"  {i:2d}. {winner} {match['p1']:<15} ({prob1:.0f}%) vs {loser} {match['p2']:<15} ({prob2:.0f}%) → {match['winner']}")
    
    lines.append("")
    
    # Quarterfinals
    lines.append("QUARTERFINALS:")
    for i, match in enumerate(bracket['quarterfinals'], 1):
        winner = "✓" if match['winner'] == match['p1'] else " "
        loser = " " if match['winner'] == match['p1'] else "✓"
        prob1 = match['prob'] * 100
        prob2 = (1 - match['prob']) * 100
        lines.append(f"  {i:2d}. {winner} {match['p1']:<15} ({prob1:.0f}%) vs {loser} {match['p2']:<15} ({prob2:.0f}%) → {match['winner']}")
    
    lines.append("")
    
    # Semifinals
    lines.append("SEMIFINALS:")
    for i, match in enumerate(bracket['semifinals'], 1):
        winner = "✓" if match['winner'] == match['p1'] else " "
        loser = " " if match['winner'] == match['p1'] else "✓"
        prob1 = match['prob'] * 100
        prob2 = (1 - match['prob']) * 100
        lines.append(f"  {i:2d}. {winner} {match['p1']:<15} ({prob1:.0f}%) vs {loser} {match['p2']:<15} ({prob2:.0f}%) → {match['winner']}")
    
    lines.append("")
    
    # Final
    if bracket['final']:
        lines.append("FINAL:")
        match = bracket['final']
        winner = "✓" if match['winner'] == match['p1'] else " "
        loser = " " if match['winner'] == match['p1'] else "✓"
        prob1 = match['prob'] * 100
        prob2 = (1 - match['prob']) * 100
        lines.append(f"     {winner} {match['p1']:<15} ({prob1:.0f}%) vs {loser} {match['p2']:<15} ({prob2:.0f}%) → {match['winner']}")
    
    lines.append("")
    lines.append(f"🏆 CHAMPION: {bracket['champion']}")
    lines.append("=" * 80)
    
    return '\n'.join(lines)


def _identify_upsets(bracket):
    """Identify potential upsets in the bracket"""
    upsets = []
    
    # Check all rounds
    rounds_data = [
        ('R1', bracket['round1']),
        ('R2', bracket['quarterfinals']),
        ('QF', bracket['semifinals']),
        ('SF', [bracket['final']] if bracket['final'] else [])
    ]
    
    for round_name, matches in rounds_data:
        for match in matches:
            if not match:
                continue
            
            prob1 = match['prob'] * 100
            prob2 = (1 - match['prob']) * 100
            
            # Identify close matches (potential upsets)
            diff = abs(prob1 - prob2)
            
            match_desc = f"{match['p1']} vs {match['p2']} ({prob1:.0f}% vs {prob2:.0f}%)"
            
            if diff < 15:  # Within 15% - coin flip
                upsets.append({
                    'round': round_name,
                    'match': match_desc,
                    'prob1': prob1,
                    'prob2': prob2,
                    'risk': 'HIGH',
                    'description': 'HIGH UPSET POTENTIAL - Virtual coin flip',
                    'upset_score': diff
                })
            elif diff < 25 and min(prob1, prob2) > 30:  # Reasonable upset chance
                upsets.append({
                    'round': round_name,
                    'match': match_desc,
                    'prob1': prob1,
                    'prob2': prob2,
                    'risk': 'MEDIUM',
                    'description': 'Upset possible - Competitive matchup',
                    'upset_score': diff
                })
    
    # Sort by upset potential (lower diff = higher potential) and return top 5
    upsets.sort(key=lambda x: x['upset_score'])
    return upsets[:5]


def _display_title_probabilities_chart(probabilities, champion):
    """Display visual chart of title probabilities"""
    import pandas as pd
    
    # Show as clean dataframe only
    chart_data = []
    for rank, (player, prob) in enumerate(list(probabilities.items())[:10], 1):
        is_champion = (player == champion)
        chart_data.append({
            'Rank': f"{rank}.",
            'Player': f"{'🏆 ' if is_champion else ''}{player}",
            'Probability': f"{prob:.1f}%"
        })
    
    df = pd.DataFrame(chart_data)
    st.dataframe(df, hide_index=True, width='stretch')