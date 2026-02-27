import os
import base64
import json
import requests
import logging
from engine.engine import BaseAgent, Role
from engine.agents import parse_llm_json, format_observation_as_text
from google.auth.transport.requests import Request
from google.oauth2 import service_account

# --- Vertex AI Utilities ---

class VertexAIWrapper:
    """
    A reusable wrapper for calling Gemini 3 Flash on Vertex AI.
    Handles authentication and token usage tracking.
    """
    def __init__(self):
        self.project = os.environ.get("GEMINI_VERTEX_PROJECT")
        self.location = os.environ.get("GEMINI_VERTEX_LOCATION", "global")
        self.model_id = "gemini-3-flash-preview"
        self.creds = None
        self.token = None
        
        b64_creds = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON_B64")
        if b64_creds:
            creds_json = json.loads(base64.b64decode(b64_creds))
            self.creds = service_account.Credentials.from_service_account_info(
                creds_json, 
                scopes=['https://www.googleapis.com/auth/cloud-platform']
            )
        else:
            raise ValueError("Environment variable GOOGLE_APPLICATION_CREDENTIALS_JSON_B64 not found.")

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
            "systemInstruction": { "parts": [{"text": system_prompt}] },
            "contents": [{ "role": "user", "parts": [{"text": user_message}] }],
            "generationConfig": { "maxOutputTokens": max_tokens, "temperature": 0.7 }
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
                return "".join(text_parts)
            return ""
        except Exception as e:
            logging.error(f"LLM Call failed: {e}")
            return ""

# --- The Personality Agent ---

class GeminiPersonalityAgent(BaseAgent):
    """
    An optimized agent that uses Vertex AI Gemini 3 Flash.
    Includes a specific personality and strategic instructions.
    """
    def __init__(self, personality="The Analytical Detective: Logical, tracks movements, suspicious of alibis."):
        self.llm = VertexAIWrapper()
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
- Impostor: You must be in the SAME room as someone to kill them. Predict movement.
- DISCUSSION: Be logical. If there are 4-5 players left, SKIPPING is dangerous. Vote for the most suspicious person.
- GHOSTS: If dead, your ONLY goal is to move to your task locations and finish them.

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
            state_note = "
NOTE: You are a GHOST (dead). Focus on tasks."
        
        user_msg = f"CURRENT OBSERVATION:
{obs_text}{state_note}

What is your next action? Respond ONLY with JSON. If doing a task, use the EXACT ID provided."
        resp = self.llm.call(prompt, user_msg)
        return parse_llm_json(resp, {"action": "wait"})

    def on_discussion(self, obs):
        prompt = self._get_system_prompt()
        obs_text = format_observation_as_text(obs)
        chat_hist = "
".join([f"{m['speaker']}: {m['message']}" for m in obs.get("chat_history", [])])
        user_msg = f"MEETING CONTEXT: {obs.get('meeting_context')}

CHAT HISTORY:
{chat_hist}

It is your turn. Be concise."
        return self.llm.call(prompt, user_msg)

    def on_vote(self, obs):
        prompt = self._get_system_prompt()
        chat_hist = "
".join([f"{m['speaker']}: {m['message']}" for m in obs.get("chat_history", [])])
        user_msg = f"CHAT HISTORY:
{chat_hist}

Who do you vote for? Respond with Player ID or 'skip'."
        resp = self.llm.call(prompt, user_msg)
        # Simple extraction of the ID from the response
        return resp.strip().split()[-1].replace('"', '').replace("'", "")

    def on_game_end(self, result):
        pass
