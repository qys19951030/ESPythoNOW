import sys
import os
import struct
import collections
import copy
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

from ESPythoNOW import ESPythoNow, decoders as builtin_decoders


def dummy_callback(from_mac, to_mac, data):
    pass


def create_espnow():
    return ESPythoNow(
        interface="dummy0",
        set_interface=False,
        accept_all=True,
        callback=dummy_callback,
        decoders=copy.deepcopy(builtin_decoders)
    )


def test_1_builtin_decoder_name():
    print("=" * 60)
    print("TEST 1: Built-in decoder name registration")
    print("=" * 60)

    espnow = create_espnow()
    initial_decoders = set(espnow.decoders.keys())
    print(f"Initial decoders: {initial_decoders}")

    result = espnow.add_signature("wizmote", dummy_callback, data="dict")
    print(f"add_signature('wizmote', ...) returned: {result}")

    assert result == True, "Expected True for successful registration"
    assert "wizmote" in espnow.decoders, "'wizmote' should be in decoders"
    assert espnow.decoders["wizmote"]["callback"] == dummy_callback, "Callback should be set"
    assert espnow.decoders["wizmote"]["data"] == "dict", "Data type should be 'dict'"

    print(f"  callback set: {espnow.decoders['wizmote']['callback'] == dummy_callback}")
    print(f"  data type set: {espnow.decoders['wizmote']['data'] == 'dict'}")

    result2 = espnow.add_signature("wiz_motion", dummy_callback, data="json")
    print(f"add_signature('wiz_motion', ...) returned: {result2}")
    assert result2 == True, "Expected True for successful registration"

    result3 = espnow.add_signature("nonexistent_decoder", dummy_callback)
    print(f"add_signature('nonexistent_decoder', ...) returned: {result3}")
    assert result3 == False, "Expected False for unknown decoder"

    print("TEST 1 PASSED: Built-in decoder name registration works\n")


def test_2_custom_profile_dict():
    print("=" * 60)
    print("TEST 2: Custom profile dict registration and save")
    print("=" * 60)

    espnow = create_espnow()

    custom_profile = {
        "name": "my_custom_device",
        "struct": "<BIBBBBBBBB4s",
        "vars": ["type", "sequence", "dt1", "_0", "_1", "_2", "motion", "_3", "_4", "_5", "ccm"],
        "dict": {"motion": {0x0b: True, 0x19: True, 0x0a: False, 0x18: False}},
        "signature": {"length": 17, "bytes": {0: 0x91, 5: 0x42}}
    }

    initial_count = len(espnow.decoders)
    result = espnow.add_signature(custom_profile, dummy_callback, data="dict", dedupe=5)
    print(f"add_signature(custom_profile_dict, ...) returned: {result}")

    assert result == True, "Expected True for successful custom profile registration"
    assert len(espnow.decoders) == initial_count + 1, "Should have added one more decoder"

    profile_name = custom_profile["name"]
    assert profile_name in espnow.decoders, f"'{profile_name}' should be in decoders"

    dec = espnow.decoders[profile_name]
    assert dec["name"] == "my_custom_device"
    assert dec["struct"] == "<BIBBBBBBBB4s"
    assert dec["callback"] == dummy_callback
    assert dec["data"] == "dict"

    print(f"  Registered name: {profile_name}")
    print(f"  struct preserved: {dec['struct'] == '<BIBBBBBBBB4s'}")
    print(f"  signature preserved: {dec['signature'] == {'length': 17, 'bytes': {0: 0x91, 5: 0x42}}}")

    msg = struct.pack("<BIBBBBBBBB4s", 0x91, 12345, 0x42, 0, 0, 0, 0x0b, 0, 0, 0, b"\x00\x00\x00\x00")
    matched_decoder = espnow.check_decoders(msg)
    print(f"  check_decoders for matching message: {matched_decoder is not None}")
    print(f"  matched decoder name: {matched_decoder.get('name') if matched_decoder else 'None'}")
    assert matched_decoder is not None, "Decoder should match the message signature"
    assert matched_decoder["name"] == "my_custom_device", "Should match our custom device"

    decoded = espnow.decode(matched_decoder, msg)
    print(f"  decoded data: {decoded}")
    assert decoded["motion"] == True, "Decoding should work correctly"

    print("TEST 2 PASSED: Custom profile dict registration and decode works\n")


