import random
from engine.engine import BaseAgent
from engine.config import MAP_ADJACENCY
from engine.agents import bfs_shortest_path

class SimpleRuleBasedAgent(BaseAgent):
    """
    A strategic non-LLM bot that follows a simple rule-set:
    1. Report bodies immediately.
    2. If crewmate, find nearest task and move toward it.
    3. If impostor, kill if alone, otherwise fake tasks.
    """
    def on_game_start(self, config):
        self.id = config["your_id"]
        self.role = config["your_role"]
        self.tasks = config.get("tasks", [])

    def on_task_phase(self, obs):
        avail = obs.get("available_actions", {})
        loc = obs["identity"]["your_location"]
        
        # 1. Always report if possible
        if avail.get("can_report"):
            return {"action": "report"}
            
        # 2. Handle roles
        if self.role == "crewmate":
            # Do task if in room
            tasks = obs.get("tasks", {}).get("your_tasks", [])
            for t in tasks:
                if t["location"] == loc and t["progress"] < t["required"]:
                    return {"action": "do_task", "target": t["id_to_use"]}
            
            # Otherwise move toward first incomplete task
            pending = [t for t in tasks if t["progress"] < t["required"]]
            if pending:
                path = bfs_shortest_path(loc, pending[0]["location"], MAP_ADJACENCY)
                if len(path) > 1:
                    return {"action": "move", "target": path[1]}
        
        else: # Impostor
            if avail.get("can_kill"):
                players = obs.get("room_observations", {}).get("players_present", [])
                if len(players) == 1: # Kill if alone
                    return {"action": "kill", "target": players[0]["id"]}
            
            if avail.get("can_sabotage"):
                return {"action": "sabotage", "target": "reactor"}
                
        # Random move if nothing else to do
        adj = obs.get("room_observations", {}).get("adjacent_rooms", [])
        if adj:
            return {"action": "move", "target": random.choice(adj)}
            
        return {"action": "wait"}

    def on_discussion(self, obs):
        return f"I am {self.id} and I was in {obs['identity']['your_location']}."

    def on_vote(self, obs):
        return "skip"

    def on_game_end(self, result):
        pass
