"""Tests for the orb-agent-format extensions get_interfaces_vlans / get_lldp_status.

They are not NAPALM base getters, so they are tested outside BaseTestGetters,
replaying the saved device output via the same test double.
"""
import json
import os

from conftest import PatchedC2950Driver
from napalm_c2950 import c2950

HERE = os.path.dirname(__file__)
CASE = os.path.join(HERE, "mocked_data", "test_get_interfaces_vlans", "normal")


def _driver():
    driver = PatchedC2950Driver("host", "user", "pass")
    driver.open()
    driver.device.current_test = "test_get_interfaces_vlans"
    driver.device.current_test_case = "normal"
    return driver


def test_get_interfaces_vlans():
    """Real WS-C2950G-48-EI configuration: 44 access ports in VLAN 10, 6 trunks."""
    with open(os.path.join(CASE, "expected_result.json")) as handle:
        expected = json.load(handle)
    result = _driver().get_interfaces_vlans()
    assert result == expected
    assert result["FastEthernet0/1"] == {"mode": "access", "tagged": [], "untagged": 10}
    # "switchport access vlan 10" + "switchport mode trunk": a trunk of all VLANs, native 1
    assert result["FastEthernet0/45"] == {"mode": "trunk-all", "tagged": [], "untagged": 1}
    assert "Vlan2" not in result  # SVIs are not switch ports


def test_dtp_ports_use_the_operational_state():
    """Ports without "switchport mode" negotiate (DTP); show interfaces status tells the outcome."""
    with open(os.path.join(CASE, "show_interfaces_status.txt")) as handle:
        status = c2950._parse_interfaces_status_vlans(handle.read())
    assert status["FastEthernet0/48"] == "trunk" and status["FastEthernet0/1"] == "10"
    config = c2950._parse_switchport_config(
        "interface FastEthernet0/1\n switchport access vlan 10\n!\n"
        "interface FastEthernet0/48\n switchport trunk native vlan 5\n"
        " switchport trunk allowed vlan 5,10-12\n switchport trunk allowed vlan add 20\n!\n"
        "interface FastEthernet0/2\n switchport mode dynamic auto\n!\n"
    )
    assert c2950._classify_switchport(config["FastEthernet0/1"], status["FastEthernet0/1"]) == {
        "mode": "access", "tagged": [], "untagged": 10}
    assert c2950._classify_switchport(config["FastEthernet0/48"], status["FastEthernet0/48"]) == {
        "mode": "trunk", "tagged": [10, 11, 12, 20], "untagged": 5}
    # no operational state known: left alone
    assert c2950._classify_switchport(config["FastEthernet0/2"], None)["mode"] == "routed"


def test_voice_vlan_and_allowed_none():
    config = c2950._parse_switchport_config(
        "interface FastEthernet0/3\n switchport access vlan 10\n switchport mode access\n"
        " switchport voice vlan 20\n!\n"
        "interface FastEthernet0/4\n switchport mode trunk\n switchport trunk allowed vlan none\n!\n"
    )
    assert c2950._classify_switchport(config["FastEthernet0/3"], None) == {
        "mode": "trunk", "tagged": [20], "untagged": 10}
    assert c2950._classify_switchport(config["FastEthernet0/4"], None) == {
        "mode": "trunk", "tagged": [], "untagged": 1}


def test_get_lldp_status():
    assert _driver().get_lldp_status() == {"enabled": False, "supported": False}
