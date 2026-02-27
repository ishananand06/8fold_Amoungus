import json
import re
import random
from collections import deque

from engine import BaseAgent
from config import MAP_ADJACENCY

def parse_llm_json(text: str, fallback: dict | None = None) -> dict:
    if text is None: return fallback or {}
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    match = re.search(r"\{[^{}]*\}", text)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    return fallback or {}

def format_observation_as_text(obs: dict) -> str:
    md = obs.get("game_metadata", {})
    r_num = md.get("round_number", "?")
    
    identity = obs.get("identity", {})
    uid = identity.get("your_id", "?")
    role = identity.get("your_role", "?")
    loc = identity.get("your_location", "?")
    
    parts = [f"Round {r_num}. You are {uid} ({role}) in {loc}."]
    
    if "room_observations" in obs:
        room = obs["room_observations"]
        players = [f"{p['id']} ({p['last_action']})" for p in room.get("players_present", [])]
        parts.append(f"Players here: {', '.join(players) if players else 'None'}.")
        parts.append(f"Bodies: {', '.join(room.get('bodies_present', [])) or 'None'}.")
        
    events = obs.get("events_last_round", [])
    if events:
        parts.append("Last round: " + ". ".join(events) + ".")
        
    tasks = obs.get("tasks", {})
    if isinstance(tasks.get("your_tasks"), list):
        task_strs = [f"{t['name']} in {t['location']} ({t['progress']}/{t['required']})" for t in tasks["your_tasks"]]
        parts.append(f"Your tasks: {', '.join(task_strs)}.")
    
    parts.append(f"Global task progress: {int(tasks.get('global_task_progress', 0.0) * 100)}%")
    
    sab = obs.get("sabotage", {}).get("active")
    if sab:
        parts.append(f"ALERT: {sab['type']} active! {sab.get('countdown', 'No')} rounds. Fix at {list(sab.get('fix_required', {}).keys())}.")
        
    if "impostor_info" in obs and obs["impostor_info"]:
        ii = obs["impostor_info"]
        parts.append(f"Your teammates: {', '.join(ii.get('teammates', []))}. Kill cooldown: {ii.get('kill_cooldown', 0)}.")
        
    avail = obs.get("available_actions", {})
    actions = [k for k, v in avail.items() if v]
    if actions:
        parts.append(f"You can: {', '.join(actions)}.")
        
    prev = obs.get("previous_action_result")
    if prev:
        parts.append(f"Your last action ({prev['action']}) {'succeeded' if prev['success'] else 'failed: ' + str(prev.get('reason'))}.")
        
    return "\\n".join(parts)

def bfs_shortest_path(start: str, end: str, adjacency: dict) -> list[str]:
    if start == end: return [start]
    queue = deque([[start]])
    visited = {start}
    while queue:
        path = queue.popleft()
        node = path[-1]
        for neighbor in adjacency.get(node, []):
            if neighbor == end:
                return path + [neighbor]
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(path + [neighbor])
    return []

class RandomBot(BaseAgent):
    def on_game_start(self, config):
        self.id = config["your_id"]
        self.role = config["your_role"]
        
    def on_task_phase(self, obs):
        avail = obs.get("available_actions", {})
        if avail.get("can_report"):
            return {"action": "report"}
            
        tasks = obs.get("tasks", {}).get("your_tasks", [])
        if self.role == "crewmate" and isinstance(tasks, list):
            for t in tasks:
                if t["location"] == obs["identity"]["your_location"] and t["progress"] < t["required"]:
                    if random.random() < 0.7:
                        return {"action": "do_task", "target": t["task_id"]}
                        
        if self.role == "impostor" and avail.get("can_kill"):
            room = obs.get("room_observations", {})
            players = room.get("players_present", [])
            if players and random.random() < 0.3:
                return {"action": "kill", "target": random.choice(players)["id"]}
                
        room = obs.get("room_observations", {})
        adj = room.get("adjacent_rooms", [])
        if adj and random.random() < 0.8:
            return {"action": "move", "target": random.choice(adj)}
            
        return {"action": "wait"}
        
    def on_discussion(self, obs):
        loc = obs["identity"]["your_location"]
        msgs = [
            "I was doing tasks.", "That's suspicious.",
            "I think we should skip.", "I saw nothing.",
            f"I was in {loc}.", "Let's not vote randomly."
        ]
        return random.choice(msgs)
        
    def on_vote(self, obs):
        if random.random() < 0.4: return "skip"
        alive = [p for p in obs["players"]["alive"] if p != self.id]
        if alive: return random.choice(alive)
        return "skip"
        
    def on_game_end(self, result):
        pass

