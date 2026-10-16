import unittest

from src.commands import parse_command


class CommandTests(unittest.TestCase):
    def test_slash_command(self):
        self.assertEqual(parse_command("/gold"), "gold")

    def test_group_command(self):
        self.assertEqual(parse_command("/news@FoxZ4_bot"), "news")

    def test_thai_alias(self):
        self.assertEqual(parse_command("  วิเคราะห์ทอง  "), "gold")

    def test_chart_command_and_alias(self):
        self.assertEqual(parse_command("/chart"), "chart")
        self.assertEqual(parse_command("กราฟทอง"), "chart")

    def test_paper_stats_command(self):
        self.assertEqual(parse_command("/paper"), "paper")
        self.assertEqual(parse_command("/stats"), "paper")
        self.assertEqual(parse_command("สถิติ"), "paper")

    def test_unknown_text(self):
        self.assertIsNone(parse_command("hello there"))

