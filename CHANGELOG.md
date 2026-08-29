# Changelog

## 0.1.0 (unreleased)

Initial release. Verified against **Cisco WS-C2950G-48-EI**, IOS **12.1(22)EA9**.

Implemented getters:
- `get_facts`, `get_interfaces`, `get_interfaces_ip`, `get_interfaces_counters`
- `get_mac_address_table`, `get_arp_table`, `get_vlans`
- `get_config` (running/startup, `sanitized` supported; candidate not applicable)
- `get_users`, `get_snmp_information`, `get_ntp_servers`, `get_ntp_stats`
- `get_environment`

Non-NAPALM helper:
- `_get_cdp_neighbors_detail` (the 2950 has no LLDP, only CDP)

Not applicable on this platform (raise `NotImplementedError`): LLDP, BGP,
optics, routing, probes, `get_ntp_peers`.
