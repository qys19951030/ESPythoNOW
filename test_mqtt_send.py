import sys
import os
from unittest.mock import Mock, MagicMock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import scapy.all as scapy
scapy.conf.L2socket = Mock(return_value=Mock(iface="dummy0", ins=Mock(send=Mock())))
scapy.get_if_hwaddr = Mock(return_value="AA:BB:CC:DD:EE:FF")
scapy.threading = MagicMock()
scapy.threading.Event = MagicMock
scapy.AsyncSniffer = MagicMock()
scapy.orb = MagicMock(side_effect=lambda x: x)
scapy.get_if_raw_hwaddr = Mock(return_value=(None, b'\xaa\xbb\xcc\xdd\xee\xff'))

from ESPythoNOW import ESPythoNow

BASE = "ESPythoNOW-AA:BB:CC:DD:EE:FF"
SEND = BASE + "/send"


def make_espnow():
    e = ESPythoNow(interface="dummy0", set_interface=False, accept_all=True)
    e.mqtt_topic_base = BASE
    e.mqtt_topic_send = SEND
    e.mqtt_discard_empty = True
    e.send = Mock()
    return e


class FakeMsg:
    def __init__(self, topic, payload):
        self.topic = topic
        self.payload = payload


def parse(e, topic, payload):
    return e.parse_mqtt_send_message(topic, payload)


passed = 0
failed = 0


def check(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}")


print("=" * 64)
print("MQTT -> ESP-NOW send bridge verification")
print("=" * 64)

# ---------------------------------------------------------------------------
print("\n--- Group 1: raw bytes topic (<send>/<mac>) ---")

e = make_espnow()
r = parse(e, f"{SEND}/AABBCCDDEEFF", b"\x01\x02\x03")
check("raw: returns dict", r is not None)
check("raw: mac captured", r and r["mac"] == "AABBCCDDEEFF")
check("raw: msg is bytes", r and r["msg"] == b"\x01\x02\x03")
check("raw: mode raw", r and r["mode"] == "raw")

e = make_espnow()
e.mqtt_on_message(None, None, FakeMsg(f"{SEND}/AA:BB:CC:DD:EE:FF", b"hello"))
check("raw end-to-end: send called once", e.send.call_count == 1)
args, kwargs = e.send.call_args
check("raw end-to-end: mac arg correct", args[0] == "AA:BB:CC:DD:EE:FF")
check("raw end-to-end: msg arg correct", args[1] == b"hello")

# ---------------------------------------------------------------------------
print("\n--- Group 2: hex topic (<send>/<mac>/hex) ---")

e = make_espnow()
r = parse(e, f"{SEND}/AABBCCDDEEFF/hex", b"01 02 03")
check("hex: returns dict", r is not None)
check("hex: mac captured", r and r["mac"] == "AABBCCDDEEFF")
check("hex: msg decoded from spaces", r and r["msg"] == b"\x01\x02\x03")
check("hex: mode hex", r and r["mode"] == "hex")

# hex with colons
e = make_espnow()
r = parse(e, f"{SEND}/AABBCCDDEEFF/hex", b"AA:BB:CC")
check("hex: colons decoded", r and r["msg"] == b"\xaa\xbb\xcc")

# hex plain no separators
e = make_espnow()
r = parse(e, f"{SEND}/AABBCCDDEEFF/hex", b"aabbccdd")
check("hex: plain lowercase decoded", r and r["msg"] == b"\xaa\xbb\xcc\xdd")

# end-to-end hex
e = make_espnow()
e.mqtt_on_message(None, None, FakeMsg(f"{SEND}/AA:BB:CC:DD:EE:FF/hex", b"DE AD BE EF"))
check("hex end-to-end: send called once", e.send.call_count == 1)
args, kwargs = e.send.call_args
check("hex end-to-end: mac arg correct", args[0] == "AA:BB:CC:DD:EE:FF")
check("hex end-to-end: msg arg correct", args[1] == b"\xde\xad\xbe\xef")

# ---------------------------------------------------------------------------
print("\n--- Group 3: rejection cases (send must NOT be called) ---")

cases = [
    ("empty payload bytes", f"{SEND}/AABBCCDDEEFF", b""),
    ("empty payload str", f"{SEND}/AABBCCDDEEFF", ""),
    ("empty hex payload", f"{SEND}/AABBCCDDEEFF/hex", b""),
    ("None payload", f"{SEND}/AABBCCDDEEFF", None),
    ("invalid mac", f"{SEND}/ZZZZZZZZZZZZ", b"\x01"),
    ("invalid mac (short)", f"{SEND}/AABBCC", b"\x01"),
    ("invalid hex chars", f"{SEND}/AABBCCDDEEFF/hex", b"ZZZZ"),
    ("odd-length hex", f"{SEND}/AABBCCDDEEFF/hex", b"ABC"),
    ("non-ascii hex", f"{SEND}/AABBCCDDEEFF/hex", "AABB\u00ff".encode("utf-8")),
    ("unknown subtopic", f"{SEND}/AABBCCDDEEFF/foo", b"\x01"),
    ("extra path segment", f"{SEND}/AABBCCDDEEFF/hex/extra", b"\x01"),
    ("topic not under send", f"{BASE}/AABBCCDDEEFF", b"\x01"),
    ("send topic with no mac", f"{SEND}", b"\x01"),
    ("send topic trailing slash", f"{SEND}/", b"\x01"),
    ("completely unrelated topic", "homeassistant/light", b"\x01"),
]

