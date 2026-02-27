import os
import json
import requests
import logging
from engine.engine import BaseAgent, Role
from engine.agents import parse_llm_json, format_observation_as_text

# --- OpenRouter Utilities ---

class OpenRouterWrapper:
    """
    A reusable wrapper for calling models via OpenRouter.
    Uses the standard OpenAI Chat Completions API format.
    """
    def __init__(self, model_name="meta-llama/llama-3-8b-instruct:free"):
        self.api_key = os.environ.get("OPENROUTER_API_KEY")
        self.model_name = model_name
        
        if not self.api_key:
            raise ValueError("Environment variable OPENROUTER_API_KEY not found.")

    def call(self, system_prompt: str, user_message: str, max_tokens: int = 500, json_mode: bool = False) -> str:
        url = "https://openrouter.ai/api/v1/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/goelanmol124/EightFold_Amongus", # Optional but recommended by OpenRouter
            "X-Title": "ARIES Simulation" # Optional but recommended
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

        # Force JSON output for models that support it
        if json_mode:
            data["response_format"] = {"type": "json_object"}
        
        try:
            response = requests.post(url, headers=headers, json=data, timeout=30)
            if response.status_code == 200:
                # OpenRouter returns standard OpenAI-style JSON
                return response.json().get("choices", [{}])[0].get("message", {}).get("content", "")
            else:
                logging.error(f"OpenRouter API Error ({response.status_code}): {response.text}")
                return ""
        except Exception as e:
            logging.error(f"OpenRouter Call failed: {e}")
            return ""

# --- The Personality Agent ---

class OpenRouterPersonalityAgent(BaseAgent):
    """
    An optimized agent that uses OpenRouter.
    Includes a specific personality and strategic instructions.
    """
    def __init__(self, personality="The Analytical Detective: Logical, tracks movements, suspicious of alibis.", model_name="meta-llama/llama-3-8b-instruct:free"):
        try:
            self.llm = OpenRouterWrapper(model_name=model_name)
            self.llm_available = True
        except Exception as e:
            print(f"Warning: Agent could not initialize LLM ({e}). Falling back to dummy responses.")
            self.llm_available = False
            
        self.personality = personality
        self.id = ""
        self.role = ""

    def on_game_start(self, config):
        self.id = config["your_id"]
        self.role = config["your_role"]

    def _get_system_prompt(self):
        return f"""You are playing 'Among Us' as {self.id}, a {self.role}.
PERSONALITY: {self.personality}

STRATEGY:
- Crewmate: Prioritize tasks. If you see a body, report it.
- Impostor: To kill someone, predict where they will move next. CRITICAL: Check your observation for your "teammates". NEVER try to kill your teammate.
- DISCUSSION: Be logical. If there are 4-5 players left, SKIPPING is dangerous. Vote for the most suspicious person.
- GHOSTS: If dead, your ONLY goal is to move to your task locations and finish them.

RESPONSE FORMAT:
- During TASK phase: Respond with a JSON object. 
  - To move: {{"action": "move", "target": "Admin"}}
  - To do a task: {{"action": "do_task", "target": "task_id_here"}} (CRITICAL: You MUST use the exact string inside the [ID: ...] brackets. NEVER use the human-readable task name).
- During DISCUSSION: Respond with plain text conversational message.
- During VOTING: Respond with player ID or "skip"."""

    def on_task_phase(self, obs):
        if not self.llm_available:
            return {"action": "wait"}
            
        prompt = self._get_system_prompt()
        obs_text = format_observation_as_text(obs)
        
        state_note = ""
        if "available_actions" not in obs:
            state_note = "\nNOTE: You are a GHOST (dead). Focus on tasks."
        
        user_msg = f"CURRENT OBSERVATION:\n{obs_text}{state_note}\n\nWhat is your next action? Respond ONLY with JSON. If doing a task, use the EXACT ID provided in the brackets, not the name."
        
        resp = self.llm.call(prompt, user_msg, json_mode=True)
        return parse_llm_json(resp, {"action": "wait"})

    def on_discussion(self, obs):
        if not self.llm_available:
            return "I am a robot and my LLM is offline."
            
        prompt = self._get_system_prompt()
        obs_text = format_observation_as_text(obs)
        chat_hist = "\n".join([f"{m['speaker']}: {m['message']}" for m in obs.get("chat_history", [])])
        user_msg = f"MEETING CONTEXT: {obs.get('meeting_context')}\n\nCHAT HISTORY:\n{chat_hist}\n\nIt is your turn. Be concise."
        
        return self.llm.call(prompt, user_msg)

    def on_vote(self, obs):
        if not self.llm_available:
            return "skip"
            
        prompt = self._get_system_prompt()
        chat_hist = "\n".join([f"{m['speaker']}: {m['message']}" for m in obs.get("chat_history", [])])
        user_msg = f"CHAT HISTORY:\n{chat_hist}\n\nWho do you vote for? Respond with Player ID or 'skip'."
        
        resp = self.llm.call(prompt, user_msg)
        if not resp: return "skip"
        return resp.strip().split()[-1].replace('"', '').replace("'", "")

    def on_game_end(self, result):
        pass

# Hook for the engine
Agent = OpenRouterPersonalityAgent