#!/usr/bin/env python3
"""AceCast — tennis match and tournament prediction CLI.

Builds statistical context (Elo ratings, head-to-head records, title
probabilities) from historical match CSVs, then asks an Anthropic model on
Amazon Bedrock to turn that context into a natural-language prediction.

Usage:
  python app.py match --playerA "Carlos Alcaraz" --playerB "Jannik Sinner" \
      --surface indoor_hard --csv data/atp_matches_2024.csv \
      --model-id anthropic.claude-3-sonnet-20240229-v1:0
  python app.py tournament --players "Carlos Alcaraz,Jannik Sinner,Daniil Medvedev,Alexander Zverev" \
      --surface indoor_hard --csv data/atp_matches_2024.csv \
      --model-id anthropic.claude-3-sonnet-20240229-v1:0 --simulate 1000
"""

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Dict, List, Optional

import boto3

from elo import ELO_SCALE, EloModel

SURFACE_CHOICES = ("hard", "indoor_hard", "clay", "grass")
DEFAULT_AWS_REGION = "us-east-1"
SYSTEM_PROMPT_PATH = Path("prompts/system.txt")

# Bedrock request parameters.
BEDROCK_MAX_TOKENS = 800
BEDROCK_TEMPERATURE = 0.3
ANTHROPIC_API_VERSION = "bedrock-2023-05-31"

# A first-round matchup counts as an upset risk when the favorite's win
# probability falls below this threshold; only the top few are reported.
UPSET_PROBABILITY_THRESHOLD = 0.65
MAX_UPSET_RISKS = 3

NOTES_PREVIEW_CHARS = 200


def load_notes(path: Optional[str]) -> Optional[str]:
    """Load optional free-text notes from a file, returning None on failure."""
    if not path:
        return None
    try:
        return Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        print(f"Warning: Could not load notes from {path}: {exc}", file=sys.stderr)
        return None


def build_match_context(model: EloModel, player_a: str, player_b: str, surface: str) -> Dict:
    """Build the JSON-serializable context for a single-match prediction."""
    snapshot_a = model.export_player_snapshot(player_a, surface)
    snapshot_b = model.export_player_snapshot(player_b, surface)

    win_prob_a = model.match_win_prob(player_a, player_b, surface)
    win_prob_b = 1 - win_prob_a

    h2h_overall = model.head_to_head(player_a, player_b)
    h2h_surface = model.head_to_head(player_a, player_b, surface)

    return {
        "mode": "match_insight",
        "surface": surface,
        "match": {
            "playerA": {"name": player_a, "snapshot": snapshot_a},
            "playerB": {"name": player_b, "snapshot": snapshot_b},
        },
        "win_prob_A": win_prob_a,
        "win_prob_B": win_prob_b,
        "h2h_overall": {"wins_A": h2h_overall[0], "wins_B": h2h_overall[1]},
        "h2h_surface": {"wins_A": h2h_surface[0], "wins_B": h2h_surface[1]},
    }


