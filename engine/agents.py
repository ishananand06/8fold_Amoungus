import json
import re
import random
import os
import base64
import requests
import logging
from collections import deque
from google.auth.transport.requests import Request
from google.oauth2 import service_account

from .engine import BaseAgent, Role
from .config import MAP_ADJACENCY

# --- LLM Utilities ---

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
    try:
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
            adj = room.get("adjacent_rooms", [])
            parts.append(f"ADJACENT ROOMS (You can only move here): {', '.join(adj)}.")
            
        events = obs.get("events_last_round", [])
        if events:
            parts.append("Events last round: " + ". ".join(events) + ".")
            
        tasks = obs.get("tasks", {})
        if isinstance(tasks.get("your_tasks"), list):
            task_strs = [f"{t['name']} in {t['location']} ({t['progress']}/{t['required']}) [ID: {t['id_to_use']}]" for t in tasks["your_tasks"]]
            parts.append(f"Your tasks: {', '.join(task_strs)}.")
            
            # Room specific tasks
            loc_tasks = [t['id_to_use'] for t in tasks["your_tasks"] if t['location'] == loc and t['progress'] < t['required']]
            if loc_tasks:
                parts.append(f"AVAILABLE TASKS IN THIS ROOM: {', '.join(loc_tasks)}.")
            else:
                parts.append("No tasks available in this room. Move to another room to find tasks.")
        
        parts.append(f"Global task progress: {int(tasks.get('global_task_progress', 0.0) * 100)}%")
        
        sab = obs.get("sabotage", {}).get("active")
        if sab:
            parts.append(f"ALERT: {sab['type']} active! {sab.get('countdown', 'No')} rounds left. Fix at {list(sab.get('fix_required', {}).keys())}.")
            
        if "impostor_info" in obs and obs["impostor_info"]:
            ii = obs["impostor_info"]
            parts.append(f"Your teammate: {', '.join(ii.get('teammates', []))}. Kill cooldown: {ii.get('kill_cooldown', 0)}.")
            
        avail = obs.get("available_actions", {})
        actions = [k for k, v in avail.items() if v]
        if actions:
            parts.append(f"Available actions: {', '.join(actions)}.")
            
        prev = obs.get("previous_action_result")
        if prev:
            parts.append(f"Your last action ({prev['action']}) {'succeeded' if prev['success'] else 'failed: ' + str(prev.get('reason'))}.")
            
        return "\n".join(parts)
    except Exception as e:
        logging.error(f"Error formatting observation: {e}")
        return "Error reading observation. Check your logs."

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

# --- Vertex AI Wrapper ---

class VertexAIWrapper:
    def __init__(self):
        self.project = os.environ.get("GEMINI_VERTEX_PROJECT", "civic-project-488404")
        self.location = os.environ.get("GEMINI_VERTEX_LOCATION", "global")
        self.model_id = "gemini-3-flash-preview"
        self.creds = None
        self.token = None
        self.total_prompt_tokens = 0
        self.total_candidate_tokens = 0
        self.total_thought_tokens = 0
        
        b64_creds = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON_B64")
        if b64_creds:
            creds_json = json.loads(base64.b64decode(b64_creds))
            self.creds = service_account.Credentials.from_service_account_info(
                creds_json, 
                scopes=['https://www.googleapis.com/auth/cloud-platform']
            )
        else:
            raise ValueError("Missing GOOGLE_APPLICATION_CREDENTIALS_JSON_B64")

    def _refresh_token(self):
        if not self.token or self.creds.expired:
            self.creds.refresh(Request())
            self.token = self.creds.token

    def call(self, system_prompt: str, user_message: str, max_tokens: int = 500) -> str:
        self._refresh_token()
        
        url = f"https://aiplatform.googleapis.com/v1/projects/{self.project}/locations/{self.location}/publishers/google/models/{self.model_id}:streamGenerateContent"
        
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        
        data = {
            "systemInstruction": {
                "parts": [{"text": system_prompt}]
            },
            "contents": [{
                "role": "user",
                "parts": [{"text": user_message}]
            }],
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": 0.7
            }
        }
        
        try:
            response = requests.post(url, headers=headers, json=data, timeout=30)
            if response.status_code == 200:
                chunks = response.json()
                text_parts = []
                for chunk in chunks:
                    if "candidates" in chunk:
                        for cand in chunk["candidates"]:
                            if "content" in cand and "parts" in cand["content"]:
                                for part in cand["content"]["parts"]:
                                    if "text" in part:
                                        text_parts.append(part["text"])
                    
                    if "usageMetadata" in chunk:
                        usage = chunk["usageMetadata"]
                        self.total_prompt_tokens += usage.get("promptTokenCount", 0)
                        self.total_candidate_tokens += usage.get("candidatesTokenCount", 0)
                        self.total_thought_tokens += usage.get("thoughtsTokenCount", 0)
                
                return "".join(text_parts)
            else:
                logging.error(f"Vertex AI error: {response.status_code} - {response.text}")
                return ""
        except Exception as e:
            logging.error(f"Vertex AI call exception: {e}")
            return ""

    def get_token_summary(self) -> dict:
        return {
            "prompt_tokens": self.total_prompt_tokens,
            "candidate_tokens": self.total_candidate_tokens,
            "thought_tokens": self.total_thought_tokens,
            "total_tokens": self.total_prompt_tokens + self.total_candidate_tokens + self.total_thought_tokens
        }

# --- Specialized Agents ---

