import pytest
from app.service import add

@pytest.mark.parametrize("a,b,expected", [(2, 3, 5), (0, 0, 0), (-2, 3, 1), (1.5, 2.5, 4)])
def test_add(a, b, expected):
    assert add(a, b) == expected