def simulate_tournament(
    players: List[str], model: EloModel, surface: str, iterations: int
) -> Dict[str, float]:
    """Estimate title probabilities via Monte Carlo single-elimination brackets.

    Args:
        players: Entrants in seeding order.
        model: Elo model used for per-match win probabilities.
        surface: Court surface for all simulated matches.
        iterations: Number of full bracket simulations to run.

    Returns:
        Mapping of player name to estimated title probability.
    """
    title_counts = {player: 0 for player in players}

    for _ in range(iterations):
        bracket = players.copy()

        while len(bracket) > 1:
            next_round = []
            # Pair top seed vs bottom seed (1 vs last, 2 vs second-last, ...).
            for i in range(len(bracket) // 2):
                p1 = bracket[i]
                p2 = bracket[-(i + 1)]

                prob = model.match_win_prob(p1, p2, surface)
                winner = p1 if random.random() < prob else p2
                next_round.append(winner)

            bracket = next_round

        if bracket:
            title_counts[bracket[0]] += 1

    return {player: count / iterations for player, count in title_counts.items()}


def _estimate_title_probs_from_elo(player_data: List[Dict]) -> None:
    """Set each player's title_prob from relative Elo strength (in place).

    A cheap heuristic used instead of simulation: strength is exponential in
    surface Elo, and each player's share of total strength is their
    probability.
    """
    total_strength = sum(2 ** (p["surface_elo"] / ELO_SCALE) for p in player_data)
    for player_info in player_data:
        strength = 2 ** (player_info["surface_elo"] / ELO_SCALE)
        player_info["title_prob"] = strength / total_strength


def _find_upset_risks(model: EloModel, player_data: List[Dict], surface: str) -> List[Dict]:
    """Find close matchups between adjacent seeds, ordered strongest first."""
    upset_risks = []
    sorted_players = sorted(player_data, key=lambda p: p["surface_elo"], reverse=True)

    for i in range(0, len(sorted_players) - 1, 2):
        favorite = sorted_players[i]
        underdog = sorted_players[i + 1]
        prob = model.match_win_prob(favorite["name"], underdog["name"], surface)

        if prob < UPSET_PROBABILITY_THRESHOLD:
            upset_risks.append(
                {
                    "favorite": favorite["name"],
                    "underdog": underdog["name"],
                    "favorite_prob": prob,
                    "upset_potential": 1 - prob,
                }
            )

    return upset_risks


def build_tournament_context(
    model: EloModel, players: List[str], surface: str, simulate: int
) -> Dict:
    """Build the JSON-serializable context for a tournament brief.

    Args:
        model: Elo model with ingested match data.
        players: Entrants in seeding order.
        surface: Court surface for the tournament.
        simulate: Monte Carlo iterations; 0 uses a quick Elo-based estimate.
    """
    player_data = [
        {
            "name": player,
            "surface_elo": model.get_rating(player, surface),
            "snapshot": model.export_player_snapshot(player, surface),
        }
        for player in players
    ]

    if simulate > 0:
        title_probs = simulate_tournament(players, model, surface, simulate)
        for player_info in player_data:
            player_info["title_prob"] = title_probs[player_info["name"]]
    else:
        _estimate_title_probs_from_elo(player_data)

    upset_risks = _find_upset_risks(model, player_data, surface)

    return {
        "mode": "tournament_brief",
        "surface": surface,
        "players": player_data,
        "top_upset_risks": upset_risks[:MAX_UPSET_RISKS],
    }


def format_user_message(question: str, context: Dict, notes: Optional[str] = None) -> str:
    """Assemble the user prompt from a question, context JSON, and notes."""
    message = (
        f"QUESTION:\n{question}\n\n"
        f"CONTEXT_JSON:\n{json.dumps(context, ensure_ascii=False, indent=2)}"
    )
    if notes:
        message += f"\n\nOPTIONAL_NOTES_FROM_RAG:\n{notes}"
    return message


def print_verbose_context(context: Dict, notes: Optional[str] = None) -> None:
    """Print the context (and a notes preview) that will be sent to the model."""
    print("=== CONTEXT_JSON ===")
    print(json.dumps(context, indent=2))
    if notes:
        print(f"\n=== NOTES (first {NOTES_PREVIEW_CHARS} chars) ===")
        preview = notes[:NOTES_PREVIEW_CHARS] + "..." if len(notes) > NOTES_PREVIEW_CHARS else notes
        print(preview)
    print("\n=== BEDROCK RESPONSE ===")


def call_bedrock(system: str, user: str, model_id: str, region: str) -> str:
    """Invoke an Anthropic model on Amazon Bedrock and return its text reply."""
    client = boto3.client("bedrock-runtime", region_name=region)

    messages = [
        {"role": "system", "content": [{"type": "text", "text": system}]},
        {"role": "user", "content": [{"type": "text", "text": user}]},
    ]

    body = {
        "messages": messages,
        "max_tokens": BEDROCK_MAX_TOKENS,
        "temperature": BEDROCK_TEMPERATURE,
        "anthropic_version": ANTHROPIC_API_VERSION,
    }

    response = client.invoke_model(modelId=model_id, body=json.dumps(body))
    result = json.loads(response["body"].read())
    return result["content"][0]["text"]


def run_match_command(args: argparse.Namespace, model: EloModel, system_prompt: str) -> None:
    """Handle the ``match`` subcommand: predict a single match."""
    context = build_match_context(model, args.playerA, args.playerB, args.surface)
    question = (
        f"Who is favored on {args.surface} between {args.playerA} and {args.playerB}, and why?"
    )

    notes = load_notes(args.notes)
    user_message = format_user_message(question, context, notes)

    if args.verbose:
        print_verbose_context(context, notes)

    print(call_bedrock(system_prompt, user_message, args.model_id, args.region))


def run_tournament_command(args: argparse.Namespace, model: EloModel, system_prompt: str) -> None:
    """Handle the ``tournament`` subcommand: brief for a tournament draw."""
    players = [p.strip() for p in args.players.split(",")]
    context = build_tournament_context(model, players, args.surface, args.simulate)
    question = f"Give me a quick {args.surface} brief: favorites, dark horses, and early upset risks."

    user_message = format_user_message(question, context)

    if args.verbose:
        print_verbose_context(context)

    print(call_bedrock(system_prompt, user_message, args.model_id, args.region))


def _add_common_arguments(parser: argparse.ArgumentParser) -> None:
    """Add arguments shared by every subcommand."""
    parser.add_argument("--surface", required=True, choices=SURFACE_CHOICES, help="Court surface")
    parser.add_argument("--csv", required=True, nargs="+", help="CSV file paths")
    parser.add_argument("--model-id", required=True, help="Bedrock model ID")
    parser.add_argument("--region", default=DEFAULT_AWS_REGION, help="AWS region")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser with match and tournament subcommands."""
    parser = argparse.ArgumentParser(description="AceCast — Tennis Tournament Predictor")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    match_parser = subparsers.add_parser("match", help="Predict a single match")
    match_parser.add_argument("--playerA", required=True, help="First player name")
    match_parser.add_argument("--playerB", required=True, help="Second player name")
    match_parser.add_argument("--notes", help="Path to notes file")
    _add_common_arguments(match_parser)

    tournament_parser = subparsers.add_parser("tournament", help="Brief for tournament draw")
    tournament_parser.add_argument("--players", required=True, help="Comma-separated player names")
    tournament_parser.add_argument(
        "--simulate", type=int, default=0, help="Tournament analysis iterations (0 for quick estimate)"
    )
    _add_common_arguments(tournament_parser)

    return parser


def load_system_prompt() -> str:
    """Read the system prompt file, exiting with an error if it is missing."""
    if not SYSTEM_PROMPT_PATH.exists():
        print(f"Error: {SYSTEM_PROMPT_PATH} not found", file=sys.stderr)
        sys.exit(1)
    return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")


def main() -> None:
    """Parse arguments, build prediction context, and print the model's reply."""
    parser = build_arg_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    try:
        system_prompt = load_system_prompt()

        model = EloModel()
        model.ingest_csv_files(args.csv)

        if args.command == "match":
            run_match_command(args, model, system_prompt)
        elif args.command == "tournament":
            run_tournament_command(args, model, system_prompt)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