class PersonalityAgent(BaseAgent):
    def __init__(self, llm: VertexAIWrapper, personality: str):
        self.llm = llm
        self.personality = personality
        self.id = ""
        self.role = ""
        self.memory = []

    def on_game_start(self, config):
        self.id = config["your_id"]
        self.role = config["your_role"]
        self.game_config = config

    def _get_system_prompt(self):
        return f"""You are playing 'Among Us' as {self.id}, a {self.role}.
PERSONALITY: {self.personality}

RULES:
- Crewmates win by completing all tasks or ejecting all impostors.
- Impostors win by killing crewmates or critical sabotage.
- Movement takes 1 round.
- Action Model: resolve movement -> resolve kills -> resolve tasks -> resolve reports.

STRATEGY:
- If Crewmate: prioritize tasks. If you see a body, report it.
- If Impostor: you must be in the SAME room as someone to kill them. Predict their movement.
- DISCUSSION: Be logical. If there are 4 or 5 players left, SKIPPING is dangerous. Vote for the most suspicious person.
- GHOSTS: If you are dead, your ONLY goal is to move to your task locations and finish them.

RESPONSE FORMAT:
- During TASK phase: Respond with a JSON object like {{"action": "move", "target": "Admin"}} or {{"action": "do_task", "target": "task_id"}}.
- During DISCUSSION: Respond with plain text conversational message.
- During VOTING: Respond with player ID or "skip".
"""

    def on_task_phase(self, obs):
        prompt = self._get_system_prompt()
        obs_text = format_observation_as_text(obs)
        
        state_note = ""
        if "available_actions" not in obs:
            state_note = "\nNOTE: You are a GHOST (dead). You can still help your team by moving to task locations and doing tasks. You are invisible to living players."
        
        user_msg = f"CURRENT OBSERVATION:\n{obs_text}{state_note}\n\nWhat is your next action? Respond ONLY with JSON. \n- If doing a task, use the EXACT 'ID' provided.\n- If moving, pick a DIFFERENT adjacent room than your current one.\n- If Impostor and someone is alone with you, consider 'kill'."
        resp = self.llm.call(prompt, user_msg)
        return parse_llm_json(resp, {"action": "wait"})

    def on_discussion(self, obs):
        prompt = self._get_system_prompt()
        obs_text = format_observation_as_text(obs)
        # Add chat history context
        chat_hist = "\n".join([f"{m['speaker']}: {m['message']}" for m in obs.get("chat_history", [])])
        user_msg = f"MEETING CONTEXT: {obs.get('meeting_context')}\n\nCHAT HISTORY:\n{chat_hist}\n\nIt is your turn to speak. Be concise and stay in character."
        return self.llm.call(prompt, user_msg)

    def on_vote(self, obs):
        prompt = self._get_system_prompt()
        chat_hist = "\n".join([f"{m['speaker']}: {m['message']}" for m in obs.get("chat_history", [])])
        user_msg = f"CHAT HISTORY:\n{chat_hist}\n\nWho do you vote for? Respond with Player ID or 'skip'."
        resp = self.llm.call(prompt, user_msg)
        # Clean up response to just the ID
        return resp.strip().split()[-1].replace('"', '').replace("'", "")

    def on_game_end(self, result):
        pass

# --- Agent Personalities ---

AGENT_PERSONALITIES = [
    "The Analytical Detective: Logical, tracks everyone's movements, asks for locations, very suspicious of alibis that don't add up.",
    "The Quiet Worker: Focused on tasks, stays out of drama, only speaks when they have hard evidence, tends to follow others for safety.",
    "The Aggressive Accuser: Quick to point fingers, uses strong language, 'loud' in meetings, often focuses on the first person they see near a body.",
    "The Paranoic Survivor: Terrified of being alone, constantly checks who is around, reports even slight 'sus' behavior, very defensive.",
    "The Strategic Deceiver (if Impostor): Calculated, builds trust by helping with sabotages, creates complex alibis involving multiple rooms.",
    "The Friendly Team-Player: Highly cooperative, encourages others to stay together, shares their location frequently, trusts others easily.",
    "The Chaotic Wildcard: Unpredictable, might vote randomly, makes strange jokes in meetings, moves in unusual patterns."
]

# --- Default Bots (Keep for fallback) ---

class RandomBot(BaseAgent):
    def on_game_start(self, config):
        self.id = config["your_id"]
        self.role = config["your_role"]
    def on_task_phase(self, obs):
        adj = obs.get("room_observations", {}).get("adjacent_rooms", [])
        return {"action": "move", "target": random.choice(adj)} if adj else {"action": "wait"}
    def on_discussion(self, obs): return "I saw nothing."
    def on_vote(self, obs): return "skip"
    def on_game_end(self, result): pass

class RuleBasedBot(BaseAgent):
    def on_game_start(self, config):
        self.id = config["your_id"]
        self.role = config["your_role"]
    def on_task_phase(self, obs):
        avail = obs.get("available_actions", {})
        if avail.get("can_report"): return {"action": "report"}
        if self.role == "impostor" and avail.get("can_kill"):
            players = obs.get("room_observations", {}).get("players_present", [])
            if players: return {"action": "kill", "target": players[0]["id"]}
        adj = obs.get("room_observations", {}).get("adjacent_rooms", [])
        return {"action": "move", "target": random.choice(adj)} if adj else {"action": "wait"}
    def on_discussion(self, obs): return "I was doing tasks."
    def on_vote(self, obs): return "skip"
    def on_game_end(self, result): pass