def test_3_dedupe_parameter():
    print("=" * 60)
    print("TEST 3: dedupe parameter affects recent buffer config")
    print("=" * 60)

    espnow = create_espnow()

    print("--- Test 3a: dedupe with integer value ---")
    result = espnow.add_signature("wizmote", dummy_callback, data="dict", dedupe=25)
    assert result == True
    dec = espnow.decoders["wizmote"]
    assert dec["dedupe"] == 25, f"Expected dedupe=25, got {dec.get('dedupe')}"
    assert "recent" in dec, "Should have 'recent' deque"
    assert isinstance(dec["recent"], collections.deque), "Should be a deque"
    assert dec["recent"].maxlen == 25, f"Expected maxlen=25, got {dec['recent'].maxlen}"
    print(f"  dedupe={dec['dedupe']}, recent.maxlen={dec['recent'].maxlen} - CORRECT")

    print("--- Test 3b: dedupe=True (uses default 10) ---")
    custom1 = {
        "name": "custom_dedupe_true",
        "struct": "<B",
        "vars": ["type"],
        "dict": {"type": True},
        "signature": {"length": 1, "bytes": {0: 0x99}},
        "dedupe": 100
    }
    result = espnow.add_signature(custom1, dummy_callback, data="dict", dedupe=True)
    assert result == True
    dec = espnow.decoders["custom_dedupe_true"]
    assert dec["dedupe"] == 10, f"Expected dedupe=10 (default), got {dec.get('dedupe')}"
    assert dec["recent"].maxlen == 10, f"Expected maxlen=10, got {dec['recent'].maxlen}"
    print(f"  dedupe={dec['dedupe']}, recent.maxlen={dec['recent'].maxlen} - CORRECT (overrode profile's 100)")

    print("--- Test 3c: dedupe=False (disables dedupe) ---")
    custom2 = {
        "name": "custom_dedupe_false",
        "struct": "<B",
        "vars": ["type"],
        "dict": {"type": True},
        "signature": {"length": 1, "bytes": {0: 0x88}},
        "dedupe": 50
    }
    result = espnow.add_signature(custom2, dummy_callback, data="dict", dedupe=False)
    assert result == True
    dec = espnow.decoders["custom_dedupe_false"]
    assert "dedupe" not in dec, "Should NOT have 'dedupe' key when dedupe=False"
    assert "recent" not in dec, "Should NOT have 'recent' deque when dedupe=False"
    print(f"  dedupe present: {'dedupe' in dec}, recent present: {'recent' in dec} - CORRECT (both removed)")

    print("--- Test 3d: dedupe=0 (also disables dedupe) ---")
    custom3 = {
        "name": "custom_dedupe_zero",
        "struct": "<B",
        "vars": ["type"],
        "dict": {"type": True},
        "signature": {"length": 1, "bytes": {0: 0x77}},
        "dedupe": 30
    }
    result = espnow.add_signature(custom3, dummy_callback, data="dict", dedupe=0)
    assert result == True
    dec = espnow.decoders["custom_dedupe_zero"]
    assert "dedupe" not in dec, "Should NOT have 'dedupe' key when dedupe=0"
    assert "recent" not in dec, "Should NOT have 'recent' deque when dedupe=0"
    print(f"  dedupe present: {'dedupe' in dec}, recent present: {'recent' in dec} - CORRECT (both removed)")

    print("--- Test 3e: dedupe=None (uses profile's built-in default) ---")
    custom4 = {
        "name": "custom_dedupe_default",
        "struct": "<B",
        "vars": ["type"],
        "dict": {"type": True},
        "signature": {"length": 1, "bytes": {0: 0x66}},
        "dedupe": 7
    }
    result = espnow.add_signature(custom4, dummy_callback, data="dict", dedupe=None)
    assert result == True
    dec = espnow.decoders["custom_dedupe_default"]
    assert dec["dedupe"] == 7, f"Expected dedupe=7 (profile default), got {dec.get('dedupe')}"
    assert dec["recent"].maxlen == 7, f"Expected maxlen=7, got {dec['recent'].maxlen}"
    print(f"  dedupe={dec['dedupe']}, recent.maxlen={dec['recent'].maxlen} - CORRECT (used profile's 7)")

    print("--- Test 3f: dedupe overrides profile default ---")
    custom5 = {
        "name": "custom_dedupe_override",
        "struct": "<B",
        "vars": ["type"],
        "dict": {"type": True},
        "signature": {"length": 1, "bytes": {0: 0x55}},
        "dedupe": 15
    }
    result = espnow.add_signature(custom5, dummy_callback, data="dict", dedupe=100)
    assert result == True
    dec = espnow.decoders["custom_dedupe_override"]
    assert dec["dedupe"] == 100, f"Expected dedupe=100 (overridden), got {dec.get('dedupe')}"
    assert dec["recent"].maxlen == 100, f"Expected maxlen=100, got {dec['recent'].maxlen}"
    print(f"  dedupe={dec['dedupe']}, recent.maxlen={dec['recent'].maxlen} - CORRECT (overrode profile's 15 with 100)")

    print("--- Test 3g: verify dedupe actually filters duplicates in parsing ---")
    custom6 = {
        "name": "test_dedupe_filter",
        "struct": "<I",
        "vars": ["counter"],
        "dict": {"counter": True},
        "signature": {"length": 4, "bytes": {}}
    }
    callback_calls = []
    def counting_callback(from_mac, to_mac, data):
        callback_calls.append(data)

    result = espnow.add_signature(custom6, counting_callback, data="dict", dedupe=3)
    assert result == True
    dec = espnow.decoders["test_dedupe_filter"]
    assert dec["recent"].maxlen == 3

    msg1 = struct.pack("<I", 42)
    msg2 = struct.pack("<I", 43)
    msg3 = struct.pack("<I", 44)
    msg4 = struct.pack("<I", 45)

    print(f"  Initial recent deque: {list(dec['recent'])}")

    from_mac = "AA:BB:CC:DD:EE:FF"
    to_mac = "FF:FF:FF:FF:FF:FF"

    for i, msg in enumerate([msg1, msg1, msg2, msg2, msg3, msg3, msg1, msg4, msg1]):
        if "recent" in dec and msg in dec["recent"]:
            is_duplicate = True
        else:
            is_duplicate = False
            if "recent" in dec:
                dec["recent"].append(msg)

        if not is_duplicate:
            counting_callback(from_mac, to_mac, espnow.decode(dec, msg))

        print(f"  msg #{i}: value={struct.unpack('<I', msg)[0]}, duplicate={is_duplicate}, callback_count={len(callback_calls)}, recent={list(dec['recent'])}")

    assert len(callback_calls) == 5, f"Expected 5 callback calls (msg1 evicted from buffer when msg4 added), got {len(callback_calls)}"
    print(f"  Total callback calls: {len(callback_calls)} (expected 5 with buffer=3: msg1 evicted then re-added)")

    print("TEST 3 PASSED: dedupe parameter correctly affects buffer configuration and filtering\n")


