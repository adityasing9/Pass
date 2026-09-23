"""Tests for config, device identity, and trust manager"""
import os
import shutil
import tempfile
from pathlib import Path
import pytest

from passx.core.config import ConfigManager
from passx.core.identity import DeviceIdentity
from passx.core.trust import TrustManager


@pytest.fixture
def temp_config_dir():
    temp_dir = tempfile.mkdtemp(prefix="pass_test_config_")
    yield Path(temp_dir)
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_config_defaults(temp_config_dir):
    cfg = ConfigManager(temp_config_dir)
    assert cfg.discovery_port == 42424
    assert cfg.transfer_port == 42425
    assert cfg.chunk_size == 1024 * 1024
    assert len(cfg.device_name) > 0
    assert cfg.download_dir.exists()


def test_config_set_and_load(temp_config_dir):
    cfg = ConfigManager(temp_config_dir)
    cfg.device_name = "TEST-PC-CUSTOM"
    assert cfg.device_name == "TEST-PC-CUSTOM"

    # Reload from disk
    cfg2 = ConfigManager(temp_config_dir)
    assert cfg2.device_name == "TEST-PC-CUSTOM"


def test_device_identity_and_certs(temp_config_dir):
    cfg = ConfigManager(temp_config_dir)
    ident = DeviceIdentity(cfg)

    assert len(ident.device_id) == 36  # UUID length
    assert len(ident.fingerprint) == 64  # SHA256 hex length
    assert ident.cert_file.exists()
    assert ident.key_file.exists()

    # Re-initialization should preserve the same device ID and certificates
    ident2 = DeviceIdentity(cfg)
    assert ident2.device_id == ident.device_id
    assert ident2.fingerprint == ident.fingerprint


def test_trust_manager(temp_config_dir):
    cfg = ConfigManager(temp_config_dir)
    trust = TrustManager(cfg)

    dev_id = "test-uuid-1234"
    fingerprint = "abcdef0123456789"

    assert not trust.is_trusted(dev_id, fingerprint)

    trust.trust_device(dev_id, "TEST-PEER", fingerprint)
    assert trust.is_trusted(dev_id, fingerprint)
    # Wrong fingerprint must fail
    assert not trust.is_trusted(dev_id, "wrongfingerprint")

    trusted_list = trust.list_trusted()
    assert len(trusted_list) == 1
    assert trusted_list[0]["device_id"] == dev_id
    assert trusted_list[0]["device_name"] == "TEST-PEER"

    # Untrust
    assert trust.untrust_device("TEST-PEER")
    assert not trust.is_trusted(dev_id, fingerprint)
