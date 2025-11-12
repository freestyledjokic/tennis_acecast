#!/usr/bin/env python3
"""
Tennis Match Prediction System using Elo Ratings

Implements an Elo rating system for tennis matches with both overall and surface-specific ratings.
Supports ATP/WTA CSV format data and provides match prediction capabilities.
"""

import csv
import math
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional


@dataclass
class Match:
    """Represents a tennis match with relevant details."""
    date: datetime
    surface: str
    winner: str
    loser: str
    score: str
    best_of: int
    round_name: str


@dataclass
class PlayerStats:
    """Tracks player statistics and ratings."""
    overall_elo: float = 1500.0
    surface_elos: Dict[str, float] = field(default_factory=lambda: defaultdict(lambda: 1500.0))
    match_history: Dict[str, deque] = field(default_factory=lambda: defaultdict(lambda: deque(maxlen=50)))
    h2h_overall: Dict[str, Tuple[int, int]] = field(default_factory=lambda: defaultdict(lambda: (0, 0)))
    h2h_surface: Dict[str, Dict[str, Tuple[int, int]]] = field(default_factory=lambda: defaultdict(lambda: defaultdict(lambda: (0, 0))))


class EloModel:
    """Tennis Elo rating system with surface-specific ratings."""
    
    def __init__(self, k: float = 32.0, bleed: float = 0.2) -> None:
        """
        Initialize the Elo model.
        
        Args:
            k: Base K-factor for rating updates
            bleed: Percentage of surface rating change to apply to overall rating
        """
        self.k = k
        self.bleed = bleed
        self.players: Dict[str, PlayerStats] = defaultdict(PlayerStats)
        self.matches: List[Match] = []
        self.max_date: Optional[datetime] = None
    
    def normalize_name(self, name: str) -> str:
        """Normalize player name by stripping whitespace and collapsing spaces."""
        return ' '.join(name.strip().split())
    
    def normalize_surface(self, surface_str: str) -> str:
        """Normalize surface name to standard format."""
        surface = surface_str.strip().lower()
        if surface in ['carpet', 'indoor hard']:
            return 'indoor_hard'
        elif surface in ['hard', 'clay', 'grass', 'indoor_hard']:
            return surface
        else:
            return 'hard'  # Default for unknown surfaces
    
    def expected_score(self, ra: float, rb: float) -> float:
        """Calculate expected score for player A against player B."""
        return 1 / (1 + 10**((rb - ra) / 400))
    
    def ingest_csv_files(self, paths: List[str]) -> None:
        """
        Read and process CSV files containing match data.
        
        Args:
            paths: List of file paths to CSV files
        """
        all_matches = []
        
        for path in paths:
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        try:
                            # Parse date
                            date_str = row.get('tourney_date', '').strip()
                            if not date_str or len(date_str) != 8:
                                continue
                            
                            match_date = datetime.strptime(date_str, '%Y%m%d')
                            
                            # Extract match details
                            surface = self.normalize_surface(row.get('surface', ''))
                            winner = self.normalize_name(row.get('winner_name', ''))
                            loser = self.normalize_name(row.get('loser_name', ''))
                            score = row.get('score', '').strip()
                            best_of = int(row.get('best_of', 3))
                            round_name = row.get('round', '').strip()
                            
                            if not winner or not loser:
                                continue
                            
                            match = Match(match_date, surface, winner, loser, score, best_of, round_name)
                            all_matches.append(match)
                            
                        except (ValueError, KeyError) as e:
                            print(f"Warning: Skipping malformed row in {path}: {e}")
                            continue
                            
            except FileNotFoundError:
                print(f"Warning: File not found: {path}")
                continue
        
        # Sort matches by date
        all_matches.sort(key=lambda m: m.date)
        self.matches = all_matches
        
        if all_matches:
            self.max_date = max(match.date for match in all_matches)
        
        # Process matches chronologically
        for match in all_matches:
            self._process_match(match)
    
    def _process_match(self, match: Match) -> None:
        """Process a single match and update player ratings."""
        winner = match.winner
        loser = match.loser
        surface = match.surface
        
        # Get current ratings
        winner_surface_elo = self.players[winner].surface_elos[surface]
        loser_surface_elo = self.players[loser].surface_elos[surface]
        
        # Calculate expected scores
        winner_expected = self.expected_score(winner_surface_elo, loser_surface_elo)
        loser_expected = 1 - winner_expected
        
        # Calculate K-factor with recency boost
        k_factor = self.k
        if self.max_date and (self.max_date - match.date).days <= 365:
            k_factor *= 1.10
        
        # Calculate rating changes
        winner_delta = k_factor * (1 - winner_expected)
        loser_delta = k_factor * (0 - loser_expected)
        
        # Update surface ratings
        self.players[winner].surface_elos[surface] += winner_delta
        self.players[loser].surface_elos[surface] += loser_delta
        
        # Bleed into overall ratings
        self.players[winner].overall_elo += self.bleed * winner_delta
        self.players[loser].overall_elo += self.bleed * loser_delta
        
        # Update match history
        self.players[winner].match_history[surface].append(('W', match.date))
        self.players[loser].match_history[surface].append(('L', match.date))
        
        # Update head-to-head records
        # Overall H2H
        w_wins, w_losses = self.players[winner].h2h_overall[loser]
        self.players[winner].h2h_overall[loser] = (w_wins + 1, w_losses)
        l_wins, l_losses = self.players[loser].h2h_overall[winner]
        self.players[loser].h2h_overall[winner] = (l_wins, l_losses + 1)
        
        # Surface H2H
        w_surf_wins, w_surf_losses = self.players[winner].h2h_surface[surface][loser]
        self.players[winner].h2h_surface[surface][loser] = (w_surf_wins + 1, w_surf_losses)
        l_surf_wins, l_surf_losses = self.players[loser].h2h_surface[surface][winner]
        self.players[loser].h2h_surface[surface][winner] = (l_surf_wins, l_surf_losses + 1)
    
    def get_rating(self, player: str, surface: Optional[str] = None) -> float:
        """
        Get player's rating.
        
        Args:
            player: Player name
            surface: Surface type (if None, returns overall rating)
            
        Returns:
            Player's rating (1500.0 if player not found)
        """
        normalized_player = self.normalize_name(player)
        if normalized_player not in self.players:
            return 1500.0
        
        if surface is None:
            return self.players[normalized_player].overall_elo
        else:
            normalized_surface = self.normalize_surface(surface)
            return self.players[normalized_player].surface_elos[normalized_surface]
    
    def head_to_head(self, player_a: str, player_b: str, surface: Optional[str] = None) -> Tuple[int, int]:
        """
        Get head-to-head record between two players.
        
        Args:
            player_a: First player name
            player_b: Second player name
            surface: Surface type (if None, returns overall H2H)
            
        Returns:
            Tuple of (wins_for_a, wins_for_b)
        """
        norm_a = self.normalize_name(player_a)
        norm_b = self.normalize_name(player_b)
        
        if norm_a not in self.players:
            return (0, 0)
        
        if surface is None:
            return self.players[norm_a].h2h_overall[norm_b]
        else:
            normalized_surface = self.normalize_surface(surface)
            return self.players[norm_a].h2h_surface[normalized_surface][norm_b]
    
    def last_n_record(self, player: str, surface: str, n: int = 10) -> Tuple[int, int]:
        """
        Get player's last N matches record on specified surface.
        
        Args:
            player: Player name
            surface: Surface type
            n: Number of recent matches to consider
            
        Returns:
            Tuple of (wins, losses)
        """
        normalized_player = self.normalize_name(player)
        normalized_surface = self.normalize_surface(surface)
        
        if normalized_player not in self.players:
            return (0, 0)
        
        history = self.players[normalized_player].match_history[normalized_surface]
        recent_matches = list(history)[-n:] if len(history) >= n else list(history)
        
        wins = sum(1 for result, _ in recent_matches if result == 'W')
        losses = len(recent_matches) - wins
        
        return (wins, losses)
    
    def match_win_prob(self, player_a: str, player_b: str, surface: str) -> float:
        """
        Calculate win probability for player_a against player_b on specified surface.
        
        Args:
            player_a: First player name
            player_b: Second player name
            surface: Surface type
            
        Returns:
            Win probability for player_a (0.0 to 1.0)
        """
        norm_a = self.normalize_name(player_a)
        norm_b = self.normalize_name(player_b)
        normalized_surface = self.normalize_surface(surface)
        
        # Try surface-specific ratings first
        if (norm_a in self.players and normalized_surface in self.players[norm_a].surface_elos and
            norm_b in self.players and normalized_surface in self.players[norm_b].surface_elos):
            rating_a = self.players[norm_a].surface_elos[normalized_surface]
            rating_b = self.players[norm_b].surface_elos[normalized_surface]
        else:
            # Fallback to overall ratings
            rating_a = self.get_rating(norm_a)
            rating_b = self.get_rating(norm_b)
        
        return self.expected_score(rating_a, rating_b)
    
    def export_player_snapshot(self, player: str, surface: str) -> Dict:
        """
        Export player snapshot with ratings and recent record.
        
        Args:
            player: Player name
            surface: Surface type
            
        Returns:
            Dictionary with player statistics
        """
        normalized_player = self.normalize_name(player)
        normalized_surface = self.normalize_surface(surface)
        
        surface_elo = self.get_rating(normalized_player, normalized_surface)
        overall_elo = self.get_rating(normalized_player)
        wins, losses = self.last_n_record(normalized_player, normalized_surface, 10)
        
        return {
            "elo_surface": surface_elo,
            "elo_overall": overall_elo,
            "last10_surface": f"{wins}-{losses}"
        }


