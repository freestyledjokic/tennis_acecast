#!/usr/bin/env python3
"""Tennis match prediction engine based on Elo ratings.

Implements an Elo rating system for tennis with both overall and
surface-specific ratings. Ingests ATP/WTA-format CSV match data and answers
questions about win probability, head-to-head records, and recent form.

Run directly (``python elo.py``) for a small demonstration that loads any
CSV files found in ``data/`` (or falls back to hard-coded sample matches).
"""

import csv
import sys
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Deque, Dict, List, Optional, Tuple

# --- Rating constants -------------------------------------------------------
DEFAULT_RATING = 1500.0  # Starting Elo for players with no recorded matches
ELO_SCALE = 400.0  # Standard Elo logistic scale (rating-difference divisor)
DEFAULT_K_FACTOR = 32.0
DEFAULT_BLEED = 0.2  # Fraction of a surface rating change applied overall

# Matches played within this window of the newest match in the dataset get a
# boosted K-factor, so ratings track current form more closely.
RECENT_WINDOW_DAYS = 365
RECENT_K_MULTIPLIER = 1.10

MATCH_HISTORY_LIMIT = 50  # Per-surface results retained per player

# --- CSV parsing constants ---------------------------------------------------
DATE_FORMAT = "%Y%m%d"  # tourney_date column format, e.g. "20240115"
DATE_LENGTH = 8

# --- Surface handling ---------------------------------------------------------
DEFAULT_SURFACE = "hard"
KNOWN_SURFACES = ("hard", "clay", "grass", "indoor_hard")
# Raw CSV surface values that map onto the indoor hard-court rating pool.
INDOOR_HARD_ALIASES = ("carpet", "indoor hard")


@dataclass
class Match:
    """A single completed tennis match."""

    date: datetime
    surface: str
    winner: str
    loser: str
    score: str
    best_of: int
    round_name: str


@dataclass
class PlayerStats:
    """Mutable rating state and history for a single player.

    Attributes:
        overall_elo: Surface-independent rating.
        surface_elos: Rating per surface, defaulting to ``DEFAULT_RATING``.
        match_history: Recent ('W'/'L', date) results per surface, capped at
            ``MATCH_HISTORY_LIMIT`` entries.
        h2h_overall: Opponent name -> (wins, losses) across all surfaces.
        h2h_surface: Surface -> opponent name -> (wins, losses).
    """

    overall_elo: float = DEFAULT_RATING
    surface_elos: Dict[str, float] = field(
        default_factory=lambda: defaultdict(lambda: DEFAULT_RATING)
    )
    match_history: Dict[str, Deque[Tuple[str, datetime]]] = field(
        default_factory=lambda: defaultdict(lambda: deque(maxlen=MATCH_HISTORY_LIMIT))
    )
    h2h_overall: Dict[str, Tuple[int, int]] = field(
        default_factory=lambda: defaultdict(lambda: (0, 0))
    )
    h2h_surface: Dict[str, Dict[str, Tuple[int, int]]] = field(
        default_factory=lambda: defaultdict(lambda: defaultdict(lambda: (0, 0)))
    )


