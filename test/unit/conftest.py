"""pytest fixtures wiring the C2950 driver into the NAPALM test framework."""
import pytest

from napalm.base.test import conftest as parent_conftest
from napalm.base.test.double import BaseTestDouble

from napalm_c2950 import c2950


@pytest.fixture(scope="class")
def set_device_parameters(request):
    """Set up the class."""

    def fin():
        request.cls.device.close()

    request.addfinalizer(fin)

    request.cls.driver = c2950.C2950Driver
    request.cls.patched_driver = PatchedC2950Driver
    request.cls.vendor = "c2950"
    parent_conftest.set_device_parameters(request)


def pytest_generate_tests(metafunc):
    """Generate test cases dynamically from mocked_data/."""
    parent_conftest.pytest_generate_tests(metafunc, __file__)


class PatchedC2950Driver(c2950.C2950Driver):
    """Patched C2950 driver that reads from a test double instead of a device."""

    def __init__(self, hostname, username, password, timeout=60, optional_args=None):
        super().__init__(hostname, username, password, timeout, optional_args)
        self.patched_attrs = ["device"]
        self.device = FakeC2950Device()

    def open(self):
        # Keep the pre-wired test double; do not open a real netmiko session.
        pass

    def close(self):
        pass


class FakeC2950Device(BaseTestDouble):
    """C2950 device test double that replays saved command output."""

    def send_command(self, command, **kwargs):
        filename = "{}.txt".format(self.sanitize_text(command))
        full_path = self.find_file(filename)
        return self.read_txt_file(full_path)
