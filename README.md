# napalm-c2950

NAPALM driver for the **Cisco Catalyst 2950 (WS-C2950G-48-EI)** — a Layer-2-only
switch running classic IOS 12.1(x)EA. The official `napalm-ios` driver assumes
modern IOS syntax and features (e.g. `show mac address-table`, LLDP) that this
platform predates or lacks, so this dedicated driver targets the old CLI.

- Transport: `netmiko` (`device_type=cisco_ios`)
- Base class: `napalm.base.NetworkDriver`

## Install

```bash
pip install napalm-c2950
```

## Usage

```python
from napalm import get_network_driver

driver = get_network_driver("c2950")   # resolves to napalm_c2950.C2950Driver
with driver("192.0.2.10", "admin", "secret") as device:
    print(device.get_facts())
    print(device.get_vlans())
```

## Supported getters

| Getter | Status | Command(s) |
|---|---|---|
| `get_facts` | ✅ done | `show version`, `show ip interface brief` |
| `get_interfaces` | ✅ done | `show interfaces` |
| `get_interfaces_ip` | ✅ done | `show interfaces` |
| `get_interfaces_counters` | ✅ done¹ | `show interfaces` |
| `get_mac_address_table` | ✅ done | `show mac-address-table` |
| `get_arp_table` | ✅ done² | `show ip arp` |
| `get_vlans` | ✅ done | `show vlan brief` |
| `get_config` | ✅ done³ | `show running-config`, `show startup-config` |
| `get_users` | ✅ done | `show running-config` |
| `get_snmp_information` | ✅ done | `show running-config` |
| `get_ntp_servers` | ✅ done | `show running-config` |
| `get_ntp_stats` | ✅ done⁴ | `show ntp associations` |
| `get_environment` | ✅ done⁵ | `show env all` |
| `get_ntp_peers` | ❌ n/a | no `ntp peer` on this platform |
| `get_lldp_neighbors_detail` | ❌ n/a | 2950 has no LLDP (CDP only) — see notes |
| `_get_cdp_neighbors_detail` | ✅ done⁶ | `show cdp neighbors detail` |
| `get_interfaces_vlans` | ✅ extension⁷ | `show running-config`, `show interfaces status` |
| `get_lldp_status` | ✅ extension⁷ | — (always disabled: no LLDP on the 2950) |

Everything else raises `NotImplementedError`.

¹ The 2950 does not report unicast counts or a TX multicast/broadcast split;
those six fields are returned as `-1`.
² IOS reports ARP age in minutes; it is converted to seconds. `vrf` is accepted
for API compatibility but ignored (single routing table).
³ Candidate config is not supported (`candidate` is always `""`). `sanitized=True`
uses NAPALM's `CISCO_SANITIZE_FILTERS`. `full=True` is accepted but ignored — this
IOS has no `show running-config all`.
⁴ The `disp` column is mapped to `jitter`; `type` is not reported (empty string).
⁵ Only fan and power status are exposed by `show env all`; `temperature`/`cpu`
are empty and `memory` fields are `-1`.
⁶ Not part of the NAPALM schema (there is no CDP getter). Provided as a private
method because the 2950 has no LLDP; kept private so the NAPALM
method-signature test still passes.
⁷ Not NAPALM base getters (excluded from the
method-signature test): the format of the orb-agent `custom_napalm` drivers
(NetBox Labs), consumed by Lineman. `get_interfaces_vlans` returns
`{port: {"mode": "access" | "trunk" | "trunk-all" | "routed", "tagged": [...],
"untagged": vid | null}}` from the running configuration (voice VLAN on an
access port -> `trunk` with the voice VLAN tagged); ports without
`switchport mode` (DTP) take the negotiated state from `show interfaces status`,
and stay `routed` (unknown) when it cannot be read.

## Tested firmware

- IOS **12.1(22)EA9** on **WS-C2950G-48-EI**

## Notes

- The 2950 does not implement LLDP. `get_lldp_neighbors_detail` currently raises
  `NotImplementedError`; a CDP-based (`show cdp neighbors detail`) alternative can
  be added if desired, though it is not standard NAPALM LLDP semantics.

## License

Apache 2.0
