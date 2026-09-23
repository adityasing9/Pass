"""End-to-end integration tests for direct P2P TLS transfers"""
import os
import shutil
import tempfile
import time
from pathlib import Path
import pytest

from passx.core.config import ConfigManager
from passx.core.identity import DeviceIdentity
from passx.core.trust import TrustManager
from passx.transfer.manifest import build_manifest_from_paths
from passx.transfer.receiver import ReceiverServer
from passx.transfer.resume import ResumeManager
from passx.transfer.sender import TransferSender, TransferRejected, PeerVerificationError


@pytest.fixture
def node_pair():
    dir_a = tempfile.mkdtemp(prefix="pass_node_a_")
    dir_b = tempfile.mkdtemp(prefix="pass_node_b_")
    
    cfg_a = ConfigManager(Path(dir_a) / "config")
    cfg_a.download_dir = Path(dir_a) / "downloads"
    id_a = DeviceIdentity(cfg_a)
    trust_a = TrustManager(cfg_a)

    cfg_b = ConfigManager(Path(dir_b) / "config")
    cfg_b.download_dir = Path(dir_b) / "downloads"
    id_b = DeviceIdentity(cfg_b)
    trust_b = TrustManager(cfg_b)

    receiver = ReceiverServer(
        config=cfg_b,
        identity=id_b,
        trust_manager=trust_b,
        bind_host="127.0.0.1",
        port=0,  # dynamic port
    )
    receiver.start()
    time.sleep(0.1)

    sender = TransferSender(config=cfg_a, identity=id_a, trust_manager=trust_a)

    yield {
        "dir_a": Path(dir_a),
        "dir_b": Path(dir_b),
        "cfg_a": cfg_a,
        "cfg_b": cfg_b,
        "id_a": id_a,
        "id_b": id_b,
        "receiver": receiver,
        "sender": sender,
    }

    receiver.stop()
    shutil.rmtree(dir_a, ignore_errors=True)
    shutil.rmtree(dir_b, ignore_errors=True)


def test_transfer_single_file(node_pair):
    sender = node_pair["sender"]
    receiver = node_pair["receiver"]
    id_b = node_pair["id_b"]
    dir_a = node_pair["dir_a"]
    dir_b = node_pair["dir_b"]

    # Create 500 KB test file
    test_file = dir_a / "test_data.bin"
    content = b"P2P-PASS-BINARY-DATA-CHUNK" * 20000
    test_file.write_bytes(content)

    manifest = build_manifest_from_paths([test_file])
    success = sender.send(
        peer_ip="127.0.0.1",
        peer_port=receiver.actual_port,
        peer_fingerprint=id_b.fingerprint,
        manifest=manifest,
    )
    assert success is True

    # Verify received file
    received_file = node_pair["cfg_b"].download_dir / "test_data.bin"
    assert received_file.exists()
    assert received_file.read_bytes() == content


def test_transfer_directory_structure(node_pair):
    sender = node_pair["sender"]
    receiver = node_pair["receiver"]
    id_b = node_pair["id_b"]
    dir_a = node_pair["dir_a"]

    # Create folder structure
    proj_dir = dir_a / "my_code"
    proj_dir.mkdir()
    (proj_dir / "main.py").write_text("print('hello')")
    sub = proj_dir / "pkg"
    sub.mkdir()
    (sub / "mod.py").write_text("x = 42")

    manifest = build_manifest_from_paths([proj_dir])
    success = sender.send(
        peer_ip="127.0.0.1",
        peer_port=receiver.actual_port,
        peer_fingerprint=id_b.fingerprint,
        manifest=manifest,
    )
    assert success is True

    # Verify directory structure preserved
    dl_dir = node_pair["cfg_b"].download_dir
    assert (dl_dir / "my_code" / "main.py").read_text() == "print('hello')"
    assert (dl_dir / "my_code" / "pkg" / "mod.py").read_text() == "x = 42"


def test_peer_fingerprint_mismatch_rejected(node_pair):
    sender = node_pair["sender"]
    receiver = node_pair["receiver"]
    dir_a = node_pair["dir_a"]

    test_file = dir_a / "secret.txt"
    test_file.write_text("confidential")
    manifest = build_manifest_from_paths([test_file])

    # Wrong fingerprint must abort transfer immediately
    with pytest.raises(PeerVerificationError):
        sender.send(
            peer_ip="127.0.0.1",
            peer_port=receiver.actual_port,
            peer_fingerprint="0000000000000000000000000000000000000000000000000000000000000000",
            manifest=manifest,
        )


def test_transfer_rejection_by_receiver(node_pair):
    receiver = node_pair["receiver"]
    sender = node_pair["sender"]
    id_b = node_pair["id_b"]
    dir_a = node_pair["dir_a"]

    # Set callback to reject
    receiver.on_request_callback = lambda sender_info, manifest: False

    test_file = dir_a / "file.txt"
    test_file.write_text("hello")
    manifest = build_manifest_from_paths([test_file])

    with pytest.raises(TransferRejected):
        sender.send(
            peer_ip="127.0.0.1",
            peer_port=receiver.actual_port,
            peer_fingerprint=id_b.fingerprint,
            manifest=manifest,
        )


def test_resumable_transfer(node_pair):
    sender = node_pair["sender"]
    receiver = node_pair["receiver"]
    id_b = node_pair["id_b"]
    dir_a = node_pair["dir_a"]
    cfg_b = node_pair["cfg_b"]

    # 100 KB payload
    full_content = b"RESUME-CHUNK-DATA-" * 5000
    test_file = dir_a / "resumable.bin"
    test_file.write_bytes(full_content)
    total_size = len(full_content)

    # Pre-create partial state simulating interrupted transfer of 30,000 bytes
    dest_path = cfg_b.download_dir / "resumable.bin"
    partial_path, _ = ResumeManager.get_partial_paths(dest_path)
    partial_path.parent.mkdir(parents=True, exist_ok=True)
    partial_path.write_bytes(full_content[:30000])

    ResumeManager.save_checkpoint(
        dest_path,
        transfer_id="res-tx-1",
        relative_path="resumable.bin",
        total_size=total_size,
        received_bytes=30000,
    )

    manifest = build_manifest_from_paths([test_file])
    success = sender.send(
        peer_ip="127.0.0.1",
        peer_port=receiver.actual_port,
        peer_fingerprint=id_b.fingerprint,
        manifest=manifest,
    )
    assert success is True

    # Check complete file
    assert dest_path.exists()
    assert dest_path.stat().st_size == total_size
    assert dest_path.read_bytes() == full_content