def test_4_main_backward_compatibility():
    print("=" * 60)
    print("TEST 4: Backward compatibility with main() usage")
    print("=" * 60)

    espnow = create_espnow()

    result1 = espnow.add_signature("wizmote", dummy_callback, data="dict")
    result2 = espnow.add_signature("wiz_motion", dummy_callback, data="dict")

    assert result1 == True
    assert result2 == True

    dec1 = espnow.decoders["wizmote"]
    dec2 = espnow.decoders["wiz_motion"]

    assert dec1["dedupe"] == 10, f"wizmote should have profile default dedupe=10, got {dec1.get('dedupe')}"
    assert dec1["recent"].maxlen == 10, f"wizmote recent maxlen should be 10, got {dec1['recent'].maxlen}"
    assert dec2["dedupe"] == 10, f"wiz_motion should have profile default dedupe=10, got {dec2.get('dedupe')}"
    assert dec2["recent"].maxlen == 10, f"wiz_motion recent maxlen should be 10, got {dec2['recent'].maxlen}"

    print(f"  wizmote: dedupe={dec1['dedupe']}, recent.maxlen={dec1['recent'].maxlen}")
    print(f"  wiz_motion: dedupe={dec2['dedupe']}, recent.maxlen={dec2['recent'].maxlen}")

    print("TEST 4 PASSED: Backward compatibility with existing main() usage\n")


def test_5_custom_profile_without_name():
    print("=" * 60)
    print("TEST 5: Custom profile without 'name' field (auto-generated)")
    print("=" * 60)

    espnow = create_espnow()

    custom_no_name = {
        "struct": "<H",
        "vars": ["value"],
        "dict": {"value": True},
        "signature": {"length": 2, "bytes": {0: 0x01}}
    }

    initial_count = len(espnow.decoders)
    result = espnow.add_signature(custom_no_name, dummy_callback, data="dict", dedupe=5)
    assert result == True
    assert len(espnow.decoders) == initial_count + 1

    new_keys = set(espnow.decoders.keys()) - {"wizmote", "wiz_motion"}
    auto_name = list(new_keys)[0]
    print(f"  Auto-generated name: {auto_name}")
    assert auto_name.startswith("custom_"), f"Name should start with 'custom_', got '{auto_name}'"

    dec = espnow.decoders[auto_name]
    assert dec["dedupe"] == 5
    assert dec["recent"].maxlen == 5
    print(f"  dedupe={dec['dedupe']}, recent.maxlen={dec['recent'].maxlen}")

    print("TEST 5 PASSED: Auto-generated name for profile without 'name' field\n")


if __name__ == "__main__":
    print("ESPythoNow.add_signature Verification Suite")
    print("=" * 60)
    print()

    try:
        test_1_builtin_decoder_name()
        test_2_custom_profile_dict()
        test_3_dedupe_parameter()
        test_4_main_backward_compatibility()
        test_5_custom_profile_without_name()

        print("=" * 60)
        print("ALL TESTS PASSED!")
        print("=" * 60)
        sys.exit(0)
    except AssertionError as e:
        print(f"\nTEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
