import unittest
from app.service import add

class TestService(unittest.TestCase):
    def test_add(self):
        self.assertEqual(add(2, 3), 5)
        self.assertEqual(add(0, 5), 5)
        self.assertEqual(add(-1, 4), 3)
        self.assertEqual(add(7, -2), 5)

if __name__ == "__main__":
    unittest.main()