Work in progress



---
Selecting an Interface
---
Start ESPythoNOW with no interface specified.

Check logs for

```
[ESPythoNOW] Home Assistant mode
Interface must be specified.
Available Interface(s)
	wlp2s0
Unavailable Interface(s)
```

Copy the available Interface to the "Wireless Interface" in the configuration menu. (wlp2s0 in this case)

Restart ESPythoNOW.

Check Logs again.

*NOTE*
* Wireless Interface must support monitor mode.
* Performance and advanced options dependent on driver/interface.




---
MQTT
---
ESPythoNOW bridges ESP-NOW and MQTT. The base topic defaults to `ESPythoNOW-<local_mac>` (or the configured `base_topic`).

* Received ESP-NOW messages are published to `<base_topic>/<sender_mac>/<receiver_mac>`:
  * `/raw` - raw bytes
  * `/hex` - space-separated hex text, e.g. `de ad be ef`
  * `/json` - decoded JSON if a matching decoder exists
* Received messages with empty payloads are discarded.

Sending ESP-NOW messages from MQTT:
* Subscribe to `<base_topic>/send/#`.
* Publish a message to one of the send topics below and it will be forwarded to the target ESP-NOW peer over the air:

| Send topic | Payload | Behavior |
| --- | --- | --- |
| `<base_topic>/send/<mac>` | raw bytes | Payload bytes are sent to `<mac>` verbatim. |
| `<base_topic>/send/<mac>/hex` | hex text | Hex text is decoded to bytes (spaces and colons tolerated) and sent to `<mac>`. |

* `<mac>` may be in `AA:BB:CC:DD:EE:FF` or `AABBCCDDEEFF` form.
* To send a message, publish message to `<base_topic>/send/<mac>` (raw) or `<base_topic>/send/<mac>/hex` (hex text).
* **Exact topic match required.** The `send` segment must end with `/`. Topics such as `<base_topic>/sendx/<mac>`, `<base_topic>/sender/<mac>`, `<base_topic>/sendfoo/<mac>/hex`, or any variant that appends characters before the next `/` are NOT recognized and will be silently ignored.

Invalid inputs are silently rejected and will NOT trigger an ESP-NOW send:
* Empty payload
* Invalid MAC address
* Invalid hex text (non-hex characters or odd length)
* Topics that do not **exactly** match the `<base_topic>/send/<mac>` or `<base_topic>/send/<mac>/hex` convention (including ambiguous send-prefix variants like `sendx`, `sender`, `sendfoo`)

