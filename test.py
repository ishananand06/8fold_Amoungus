import unittest
from config import GameConfig, MAP_ADJACENCY, ALL_ROOMS, TASK_POOL

class TestConfig(unittest.TestCase):
    def test_default_config_valid(self):
        config = GameConfig()
        config.validate()  # Should not raise exception

    def test_invalid_config_raises(self):
        config = GameConfig(num_players=4, num_impostors=2)
        with self.assertRaises(AssertionError):
            config.validate()

    def test_map_adjacency(self):
        self.assertEqual(len(ALL_ROOMS), 10)
        self.assertIn("Medbay", MAP_ADJACENCY["Cafeteria"])
        self.assertIn("Cafeteria", MAP_ADJACENCY["Medbay"])

    def test_task_pool(self):
        self.assertEqual(len(TASK_POOL), 16)
        visual_tasks = [t for t in TASK_POOL if t["visual"]]
        self.assertEqual(len(visual_tasks), 2)

if __name__ == '__main__':
    unittest.main()
