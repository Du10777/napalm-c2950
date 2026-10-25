"""Tests for getters using the standard NAPALM test harness."""
import inspect

import pytest

from napalm.base import NetworkDriver
from napalm.base.test.getters import BaseTestGetters

# Public methods that are not NAPALM base getters: the orb-agent / Lineman
# extensions (tested in test_extensions.py).
EXTENSIONS = {"get_interfaces_vlans", "get_lldp_status"}


@pytest.mark.usefixtures("set_device_parameters")
class TestGetter(BaseTestGetters):
    """Run the NAPALM getter test suite against mocked_data/."""

    def test_method_signatures(self):
        """Same as NAPALM's check, except for the documented extensions."""
        errors = {}
        obj = self.driver(hostname="test", username="admin", password="pwd")
        for attr, func in inspect.getmembers(obj):
            if attr.startswith("_") or attr in EXTENSIONS or not inspect.ismethod(func):
                continue
            try:
                orig_spec = inspect.getfullargspec(getattr(NetworkDriver, attr))[:4]
            except AttributeError:
                orig_spec = "Method does not exist in napalm.base"
            if inspect.getfullargspec(func)[:4] != orig_spec:
                errors[attr] = orig_spec
        assert not errors, "Some methods vary. \n{}".format(errors.keys())
