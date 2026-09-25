"""Tests for AliasManager and device nickname functionality"""
import pytest
from passx.core.config import ConfigManager
from passx.core.identity import DeviceIdentity
from passx.core.aliases import AliasManager
from passx.discovery.beacon import PeerInfo
from passx.cli.main import build_parser


def test_alias_manager_crud(tmp_path):
    config = ConfigManager(config_dir=tmp_path)
    mgr = AliasManager(config)

    # Initial state
    assert mgr.list_aliases() == []
    assert mgr.get_alias("dev-1") is None

    # Set nickname by device_id
    mgr.set_alias("IQOO-NEO-10", "My Phone", device_id="dev-1", fingerprint="fp123")
    assert mgr.get_alias("dev-1") == "My Phone"
    assert mgr.get_alias("IQOO-NEO-10") == "My Phone"

    # Display name helper
    assert mgr.get_display_name("dev-1", "IQOO-NEO-10") == "My Phone (IQOO-NEO-10)"
    assert mgr.get_display_name("unknown-id", "Some-PC") == "Some-PC"

    # Resolve target
    resolved = mgr.resolve_target("My Phone")
    assert resolved is not None
    assert resolved["nickname"] == "My Phone"
    assert resolved["target"] == "IQOO-NEO-10"

    # List aliases
    all_aliases = mgr.list_aliases()
    assert len(all_aliases) == 1
    assert all_aliases[0]["nickname"] == "My Phone"

    # Remove alias
    removed = mgr.remove_alias("My Phone")
    assert removed is True
    assert mgr.get_alias("dev-1") is None
    assert mgr.list_aliases() == []


def test_peer_info_display_name():
    p = PeerInfo(
        device_id="id-1",
        device_name="DESKTOP-ABC",
        platform="windows",
        ip="192.168.1.50",
        port=42425,
        fingerprint="fp...",
    )
    assert p.display_name == "DESKTOP-ABC"

    p.nickname = "Work PC"
    assert p.display_name == "Work PC (DESKTOP-ABC)"


def test_rename_parser():
    parser = build_parser()

    # rename remote device
    args = parser.parse_args(["rename", "IQOO-NEO-10", "My Phone"])
    assert args.command == "rename"
    assert args.target == "IQOO-NEO-10"
    assert args.nickname == "My Phone"

    # rename self
    args = parser.parse_args(["rename", "--self", "Laptop"])
    assert args.command == "rename"
    assert getattr(args, "self") is True
    assert args.target == "Laptop"

    # list aliases
    args = parser.parse_args(["rename", "--list"])
    assert args.command == "rename"
    assert args.list is True

    # remove alias
    args = parser.parse_args(["alias", "--remove", "My Phone"])
    assert args.command == "alias"
    assert args.remove is True
    assert args.target == "My Phone"

    # nickname command
    args = parser.parse_args(["nickname", "192.168.1.100", "Living Room TV"])
    assert args.command == "nickname"
    assert args.target == "192.168.1.100"
    assert args.nickname == "Living Room TV"


def test_alias_manager_with_ip(tmp_path):
    config = ConfigManager(config_dir=tmp_path)
    mgr = AliasManager(config)

    # Set nickname with explicit IP
    mgr.set_alias("Pixel-7", "My Phone", device_id="dev-2", ip="192.168.1.105")
    resolved = mgr.resolve_target("My Phone")
    assert resolved is not None
    assert resolved["ip"] == "192.168.1.105"

    # Set nickname where target is an IP
    mgr.set_alias("192.168.1.200", "Printer")
    printer = mgr.resolve_target("Printer")
    assert printer is not None
    assert printer["ip"] == "192.168.1.200"


def test_get_primary_ip():
    from passx.network.interfaces import get_primary_ip
    ip = get_primary_ip()
    assert isinstance(ip, str)
    assert len(ip.split(".")) == 4
