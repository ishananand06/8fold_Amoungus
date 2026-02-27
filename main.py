import argparse
import json
import importlib.util
from pathlib import Path

from config import GameConfig
from engine import GameEngine, BaseAgent
from tournament import TournamentRunner
from agents import RandomBot, RuleBasedBot

def load_agent_class(path: str) -> type:
    if path == "random": return RandomBot
    if path == "rulebased": return RuleBasedBot
    
    spec = importlib.util.spec_from_file_location("agent", path)
    if not spec or not spec.loader:
        print(f"Warning: Failed to load {path}, falling back to RuleBasedBot")
        return RuleBasedBot
        
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if isinstance(attr, type) and issubclass(attr, BaseAgent) and attr is not BaseAgent:
                return attr
    except Exception as e:
        print(f"Warning: Exception {e} loading {path}, falling back to RuleBasedBot")
        
    print(f"Warning: No BaseAgent subclass found in {path}, falling back to RuleBasedBot")
    return RuleBasedBot

def main():
    parser = argparse.ArgumentParser(description="Among Us LLM Simulation")
    subparsers = parser.add_subparsers(dest="command")

    play_parser = subparsers.add_parser("play", help="Run a single game")
    play_parser.add_argument("--agents", nargs="+", default=["random", "random", "rulebased", "rulebased", "rulebased", "rulebased", "rulebased"], help="List of agent paths or names ('random', 'rulebased')")
    play_parser.add_argument("--config", type=str, help="Path to JSON config override")
    play_parser.add_argument("--output", type=str, default="game_log.json", help="Output file for game log")
    play_parser.add_argument("--verbose", action="store_true", help="Print round details")

    tourney_parser = subparsers.add_parser("tournament", help="Run a multi-game tournament")
    tourney_parser.add_argument("--agents-dir", type=str, required=True, help="Directory containing agent .py files")
    tourney_parser.add_argument("--games", type=int, default=20, help="Games per team")
    tourney_parser.add_argument("--config", type=str, help="Path to JSON config override")
    tourney_parser.add_argument("--output-dir", type=str, default="game_logs", help="Directory for logs and standings")

    args = parser.parse_args()

    config = GameConfig()
    if args.config:
        with open(args.config, "r") as f:
            overrides = json.load(f)
            for k, v in overrides.items():
                if hasattr(config, k):
                    setattr(config, k, v)

    if args.command == "play":
        agent_instances = {}
        for i, p in enumerate(args.agents):
            agent_class = load_agent_class(p)
            agent_instances[f"player_{i}"] = agent_class()
            
        config.num_players = len(agent_instances)
        if config.num_impostors >= config.num_players / 2:
            config.num_impostors = max(1, int(config.num_players // 2) - 1)
            
        engine = GameEngine(config, agent_instances)
        result = engine.run()
        print(f"Game Over! Winner: {result['winner']} (Cause: {result['cause']})")
        print(f"Final Round: {result['final_round']}")
        
        with open(args.output, "w") as f:
            json.dump(result, f, indent=2)
            
        print(f"Game log saved to {args.output}")

    elif args.command == "tournament":
        agent_classes = {}
        agents_dir = Path(args.agents_dir)
        if agents_dir.exists() and agents_dir.is_dir():
            for p in agents_dir.glob("*.py"):
                team_name = p.stem
                agent_classes[team_name] = load_agent_class(str(p))
        else:
            print(f"Error: Directory {args.agents_dir} not found.")
            return

        runner = TournamentRunner(agent_classes, config, games_per_team=args.games, log_dir=args.output_dir)
        standings = runner.run_tournament()
        
        print("\\n=== TOURNAMENT STANDINGS ===")
        for s in standings:
            print(f"{s['rank']}. {s['team']} - Elo: {s['elo']} (Win Rate: {s['win_rate']:.1%})")
            
        with open(Path(args.output_dir) / "standings.json", "w") as f:
            json.dump(standings, f, indent=2)

if __name__ == "__main__":
    main()
