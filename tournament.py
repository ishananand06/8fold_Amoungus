import json
from pathlib import Path
from math import ceil

from config import GameConfig
from engine import GameEngine
from agents import RuleBasedBot

def compute_elo_delta(own_rating: float, opp_avg_rating: float, won: bool, k: int = 16) -> float:
    expected = 1.0 / (1.0 + 10 ** ((opp_avg_rating - own_rating) / 400.0))
    actual = 1.0 if won else 0.0
    return k * (actual - expected)

def _empty_stats():
    return {
        "games": 0, "wins": 0, "losses": 0,
        "games_as_impostor": 0, "games_as_crewmate": 0,
        "kills": 0, "correct_votes": 0, "times_ejected": 0,
        "tasks_completed": 0, "survival_count": 0
    }

class TournamentRunner:
    def __init__(self, agent_classes: dict[str, type], config: GameConfig, games_per_team: int = 20, log_dir: str = "game_logs"):
        self.agent_classes = agent_classes
        self.config = config
        self.games_per_team = games_per_team
        self.log_dir = Path(log_dir)
        self.elo = {team: 1200.0 for team in agent_classes}
        self.stats = {team: _empty_stats() for team in agent_classes}
        self.game_results = []

    def generate_matchups(self) -> list[list[str]]:
        teams = list(self.agent_classes.keys())
        if not teams: return []
        num_games = max(self.games_per_team, ceil(self.games_per_team * len(teams) / self.config.num_players))
        lobbies = []
        for i in range(num_games):
            lobby = []
            for j in range(self.config.num_players):
                idx = (i * self.config.num_players + j) % len(teams)
                lobby.append(teams[idx])
            lobbies.append(lobby)
        return lobbies

    def run_tournament(self) -> list[dict]:
        self.log_dir.mkdir(parents=True, exist_ok=True)
        matchups = self.generate_matchups()
        
        for game_idx, lobby in enumerate(matchups):
            agents = {}
            team_mapping = {}
            for i, team_name in enumerate(lobby):
                pid = f"player_{i}"
                if team_name == "__RuleBasedBot__":
                    agents[pid] = RuleBasedBot()
                else:
                    agents[pid] = self.agent_classes[team_name]()
                team_mapping[pid] = team_name
                
            engine = GameEngine(self.config, agents)
            result = engine.run()
            result["team_mapping"] = team_mapping
            
            self._update_elo(result, team_mapping)
            self._update_stats(result, team_mapping)
            
            log_path = self.log_dir / f"game_{game_idx:04d}.json"
            with open(log_path, "w") as f:
                json.dump(result, f, indent=2)
                
            self.game_results.append(result)
            print(f"Game {game_idx+1}/{len(matchups)}: {result['winner']} wins")
            
        return self.get_standings()

    def _update_elo(self, result: dict, team_mapping: dict) -> None:
        winner = result["winner"]
        for pid, team in team_mapping.items():
            if team == "__RuleBasedBot__": continue
            role = result["all_roles"][pid]
            won = (role == "crewmate" and winner == "crewmates") or (role == "impostor" and winner == "impostors")
            
            opponents = [team_mapping[oid] for oid in team_mapping if oid != pid and team_mapping[oid] != "__RuleBasedBot__"]
            if opponents:
                opp_avg = sum(self.elo[t] for t in opponents) / len(opponents)
            else:
                opp_avg = 1200.0
                
            k = 32 if self.stats[team]["games"] < 10 else 16
            self.elo[team] += compute_elo_delta(self.elo[team], opp_avg, won, k)

    def _update_stats(self, result: dict, team_mapping: dict) -> None:
        winner = result["winner"]
        for pid, team in team_mapping.items():
            if team not in self.stats: continue
            role = result["all_roles"][pid]
            won = (role == "crewmate" and winner == "crewmates") or (role == "impostor" and winner == "impostors")
            st = self.stats[team]
            st["games"] += 1
            if won: st["wins"] += 1
            else: st["losses"] += 1
            
            if role == "impostor": st["games_as_impostor"] += 1
            else: st["games_as_crewmate"] += 1
            
            # Additional stats could be parsed from game_log, 
            # for now we'll just keep the structure ready

    def get_standings(self) -> list[dict]:
        sorted_teams = sorted(self.elo.keys(), key=lambda t: self.elo[t], reverse=True)
        standings = []
        for rank, team in enumerate(sorted_teams):
            st = self.stats[team]
            win_rate = st["wins"] / st["games"] if st["games"] > 0 else 0.0
            standings.append({
                "rank": rank + 1,
                "team": team,
                "elo": round(self.elo[team], 1),
                "win_rate": round(win_rate, 3),
                "games": st["games"],
                "as_impostor": st["games_as_impostor"],
                "as_crewmate": st["games_as_crewmate"]
            })
        return standings
