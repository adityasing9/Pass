"""CLI command and argument parsing tests"""
import os
import tempfile
from pathlib import Path
import pytest
from passx.cli.main import main, build_parser


def test_cli_parser_defaults():
    parser = build_parser()
    args = parser.parse_args(["version"])
    assert args.command == "version"

    args = parser.parse_args(["status"])
    assert args.command == "status"

    args = parser.parse_args(["devices"])
    assert args.command == "devices"

    args = parser.parse_args(["update"])
    assert args.command == "update"

    args = parser.parse_args(["send", "test.txt", "--to", "LINUX-PC", "--turbo"])
    assert args.command == "send"
    assert args.paths == ["test.txt"]
    assert args.to == "LINUX-PC"
    assert args.turbo is True

    args = parser.parse_args(["receive", "--dir", "my_dl", "-y"])
    assert args.command == "receive"
    assert args.dir == "my_dl"
    assert args.yes is True

    args = parser.parse_args(["pair", "192.168.1.105"])
    assert args.command == "pair"
    assert args.target == "192.168.1.105"

    args = parser.parse_args(["daemon", "status"])
    assert args.command == "daemon"
    assert args.action == "status"

    args = parser.parse_args(["auto-accept", "on"])
    assert args.command == "auto-accept"
    assert args.state == "on"


def test_cli_version_execution(capsys):
    ret = main(["version"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "PASS (passx) version" in captured.out


def test_cli_status_execution(capsys):
    ret = main(["status"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "Device Information:" in captured.out
    assert "Discovery Port:" in captured.out


def test_cli_trust_untrust(capsys):
    ret = main(["trust"])
    assert ret == 0

    # Untrust non-existent
    ret = main(["untrust", "non-existent-device-xyz"])
    assert ret == 1


def test_cli_auto_accept(capsys):
    ret = main(["auto-accept", "on"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "Auto-accept enabled" in captured.out

    ret = main(["auto-accept", "off"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "Auto-accept disabled" in captured.out


def test_cli_daemon_status(capsys):
    ret = main(["daemon", "status"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "Background Receiver" in captured.out
