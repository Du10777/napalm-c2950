"""Regenerate every expected_result.json from the driver over the fixtures.

Use after changing fixtures (e.g. anonymisation). The driver parses the
mocked_data/*.txt and its output becomes the golden file, so tests and the
independent cross-check (dev/verify_getters.py) stay consistent.

Usage: py -3.12 dev/regen_expected.py
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "test", "unit"))
from conftest import PatchedC2950Driver as D  # noqa: E402

TASKS = {
    "test_get_facts": lambda d: d.get_facts(),
    "test_get_interfaces": lambda d: d.get_interfaces(),
    "test_get_interfaces_ip": lambda d: d.get_interfaces_ip(),
    "test_get_interfaces_counters": lambda d: d.get_interfaces_counters(),
    "test_get_mac_address_table": lambda d: d.get_mac_address_table(),
    "test_get_arp_table": lambda d: d.get_arp_table(),
    "test_get_arp_table_with_vrf": lambda d: d.get_arp_table(vrf="TEST"),
    "test_get_vlans": lambda d: d.get_vlans(),
    "test_get_config": lambda d: d.get_config(),
    "test_get_config_filtered": lambda d: d.get_config(retrieve="candidate"),
    "test_get_config_sanitized": lambda d: d.get_config(sanitized=True),
    "test_get_config_sanitized_filtered": lambda d: {
        "running": d.get_config(retrieve="running", sanitized=True)["running"],
        "startup": d.get_config(retrieve="startup", sanitized=True)["startup"],
        "candidate": "",
    },
    "test_get_users": lambda d: d.get_users(),
    "test_get_snmp_information": lambda d: d.get_snmp_information(),
    "test_get_ntp_servers": lambda d: d.get_ntp_servers(),
    "test_get_ntp_stats": lambda d: d.get_ntp_stats(),
    "test_get_environment": lambda d: d.get_environment(),
    "test_get_cdp_neighbors_detail": lambda d: d._get_cdp_neighbors_detail(),
}


def main():
    for testdir, fn in TASKS.items():
        d = D("h", "u", "p")
        d.open()
        d.device.current_test = testdir
        d.device.current_test_case = "normal"
        result = fn(d)
        path = os.path.join(MD_DIR := os.path.join(ROOT, "test", "unit", "mocked_data"),
                            testdir, "normal", "expected_result.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=4)
            fh.write("\n")
    print("regenerated", len(TASKS), "expected_result.json files")


if __name__ == "__main__":
    main()
