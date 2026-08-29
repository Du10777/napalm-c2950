"""Standalone test for the (non-NAPALM) CDP neighbour getter.

CDP is not part of the NAPALM schema, so it is tested outside BaseTestGetters
but still replays the saved device output via the same test double.
"""
import json
import os

from conftest import PatchedC2950Driver


def test_get_cdp_neighbors_detail():
    driver = PatchedC2950Driver("host", "user", "pass")
    driver.open()
    driver.device.current_test = "test_get_cdp_neighbors_detail"
    driver.device.current_test_case = "normal"

    result = driver._get_cdp_neighbors_detail()

    expected_path = os.path.join(
        os.path.dirname(__file__),
        "mocked_data",
        "test_get_cdp_neighbors_detail",
        "normal",
        "expected_result.json",
    )
    with open(expected_path) as handle:
        expected = json.load(handle)

    assert result == expected
