"""NAPALM driver for Cisco Catalyst 2950 (WS-C2950G-48-EI), classic IOS.

The Catalyst 2950 EI is a Layer-2-only switch running classic IOS 12.1(x)EA.
The official ``napalm-ios`` driver targets modern IOS syntax and features
(e.g. ``show mac address-table``, LLDP) that this platform predates or lacks,
so a dedicated driver is used.

Getters are implemented one at a time, only after real device output has been
seen. Unimplemented getters raise ``NotImplementedError`` so the driver still
imports and partially works.

Verified firmware: IOS 12.1(22)EA9 on WS-C2950G-48-EI.
"""
import os
import re

import textfsm

from napalm.base import NetworkDriver
from napalm.base.constants import CISCO_SANITIZE_FILTERS
from napalm.base.helpers import canonical_interface_name, mac, sanitize_configs

_TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")

# uptime unit -> seconds, used by _parse_uptime()
_UPTIME_UNITS = {
    "year": 31536000,
    "week": 604800,
    "day": 86400,
    "hour": 3600,
    "minute": 60,
    "second": 1,
}


def _textfsm_parse(template, raw_text):
    """Parse ``raw_text`` with the named TextFSM template in ``templates/``.

    Returns a list of dicts keyed by the template's Value names.
    """
    path = os.path.join(_TEMPLATE_DIR, template)
    with open(path) as handle:
        fsm = textfsm.TextFSM(handle)
        headers = fsm.header
        rows = fsm.ParseText(raw_text)
    return [dict(zip(headers, row)) for row in rows]


def _canonical(name):
    """Expand an interface abbreviation (Fa0/1 -> FastEthernet0/1).

    Falls back to the raw string for non-interface tokens such as "CPU".
    """
    try:
        return canonical_interface_name(name)
    except Exception:
        return name


def _parse_uptime(uptime_str):
    """Convert an IOS uptime string to seconds (float).

    Example: "2 weeks, 5 days, 11 hours, 49 minutes" -> 1684140.0
    Returns -1.0 when the string is empty/unparseable.
    """
    if not uptime_str:
        return -1.0
    seconds = 0
    matched = False
    for value, unit in re.findall(
        r"(\d+)\s+(year|week|day|hour|minute|second)s?", uptime_str
    ):
        seconds += int(value) * _UPTIME_UNITS[unit]
        matched = True
    return float(seconds) if matched else -1.0


