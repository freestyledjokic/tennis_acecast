#!/usr/bin/env python3
"""
AceCast — Tennis Tournament Predictor

CLI tool for tennis match and tournament predictions using Elo ratings and Amazon Bedrock.

Usage:
  python app.py match --playerA "Carlos Alcaraz" --playerB "Jannik Sinner" --surface indoor_hard --csv data/atp_matches_2024.csv --model-id anthropic.claude-3-sonnet-20240229-v1:0
  python app.py tournament --players "Carlos Alcaraz,Jannik Sinner,Daniil Medvedev,Alexander Zverev" --surface indoor_hard --csv data/atp_matches_2024.csv --model-id anthropic.claude-3-sonnet-20240229-v1:0 --simulate 1000
"""

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import boto3

from elo import EloModel


def load_notes(path: Optional[str]) -> Optional[str]:
    """Load notes from file if provided."""
    if not path:
        return None
    try:
        return Path(path).read_text(encoding='utf-8')
    except Exception as e:
        print(f"Warning: Could not load notes from {path}: {e}")
        return None


def build_match_context(model: EloModel, player_a: str, player_b: str, surface: str) -> Dict:
    """Build context for match prediction."""
    # Get snapshots
    snapshot_a = model.export_player_snapshot(player_a, surface)
    snapshot_b = model.export_player_snapshot(player_b, surface)
    
    # Get win probabilities
    win_prob_a = model.match_win_prob(player_a, player_b, surface)
    win_prob_b = 1 - win_prob_a
    
    # Get head-to-head
    h2h_overall = model.head_to_head(player_a, player_b)
    h2h_surface = model.head_to_head(player_a, player_b, surface)
    
    return {
        "mode": "match_insight",
        "surface": surface,
        "match": {
            "playerA": {
                "name": player_a,
                "snapshot": snapshot_a
            },
            "playerB": {
                "name": player_b,
                "snapshot": snapshot_b
            }
        },
        "win_prob_A": win_prob_a,
        "win_prob_B": win_prob_b,
        "h2h_overall": {"wins_A": h2h_overall[0], "wins_B": h2h_overall[1]},
        "h2h_surface": {"wins_A": h2h_surface[0], "wins_B": h2h_surface[1]}
    }


