"""Independent cross-check of driver output against the raw device text.

For every implemented getter this re-derives the expected values from the raw
mocked_data/*.txt using DIFFERENT parsing logic than the driver's TextFSM
templates, then compares. Prints OK/FAIL per getter. Exit code != 0 on any FAIL.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "test", "unit"))
from conftest import PatchedC2950Driver as D  # noqa: E402

MD = os.path.join(ROOT, "test", "unit", "mocked_data")
FAILS = []


def raw(testdir, filename):
    with open(os.path.join(MD, testdir, "normal", filename), encoding="utf-8") as f:
        return f.read()


def drv(testdir, call):
    d = D("h", "u", "p")
    d.open()
    d.device.current_test = testdir
    d.device.current_test_case = "normal"
    return call(d)


def check(name, cond, detail=""):
    if cond:
        print(f"  OK   {name}")
    else:
        print(f"  FAIL {name}: {detail}")
        FAILS.append(name)


# ---- independent helpers (deliberately NOT the driver's parsers) -------------
ABBR = {"fa": "FastEthernet", "gi": "GigabitEthernet", "te": "TenGigabitEthernet",
        "po": "Port-channel", "vl": "Vlan", "eth": "Ethernet"}


def canon(p):
    m = re.match(r"^([A-Za-z]+)(\d.*)$", p)
    if not m:
        return p
    pre, rest = m.groups()
    full = ABBR.get(pre.lower())
    return (full + rest) if full else p


def macfmt(rawmac):
    h = rawmac.replace(".", "").upper()
    return ":".join(h[i:i + 2] for i in range(0, 12, 2))


def uptime_secs(s):
    u = {"year": 31536000, "week": 604800, "day": 86400, "hour": 3600, "minute": 60, "second": 1}
    return float(sum(int(n) * u[unit] for n, unit in
                     re.findall(r"(\d+)\s+(year|week|day|hour|minute|second)s?", s)))


def iface_blocks(text):
    blocks, name, buf = [], None, []
    for line in text.splitlines():
        m = re.match(r"^(\S+) is .+, line protocol is", line)
        if m:
            if name is not None:
                blocks.append((name, "\n".join(buf)))
            name, buf = m.group(1), [line]
        elif name is not None:
            buf.append(line)
    if name is not None:
        blocks.append((name, "\n".join(buf)))
    return blocks


# ============================ get_facts ======================================
print("get_facts")
sv = raw("test_get_facts", "show_version.txt")
sib = raw("test_get_facts", "show_ip_interface_brief.txt")
f = drv("test_get_facts", lambda d: d.get_facts())
exp_host = re.search(r"^(\S+) uptime is", sv, re.M).group(1)
exp_model = re.search(r"^Model number:\s+(\S+)", sv, re.M).group(1)
exp_serial = re.search(r"^System serial number:\s+(\S+)", sv, re.M).group(1)
exp_ver = re.search(r"Version (\S+),", sv).group(1)
exp_uptime = uptime_secs(re.search(r"uptime is (.+)", sv).group(1))
exp_ifaces = [m.group(1) for m in re.finditer(r"^(\S+)\s+\S+\s+(?:YES|NO)\b", sib, re.M)]
check("hostname", f["hostname"] == exp_host, f'{f["hostname"]} != {exp_host}')
check("model", f["model"] == exp_model, f'{f["model"]} != {exp_model}')
check("serial", f["serial_number"] == exp_serial, f'{f["serial_number"]} != {exp_serial}')
check("os_version", f["os_version"] == exp_ver, f'{f["os_version"]} != {exp_ver}')
check("uptime", f["uptime"] == exp_uptime, f'{f["uptime"]} != {exp_uptime}')
check("interface_list", f["interface_list"] == exp_ifaces,
      f'{len(f["interface_list"])} vs {len(exp_ifaces)}')

# ============================ get_interfaces =================================
print("get_interfaces")
si = raw("test_get_interfaces", "show_interfaces.txt")
gi = drv("test_get_interfaces", lambda d: d.get_interfaces())
exp_if = {}
for nm, b in iface_blocks(si):
    admin = re.search(r"^\S+ is (.+?), line protocol is (\S+)", b).group(1)
    proto = re.search(r"^\S+ is .+?, line protocol is (\S+)", b).group(1)
    mac = re.search(r"address is (\S+)", b).group(1)
    mtu = int(re.search(r"MTU (\d+) bytes", b).group(1))
    bw = int(re.search(r"BW (\d+) Kbit", b).group(1))
    exp_if[nm] = {"is_enabled": "administratively down" not in admin,
                  "is_up": proto == "up", "mtu": mtu, "speed": bw / 1000.0,
                  "mac_address": macfmt(mac)}
check("count", len(gi) == len(exp_if), f"{len(gi)} vs {len(exp_if)}")
bad = []
for nm, e in exp_if.items():
    g = gi.get(nm, {})
    for k, v in e.items():
        if g.get(k) != v:
            bad.append(f"{nm}.{k}: drv={g.get(k)} raw={v}")
check("fields (52 ifaces x is_up/enabled/mtu/speed/mac)", not bad, "; ".join(bad[:5]))

# ============================ get_interfaces_ip =============================
print("get_interfaces_ip")
gip = drv("test_get_interfaces_ip", lambda d: d.get_interfaces_ip())
exp_ip = {}
for nm, b in iface_blocks(si):
    m = re.search(r"Internet address is (\d+\.\d+\.\d+\.\d+)/(\d+)", b)
    if m:
        exp_ip.setdefault(nm, {"ipv4": {}})["ipv4"][m.group(1)] = {"prefix_length": int(m.group(2))}
check("interfaces_ip", gip == exp_ip, f"{gip} != {exp_ip}")

# ============================ get_interfaces_counters =======================
print("get_interfaces_counters")
gc = drv("test_get_interfaces_counters", lambda d: d.get_interfaces_counters())
cbad = []
for nm, b in iface_blocks(si):
    rxd = int(re.search(r"Input queue:\s+\d+/\d+/(\d+)/\d+", b).group(1))
    txd = int(re.search(r"Total output drops:\s+(\d+)", b).group(1))
    rxo = int(re.search(r"\d+ packets input, (\d+) bytes", b).group(1))
    bc = re.search(r"Received (\d+) broadcasts \((\d+)", b)
    rxb, rxm = int(bc.group(1)), int(bc.group(2))
    rxe = int(re.search(r"(\d+) input errors,", b).group(1))
    txo = int(re.search(r"\d+ packets output, (\d+) bytes", b).group(1))
    txe = int(re.search(r"(\d+) output errors,", b).group(1))
    g = gc[nm]
    exp = {"rx_discards": rxd, "tx_discards": txd, "rx_octets": rxo,
           "rx_broadcast_packets": rxb, "rx_multicast_packets": rxm,
           "rx_errors": rxe, "tx_octets": txo, "tx_errors": txe}
    for k, v in exp.items():
        if g[k] != v:
            cbad.append(f"{nm}.{k}: drv={g[k]} raw={v}")
    for k in ("tx_unicast_packets", "rx_unicast_packets", "tx_multicast_packets", "tx_broadcast_packets"):
        if g[k] != -1:
            cbad.append(f"{nm}.{k}!=-1")
check("count", len(gc) == len(exp_if), f"{len(gc)} vs {len(exp_if)}")
check("counter fields", not cbad, "; ".join(cbad[:5]))

# ============================ get_mac_address_table ========================
print("get_mac_address_table")
smt = raw("test_get_mac_address_table", "show_mac_address_table.txt")
gmt = drv("test_get_mac_address_table", lambda d: d.get_mac_address_table())
exp_mac = []
for line in smt.splitlines():
    m = re.match(r"^\s*(\S+)\s+([0-9a-fA-F]{4}\.[0-9a-fA-F]{4}\.[0-9a-fA-F]{4})\s+(\S+)\s+(\S+)\s*$", line)
    if not m:
        continue
    vl, mac, typ, port = m.groups()
    exp_mac.append({"mac": macfmt(mac),
                    "interface": canon(port),
                    "vlan": (0 if vl.lower() == "all" else int(vl)),
                    "static": typ.upper() == "STATIC",
                    "active": True, "moves": -1, "last_move": -1.0})
check("count", len(gmt) == len(exp_mac), f"{len(gmt)} vs {len(exp_mac)}")
check("total==331", len(gmt) == 331, str(len(gmt)))
mbad = [i for i in range(min(len(gmt), len(exp_mac))) if gmt[i] != exp_mac[i]]
check("every entry matches raw", not mbad,
      f"first diff idx {mbad[0]}: {gmt[mbad[0]]} != {exp_mac[mbad[0]]}" if mbad else "")
check("no dashes/header leaked",
      all(re.match(r"^[0-9A-F:]{17}$", e["mac"]) for e in gmt), "bad mac present")

# ============================ get_arp_table ================================
print("get_arp_table")
sa = raw("test_get_arp_table", "show_ip_arp.txt")
ga = drv("test_get_arp_table", lambda d: d.get_arp_table())
exp_arp = []
for line in sa.splitlines():
    m = re.match(r"^Internet\s+(\d+\.\d+\.\d+\.\d+)\s+(\S+)\s+([0-9a-fA-F.]+)\s+\S+\s+(\S+)", line)
    if not m:
        continue
    ip, age, mac, ifc = m.groups()
    exp_arp.append({"interface": canon(ifc), "mac": macfmt(mac), "ip": ip,
                    "age": (-1.0 if age == "-" else float(age) * 60.0)})
check("arp_table", ga == exp_arp, f"{ga} != {exp_arp}")

# ============================ get_vlans ====================================
print("get_vlans")
svl = raw("test_get_vlans", "show_vlan_brief.txt")
gv = drv("test_get_vlans", lambda d: d.get_vlans())
exp_vl = {}
cur = None
for line in svl.splitlines():
    if not line.strip():
        continue
    m = re.match(r"^(\d+)\s+(\S+)\s+(\S+)\s*(.*)$", line)
    if m:
        vid, nm, st, ports = m.groups()
        cur = vid
        exp_vl[vid] = {"name": nm, "interfaces": [canon(p.strip()) for p in ports.split(",") if p.strip()]}
    elif cur and re.match(r"^\s+\S", line):
        exp_vl[cur]["interfaces"].extend(canon(p.strip()) for p in line.split(",") if p.strip())
check("count", len(gv) == len(exp_vl), f"{len(gv)} vs {len(exp_vl)}")
check("count==97", len(gv) == 97, str(len(gv)))
vbad = [vid for vid in exp_vl if gv.get(vid) != exp_vl[vid]]
check("every vlan matches raw", not vbad,
      f"{vbad[:3]} e.g. drv={gv.get(vbad[0]) if vbad else None} raw={exp_vl.get(vbad[0]) if vbad else None}")
check("vlan10 continuation captured (46 ports)", len(gv.get("10", {}).get("interfaces", [])) == 46,
      str(len(gv.get("10", {}).get("interfaces", []))))

# ============================ get_users ====================================
print("get_users")
rc = raw("test_get_users", "show_running_config.txt")
gu = drv("test_get_users", lambda d: d.get_users())
exp_users = {}
for m in re.finditer(r"^username (\S+)(?: privilege (\d+))?(?: (?:password|secret) \d+ (\S+))?", rc, re.M):
    exp_users[m.group(1)] = {"level": int(m.group(2)) if m.group(2) else 1,
                             "password": m.group(3) or "", "sshkeys": []}
check("users", gu == exp_users, f"{gu} != {exp_users}")

# ============================ get_snmp_information =========================
print("get_snmp_information")
gs = drv("test_get_snmp_information", lambda d: d.get_snmp_information())
exp_comm = {}
for m in re.finditer(r"^snmp-server community (\S+) (RO|RW) (\S+)", rc, re.M):
    exp_comm[m.group(1)] = {"acl": m.group(3), "mode": m.group(2).lower()}
check("communities", gs["community"] == exp_comm, f'{gs["community"]} != {exp_comm}')

# ============================ get_ntp_servers =============================
print("get_ntp_servers")
gns = drv("test_get_ntp_servers", lambda d: d.get_ntp_servers())
exp_srv = {m.group(1): {} for m in re.finditer(r"^ntp server (\S+)", rc, re.M)}
check("ntp_servers", gns == exp_srv, f"{gns} != {exp_srv}")

# ============================ get_ntp_stats ===============================
print("get_ntp_stats")
sna = raw("test_get_ntp_stats", "show_ntp_associations.txt")
gnt = drv("test_get_ntp_stats", lambda d: d.get_ntp_stats())
m = re.search(r"^([*#+~o-]*)(\S+)\s+(\S+)\s+(\d+)\s+(\S+)\s+(\d+)\s+(\d+)\s+(\S+)\s+(\S+)\s+(\S+)\s*$", sna, re.M)
exp_ntp = [{"remote": m.group(2), "referenceid": m.group(3), "synchronized": "*" in m.group(1),
            "stratum": int(m.group(4)), "type": "", "when": m.group(5), "hostpoll": int(m.group(6)),
            "reachability": int(m.group(7)), "delay": float(m.group(8)), "offset": float(m.group(9)),
            "jitter": float(m.group(10))}]
check("ntp_stats", gnt == exp_ntp, f"{gnt} != {exp_ntp}")

# ============================ get_environment =============================
print("get_environment")
se = raw("test_get_environment", "show_env_all.txt")
ge = drv("test_get_environment", lambda d: d.get_environment())
check("fan status", ge["fans"] == {"FAN": {"status": "FAN is OK" in se}}, str(ge["fans"]))
check("power Internal", ge["power"]["Internal"]["status"] == ("Internal POWER supply is OK" in se), "")
check("power RPS false", ge["power"]["RPS"]["status"] is False, str(ge["power"].get("RPS")))
check("no temp/cpu, memory=-1", ge["temperature"] == {} and ge["cpu"] == {}
      and ge["memory"] == {"used_ram": -1, "available_ram": -1}, str(ge["memory"]))

# ============================ get_config ==================================
print("get_config")
gcfg = drv("test_get_config", lambda d: d.get_config())
run_raw = raw("test_get_config", "show_running_config.txt")
check("candidate empty", gcfg["candidate"] == "", repr(gcfg["candidate"]))
check("running non-empty", len(gcfg["running"]) > 100, str(len(gcfg["running"])))
check("startup non-empty", len(gcfg["startup"]) > 100, str(len(gcfg["startup"])))
check("preamble stripped", "Building configuration" not in gcfg["running"]
      and "Current configuration" not in gcfg["running"], "")
check("body preserved (hostname/Vlan2)", "hostname switch01" in gcfg["running"]
      and "interface Vlan2" in gcfg["running"], "")

print("get_config (sanitized)")
gsan = drv("test_get_config_sanitized", lambda d: d.get_config(sanitized=True))["running"]
secrets = ["094F471A1A0A", "$1$abcd$1111111111111111111111", "104D000A0618"]
check("raw contains secrets (control)", all(s in run_raw for s in secrets), "raw missing a secret?")
check("secrets removed", all(s not in gsan for s in secrets),
      "; ".join(s for s in secrets if s in gsan))
check("snmp community name masked", "snmp_ro" not in gsan and "snmp_rw" not in gsan
      and "<removed>" in gsan, "")

print("get_config (filtered)")
gf_run = drv("test_get_config_filtered", lambda d: d.get_config(retrieve="running"))
gf_sta = drv("test_get_config_filtered", lambda d: d.get_config(retrieve="startup"))
gf_can = drv("test_get_config_filtered", lambda d: d.get_config(retrieve="candidate"))
check("retrieve=running only", gf_run["running"] != "" and gf_run["startup"] == "" and gf_run["candidate"] == "", "")
check("retrieve=startup only", gf_sta["startup"] != "" and gf_sta["running"] == "" and gf_sta["candidate"] == "", "")
check("retrieve=candidate empty", gf_can == {"running": "", "startup": "", "candidate": ""}, str(gf_can))

# ============================ _get_cdp_neighbors_detail ===================
print("_get_cdp_neighbors_detail")
scd = raw("test_get_cdp_neighbors_detail", "show_cdp_neighbors_detail.txt")
gcd = drv("test_get_cdp_neighbors_detail", lambda d: d._get_cdp_neighbors_detail())
dev = re.search(r"Device ID:\s+(\S+)", scd).group(1)
mip = re.search(r"IP address:\s+(\d+\.\d+\.\d+\.\d+)", scd).group(1)
plat, caps = re.search(r"Platform:\s+(.+?),\s+Capabilities:\s+(.+)", scd).groups()
loc, rport = re.search(r"Interface:\s+(\S+),\s+Port ID \(outgoing port\):\s+(\S+)", scd).groups()
hold = int(re.search(r"Holdtime\s*:\s+(\d+)", scd).group(1))
ver = re.search(r"Version :\s*\r?\n(.+)", scd).group(1)
exp_cdp = {canon(loc): [{"remote_system_name": dev, "remote_port": rport, "remote_chassis_id": mip,
                         "remote_system_description": ver, "remote_system_capab": caps.split(),
                         "platform": plat, "holdtime": hold}]}
check("cdp_neighbors_detail", gcd == exp_cdp, f"{gcd} != {exp_cdp}")

# ============================ summary =====================================
print("\n" + ("ALL CHECKS PASSED" if not FAILS else f"FAILURES: {FAILS}"))
sys.exit(1 if FAILS else 0)
