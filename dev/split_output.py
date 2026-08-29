"""Split a raw device session capture into per-command mocked_data files.

Usage:
    py -3.12 dev/split_output.py [capture.txt]

Splits the capture on the CLI prompt (text up to and including the first '#')
and writes each mapped command's body to
``test/unit/mocked_data/<test_getter>/normal/<command>.txt`` using the same
filename convention NAPALM's test double expects (non-alnum -> '_').

A command may feed several getter test directories (e.g. running-config is
consumed by get_config, get_users, get_snmp_information, get_ntp_servers).
Commands not present in the given capture are reported as MISSING and skipped.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# command -> list of (test-getter directory, mocked filename)
MAPPING = {
    "show version": [("test_get_facts", "show_version.txt")],
    "show ip interface brief": [("test_get_facts", "show_ip_interface_brief.txt")],
    "show interfaces": [
        ("test_get_interfaces", "show_interfaces.txt"),
        ("test_get_interfaces_ip", "show_interfaces.txt"),
        ("test_get_interfaces_counters", "show_interfaces.txt"),
    ],
    "show mac-address-table": [("test_get_mac_address_table", "show_mac_address_table.txt")],
    "show ip arp": [
        ("test_get_arp_table", "show_ip_arp.txt"),
        ("test_get_arp_table_with_vrf", "show_ip_arp.txt"),
    ],
    "show cdp neighbors detail": [("test_get_cdp_neighbors_detail", "show_cdp_neighbors_detail.txt")],
    "show running-config": [
        ("test_get_config", "show_running_config.txt"),
        ("test_get_config_filtered", "show_running_config.txt"),
        ("test_get_config_sanitized", "show_running_config.txt"),
        ("test_get_config_sanitized_filtered", "show_running_config.txt"),
        ("test_get_users", "show_running_config.txt"),
        ("test_get_snmp_information", "show_running_config.txt"),
        ("test_get_ntp_servers", "show_running_config.txt"),
    ],
    "show startup-config": [
        ("test_get_config", "show_startup_config.txt"),
        ("test_get_config_filtered", "show_startup_config.txt"),
        ("test_get_config_sanitized", "show_startup_config.txt"),
        ("test_get_config_sanitized_filtered", "show_startup_config.txt"),
    ],
    "show vlan brief": [("test_get_vlans", "show_vlan_brief.txt")],
    "show ntp associations": [("test_get_ntp_stats", "show_ntp_associations.txt")],
    "show env all": [("test_get_environment", "show_env_all.txt")],
}


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "output.txt")
    if not os.path.isabs(src):
        src = os.path.join(ROOT, src)
    with open(src, encoding="utf-8") as handle:
        lines = handle.read().splitlines()

    prompt = re.match(r"^(.*?#)", lines[0]).group(1)

    blocks = {}
    current = None
    for line in lines:
        if line.startswith(prompt):
            current = line[len(prompt):].strip()
            blocks[current] = []
            continue
        if current is not None:
            blocks[current].append(line)

    for command, destinations in MAPPING.items():
        if command not in blocks:
            continue
        body = "\n".join(blocks[command]).strip("\n") + "\n"
        for subdir, filename in destinations:
            dest_dir = os.path.join(ROOT, "test", "unit", "mocked_data", subdir, "normal")
            os.makedirs(dest_dir, exist_ok=True)
            with open(os.path.join(dest_dir, filename), "w", encoding="utf-8") as out:
                out.write(body)
        print(f"{command!r:28} -> {len(destinations)} dir(s)  ({len(blocks[command])} lines)")


if __name__ == "__main__":
    main()