class RuleBasedBot(BaseAgent):
    def on_game_start(self, config):
        self.id = config["your_id"]
        self.role = config["your_role"]
        self.tasks = config.get("tasks", [])
        self.teammates = config.get("impostor_teammates", []) or []
        self.suspicion = {p: 0.0 for p in config.get("players", []) if p != self.id}
        self.task_route = self._plan_route("Cafeteria")
        
    def _plan_route(self, current: str):
        pending = [t["location"] for t in self.tasks if t.get("progress", 0) < t.get("required", 1)]
        if not pending: return []
        return pending

    def on_task_phase(self, obs):
        avail = obs.get("available_actions", {})
        loc = obs["identity"]["your_location"]
        
        if avail.get("can_report"):
            return {"action": "report"}
            
        sab = obs.get("sabotage", {}).get("active")
        if sab and sab.get("type") in ("reactor", "o2"):
            targets = list(sab.get("fix_required", {}).keys())
            if targets:
                path = bfs_shortest_path(loc, targets[0], MAP_ADJACENCY)
                if len(path) > 1:
                    return {"action": "move", "target": path[1]}
                else:
                    return {"action": "fix_sabotage"}

        if self.role == "crewmate":
            tasks = obs.get("tasks", {}).get("your_tasks", [])
            for t in tasks:
                if t["location"] == loc and t["progress"] < t["required"]:
                    return {"action": "do_task", "target": t["task_id"]}
            self.task_route = self._plan_route(loc)
            if self.task_route:
                path = bfs_shortest_path(loc, self.task_route[0], MAP_ADJACENCY)
                if len(path) > 1:
                    return {"action": "move", "target": path[1]}
        
        if self.role == "impostor":
            room = obs.get("room_observations", {})
            players = room.get("players_present", [])
            crew = [p for p in players if p["id"] not in self.teammates]
            if len(crew) == 1 and len(players) == 1 and avail.get("can_kill"):
                return {"action": "kill", "target": crew[0]["id"]}
            if players:
                return {"action": "fake_task"}
            if avail.get("can_sabotage"):
                return {"action": "sabotage", "target": "reactor"}
                
        adj = obs.get("room_observations", {}).get("adjacent_rooms", [])
        if adj: return {"action": "move", "target": random.choice(adj)}
        return {"action": "wait"}

    def on_discussion(self, obs):
        loc = obs["identity"]["your_location"]
        if self.role == "crewmate":
            return f"I was in {loc}."
        return f"I was in {loc} doing my fake task."

    def on_vote(self, obs):
        alive = [p for p in obs.get("players", {}).get("alive", []) if p != self.id]
        if self.role == "crewmate":
            return random.choice(alive) if alive else "skip"
        else:
            crew = [p for p in alive if p not in self.teammates]
            return random.choice(crew) if crew else "skip"
            
    def on_game_end(self, result): pass

class LLMAgentWrapper(BaseAgent):
    def __init__(self, api_call_fn):
        self.api_call_fn = api_call_fn
        self.sys_prompt = ""
        
    def on_game_start(self, config):
        self.sys_prompt = f"You are {config['your_role']} in Among Us."
        
    def on_task_phase(self, obs):
        msg = format_observation_as_text(obs)
        resp = self.api_call_fn(self.sys_prompt, msg + "\\nReturn JSON action.")
        return parse_llm_json(resp, {"action": "wait"})
        
    def on_discussion(self, obs):
        return "I am an LLM!"
        
    def on_vote(self, obs):
        return "skip"
        
    def on_game_end(self, result): pass
