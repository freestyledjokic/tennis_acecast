"""
Player Profiles UI Module
Displays comprehensive player statistics, Elo ratings, and performance metrics
"""

import streamlit as st
import pandas as pd
import csv
from datetime import datetime


def render(model, default_surface='hard'):
    """
    Render the player profiles page
    
    Args:
        model: EloSystem instance or boolean indicating if model is loaded
        default_surface: Default surface for queries ('hard', 'clay', 'grass', 'indoor_hard')
    """
    st.markdown('<div class="page-title">👤 Player Profiles</div>', unsafe_allow_html=True)
    
    # Check if model is actually loaded (not just a boolean)
    if not model or isinstance(model, bool):
        st.error("❌ Unable to load player data. Please check your data directory.")
        if st.button("← Back to Home"):
            st.session_state.page = 'home'
            st.rerun()
        return
    
    # Get all players from the model
    all_players = _get_all_players(model)
    
    if not all_players:
        st.warning("No players found in database.")
        if st.button("← Back to Home"):
            st.session_state.page = 'home'
            st.rerun()
        return
    
    # Player search interface
    st.markdown("### 🔍 Search Player")
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        selected_player = st.selectbox(
            "Select a player to view their profile",
            options=[""] + all_players,
            index=0,
            key="player_search",
            help="Start typing to search for a player"
        )
    
    # Display player profile if selected
    if selected_player and selected_player != "":
        _display_player_profile(model, selected_player, default_surface)
    else:
        # Show helpful message
        st.markdown("""
        <div style='background: linear-gradient(135deg, #0f1629 0%, #1a2332 100%); 
                    border: 1px solid #1a2332; border-radius: 12px; padding: 2rem; 
                    text-align: center; margin-top: 2rem;'>
            <h3 style='color: #00d4ff; margin: 0;'>👆 Select a Player</h3>
            <p style='color: #94a3b8; margin-top: 1rem;'>
                Choose a player from the dropdown above to view their detailed profile, 
                including Elo ratings, recent form, and performance statistics.
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    # Back button
    st.markdown("<br><br>", unsafe_allow_html=True)
    if st.button("← Back to Home", key="back_home"):
        st.session_state.page = 'home'
        st.session_state.selected_player = None
        st.rerun()


def _get_all_players(model):
    """Extract all unique players from the model"""
    try:
        # Try to get players from EloSystem method
        if hasattr(model, 'get_all_players'):
            return model.get_all_players()
        # Fallback to accessing players directly
        elif hasattr(model, 'players'):
            return sorted(list(model.players.keys()))
        else:
            return []
    except Exception as e:
        st.error(f"Error getting players: {e}")
        return []


def _display_player_profile(model, player_name, default_surface):
    """Display comprehensive player profile"""
    
    with st.spinner(f"Loading {player_name}'s profile..."):
        player_stats = _get_player_stats(model, player_name)
    
    if not player_stats:
        st.error(f"Unable to load data for {player_name}")
        return
    
    # Get player biographical info
    player_info = _get_player_info(player_name)
    
    # Player Header
    st.markdown(f"""
    <div style='background: linear-gradient(135deg, #0f1629 0%, #1a2332 100%); 
                border: 1px solid #1a2332; border-radius: 16px; padding: 2rem; margin-bottom: 2rem;'>
        <div style='font-size: 2rem; font-weight: 700; margin: 0;
                    background: linear-gradient(135deg, #00d4ff 0%, #39ff14 100%);
                    -webkit-background-clip: text; -webkit-text-fill-color: transparent;'>
            {player_stats['name']}
        </div>
        <div style='color: #94a3b8; margin-top: 1rem; font-size: 0.95rem; line-height: 1.5;'>
            <strong>Hand:</strong> {player_info['hand']} &nbsp;&nbsp;
            <strong>Date of Birth:</strong> {player_info['dob']} &nbsp;&nbsp;
            <strong>Country:</strong> {player_info['country']} &nbsp;&nbsp;
            <strong>Height:</strong> {player_info['height']}
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Elo Ratings Section
    st.markdown("### 📊 ELO RATINGS")
    _render_elo_ratings(player_stats['elos'])
    
    # Performance Breakdown
    st.markdown("### 🎯 PERFORMANCE BREAKDOWN")
    _render_performance_table(player_stats['surface_stats'])
    
    # Recent Matches
    if player_stats['recent_matches']:
        st.markdown("### 🔥 RECENT MATCHES")
        _render_recent_matches(player_stats['recent_matches'])
    
    # Export functionality
    st.markdown("<br>", unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📥 Export Player Stats", width='stretch'):
            _export_player_stats(player_stats)
    with col2:
        if st.button("🔄 Compare with Another Player", width='stretch'):
            st.info("Comparison feature coming soon!")


def _get_player_stats(model, player_name):
    """Get comprehensive player statistics"""
    try:
        # Get Elo ratings for all surfaces
        elos = {
            'Hard Court': _safe_get_rating(model, player_name, 'hard'),
            'Clay Court': _safe_get_rating(model, player_name, 'clay'),
            'Grass': _safe_get_rating(model, player_name, 'grass'),
            'Indoor Hard': _safe_get_rating(model, player_name, 'indoor_hard')
        }
        
        # Get recent form (try different methods)
        recent_form = _get_recent_form(model, player_name)
        
        # Calculate surface-specific win rates
        surface_stats = _get_surface_stats(model, player_name)
        
        # Get recent matches
        recent_matches = _get_recent_matches(model, player_name)
        
        return {
            'name': player_name,
            'elos': elos,
            'recent_form': recent_form,
            'surface_stats': surface_stats,
            'recent_matches': recent_matches
        }
    except Exception as e:
        st.error(f"Error getting player stats: {e}")
        return None


def _safe_get_rating(model, player_name, surface=None):
    """Safely get player rating with fallbacks"""
    try:
        if hasattr(model, 'get_player_elo') and surface:
            return model.get_player_elo(player_name, surface)
        elif hasattr(model, 'get_rating'):
            return model.get_rating(player_name, surface)
        else:
            return 1500.0
    except:
        return 1500.0


def _get_recent_form(model, player_name):
    """Get recent form with fallbacks"""
    try:
        if hasattr(model, 'last_n_record'):
            wins, losses = model.last_n_record(player_name, 'hard', 10)
            return {'wins': wins, 'losses': losses, 'total': wins + losses}
        else:
            return {'wins': 0, 'losses': 0, 'total': 0}
    except:
        return {'wins': 0, 'losses': 0, 'total': 0}


def _get_surface_stats(model, player_name):
    """Get surface-specific statistics"""
    surface_stats = {}
    for surface in ['hard', 'clay', 'grass', 'indoor_hard']:
        try:
            # Try multiple methods to get match data
            wins, losses = 0, 0
            
            if hasattr(model, 'last_n_record'):
                wins, losses = model.last_n_record(player_name, surface, 1000)  # Get all matches
            elif hasattr(model, 'model') and hasattr(model.model, 'last_n_record'):
                wins, losses = model.model.last_n_record(player_name, surface, 1000)
            elif hasattr(model, 'players') and player_name in model.players:
                # Direct access to match history
                player_data = model.players[player_name]
                if hasattr(player_data, 'match_history') and surface in player_data.match_history:
                    matches = list(player_data.match_history[surface])
                    wins = sum(1 for result, _ in matches if result == 'W')
                    losses = len(matches) - wins
            
            total = wins + losses
            win_rate = (wins / total * 100) if total > 0 else 0
            surface_stats[surface] = {
                'win_rate': win_rate,
                'record': f"{wins}-{losses}",
                'total_matches': total
            }
        except Exception as e:
            surface_stats[surface] = {'win_rate': 0, 'record': '0-0', 'total_matches': 0}
    
    return surface_stats


def _get_recent_matches(model, player_name):
    """Get recent matches with fallbacks"""
    try:
        # Try to get from enhanced snapshot if available
        if hasattr(model, 'export_player_snapshot'):
            snapshot = model.export_player_snapshot(player_name, 'hard')
            return snapshot.get('recent_matches', [])
        else:
            return []
    except:
        return []


def _render_elo_ratings(elos):
    """Render Elo ratings with progress bars"""
    col1, col2 = st.columns(2)
    
    elo_items = list(elos.items())
    mid_point = (len(elo_items) + 1) // 2
    
    with col1:
        for surface, elo in elo_items[:mid_point]:
            try:
                if elo > 0:
                    # Clamp percentage between 0 and 100
                    percentage = max(0, min(((elo - 1500) / 1000) * 100, 100))
                    st.markdown(f"**{surface}**")
                    st.progress(percentage / 100)
                    st.markdown(f"<p style='color: #94a3b8; font-size: 0.9rem; margin-top: -0.5rem;'>{elo:.0f}</p>", 
                               unsafe_allow_html=True)
                    st.markdown("<br>", unsafe_allow_html=True)
            except:
                # Fallback display for invalid data
                st.markdown(f"**{surface}**: {elo:.0f}")
    
    with col2:
        for surface, elo in elo_items[mid_point:]:
            try:
                if elo > 0:
                    # Clamp percentage between 0 and 100
                    percentage = max(0, min(((elo - 1500) / 1000) * 100, 100))
                    st.markdown(f"**{surface}**")
                    st.progress(percentage / 100)
                    st.markdown(f"<p style='color: #94a3b8; font-size: 0.9rem; margin-top: -0.5rem;'>{elo:.0f}</p>", 
                               unsafe_allow_html=True)
                    st.markdown("<br>", unsafe_allow_html=True)
            except:
                # Fallback display for invalid data
                st.markdown(f"**{surface}**: {elo:.0f}")


def _render_performance_table(surface_stats):
    """Render performance breakdown table"""
    performance_data = []
    for surface, stats in surface_stats.items():
        performance_data.append({
            'Surface': surface.replace('_', ' ').title(),
            'Win Rate': f"{stats['win_rate']:.1f}%",
            'Record': stats['record'],
            'Total Matches': stats['total_matches']
        })
    
    df = pd.DataFrame(performance_data)
    st.dataframe(df, width='stretch', hide_index=True)


def _render_recent_matches(matches):
    """Render recent matches list"""
    for i, match in enumerate(matches[:10]):
        if isinstance(match, dict):
            result = "✓ W" if match.get('result') == 'W' else "✗ L"
            surface = match.get('surface', 'Unknown')
            date = match.get('date', 'Unknown')
        else:
            # Handle tuple format (result, date)
            result = "✓ W" if match[0] == 'W' else "✗ L"
            surface = 'Unknown'
            date = match[1] if len(match) > 1 else 'Unknown'
        
        color = "#22c55e" if 'W' in result else "#ef4444"
        
        st.markdown(f"""
        <div style='background: linear-gradient(135deg, #0f1629 0%, #1a2332 100%); 
                    border-left: 3px solid {color}; border-radius: 8px; 
                    padding: 0.75rem 1rem; margin: 0.5rem 0;'>
            <strong style='color: {color};'>{result}</strong> 
            <span style='color: #e2e8f0;'> on {surface}</span>
            <span style='color: #94a3b8; font-size: 0.9rem;'> ({date})</span>
        </div>
        """, unsafe_allow_html=True)


@st.cache_data
def _load_players_data():
    """Load and cache ATP players data"""
    try:
        players_data = {}
        with open('data/atp_players.csv', 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                first_name = row.get('name_first', '').strip()
                last_name = row.get('name_last', '').strip()
                
                if first_name and last_name:
                    full_name = f"{first_name} {last_name}"
                    players_data[full_name] = row
        
        return players_data
    except FileNotFoundError:
        return {}
    except Exception as e:
        st.error(f"Error loading players data: {e}")
        return {}


def _get_player_info(player_name):
    """Get player biographical information"""
    players_data = _load_players_data()
    
    # Try exact match first
    player_data = players_data.get(player_name, {})
    
    # If no exact match, try fuzzy matching
    if not player_data:
        for name, data in players_data.items():
            if player_name.lower() in name.lower() or name.lower() in player_name.lower():
                player_data = data
                break
    
    # Debug: show available names if no match found
    if not player_data and len(players_data) > 0:
        # Show first few names for debugging
        sample_names = list(players_data.keys())[:5]
        st.write(f"Debug: Player '{player_name}' not found. Sample names: {sample_names}")
    
    # Parse hand
    hand_raw = player_data.get('hand', '').strip().upper()
    hand = {'R': 'Right', 'L': 'Left', 'U': 'N/A'}.get(hand_raw, 'N/A')
    
    # Parse date of birth
    dob_raw = player_data.get('dob', '').strip()
    if dob_raw and len(dob_raw) == 8:
        try:
            dob_date = datetime.strptime(dob_raw, '%Y%m%d')
            dob = dob_date.strftime('%B %d, %Y')
        except ValueError:
            dob = 'N/A'
    else:
        dob = 'N/A'
    
    # Parse country
    country = player_data.get('ioc', '').strip() or 'N/A'
    
    # Parse height
    height_raw = player_data.get('height', '').strip()
    if height_raw:
        height = f"{height_raw} cm"
    else:
        height = 'N/A'
    
    return {
        'hand': hand,
        'dob': dob,
        'country': country,
        'height': height
    }


def _export_player_stats(player_stats):
    """Export player statistics as JSON"""
    import json
    stats_json = json.dumps(player_stats, indent=2, default=str)
    st.download_button(
        label="Download Stats as JSON",
        data=stats_json,
        file_name=f"{player_stats['name']}_stats.json",
        mime="application/json"
    )