#!/usr/bin/env python3
"""Streamlit-facing wrapper around the core Elo model.

Provides a UI-friendly facade over :class:`elo.EloModel`: a cached, sorted
player list, enriched player snapshots, and guard clauses that return safe
defaults before any match data has been loaded.
"""

from typing import Dict, List, Optional, Tuple

from elo import DEFAULT_RATING, KNOWN_SURFACES, EloModel


class EloSystem:
    """Wrapper class for EloModel providing a Streamlit-friendly interface."""

    def __init__(self) -> None:
        self.model = EloModel()
        self._players_cache: Optional[List[str]] = None
        self._loaded = False

    def load_data(self, csv_paths: List[str]) -> bool:
        """Load match data from CSV files.

        Returns:
            True on success, False if ingestion raised an error.
        """
        try:
            self.model.ingest_csv_files(csv_paths)
            self._loaded = True
            self._players_cache = None  # New data invalidates the player list
            return True
        except Exception as exc:
            print(f"Error loading data: {exc}")
            return False

    def get_all_players(self) -> List[str]:
        """Get a sorted list of all known player names (cached)."""
        if not self._loaded:
            return []

        if self._players_cache is None:
            self._players_cache = sorted(self.model.players.keys())

        return self._players_cache

    def export_player_snapshot(self, player_name: str, surface: str) -> Dict:
        """Export a player snapshot enriched with per-surface data for the UI.

        Extends the basic model snapshot with ratings and recent form for
        every surface, the player's most recent matches, and a total match
        count. Returns an empty dict for unknown players or unloaded data.
        """
        if not self._loaded or player_name not in self.model.players:
            return {}

        snapshot = self.model.export_player_snapshot(player_name, surface)
        player_stats = self.model.players[player_name]

        surface_ratings = {
            surf: self.model.get_rating(player_name, surf) for surf in KNOWN_SURFACES
        }

        recent_form = {}
        for surf in KNOWN_SURFACES:
            wins, losses = self.model.last_n_record(player_name, surf, 10)
            recent_form[surf] = {"wins": wins, "losses": losses}

        # Gather up to 10 recent results per surface, then keep the 10 most
        # recent across all surfaces combined.
        all_matches = [
            {"result": result, "date": date, "surface": surf}
            for surf, history in player_stats.match_history.items()
            for result, date in list(history)[-10:]
        ]
        all_matches.sort(key=lambda m: m["date"], reverse=True)

        return {
            **snapshot,
            "surface_ratings": surface_ratings,
            "recent_form": recent_form,
            "recent_matches": all_matches[:10],
            "total_matches": sum(
                len(history) for history in player_stats.match_history.values()
            ),
        }

    def get_player_elo(self, player_name: str, surface: str) -> float:
        """Get a player's Elo rating for a specific surface."""
        if not self._loaded:
            return DEFAULT_RATING
        return self.model.get_rating(player_name, surface)

    def get_player_overall_elo(self, player_name: str) -> float:
        """Get a player's overall (surface-independent) Elo rating."""
        if not self._loaded:
            return DEFAULT_RATING
        return self.model.get_rating(player_name)

    def get_head_to_head(
        self, player_a: str, player_b: str, surface: Optional[str] = None
    ) -> Tuple[int, int]:
        """Get the head-to-head record between two players."""
        if not self._loaded:
            return (0, 0)
        return self.model.head_to_head(player_a, player_b, surface)

    def get_match_prediction(self, player_a: str, player_b: str, surface: str) -> Dict:
        """Get win probabilities, H2H records, and ratings for a matchup."""
        if not self._loaded:
            return {}

        win_prob_a = self.model.match_win_prob(player_a, player_b, surface)

        return {
            "win_prob_a": win_prob_a,
            "win_prob_b": 1 - win_prob_a,
            "h2h_overall": self.model.head_to_head(player_a, player_b),
            "h2h_surface": self.model.head_to_head(player_a, player_b, surface),
            "player_a_elo": self.model.get_rating(player_a, surface),
            "player_b_elo": self.model.get_rating(player_b, surface),
        }
