from ESPythoNOW import *
import struct
import collections


def wizmote_callback(from_mac, to_mac, data):
    print("Wizmote:", from_mac, data)


def custom_callback(from_mac, to_mac, data):
    print("Custom:", from_mac, data)


def custom_sensor_callback(from_mac, to_mac, data):
    print("Custom Sensor:", from_mac, data)


if __name__ == "__main__":
    espnow = ESPythoNow(interface="wlan1", accept_all=True, set_interface=False)

    # 1. Register by built-in decoder name
    espnow.add_signature("wizmote", wizmote_callback, data="dict", dedupe=15)

    # 2. Register by passing custom profile dict directly
    custom_profile = {
        "name": "my_custom_device",
        "struct": "<BIBBBBBBBB4s",
        "vars": ["type", "sequence", "dt1", "_0", "_1", "_2", "motion", "_3", "_4", "_5", "ccm"],
        "dict": {"motion": {0x0b: True, 0x19: True, 0x0a: False, 0x18: False}},
        "signature": {"length": 17, "bytes": {0: 0x81, 5: 0x42}}
    }
    espnow.add_signature(custom_profile, custom_callback, data="json", dedupe=20)

    # 3. Register another custom device with dedupe disabled
    custom_sensor = {
        "name": "temp_humidity_sensor",
        "struct": "<ff",
        "vars": ["temperature", "humidity"],
        "dict": {"temperature": True, "humidity": True},
        "signature": {"length": 8, "bytes": {0: 0x01}}
    }
    espnow.add_signature(custom_sensor, custom_sensor_callback, data="dict", dedupe=False)

    # Verify decoders are registered
    print("Registered decoders:", list(espnow.decoders.keys()))

    # Verify dedupe configurations
    for name, dec in espnow.decoders.items():
        dedupe_val = dec.get("dedupe", "NOT SET")
        recent_val = dec.get("recent", "NOT SET")
        recent_len = recent_val.maxlen if hasattr(recent_val, 'maxlen') else "N/A"
        print(f"  {name}: dedupe={dedupe_val}, recent maxlen={recent_len}")

    # espnow.start()
    # input()  # Run until enter is pressed
