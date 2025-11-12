"""
Match Prediction UI Module
Provides interface for predicting match outcomes between two players
"""

import streamlit as st


def render(model, default_surface='hard', model_id=None, region=None, show_context=False):
    """
    Render the match prediction page
    
    Args:
        model: EloSystem instance
        default_surface: Default surface for predictions
        model_id: Bedrock model ID for AI analysis
        region: AWS region for Bedrock
        show_context: Whether to show the context sent to AI
    """
    st.markdown('<div class="page-title">⚔️ Match Prediction</div>', unsafe_allow_html=True)
    
    if model is None:
        st.error("❌ Unable to load prediction model. Please check your configuration.")
        return
    
    # Initialize session state for match prediction
    if 'match_player1' not in st.session_state:
        st.session_state.match_player1 = None
    if 'match_player2' not in st.session_state:
        st.session_state.match_player2 = None
    if 'match_surface' not in st.session_state:
        st.session_state.match_surface = default_surface
    if 'prediction_result' not in st.session_state:
        st.session_state.prediction_result = None
    
    # Get all players
    all_players = _get_all_players(model)
    
    if not all_players:
        st.warning("No players found in database.")
        return
    
    # Match Setup Interface
    st.markdown("### 🎾 Setup Match")
    
    # Player selection in 3 columns
    col1, col_vs, col2 = st.columns([5, 1, 5])
    
    with col1:
        st.markdown("**Player 1**")
        player1 = st.selectbox(
            "Select Player 1",
            options=[""] + all_players,
            index=0,
            key="player1_select",
            label_visibility="collapsed"
        )
        if player1 and player1 != "":
            st.session_state.match_player1 = player1
            elo1 = model.get_player_elo(player1, st.session_state.match_surface)
            st.caption(f"Elo: {elo1:.0f}")
    
    with col_vs:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("<h2 style='text-align: center; color: #00d4ff;'>VS</h2>", unsafe_allow_html=True)
    
    with col2:
        st.markdown("**Player 2**")
        player2 = st.selectbox(
            "Select Player 2",
            options=[""] + all_players,
            index=0,
            key="player2_select",
            label_visibility="collapsed"
        )
        if player2 and player2 != "":
            st.session_state.match_player2 = player2
            elo2 = model.get_player_elo(player2, st.session_state.match_surface)
            st.caption(f"Elo: {elo2:.0f}")
    
    # Surface and format selection
    st.markdown("<br>", unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**🎾 Surface**")
        surface = st.radio(
            "Surface",
            options=['hard', 'clay', 'grass', 'indoor_hard'],
            format_func=lambda x: x.replace('_', ' ').title(),
            horizontal=True,
            key="surface_select",
            label_visibility="collapsed"
        )
        st.session_state.match_surface = surface
    
    with col2:
        st.markdown("**🏆 Match Format**")
        best_of = st.radio(
            "Best of",
            options=[3, 5],
            format_func=lambda x: f"Best of {x}",
            horizontal=True,
            key="format_select",
            label_visibility="collapsed"
        )
    
    # Validation and prediction button
    st.markdown("<br>", unsafe_allow_html=True)
    
    can_predict = (st.session_state.match_player1 and 
                   st.session_state.match_player2 and 
                   st.session_state.match_player1 != st.session_state.match_player2)
    
    if st.session_state.match_player1 == st.session_state.match_player2 and st.session_state.match_player1:
        st.warning("⚠️ Please select two different players")
    
    if st.button("🎾 Predict Match", 
                 disabled=not can_predict, 
                 width='stretch'):
        with st.spinner("Analyzing match..."):
            st.session_state.prediction_result = _predict_match(
                model, 
                st.session_state.match_player1,
                st.session_state.match_player2,
                st.session_state.match_surface,
                best_of,
                model_id,
                region,
                show_context
            )
    
    # Display prediction results
    if st.session_state.prediction_result:
        _display_prediction_results(st.session_state.prediction_result, show_context)
    



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


def _predict_match(model, player1, player2, surface, best_of, model_id, region, show_context):
    """Generate match prediction"""
    try:
        # Get match prediction data
        if hasattr(model, 'get_match_prediction'):
            prediction_data = model.get_match_prediction(player1, player2, surface)
            prob1 = prediction_data.get('win_prob_a', 0.5)
            elo1 = prediction_data.get('player_a_elo', 1500)
            elo2 = prediction_data.get('player_b_elo', 1500)
        elif hasattr(model, 'model') and hasattr(model.model, 'match_win_prob'):
            prob1 = model.model.match_win_prob(player1, player2, surface)
            elo1 = model.get_player_elo(player1, surface)
            elo2 = model.get_player_elo(player2, surface)
        else:
            # Fallback calculation
            elo1 = model.get_player_elo(player1, surface)
            elo2 = model.get_player_elo(player2, surface)
            prob1 = 1 / (1 + 10**((elo2 - elo1) / 400))
        
        prob2 = 1 - prob1
        
        # Get H2H record (simplified - you may want to implement this in your elo.py)
        h2h = _get_h2h_record(model, player1, player2, surface)
        
        # Get recent form
        form1 = _get_recent_form(model, player1, surface)
        form2 = _get_recent_form(model, player2, surface)
        
        result = {
            'player1': player1,
            'player2': player2,
            'surface': surface,
            'best_of': best_of,
            'prob1': prob1,
            'prob2': prob2,
            'elo1': elo1,
            'elo2': elo2,
            'h2h': h2h,
            'form1': form1,
            'form2': form2,
            'ai_analysis': None  # Placeholder for AI analysis
        }
        
        # Generate AI analysis if model_id provided
        if model_id and region:
            result['ai_analysis'] = _generate_ai_analysis(result, model_id, region, show_context)
        
        return result
        
    except Exception as e:
        st.error(f"Error predicting match: {e}")
        return None


def _get_h2h_record(model, player1, player2, surface):
    """Get head-to-head record between two players"""
    try:
        # Try EloSystem method first
        if hasattr(model, 'head_to_head'):
            h2h_overall = model.head_to_head(player1, player2)
            h2h_surface = model.head_to_head(player1, player2, surface)
            return {
                'total': f"{h2h_overall[0]}-{h2h_overall[1]}",
                'surface': f"{h2h_surface[0]}-{h2h_surface[1]}",
                'last_match': "Data available" if sum(h2h_overall) > 0 else "No previous meetings"
            }
        # Try underlying model method
        elif hasattr(model, 'model') and hasattr(model.model, 'head_to_head'):
            h2h_overall = model.model.head_to_head(player1, player2)
            h2h_surface = model.model.head_to_head(player1, player2, surface)
            return {
                'total': f"{h2h_overall[0]}-{h2h_overall[1]}",
                'surface': f"{h2h_surface[0]}-{h2h_surface[1]}",
                'last_match': "Data available" if sum(h2h_overall) > 0 else "No previous meetings"
            }
        else:
            return {
                'total': "0-0",
                'surface': "0-0",
                'last_match': "No previous meetings"
            }
    except Exception as e:
        return {
            'total': "0-0",
            'surface': "0-0",
            'last_match': "No previous meetings"
        }


def _get_recent_form(model, player, surface):
    """Get recent form for a player"""
    try:
        # Try EloSystem method first
        if hasattr(model, 'last_n_record'):
            wins, losses = model.last_n_record(player, surface, 10)
            return f"{wins}-{losses}"
        # Try underlying model method
        elif hasattr(model, 'model') and hasattr(model.model, 'last_n_record'):
            wins, losses = model.model.last_n_record(player, surface, 10)
            return f"{wins}-{losses}"
        # Try direct access to player data
        elif hasattr(model, 'model') and hasattr(model.model, 'players'):
            if player in model.model.players:
                player_data = model.model.players[player]
                if hasattr(player_data, 'match_history') and surface in player_data.match_history:
                    matches = list(player_data.match_history[surface])[-10:]
                    wins = sum(1 for result, _ in matches if result == 'W')
                    losses = len(matches) - wins
                    return f"{wins}-{losses}"
        return "0-0"
    except Exception as e:
        return "0-0"


def _generate_ai_analysis(prediction_data, model_id, region, show_context):
    """Generate AI analysis using Bedrock"""
    
    # Enhanced fallback analysis with detailed insights
    def _create_detailed_analysis():
        p1, p2 = prediction_data['player1'], prediction_data['player2']
        elo1, elo2 = prediction_data['elo1'], prediction_data['elo2']
        prob1, prob2 = prediction_data['prob1'], prediction_data['prob2']
        surface = prediction_data['surface'].replace('_', ' ').title()
        
        # Determine favorite and underdog
        favorite = p1 if prob1 > prob2 else p2
        underdog = p2 if prob1 > prob2 else p1
        fav_prob = max(prob1, prob2) * 100
        
        # Analyze Elo difference
        elo_diff = abs(elo1 - elo2)
        if elo_diff < 50:
            elo_analysis = "very evenly matched"
        elif elo_diff < 100:
            elo_analysis = "slight edge to the favorite"
        elif elo_diff < 200:
            elo_analysis = "clear favorite emerges"
        else:
            elo_analysis = "significant skill gap"
        
        # Surface analysis
        surface_insights = {
            'Hard': "Fast-paced rallies and aggressive baseline play will be key",
            'Clay': "Patience, endurance, and topspin will determine the winner", 
            'Grass': "Serve-and-volley tactics and quick points favor big servers",
            'Indoor Hard': "Controlled conditions favor consistent, powerful groundstrokes"
        }
        
        # Form analysis
        form1_wins = int(prediction_data['form1'].split('-')[0]) if '-' in prediction_data['form1'] else 0
        form2_wins = int(prediction_data['form2'].split('-')[0]) if '-' in prediction_data['form2'] else 0
        
        if form1_wins > form2_wins + 2:
            form_analysis = f"{p1} enters with superior recent form"
        elif form2_wins > form1_wins + 2:
            form_analysis = f"{p2} has the momentum advantage"
        else:
            form_analysis = "Both players show similar recent form"
        
        return f"""
**MATCH OVERVIEW**
{favorite} enters as the {fav_prob:.0f}% favorite against {underdog} on {surface} court. The Elo ratings show {elo_analysis} ({elo_diff:.0f} point difference).

**KEY FACTORS**
• **Surface Advantage**: {surface_insights.get(surface, 'Court conditions will play a crucial role')}
• **Current Form**: {form_analysis} ({p1}: {prediction_data['form1']}, {p2}: {prediction_data['form2']})
• **Experience**: Head-to-head record shows {prediction_data['h2h']['total']} previous meetings
• **Pressure**: {'High-stakes match' if abs(prob1 - prob2) < 0.2 else 'Clear favorite must execute'}

**TACTICAL BREAKDOWN**
• **{p1}**: {'Aggressive baseline game' if elo1 > elo2 else 'Counter-punching style'} suits {surface.lower()} conditions
• **{p2}**: {'Consistent pressure' if elo2 > elo1 else 'Upset potential through variety'} could be decisive
• **Match Flow**: Expect {'tight sets with crucial break points' if elo_diff < 100 else 'momentum swings favoring the stronger player'}

**PREDICTION CONFIDENCE**
{'🔥 High' if abs(prob1 - 0.5) > 0.2 else '⚖️ Moderate' if abs(prob1 - 0.5) > 0.1 else '🎲 Low'} confidence - {'Statistical model strongly favors one player' if abs(prob1 - 0.5) > 0.2 else 'Close match with multiple possible outcomes' if abs(prob1 - 0.5) > 0.1 else 'Coin flip match, either player could win'}

**BETTING INSIGHT**
{'Value may exist on the underdog' if abs(prob1 - 0.5) < 0.15 else 'Favorite justified by data'} | Best of {prediction_data['best_of']} format {'favors consistency' if prediction_data['best_of'] == 5 else 'allows for upsets'}
        """
    
    try:
        # Try Bedrock API first
        import sys
        sys.path.append('.')
        from app import call_bedrock
        
        # Create simplified prompt to avoid validation errors
        prompt = f"Analyze this tennis match: {prediction_data['player1']} vs {prediction_data['player2']} on {prediction_data['surface'].replace('_', ' ').title()} court. Elo ratings: {prediction_data['elo1']:.0f} vs {prediction_data['elo2']:.0f}. Win probability: {prediction_data['prob1']*100:.1f}% vs {prediction_data['prob2']*100:.1f}%. Provide expert match analysis."
        
        system_prompt = "You are a tennis expert analyst providing match insights."
        response = call_bedrock(system_prompt, prompt, model_id, region)
        
        if response and len(response.strip()) > 50:
            return response
        else:
            return _create_detailed_analysis()
            
    except Exception as e:
        return _create_detailed_analysis()


def _display_prediction_results(result, show_context):
    """Display comprehensive prediction results"""
    st.markdown("---")
    st.markdown("## 📊 Match Prediction Results")
    
    # Match header
    st.markdown(f"""
    <div style='background: linear-gradient(135deg, #0f1629 0%, #1a2332 100%); 
                border: 1px solid #1a2332; border-radius: 16px; padding: 1.5rem; 
                margin-bottom: 2rem; text-align: center;'>
        <h2 style='color: #e2e8f0; margin: 0;'>
            {result['player1']} vs {result['player2']}
        </h2>
        <p style='color: #94a3b8; margin-top: 0.5rem;'>
            {result['surface'].replace('_', ' ').title()} Court | Best of {result['best_of']}
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Win probability
    st.markdown("### 📊 WIN PROBABILITY")
    col1, col_mid, col2 = st.columns([5, 1, 5])
    
    with col1:
        st.metric(result['player1'], f"{result['prob1']*100:.1f}%")
    with col_mid:
        st.markdown("<h3 style='text-align: center; color: #94a3b8;'>vs</h3>", unsafe_allow_html=True)
    with col2:
        st.metric(result['player2'], f"{result['prob2']*100:.1f}%")
    
    # Progress bar
    st.progress(result['prob1'])
    
    # Key statistics comparison
    st.markdown("### 📈 KEY STATISTICS")
    
    stats_df = pd.DataFrame({
        result['player1']: [
            f"{result['elo1']:.0f}",
            result['form1']
        ],
        'Metric': ['Elo Rating', 'Recent Form (L10)'],
        result['player2']: [
            f"{result['elo2']:.0f}",
            result['form2']
        ]
    })
    
    st.dataframe(stats_df, width='stretch', hide_index=True)
    
    # Head-to-head
    st.markdown("### ⚔️ HEAD-TO-HEAD")
    st.info(f"**Career:** {result['h2h']['total']}\n\n**On {result['surface'].title()}:** {result['h2h']['surface']}\n\n**Last Match:** {result['h2h']['last_match']}")
    
    # AI Analysis
    if result['ai_analysis']:
        st.markdown("### 🤖 AI ANALYSIS")
        with st.expander("View Detailed Analysis", expanded=True):
            st.markdown(result['ai_analysis'])
    
    # Action buttons
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🔄 New Prediction", width='stretch'):
            st.session_state.prediction_result = None
            st.rerun()
    with col2:
        if st.button("💾 Save Prediction", width='stretch'):
            st.success("Prediction saved! (Feature coming soon)")
    with col3:
        if st.button("📤 Share", width='stretch'):
            st.info("Share feature coming soon!")
    



import pandas as pd