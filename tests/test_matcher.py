import unittest

from speech_to_command_frc.matcher import find_command_matches, normalize_tokens


class MatcherTests(unittest.TestCase):
    def test_normalizes_words_and_punctuation(self) -> None:
        self.assertEqual(normalize_tokens("Move, diagonally!"), ("move", "diagonally"))

    def test_longer_overlapping_command_wins(self) -> None:
        matches = find_command_matches("please move diagonally now", ["move", "move diagonally"])
        self.assertEqual([match.command for match in matches], ["move diagonally"])

    def test_short_command_still_matches_when_alone(self) -> None:
        matches = find_command_matches("please move now", ["move", "move diagonally"])
        self.assertEqual([match.command for match in matches], ["move"])

    def test_multiple_non_overlapping_commands_match(self) -> None:
        matches = find_command_matches("move diagonally then stop", ["move", "move diagonally", "stop"])
        self.assertEqual([match.command for match in matches], ["move diagonally", "stop"])

    def test_partial_words_do_not_match(self) -> None:
        matches = find_command_matches("remove diagonally", ["move diagonally"])
        self.assertEqual(matches, [])


if __name__ == "__main__":
    unittest.main()