class C2950Driver(NetworkDriver):
    """NAPALM driver for Cisco Catalyst 2950 EI switches (classic IOS)."""

    platform = "c2950"

    def __init__(self, hostname, username, password, timeout=60, optional_args=None):
        self.hostname = hostname
        self.username = username
        self.password = password
        self.timeout = timeout
        self.optional_args = optional_args or {}
        self.device = None

    def open(self):
        self.device = self._netmiko_open(
            device_type="cisco_ios",
            netmiko_optional_args=self.optional_args,
        )

    def close(self):
        self._netmiko_close()

    def _send_command(self, command):
        """Send a command down the channel and return the raw text output."""
        return self.device.send_command(command)

    # --------------------------------------------------------------- getters --
    def get_facts(self):
        # Verified on IOS 12.1(22)EA9 / WS-C2950G-48-EI.
        version_out = self._send_command("show version")
        iface_out = self._send_command("show ip interface brief")

        parsed = _textfsm_parse("show_version.textfsm", version_out)
        facts = parsed[0] if parsed else {}

        interface_list = [
            row["INTERFACE"]
            for row in _textfsm_parse("show_ip_interface_brief.textfsm", iface_out)
        ]

        hostname = facts.get("HOSTNAME", "")
        return {
            "hostname": hostname,
            # No `ip domain-name` is captured on this box; default fqdn to
            # the hostname rather than inventing a domain.
            "fqdn": hostname,
            "vendor": "Cisco",
            "model": facts.get("MODEL", ""),
            "serial_number": facts.get("SERIAL", ""),
            "os_version": facts.get("VERSION", ""),
            "uptime": _parse_uptime(facts.get("UPTIME", "")),
            "interface_list": interface_list,
        }

    def get_interfaces(self):
        # Verified on IOS 12.1(22)EA9 / WS-C2950G-48-EI.
        # speed is derived from the "BW <n> Kbit" field (the only numeric speed
        # present for every interface, including down/auto ports).
        # last_flapped is -1.0: `show interfaces` does not report a flap time.
        out = self._send_command("show interfaces")
        interfaces = {}
        for row in _textfsm_parse("show_interfaces.textfsm", out):
            name = row["INTERFACE"]
            link = row["LINK_STATUS"].strip().lower()
            interfaces[name] = {
                "is_enabled": "administratively down" not in link,
                "is_up": row["PROTOCOL_STATUS"].strip().lower() == "up",
                "description": row["DESCRIPTION"].strip(),
                "last_flapped": -1.0,
                "mtu": int(row["MTU"]) if row["MTU"] else -1,
                "speed": (float(row["BW"]) / 1000.0) if row["BW"] else -1.0,
                "mac_address": mac(row["MAC"]) if row["MAC"] else "",
            }
        return interfaces

    def get_mac_address_table(self):
        # Verified on IOS 12.1(22)EA9 / WS-C2950G-48-EI.
        # VLAN "All" (STATIC CPU/control-plane entries) is mapped to 0.
        # moves/last_move are not reported by this platform -> -1 / -1.0.
        out = self._send_command("show mac-address-table")
        table = []
        for row in _textfsm_parse("show_mac_address_table.textfsm", out):
            try:
                vlan = int(row["VLAN"])
            except ValueError:
                vlan = 0
            table.append({
                "mac": mac(row["MAC"]),
                "interface": _canonical(row["PORTS"]),
                "vlan": vlan,
                "static": row["TYPE"].upper() == "STATIC",
                "active": True,
                "moves": -1,
                "last_move": -1.0,
            })
        return table

    def get_arp_table(self, vrf=""):
        # Verified on IOS 12.1(22)EA9 / WS-C2950G-48-EI.
        # IOS reports the age in minutes; NAPALM wants seconds -> multiply by 60.
        # "-" (the device's own SVI entry) has no age -> -1.0.
        out = self._send_command("show ip arp")
        arp_table = []
        for row in _textfsm_parse("show_ip_arp.textfsm", out):
            age_raw = row["AGE"]
            if age_raw == "-":
                age = -1.0
            else:
                try:
                    age = float(age_raw) * 60.0
                except ValueError:
                    age = -1.0
            arp_table.append({
                "interface": _canonical(row["INTERFACE"]),
                "mac": mac(row["MAC"]),
                "ip": row["IP"],
                "age": age,
            })
        return arp_table

    def get_interfaces_ip(self):
        # Verified on IOS 12.1(22)EA9 / WS-C2950G-48-EI.
        # Parsed from `show interfaces`; only SVIs with an address appear.
        out = self._send_command("show interfaces")
        result = {}
        for row in _textfsm_parse("show_interfaces.textfsm", out):
            if not row["ADDR"]:
                continue
            ipv4 = result.setdefault(row["INTERFACE"], {}).setdefault("ipv4", {})
            ipv4[row["ADDR"]] = {"prefix_length": int(row["MASKLEN"])}
        return result

    def get_interfaces_counters(self):
        # Verified on IOS 12.1(22)EA9 / WS-C2950G-48-EI.
        # The 2950 does not report unicast counts nor a TX multicast/broadcast
        # split, so those six fields are set to -1.
        out = self._send_command("show interfaces")
        counters = {}
        for row in _textfsm_parse("show_interfaces.textfsm", out):
            counters[row["INTERFACE"]] = {
                "tx_errors": int(row["TX_ERRORS"]),
                "rx_errors": int(row["RX_ERRORS"]),
                "tx_discards": int(row["TX_DISCARDS"]),
                "rx_discards": int(row["RX_DISCARDS"]),
                "tx_octets": int(row["TX_OCTETS"]),
                "rx_octets": int(row["RX_OCTETS"]),
                "tx_unicast_packets": -1,
                "rx_unicast_packets": -1,
                "tx_multicast_packets": -1,
                "rx_multicast_packets": int(row["RX_MULTICAST"]),
                "tx_broadcast_packets": -1,
                "rx_broadcast_packets": int(row["RX_BROADCAST"]),
            }
        return counters

    def get_vlans(self):
        # Verified on IOS 12.1(22)EA9 / WS-C2950G-48-EI.
        out = self._send_command("show vlan brief")
        vlans = {}
        for row in _textfsm_parse("show_vlan_brief.textfsm", out):
            interfaces = []
            for chunk in row["PORTS"]:
                for port in chunk.split(","):
                    port = port.strip()
                    if port:
                        interfaces.append(_canonical(port))
            vlans[row["VLAN_ID"]] = {"name": row["NAME"], "interfaces": interfaces}
        return vlans

    def get_users(self):
        # Verified on IOS 12.1(22)EA9. Parsed from running-config `username` lines.
        # password holds the (type 7/5) hash as stored; level defaults to 1.
        out = self._send_command("show running-config")
        users = {}
        pattern = re.compile(
            r"^username\s+(\S+)"
            r"(?:\s+privilege\s+(\d+))?"
            r"(?:\s+(?:password|secret)\s+\d+\s+(\S+))?"
        )
        for line in out.splitlines():
            match = pattern.match(line)
            if not match:
                continue
            users[match.group(1)] = {
                "level": int(match.group(2)) if match.group(2) else 1,
                "password": match.group(3) or "",
                "sshkeys": [],
            }
        return users

    def get_snmp_information(self):
        # Verified on IOS 12.1(22)EA9. Parsed from running-config.
        out = self._send_command("show running-config")
        snmp = {"chassis_id": "", "community": {}, "contact": "", "location": ""}
        for raw in out.splitlines():
            line = raw.strip()
            match = re.match(
                r"^snmp-server community (\S+)(?:\s+(RO|RW))?(?:\s+(\S+))?", line
            )
            if match:
                snmp["community"][match.group(1)] = {
                    "acl": match.group(3) or "N/A",
                    "mode": (match.group(2) or "RO").lower(),
                }
                continue
            match = re.match(r"^snmp-server location (.+)$", line)
            if match:
                snmp["location"] = match.group(1).strip()
                continue
            match = re.match(r"^snmp-server contact (.+)$", line)
            if match:
                snmp["contact"] = match.group(1).strip()
                continue
            match = re.match(r"^snmp-server chassis-id (.+)$", line)
            if match:
                snmp["chassis_id"] = match.group(1).strip()
        return snmp

    def get_ntp_servers(self):
        # Verified on IOS 12.1(22)EA9. Parsed from running-config `ntp server` lines.
        out = self._send_command("show running-config")
        servers = {}
        for line in out.splitlines():
            match = re.match(r"^ntp server (\S+)", line.strip())
            if match:
                servers[match.group(1)] = {}
        return servers

    def get_ntp_stats(self):
        # Verified on IOS 12.1(22)EA9 (`show ntp associations`).
        # The "disp" column is mapped to NAPALM's `jitter`; `type` is not
        # reported by this platform (left empty).
        out = self._send_command("show ntp associations")
        stats = []
        for row in _textfsm_parse("show_ntp_associations.textfsm", out):
            stats.append({
                "remote": row["REMOTE"],
                "referenceid": row["REFID"],
                "synchronized": "*" in row["SYNCFLAG"],
                "stratum": int(row["STRATUM"]),
                "type": "",
                "when": row["WHEN"],
                "hostpoll": int(row["POLL"]),
                "reachability": int(row["REACH"]),
                "delay": float(row["DELAY"]),
                "offset": float(row["OFFSET"]),
                "jitter": float(row["DISP"]),
            })
        return stats

    def get_environment(self):
        # Verified on IOS 12.1(22)EA9 (`show env all`). The 2950 exposes only
        # fan and power status; temperature/cpu are empty and memory is -1.
        out = self._send_command("show env all")
        env = {
            "fans": {},
            "temperature": {},
            "power": {},
            "cpu": {},
            "memory": {"used_ram": -1, "available_ram": -1},
        }
        for raw in out.splitlines():
            line = raw.strip()
            if not line:
                continue
            healthy = "OK" in line
            if re.match(r"^FAN\b", line, re.I):
                env["fans"]["FAN"] = {"status": healthy}
            elif "POWER supply" in line:
                match = re.match(r"^(\S+) POWER supply", line)
                name = match.group(1) if match else "POWER"
                env["power"][name] = {"status": healthy, "output": -1.0, "capacity": -1.0}
            elif line.startswith("RPS"):
                present = "present" in line and "NOT" not in line
                env["power"]["RPS"] = {"status": present, "output": -1.0, "capacity": -1.0}
        return env

    def get_config(self, retrieve="all", full=False, sanitized=False, format="text"):
        # Verified on IOS 12.1(22)EA9. Candidate config is not supported (-> "").
        configs = {"running": "", "startup": "", "candidate": ""}
        if retrieve in ("all", "running"):
            configs["running"] = self._clean_config(
                self._send_command("show running-config")
            )
        if retrieve in ("all", "startup"):
            configs["startup"] = self._clean_config(
                self._send_command("show startup-config")
            )
        if sanitized:
            return sanitize_configs(configs, CISCO_SANITIZE_FILTERS)
        return configs

    @staticmethod
    def _clean_config(output):
        """Strip IOS `show *-config` preamble noise, keeping the config body."""
        skip = (
            "Building configuration",
            "Current configuration",
            "Using ",
            "Error on initialize VLAN database",
        )
        lines = [line for line in output.splitlines() if not line.startswith(skip)]
        return "\n".join(lines).strip()

    def get_lldp_neighbors_detail(self, interface=""):
        # Catalyst 2950 has no LLDP support (CDP only).
        # Use _get_cdp_neighbors_detail() for neighbor discovery on this box.
        raise NotImplementedError

    # ------------------------------------------------------- non-NAPALM extra --
    def _get_cdp_neighbors_detail(self):
        """Return CDP neighbours keyed by local interface.

        This is NOT part of the NAPALM schema (there is no CDP getter); it is
        provided because the 2950 has no LLDP. Kept private so it does not break
        the NAPALM method-signature test.
        """
        out = self._send_command("show cdp neighbors detail")
        neighbors = {}
        for row in _textfsm_parse("show_cdp_neighbors_detail.textfsm", out):
            local = _canonical(row["LOCAL_INTERFACE"])
            neighbors.setdefault(local, []).append({
                "remote_system_name": row["DEVICE_ID"],
                "remote_port": row["REMOTE_PORT"],
                "remote_chassis_id": row["MGMT_IP"],
                "remote_system_description": row["VERSION"],
                "remote_system_capab": row["CAPABILITIES"].split(),
                "platform": row["PLATFORM"],
                "holdtime": int(row["HOLDTIME"]) if row["HOLDTIME"] else -1,
            })
        return neighbors
