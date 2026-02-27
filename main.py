import argparse
import json
import importlib.util
from pathlib import Path

from engine.config import GameConfig
from engine.engine import GameEngine, BaseAgent
from engine.tournament import TournamentRunner
from engine.agents import RandomBot, RuleBasedBot

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
    parser = argparse.ArgumentParser(description="Among Us LLM Simulation - Participant Kit")
    subparsers = parser.add_subparsers(dest="command")

    # Play command
    play_parser = subparsers.add_parser("play", help="Run a single game local simulation")
    play_parser.add_argument("--agents", nargs="+", default=["random", "random", "rulebased", "rulebased", "rulebased", "rulebased", "rulebased"], help="List of agent paths or names ('random', 'rulebased')")
    play_parser.add_argument("--config", type=str, help="Path to JSON config override")
    play_parser.add_argument("--output", type=str, default="game_log.json", help="Output file for game log")
    play_parser.add_argument("--verbose", action="store_true", help="Print round details to console")

    # Tournament command
    tourney_parser = subparsers.add_parser("tournament", help="Run a multi-game tournament")
    tourney_parser.add_argument("--agents-dir", type=str, required=True, help="Directory containing agent .py files")
    tourney_parser.add_argument("--games", type=int, default=1, help="Games per team")
    tourney_parser.add_argument("--config", type=str, help="Path to JSON config override")
    tourney_parser.add_argument("--output-dir", type=str, default="match_history", help="Directory for logs and standings")

    # Visualizer command
    viz_parser = subparsers.add_parser("visualize", help="Launch the basic tkinter visualizer")
    viz_parser.add_argument("logfile", type=str, help="Path to the JSON game log")

    # Theater command
    theater_parser = subparsers.add_parser("theater", help="Launch the high-end Pygame replay theater")
    theater_parser.add_argument("logfile", type=str, help="Path to the JSON game log")

    args = parser.parse_args()

    if args.command == "visualize":
        from engine.visualizer import AmongUsVisualizer
        import tkinter as tk
        root = tk.Tk()
        app = AmongUsVisualizer(root)
        app._process_data(args.logfile)
        root.mainloop()
        return

    if args.command == "theater":
        from engine.replay_theater import ReplayTheater
        theater = ReplayTheater(args.logfile)
        theater.run_theater()
        return

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
        # Ensure num_impostors is valid for the selected number of players
        if config.num_impostors >= config.num_players / 2:
            config.num_impostors = max(1, int((config.num_players - 1) // 2))
            
        engine = GameEngine(config, agent_instances)
        result = engine.run(verbose=args.verbose)
        print(f"Game Over! Winner: {result['winner']} (Cause: {result['cause']})")
        
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
        
        print("\n=== TOURNAMENT STANDINGS ===")
        for s in standings:
            print(f"{s['rank']}. {s['team']} - Elo: {s['elo']} (Win Rate: {s['win_rate']:.1%})")

if __name__ == "__main__":
    main()
