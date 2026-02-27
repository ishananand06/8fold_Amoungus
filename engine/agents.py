import json
import re
import random
import os
import requests
import logging
from collections import deque

from .engine import BaseAgent, Role
from .agents import parse_llm_json, format_observation_as_text

# --- OpenRouter Wrapper ---

class OpenRouterWrapper:
    """
    A lightweight wrapper to handle OpenRouter API calls.
    Requires OPENROUTER_API_KEY environment variable.
    """
    def __init__(self, model_name="meta-llama/llama-3-8b-instruct:free"):
        self.api_key = os.environ.get("OPENROUTER_API_KEY")
        self.model_name = model_name
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        
        if not self.api_key:
            raise ValueError("Environment variable OPENROUTER_API_KEY not found.")

    def call(self, system_prompt: str, user_message: str, max_tokens: int = 500) -> str:
        url = "https://openrouter.ai/api/v1/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/aries-society/among-us-sim", # Recommended
            "X-Title": "ARIES Among Us Simulation"
        }
        
        data = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            "max_tokens": max_tokens,
            "temperature": 0.7
        }
        
        try:
            response = requests.post(url, headers=headers, json=data, timeout=30)
            if response.status_code == 200:
                res_json = response.json()
                
                # Track usage
                usage = res_json.get("usage", {})
                self.total_prompt_tokens += usage.get("prompt_tokens", 0)
                self.total_completion_tokens += usage.get("completion_tokens", 0)
                
                return res_json.get("choices", [{}])[0].get("message", {}).get("content", "")
            else:
                logging.error(f"OpenRouter Error: {response.status_code} - {response.text}")
                return ""
        except Exception as e:
            logging.error(f"OpenRouter Request Exception: {e}")
            return ""

    def get_token_summary(self) -> dict:
        return {
            "prompt_tokens": self.total_prompt_tokens,
            "completion_tokens": self.total_completion_tokens,
            "total_tokens": self.total_prompt_tokens + self.total_completion_tokens
        }

# --- The Specialized Agent ---

class OpenRouterPersonalityAgent(BaseAgent):
    """
    An agent that uses OpenRouter to drive decisions.
    Incorporates fixes for Task IDs and Impostor Team-Killing.
    """
    def __init__(self, personality: str = None, model_name="meta-llama/llama-3-8b-instruct:free"):
        # If no personality passed, pick a random one from the list below
        self.personality = personality or random.choice(AGENT_PERSONALITIES)
        self.llm = OpenRouterWrapper(model_name=model_name)
        self.id = ""
        self.role = ""

    def on_game_start(self, config):
        self.id = config["your_id"]
        self.role = config["your_role"]

    def _get_system_prompt(self):
        return f"""You are playing 'Among Us' as {self.id}, a {self.role}.
PERSONALITY: {self.personality}

STRATEGY:
- Crewmate: Prioritize tasks. If you see a body, report it immediately.
- Impostor: To kill someone, you must be in the SAME room. Predict movement.
- TEAMWORK: If you are an Impostor, NEVER kill your teammate. Check observations for teammate IDs.
- DISCUSSION: Be logical. If 4-5 players remain, do not skip easily. Vote for the most suspicious.
- GHOSTS: If dead, your ONLY goal is to move to task locations and finish them.

RESPONSE FORMAT:
- During TASK phase: Respond with a JSON object.
  - To move: {{"action": "move", "target": "Admin"}}
  - To do a task: {{"action": "do_task", "target": "task_id_here"}} (CRITICAL: Use the EXACT ID in brackets like 'task_medbay_scan').
- During DISCUSSION: Respond with plain text conversational message.
- During VOTING: Respond with player ID or "skip"."""

    def on_task_phase(self, obs):
        prompt = self._get_system_prompt()
        obs_text = format_observation_as_text(obs)
        
        state_note = ""
        if "available_actions" not in obs:
            state_note = "\nNOTE: You are a GHOST. Focus entirely on completing your tasks."
        
        user_msg = f"CURRENT OBSERVATION:\n{obs_text}{state_note}\n\nWhat is your next action? Respond ONLY with JSON. If doing a task, use the EXACT ID string."
        
        resp = self.llm.call(prompt, user_msg)
        return parse_llm_json(resp, {"action": "wait"})

    def on_discussion(self, obs):
        prompt = self._get_system_prompt()
        obs_text = format_observation_as_text(obs)
        chat_hist = "\n".join([f"{m['speaker']}: {m['message']}" for m in obs.get("chat_history", [])])
        
        user_msg = f"MEETING CONTEXT: {obs.get('meeting_context')}\n\nCHAT HISTORY:\n{chat_hist}\n\nIt is your turn. Be concise and stay in character."
        return self.llm.call(prompt, user_msg)

    def on_vote(self, obs):
        prompt = self._get_system_prompt()
        chat_hist = "\n".join([f"{m['speaker']}: {m['message']}" for m in obs.get("chat_history", [])])
        
        user_msg = f"CHAT HISTORY:\n{chat_hist}\n\nWho do you vote for? Respond with Player ID or 'skip'."
        resp = self.llm.call(prompt, user_msg)
        
        if not resp: return "skip"
        # Extract the last word (usually the ID) and clean it
        return resp.strip().split()[-1].replace('"', '').replace("'", "").lower()

    def on_game_end(self, result):
        summary = self.llm.get_token_summary()
        logging.info(f"Agent {self.id} session tokens: {summary['total_tokens']}")

# --- Personalities List ---

AGENT_PERSONALITIES = [
    "The Analytical Detective: Logical, tracks movements, asks for locations.",
    "The Aggressive Accuser: Quick to point fingers, uses strong language.",
    "The Quiet Worker: Focused on tasks, stays out of drama, only speaks with evidence.",
    "The Strategic Deceiver: (For Impostors) Build trust by faking tasks and helping with sabotages."
]

# Standard entry point for the engine
Agent = OpenRouterPersonalityAgent