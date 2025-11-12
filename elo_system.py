#!/usr/bin/env python3
"""
EloSystem wrapper for Streamlit integration
"""

from pathlib import Path
from typing import List, Dict, Optional
from elo import EloModel
import json


class EloSystem:
    """Wrapper class for EloModel to provide Streamlit-friendly interface."""
    
    def __init__(self):
        self.model = EloModel()
        self._players_cache = None
        self._loaded = False
    
    def load_data(self, csv_paths: List[str]) -> bool:
        """Load data from CSV files."""
        try:
            self.model.ingest_csv_files(csv_paths)
            self._loaded = True
            self._players_cache = None  # Reset cache
            return True
        except Exception as e:
            print(f"Error loading data: {e}")
            return False
    
    def get_all_players(self) -> List[str]:
        """Get list of all player names."""
        if not self._loaded:
            return []
        
        if self._players_cache is None:
            self._players_cache = list(self.model.players.keys())
            self._players_cache.sort()
        
        return self._players_cache
    
    def export_player_snapshot(self, player_name: str, surface: str) -> Dict:
        """Export player snapshot with enhanced data for UI."""
        if not self._loaded or player_name not in self.model.players:
            return {}
        
        # Get basic snapshot
        snapshot = self.model.export_player_snapshot(player_name, surface)
        
        # Add enhanced data
        player_stats = self.model.players[player_name]
        
        # Get all surface ratings
        surface_ratings = {}
        for surf in ['hard', 'clay', 'grass', 'indoor_hard']:
            surface_ratings[surf] = self.model.get_rating(player_name, surf)
        
        # Get recent form for all surfaces
        recent_form = {}
        for surf in ['hard', 'clay', 'grass', 'indoor_hard']:
            wins, losses = self.model.last_n_record(player_name, surf, 10)
            recent_form[surf] = {'wins': wins, 'losses': losses}
        
        # Get match history (last 10 matches across all surfaces)
        all_matches = []
        for surf, history in player_stats.match_history.items():
            for result, date in list(history)[-10:]:
                all_matches.append({
                    'result': result,
                    'date': date,
                    'surface': surf
                })
        
        # Sort by date (most recent first)
        all_matches.sort(key=lambda x: x['date'], reverse=True)
        
        enhanced_snapshot = {
            **snapshot,
            'surface_ratings': surface_ratings,
            'recent_form': recent_form,
            'recent_matches': all_matches[:10],
            'total_matches': sum(len(history) for history in player_stats.match_history.values())
        }
        
        return enhanced_snapshot
    
    def get_player_elo(self, player_name: str, surface: str) -> float:
        """Get player's Elo rating for specific surface."""
        if not self._loaded:
            return 1500.0
        return self.model.get_rating(player_name, surface)
    
    def get_player_overall_elo(self, player_name: str) -> float:
        """Get player's overall Elo rating."""
        if not self._loaded:
            return 1500.0
        return self.model.get_rating(player_name)
    
    def get_head_to_head(self, player_a: str, player_b: str, surface: Optional[str] = None) -> tuple:
        """Get head-to-head record between two players."""
        if not self._loaded:
            return (0, 0)
        return self.model.head_to_head(player_a, player_b, surface)
    
    def get_match_prediction(self, player_a: str, player_b: str, surface: str) -> Dict:
        """Get match prediction data."""
        if not self._loaded:
            return {}
        
        win_prob_a = self.model.match_win_prob(player_a, player_b, surface)
        h2h_overall = self.model.head_to_head(player_a, player_b)
        h2h_surface = self.model.head_to_head(player_a, player_b, surface)
        
        return {
            'win_prob_a': win_prob_a,
            'win_prob_b': 1 - win_prob_a,
            'h2h_overall': h2h_overall,
            'h2h_surface': h2h_surface,
            'player_a_elo': self.model.get_rating(player_a, surface),
            'player_b_elo': self.model.get_rating(player_b, surface)
        }