for label, topic, payload in cases:
    e = make_espnow()
    e.mqtt_on_message(None, None, FakeMsg(topic, payload))
    check(f"reject [{label}]: send NOT called", e.send.call_count == 0)

# also confirm parse returns None directly for each
for label, topic, payload in cases:
    e = make_espnow()
    check(f"parse None [{label}]", parse(e, topic, payload) is None)

# ---------------------------------------------------------------------------
print("\n--- Group 3b: ambiguous send prefix rejection (no send allowed) ---")

ambiguous_cases = [
    ("sendx prefix",        f"{BASE}/sendx/AABBCCDDEEFF",            b"\x01"),
    ("sender prefix",       f"{BASE}/sender/AABBCCDDEEFF",           b"\x01"),
    ("sendfoo prefix raw",  f"{BASE}/sendfoo/AABBCCDDEEFF",          b"\x01"),
    ("sendfoo prefix hex",  f"{BASE}/sendfoo/AABBCCDDEEFF/hex",      b"01 02"),
    ("sendable prefix raw", f"{BASE}/sendable/AABBCCDDEEFF",         b"\x01"),
    ("send_ prefix raw",    f"{BASE}/send_/AABBCCDDEEFF",            b"\x01"),
    ("send1 prefix hex",    f"{BASE}/send1/AABBCCDDEEFF/hex",        b"01 02"),
    ("no slash after send", f"{BASE}/sendAABBCCDDEEFF",              b"\x01"),
    ("no slash after send hex", f"{BASE}/sendAABBCCDDEEFF/hex",      b"01 02"),
]

for label, topic, payload in ambiguous_cases:
    e = make_espnow()
    e.mqtt_on_message(None, None, FakeMsg(topic, payload))
    check(f"ambiguous [{label}]: send NOT called", e.send.call_count == 0)

for label, topic, payload in ambiguous_cases:
    e = make_espnow()
    check(f"ambiguous parse None [{label}]", parse(e, topic, payload) is None)

# ---------------------------------------------------------------------------
print("\n--- Group 4: edge cases that SHOULD send ---")

# hex with mixed spaces/colons/newlines
e = make_espnow()
r = parse(e, f"{SEND}/AABBCCDDEEFF/hex", b"AA BB:CC\nDD")
check("hex: mixed whitespace+colons", r and r["msg"] == b"\xaa\xbb\xcc\xdd")

# raw with bytearray payload
e = make_espnow()
r = parse(e, f"{SEND}/AABBCCDDEEFF", bytearray(b"\x09\x08"))
check("raw: bytearray accepted", r and r["msg"] == b"\x09\x08")

# raw with str payload
e = make_espnow()
r = parse(e, f"{SEND}/AABBCCDDEEFF", "ping")
check("raw: str payload encoded", r and r["msg"] == b"ping")

# single byte hex
e = make_espnow()
r = parse(e, f"{SEND}/AABBCCDDEEFF/hex", b"0f")
check("hex: single byte", r and r["msg"] == b"\x0f")

# ---------------------------------------------------------------------------
print("\n--- Group 5: RX publish path unchanged ---")

e = make_espnow()
e.use_mqtt = True
e.mqtt_publish_raw = True
e.mqtt_publish_hex = True
e.mqtt_publish_json = False
e.mqtt_client = Mock()
e.mqtt_client.is_connected.return_value = True
e.packet = None

fake_packet = MagicMock()
fake_packet.type = 0
fake_packet.subtype = 13
fake_packet.addr2 = "aa:bb:cc:dd:ee:ff"
fake_packet.addr1 = "ff:ff:ff:ff:ff:ff"
fake_packet.__contains__ = lambda self, key: key == scapy.Raw
fake_packet.__getitem__ = lambda self, key: Mock(load=b"\x7f\x18\xfe\x34" + b"\x00" * 11 + b"payload")
raw_layer = Mock()
raw_layer.load = b"\x7f\x18\xfe\x34" + b"\x00" * 11 + b"payload"
fake_packet.__getitem__ = lambda self, key: raw_layer

e.parse_rx_packet(fake_packet)
pubs = e.mqtt_client.publish.call_args_list
raw_pubs = [c for c in pubs if "/raw" in c.args[0]]
hex_pubs = [c for c in pubs if "/hex" in c.args[0]]
check("RX publish: raw topic published", len(raw_pubs) == 1)
check("RX publish: hex topic published", len(hex_pubs) == 1)
if hex_pubs:
    check("RX publish: hex uses space-separated", hex_pubs[0].args[1].count(" ") > 0)

# empty msg_raw on RX still discarded
e2 = make_espnow()
e2.use_mqtt = True
e2.mqtt_publish_raw = True
e2.mqtt_client = Mock()
e2.mqtt_client.is_connected.return_value = True
fake_empty = MagicMock()
fake_empty.type = 0
fake_empty.subtype = 13
fake_empty.addr2 = "aa:bb:cc:dd:ee:ff"
fake_empty.addr1 = "ff:ff:ff:ff:ff:ff"
empty_raw = Mock()
empty_raw.load = b"\x7f\x18\xfe\x34" + b"\x00" * 11
fake_empty.__getitem__ = lambda self, key: empty_raw
fake_empty.__contains__ = lambda self, key: key == scapy.Raw
e2.parse_rx_packet(fake_empty)
check("RX publish: empty payload discarded (no publish)", e2.mqtt_client.publish.call_count == 0)

# ---------------------------------------------------------------------------
print("\n" + "=" * 64)
print(f"RESULTS: {passed} passed, {failed} failed")
print("=" * 64)
sys.exit(0 if failed == 0 else 1)
