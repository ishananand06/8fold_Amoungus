from engine.engine import BaseAgent
from engine.agents import parse_llm_json, format_observation_as_text

class MyHackathonAgent(BaseAgent):
    def __init__(self):
        """
        Initialize your agent's internal state, memory, or LLM client.
        """
        self.id = ""
        self.role = ""
        self.game_config = {}

    def on_game_start(self, config: dict) -> None:
        """
        Called once at the beginning of the game.
        :param config: Dict containing map adjacency, your tasks, and player list.
        """
        self.id = config["your_id"]
        self.role = config["your_role"]
        self.game_config = config
        print(f"Agent {self.id} started as {self.role}")

    def on_task_phase(self, observation: dict) -> dict:
        """
        Called every round during the task phase.
        :param observation: Your current view of the game (location, players, tasks).
        :return: A dict with "action" and "target".
        Example: {"action": "move", "target": "Admin"}
        Example: {"action": "do_task", "target": "id_to_use_from_task_list"}
        """
        # 1. Convert the observation to readable text
        # obs_text = format_observation_as_text(observation)
        
        # 2. Call your LLM here
        
        # 3. Return a valid action JSON
        return {"action": "wait"}

    def on_discussion(self, observation: dict) -> str:
        """
        Called when it's your turn to speak during a meeting.
        :param observation: Current chat history and meeting context.
        :return: A plain text string (max 500 chars).
        """
        return "I was doing tasks in Admin. I didn't see anyone."

    def on_vote(self, observation: dict) -> str:
        """
        Called at the end of a discussion to cast your vote.
        :param observation: Full chat transcript and list of alive players.
        :return: The player ID you want to vote for, or "skip".
        """
        return "skip"

    def on_game_end(self, result: dict) -> None:
        """
        Called when the game is over.
        :param result: Dict containing the winner and game stats.
        """
        print(f"Game Over! Winner: {result['winner']}")
