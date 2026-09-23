"""Tests for UDP discovery packets, encoding, and peer registry"""
import time
import pytest
from passx.discovery.beacon import (
    DISCOVERY_MAGIC,
    PROTOCOL_VERSION,
    PeerInfo,
    encode_discovery_message,
    decode_discovery_message,
)


def test_discovery_encode_decode():
    payload = {
        "device_id": "test-device-1234",
        "device_name": "UBUNTU-TEST",
        "platform": "linux",
        "port": 42425,
        "fingerprint": "a1b2c3d4e5f6",
        "capabilities": ["tls1.3", "resume"],
    }
    raw = encode_discovery_message("BEACON", payload)
    assert raw.startswith(DISCOVERY_MAGIC)

    decoded = decode_discovery_message(raw)
    assert decoded is not None
    assert decoded["magic"] == "PASS"
    assert decoded["version"] == PROTOCOL_VERSION
    assert decoded["msg_type"] == "BEACON"
    assert decoded["device_id"] == "test-device-1234"
    assert decoded["device_name"] == "UBUNTU-TEST"
    assert decoded["platform"] == "linux"
    assert decoded["port"] == 42425
    assert decoded["fingerprint"] == "a1b2c3d4e5f6"


def test_discovery_decode_invalid():
    # Corrupt magic
    assert decode_discovery_message(b"FAIL{}") is None
    # Empty
    assert decode_discovery_message(b"") is None
    # Short
    assert decode_discovery_message(b"PAS") is None
    # Invalid JSON
    assert decode_discovery_message(b"PASS{broken json") is None
    # Missing magic in json
    assert decode_discovery_message(b'PASS{"magic":"OTHER","version":1}') is None
    # Version mismatch
    assert decode_discovery_message(b'PASS{"magic":"PASS","version":999}') is None


def test_peer_info_expiration():
    peer = PeerInfo(
        device_id="dev-1",
        device_name="DESKTOP-1",
        platform="windows",
        ip="192.168.1.10",
        port=42425,
        fingerprint="fp123",
        last_seen=time.time() - 10.0,
    )
    assert peer.is_expired(ttl_seconds=5.0)

    peer.last_seen = time.time()
    assert not peer.is_expired(ttl_seconds=5.0)