if __name__ == "__main__":
    # Demonstration of the Elo system
    print("Tennis Elo Rating System Demo")
    print("=" * 40)
    
    # Initialize model
    model = EloModel()
    
    # Try to load data from data directory
    data_dir = Path("data")
    if data_dir.exists():
        csv_files = list(data_dir.glob("*.csv"))
        if csv_files:
            print(f"Loading {len(csv_files)} CSV files from data directory...")
            model.ingest_csv_files([str(f) for f in csv_files])
            print(f"Processed {len(model.matches)} matches")
            
            # Get some sample players (first few unique players from matches)
            sample_players = []
            for match in model.matches[:100]:  # Look at first 100 matches
                if match.winner not in sample_players:
                    sample_players.append(match.winner)
                if match.loser not in sample_players:
                    sample_players.append(match.loser)
                if len(sample_players) >= 3:
                    break
            
            if len(sample_players) >= 2:
                print("\nSample Player Analysis:")
                print("-" * 30)
                
                for i, player in enumerate(sample_players[:3]):
                    print(f"\nPlayer {i+1}: {player}")
                    
                    # Show ratings for different surfaces
                    for surface in ['hard', 'clay', 'grass']:
                        surface_rating = model.get_rating(player, surface)
                        overall_rating = model.get_rating(player)
                        wins, losses = model.last_n_record(player, surface, 10)
                        
                        print(f"  {surface.capitalize()}: Elo={surface_rating:.1f}, "
                              f"Overall={overall_rating:.1f}, Last 10: {wins}-{losses}")
                    
                    # Export snapshot
                    snapshot = model.export_player_snapshot(player, 'hard')
                    print(f"  Snapshot (Hard): {snapshot}")
                
                # Head-to-head and match prediction
                if len(sample_players) >= 2:
                    p1, p2 = sample_players[0], sample_players[1]
                    print(f"\nHead-to-Head: {p1} vs {p2}")
                    
                    h2h_overall = model.head_to_head(p1, p2)
                    h2h_hard = model.head_to_head(p1, p2, 'hard')
                    
                    print(f"  Overall H2H: {h2h_overall[0]}-{h2h_overall[1]}")
                    print(f"  Hard court H2H: {h2h_hard[0]}-{h2h_hard[1]}")
                    
                    # Win probabilities
                    for surface in ['hard', 'clay', 'grass']:
                        prob = model.match_win_prob(p1, p2, surface)
                        print(f"  {p1} win prob on {surface}: {prob:.3f}")
        else:
            print("No CSV files found in data directory")
    else:
        print("Data directory not found - creating sample demonstration")
        
        # Create sample data for demonstration
        print("\nCreating sample matches for demonstration...")
        
        # Simulate some matches
        sample_matches = [
            Match(datetime(2023, 1, 15), 'hard', 'Roger Federer', 'Rafael Nadal', '6-4 6-2', 3, 'F'),
            Match(datetime(2023, 2, 20), 'clay', 'Rafael Nadal', 'Novak Djokovic', '7-5 6-3', 3, 'SF'),
            Match(datetime(2023, 3, 10), 'grass', 'Novak Djokovic', 'Roger Federer', '6-7 6-4 6-2', 3, 'F'),
            Match(datetime(2023, 4, 5), 'hard', 'Rafael Nadal', 'Roger Federer', '6-3 6-4', 3, 'QF'),
        ]
        
        for match in sample_matches:
            model._process_match(match)
        
        print("Sample analysis:")
        for player in ['Roger Federer', 'Rafael Nadal', 'Novak Djokovic']:
            print(f"\n{player}:")
            print(f"  Overall Elo: {model.get_rating(player):.1f}")
            print(f"  Hard court Elo: {model.get_rating(player, 'hard'):.1f}")
            print(f"  Clay court Elo: {model.get_rating(player, 'clay'):.1f}")
            
        # Sample prediction
        prob = model.match_win_prob('Roger Federer', 'Rafael Nadal', 'hard')
        print(f"\nFederer win probability vs Nadal on hard: {prob:.3f}")

def predict_match(model, player1, player2, surface='hard'):
    """Test prediction for specific players"""
    prob1 = model.match_win_prob(player1, player2, surface)
    prob2 = 1 - prob1
    h2h = model.head_to_head(player1, player2)
    
    print(f"\n{player1} vs {player2} on {surface}:")
    print(f"  {player1} win probability: {prob1:.3f} ({prob1*100:.1f}%)")
    print(f"  {player2} win probability: {prob2:.3f} ({prob2*100:.1f}%)")
    print(f"  Head-to-head: {h2h[0]}-{h2h[1]}")
    print(f"  {player1} Elo ({surface}): {model.get_rating(player1, surface):.1f}")
    print(f"  {player2} Elo ({surface}): {model.get_rating(player2, surface):.1f}")


