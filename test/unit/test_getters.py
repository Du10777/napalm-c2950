"""Tests for getters using the standard NAPALM test harness."""
import pytest

from napalm.base.test.getters import BaseTestGetters


@pytest.mark.usefixtures("set_device_parameters")
class TestGetter(BaseTestGetters):
    """Run the NAPALM getter test suite against mocked_data/."""
