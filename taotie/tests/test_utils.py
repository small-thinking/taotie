"""Test the utils.
Run this test with command: pytest your_assistant/tests/core/test_utils.py
"""
import pytest

import taotie.utils as utils


@pytest.mark.parametrize("input, expected", [(1681684094, "2023-04-16 14:28:14")])
def test_get_datetime(input, expected):
    assert utils.get_datetime(input) == expected
