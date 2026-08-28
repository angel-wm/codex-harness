"""Standard-library test for the disposable acceptance fixture."""
import unittest

from fixture_app import value


class TestFixture(unittest.TestCase):
    """Verify the fixture's only behavior."""

    def test_value_is_ready(self) -> None:
        self.assertEqual(value(), "ready")


if __name__ == "__main__":
    unittest.main()
