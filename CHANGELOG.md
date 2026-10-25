# Changelog

## 0.2.0

Two extension getters in the format of the orb-agent `custom_napalm` drivers
(NetBox Labs), used by [Lineman](https://github.com/Du10777) to mirror port
VLANs into NetBox. They are not NAPALM base getters.

- `get_interfaces_vlans()`: `{port: {"mode": "access|trunk|trunk-all|routed",
  "tagged": [...], "untagged": vid|None}}`, read from the running
  configuration; ports left to DTP use the operational state from
  `show interfaces status`. Verified against the WS-C2950G-48-EI configuration.
- `get_lldp_status()`: always `{"enabled": false, "supported": false}` — the
  2950 has no LLDP (CDP only).

## 0.1.1

- Fix package metadata URLs to point at the source repository.
- `get_config`: `full=True` is accepted for API compatibility but ignored —
  the Catalyst 2950 IOS has no `show running-config all` command.

## 0.1.0

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