def simulate_tournament(players: List[str], model: EloModel, surface: str, iterations: int) -> Dict[str, float]:
    """Run Monte Carlo simulation for tournament."""
    title_counts = {player: 0 for player in players}
    
    for _ in range(iterations):
        # Single elimination bracket
        bracket = players.copy()
        
        while len(bracket) > 1:
            next_round = []
            # Pair players (1 vs last, 2 vs second-last, etc.)
            for i in range(len(bracket) // 2):
                p1 = bracket[i]
                p2 = bracket[-(i+1)]
                
                # Get win probability
                prob = model.match_win_prob(p1, p2, surface)
                winner = p1 if random.random() < prob else p2
                next_round.append(winner)
            
            bracket = next_round
        
        # Winner gets title
        if bracket:
            title_counts[bracket[0]] += 1
    
    # Convert to probabilities
    return {player: count / iterations for player, count in title_counts.items()}


def build_tournament_context(model: EloModel, players: List[str], surface: str, simulate: int) -> Dict:
    """Build context for tournament prediction."""
    player_data = []
    
    for player in players:
        snapshot = model.export_player_snapshot(player, surface)
        surface_elo = model.get_rating(player, surface)
        
        player_data.append({
            "name": player,
            "surface_elo": surface_elo,
            "snapshot": snapshot
        })
    
    # Calculate title probabilities
    if simulate > 0:
        title_probs = simulate_tournament(players, model, surface, simulate)
        for i, player_info in enumerate(player_data):
            player_info["title_prob"] = title_probs[players[i]]
    else:
        # Quick approximation based on Elo
        total_strength = sum(2 ** (p["surface_elo"] / 400) for p in player_data)
        for player_info in player_data:
            strength = 2 ** (player_info["surface_elo"] / 400)
            player_info["title_prob"] = strength / total_strength
    
    # Find upset risks (early round matchups where favorite has < 65% chance)
    upset_risks = []
    sorted_players = sorted(player_data, key=lambda x: x["surface_elo"], reverse=True)
    
    for i in range(0, len(sorted_players) - 1, 2):
        if i + 1 < len(sorted_players):
            favorite = sorted_players[i]
            underdog = sorted_players[i + 1]
            prob = model.match_win_prob(favorite["name"], underdog["name"], surface)
            
            if prob < 0.65:
                upset_risks.append({
                    "favorite": favorite["name"],
                    "underdog": underdog["name"],
                    "favorite_prob": prob,
                    "upset_potential": 1 - prob
                })
    
    return {
        "mode": "tournament_brief",
        "surface": surface,
        "players": player_data,
        "top_upset_risks": upset_risks[:3]  # Top 3 upset risks
    }


def call_bedrock(system: str, user: str, model_id: str, region: str) -> str:
    """Call Amazon Bedrock with system and user messages."""
    client = boto3.client("bedrock-runtime", region_name=region)
    
    messages = [
        {"role": "system", "content": [{"type": "text", "text": system}]},
        {"role": "user", "content": [{"type": "text", "text": user}]}
    ]
    
    body = {
        "messages": messages,
        "max_tokens": 800,
        "temperature": 0.3,
        "anthropic_version": "bedrock-2023-05-31"
    }
    
    response = client.invoke_model(
        modelId=model_id,
        body=json.dumps(body)
    )
    
    result = json.loads(response['body'].read())
    return result['content'][0]['text']


def main():
    parser = argparse.ArgumentParser(description="AceCast — Tennis Tournament Predictor")
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Match subcommand
    match_parser = subparsers.add_parser('match', help='Predict a single match')
    match_parser.add_argument('--playerA', required=True, help='First player name')
    match_parser.add_argument('--playerB', required=True, help='Second player name')
    match_parser.add_argument('--surface', required=True, choices=['hard', 'indoor_hard', 'clay', 'grass'], help='Court surface')
    match_parser.add_argument('--notes', help='Path to notes file')
    match_parser.add_argument('--csv', required=True, nargs='+', help='CSV file paths')
    match_parser.add_argument('--model-id', required=True, help='Bedrock model ID')
    match_parser.add_argument('--region', default='us-east-1', help='AWS region')
    match_parser.add_argument('--verbose', action='store_true', help='Verbose output')
    
    # Tournament subcommand
    tournament_parser = subparsers.add_parser('tournament', help='Brief for tournament draw')
    tournament_parser.add_argument('--players', required=True, help='Comma-separated player names')
    tournament_parser.add_argument('--surface', required=True, choices=['hard', 'indoor_hard', 'clay', 'grass'], help='Court surface')
    tournament_parser.add_argument('--csv', required=True, nargs='+', help='CSV file paths')
    tournament_parser.add_argument('--model-id', required=True, help='Bedrock model ID')
    tournament_parser.add_argument('--region', default='us-east-1', help='AWS region')
    tournament_parser.add_argument('--simulate', type=int, default=0, help='Monte Carlo iterations (0 for quick estimate)')
    tournament_parser.add_argument('--verbose', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        # Load system prompt
        system_prompt_path = Path("prompts/system.txt")
        if not system_prompt_path.exists():
            print("Error: prompts/system.txt not found")
            sys.exit(1)
        
        system_prompt = system_prompt_path.read_text(encoding='utf-8')
        
        # Initialize Elo model
        model = EloModel()
        model.ingest_csv_files(args.csv)
        
        if args.command == 'match':
            # Build match context
            context = build_match_context(model, args.playerA, args.playerB, args.surface)
            
            # Build user message
            question = f"Who is favored on {args.surface} between {args.playerA} and {args.playerB}, and why?"
            
            user_message = f"""QUESTION:
{question}

CONTEXT_JSON:
{json.dumps(context, ensure_ascii=False, indent=2)}"""
            
            # Add notes if provided
            notes = load_notes(args.notes)
            if notes:
                user_message += f"\n\nOPTIONAL_NOTES_FROM_RAG:\n{notes}"
            
            if args.verbose:
                print("=== CONTEXT_JSON ===")
                print(json.dumps(context, indent=2))
                if notes:
                    print("\n=== NOTES (first 200 chars) ===")
                    print(notes[:200] + "..." if len(notes) > 200 else notes)
                print("\n=== BEDROCK RESPONSE ===")
            
            # Call Bedrock
            response = call_bedrock(system_prompt, user_message, args.model_id, args.region)
            print(response)
            
        elif args.command == 'tournament':
            # Parse players
            players = [p.strip() for p in args.players.split(',')]
            
            # Build tournament context
            context = build_tournament_context(model, players, args.surface, args.simulate)
            
            # Build user message
            question = f"Give me a quick {args.surface} brief: favorites, dark horses, and early upset risks."
            
            user_message = f"""QUESTION:
{question}

CONTEXT_JSON:
{json.dumps(context, ensure_ascii=False, indent=2)}"""
            
            if args.verbose:
                print("=== CONTEXT_JSON ===")
                print(json.dumps(context, indent=2))
                print("\n=== BEDROCK RESPONSE ===")
            
            # Call Bedrock
            response = call_bedrock(system_prompt, user_message, args.model_id, args.region)
            print(response)
            
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()