class EloModel:
    """Tennis Elo rating system with surface-specific ratings."""

    def __init__(self, k: float = DEFAULT_K_FACTOR, bleed: float = DEFAULT_BLEED) -> None:
        """Initialize the Elo model.

        Args:
            k: Base K-factor for rating updates.
            bleed: Fraction of each surface rating change also applied to the
                player's overall rating.
        """
        self.k = k
        self.bleed = bleed
        self.players: Dict[str, PlayerStats] = defaultdict(PlayerStats)
        self.matches: List[Match] = []
        self.max_date: Optional[datetime] = None

    # --- Normalization helpers ---------------------------------------------

    def normalize_name(self, name: str) -> str:
        """Normalize a player name by trimming and collapsing whitespace."""
        return " ".join(name.strip().split())

    def normalize_surface(self, surface_str: str) -> str:
        """Normalize a raw surface string to one of ``KNOWN_SURFACES``.

        Unknown surfaces fall back to ``DEFAULT_SURFACE``.
        """
        surface = surface_str.strip().lower()
        if surface in INDOOR_HARD_ALIASES:
            return "indoor_hard"
        if surface in KNOWN_SURFACES:
            return surface
        return DEFAULT_SURFACE

    # --- Core Elo math -------------------------------------------------------

    def expected_score(self, ra: float, rb: float) -> float:
        """Return the expected score (win probability) for rating ``ra`` vs ``rb``."""
        return 1 / (1 + 10 ** ((rb - ra) / ELO_SCALE))

    # --- Data ingestion --------------------------------------------------------

    def ingest_csv_files(self, paths: List[str]) -> None:
        """Read match CSV files and replay all matches chronologically.

        Args:
            paths: File paths to CSV files in the ATP/WTA match format
                (Jeff Sackmann style: tourney_date, surface, winner_name, ...).
        """
        all_matches: List[Match] = []
        for path in paths:
            all_matches.extend(self._parse_csv_file(path))

        # Ratings are path-dependent, so matches must be applied in date order.
        all_matches.sort(key=lambda m: m.date)
        self.matches = all_matches

        if all_matches:
            self.max_date = max(match.date for match in all_matches)

        for match in all_matches:
            self._process_match(match)

    def _parse_csv_file(self, path: str) -> List[Match]:
        """Parse one CSV file, skipping rows that cannot be parsed."""
        matches: List[Match] = []
        try:
            with open(path, "r", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    try:
                        match = self._match_from_row(row)
                    except (ValueError, KeyError) as exc:
                        print(
                            f"Warning: Skipping malformed row in {path}: {exc}",
                            file=sys.stderr,
                        )
                        continue
                    if match is not None:
                        matches.append(match)
        except FileNotFoundError:
            print(f"Warning: File not found: {path}", file=sys.stderr)
        return matches

    def _match_from_row(self, row: Dict[str, str]) -> Optional[Match]:
        """Build a ``Match`` from a raw CSV row.

        Returns None for rows missing a usable date or player names; raises
        ``ValueError`` for unparseable values (reported by the caller).
        """
        date_str = row.get("tourney_date", "").strip()
        if len(date_str) != DATE_LENGTH:
            return None
        match_date = datetime.strptime(date_str, DATE_FORMAT)

        surface = self.normalize_surface(row.get("surface", ""))
        winner = self.normalize_name(row.get("winner_name", ""))
        loser = self.normalize_name(row.get("loser_name", ""))
        score = row.get("score", "").strip()
        best_of = int(row.get("best_of", 3))
        round_name = row.get("round", "").strip()

        if not winner or not loser:
            return None

        return Match(match_date, surface, winner, loser, score, best_of, round_name)

    # --- Rating updates ---------------------------------------------------------

    def _process_match(self, match: Match) -> None:
        """Apply one match result: update ratings, form history, and H2H records."""
        winner, loser, surface = match.winner, match.loser, match.surface

        winner_delta, loser_delta = self._rating_deltas(match)

        # Surface ratings move by the full delta; overall ratings absorb only a
        # fraction ("bleed") so cross-surface strength is still reflected.
        self.players[winner].surface_elos[surface] += winner_delta
        self.players[loser].surface_elos[surface] += loser_delta
        self.players[winner].overall_elo += self.bleed * winner_delta
        self.players[loser].overall_elo += self.bleed * loser_delta

        self.players[winner].match_history[surface].append(("W", match.date))
        self.players[loser].match_history[surface].append(("L", match.date))

        self._record_head_to_head(winner, loser, surface)

    def _rating_deltas(self, match: Match) -> Tuple[float, float]:
        """Compute the Elo rating changes for the winner and loser of a match."""
        winner_elo = self.players[match.winner].surface_elos[match.surface]
        loser_elo = self.players[match.loser].surface_elos[match.surface]

        winner_expected = self.expected_score(winner_elo, loser_elo)
        loser_expected = 1 - winner_expected

        k_factor = self.k
        if self.max_date and (self.max_date - match.date).days <= RECENT_WINDOW_DAYS:
            k_factor *= RECENT_K_MULTIPLIER

        # Actual scores are 1 for the winner, 0 for the loser.
        return k_factor * (1 - winner_expected), k_factor * (0 - loser_expected)

    def _record_head_to_head(self, winner: str, loser: str, surface: str) -> None:
        """Update overall and per-surface head-to-head records for both players."""
        winner_stats = self.players[winner]
        loser_stats = self.players[loser]

        wins, losses = winner_stats.h2h_overall[loser]
        winner_stats.h2h_overall[loser] = (wins + 1, losses)
        wins, losses = loser_stats.h2h_overall[winner]
        loser_stats.h2h_overall[winner] = (wins, losses + 1)

        wins, losses = winner_stats.h2h_surface[surface][loser]
        winner_stats.h2h_surface[surface][loser] = (wins + 1, losses)
        wins, losses = loser_stats.h2h_surface[surface][winner]
        loser_stats.h2h_surface[surface][winner] = (wins, losses + 1)

    # --- Queries -------------------------------------------------------------------

    def get_rating(self, player: str, surface: Optional[str] = None) -> float:
        """Get a player's rating.

        Args:
            player: Player name.
            surface: Surface type; if None, the overall rating is returned.

        Returns:
            The player's rating, or ``DEFAULT_RATING`` for unknown players.
        """
        normalized_player = self.normalize_name(player)
        if normalized_player not in self.players:
            return DEFAULT_RATING

        if surface is None:
            return self.players[normalized_player].overall_elo
        normalized_surface = self.normalize_surface(surface)
        return self.players[normalized_player].surface_elos[normalized_surface]

    def head_to_head(
        self, player_a: str, player_b: str, surface: Optional[str] = None
    ) -> Tuple[int, int]:
        """Get the head-to-head record between two players.

        Args:
            player_a: First player name.
            player_b: Second player name.
            surface: Surface type; if None, the overall record is returned.

        Returns:
            Tuple of (wins for player_a, wins for player_b).
        """
        norm_a = self.normalize_name(player_a)
        norm_b = self.normalize_name(player_b)

        if norm_a not in self.players:
            return (0, 0)

        if surface is None:
            return self.players[norm_a].h2h_overall[norm_b]
        normalized_surface = self.normalize_surface(surface)
        return self.players[norm_a].h2h_surface[normalized_surface][norm_b]

    def last_n_record(self, player: str, surface: str, n: int = 10) -> Tuple[int, int]:
        """Get a player's record over their last ``n`` matches on a surface.

        Args:
            player: Player name.
            surface: Surface type.
            n: Number of most recent matches to consider.

        Returns:
            Tuple of (wins, losses).
        """
        normalized_player = self.normalize_name(player)
        normalized_surface = self.normalize_surface(surface)

        if normalized_player not in self.players:
            return (0, 0)

        history = self.players[normalized_player].match_history[normalized_surface]
        recent_matches = list(history)[-n:]

        wins = sum(1 for result, _ in recent_matches if result == "W")
        losses = len(recent_matches) - wins
        return (wins, losses)

    def match_win_prob(self, player_a: str, player_b: str, surface: str) -> float:
        """Calculate ``player_a``'s win probability against ``player_b``.

        Uses surface-specific ratings when both players have them, otherwise
        falls back to overall ratings.

        Args:
            player_a: First player name.
            player_b: Second player name.
            surface: Surface type.

        Returns:
            Win probability for player_a, between 0.0 and 1.0.
        """
        norm_a = self.normalize_name(player_a)
        norm_b = self.normalize_name(player_b)
        normalized_surface = self.normalize_surface(surface)

        if (
            norm_a in self.players
            and normalized_surface in self.players[norm_a].surface_elos
            and norm_b in self.players
            and normalized_surface in self.players[norm_b].surface_elos
        ):
            rating_a = self.players[norm_a].surface_elos[normalized_surface]
            rating_b = self.players[norm_b].surface_elos[normalized_surface]
        else:
            rating_a = self.get_rating(norm_a)
            rating_b = self.get_rating(norm_b)

        return self.expected_score(rating_a, rating_b)

    def export_player_snapshot(self, player: str, surface: str) -> Dict:
        """Export a compact snapshot of a player's ratings and recent record.

        Args:
            player: Player name.
            surface: Surface type.

        Returns:
            Dictionary with surface Elo, overall Elo, and last-10 record.
        """
        normalized_player = self.normalize_name(player)
        normalized_surface = self.normalize_surface(surface)

        surface_elo = self.get_rating(normalized_player, normalized_surface)
        overall_elo = self.get_rating(normalized_player)
        wins, losses = self.last_n_record(normalized_player, normalized_surface, 10)

        return {
            "elo_surface": surface_elo,
            "elo_overall": overall_elo,
            "last10_surface": f"{wins}-{losses}",
        }


# --- Demonstration (python elo.py) --------------------------------------------


def _demo_sample_players(model: EloModel, count: int = 3) -> List[str]:
    """Collect the first ``count`` unique player names from ingested matches."""
    sample_players: List[str] = []
    for match in model.matches[:100]:
        if match.winner not in sample_players:
            sample_players.append(match.winner)
        if match.loser not in sample_players:
            sample_players.append(match.loser)
        if len(sample_players) >= count:
            break
    return sample_players


def _demo_with_csv_data(model: EloModel, csv_files: List[Path]) -> None:
    """Load real CSV data and print ratings, H2H, and win probabilities."""
    print(f"Loading {len(csv_files)} CSV files from data directory...")
    model.ingest_csv_files([str(f) for f in csv_files])
    print(f"Processed {len(model.matches)} matches")

    sample_players = _demo_sample_players(model)
    if len(sample_players) < 2:
        return

    print("\nSample Player Analysis:")
    print("-" * 30)
    for i, player in enumerate(sample_players[:3]):
        print(f"\nPlayer {i + 1}: {player}")
        for surface in ["hard", "clay", "grass"]:
            surface_rating = model.get_rating(player, surface)
            overall_rating = model.get_rating(player)
            wins, losses = model.last_n_record(player, surface, 10)
            print(
                f"  {surface.capitalize()}: Elo={surface_rating:.1f}, "
                f"Overall={overall_rating:.1f}, Last 10: {wins}-{losses}"
            )
        snapshot = model.export_player_snapshot(player, "hard")
        print(f"  Snapshot (Hard): {snapshot}")

    p1, p2 = sample_players[0], sample_players[1]
    print(f"\nHead-to-Head: {p1} vs {p2}")

    h2h_overall = model.head_to_head(p1, p2)
    h2h_hard = model.head_to_head(p1, p2, "hard")
    print(f"  Overall H2H: {h2h_overall[0]}-{h2h_overall[1]}")
    print(f"  Hard court H2H: {h2h_hard[0]}-{h2h_hard[1]}")

    for surface in ["hard", "clay", "grass"]:
        prob = model.match_win_prob(p1, p2, surface)
        print(f"  {p1} win prob on {surface}: {prob:.3f}")


def _demo_with_sample_matches(model: EloModel) -> None:
    """Process a few hard-coded matches and print the resulting ratings."""
    print("\nCreating sample matches for demonstration...")
    sample_matches = [
        Match(datetime(2023, 1, 15), "hard", "Roger Federer", "Rafael Nadal", "6-4 6-2", 3, "F"),
        Match(datetime(2023, 2, 20), "clay", "Rafael Nadal", "Novak Djokovic", "7-5 6-3", 3, "SF"),
        Match(datetime(2023, 3, 10), "grass", "Novak Djokovic", "Roger Federer", "6-7 6-4 6-2", 3, "F"),
        Match(datetime(2023, 4, 5), "hard", "Rafael Nadal", "Roger Federer", "6-3 6-4", 3, "QF"),
    ]
    for match in sample_matches:
        model._process_match(match)

    print("Sample analysis:")
    for player in ["Roger Federer", "Rafael Nadal", "Novak Djokovic"]:
        print(f"\n{player}:")
        print(f"  Overall Elo: {model.get_rating(player):.1f}")
        print(f"  Hard court Elo: {model.get_rating(player, 'hard'):.1f}")
        print(f"  Clay court Elo: {model.get_rating(player, 'clay'):.1f}")

    prob = model.match_win_prob("Roger Federer", "Rafael Nadal", "hard")
    print(f"\nFederer win probability vs Nadal on hard: {prob:.3f}")


def _run_demo() -> None:
    """Demonstrate the Elo system using data/ CSVs or built-in sample matches."""
    print("Tennis Elo Rating System Demo")
    print("=" * 40)

    model = EloModel()
    data_dir = Path("data")
    if data_dir.exists():
        csv_files = list(data_dir.glob("*.csv"))
        if csv_files:
            _demo_with_csv_data(model, csv_files)
        else:
            print("No CSV files found in data directory")
    else:
        print("Data directory not found - creating sample demonstration")
        _demo_with_sample_matches(model)


if __name__ == "__main__":
    _run_demo()
