"""Tests for terminal chat (WhatsApp mode) and ChatStore"""
import time
from pathlib import Path
from passx.core.config import ConfigManager
from passx.core.identity import DeviceIdentity
from passx.core.trust import TrustManager
from passx.core.chat_store import ChatStore
from passx.core.chat_client import send_chat
from passx.protocol.messages import make_chat_msg, make_chat_ack, MSG_CHAT, MSG_CHAT_ACK
from passx.transfer.receiver import ReceiverServer


def test_chat_protocol_messages():
    msg = make_chat_msg(
        sender_id="dev-1",
        sender_name="Alice-Phone",
        fingerprint="fp123",
        text="Hello world!",
    )
    assert msg["action"] == MSG_CHAT
    assert msg["sender_id"] == "dev-1"
    assert msg["sender_name"] == "Alice-Phone"
    assert msg["text"] == "Hello world!"
    assert "timestamp" in msg

    ack = make_chat_ack(msg["msg_id"], status="DELIVERED", device_id="dev-2", device_name="Bob-PC")
    assert ack["action"] == MSG_CHAT_ACK
    assert ack["status"] == "DELIVERED"
    assert ack["device_id"] == "dev-2"


def test_chat_store_persistence(tmp_path):
    config = ConfigManager(config_dir=tmp_path)
    store = ChatStore(config)

    # Save outgoing message
    store.save_message("peer-1", "Bob", "me", "Hey Bob!")
    # Save incoming message
    store.save_message("peer-1", "Bob", "peer", "Hey Alice, how are you?")

    history = store.get_history("peer-1")
    assert len(history) == 2
    assert history[0]["sender"] == "me"
    assert history[0]["text"] == "Hey Bob!"
    assert history[1]["sender"] == "peer"
    assert history[1]["text"] == "Hey Alice, how are you?"

    # List conversations
    convs = store.list_conversations()
    assert len(convs) == 1
    assert convs[0]["peer_name"] == "Bob"
    assert convs[0]["message_count"] == 2
    assert convs[0]["last_message"] == "Hey Alice, how are you?"

    # Clear history
    store.clear_history("peer-1")
    assert len(store.get_history("peer-1")) == 0


def test_chat_store_message_limit(tmp_path):
    config = ConfigManager(config_dir=tmp_path)
    store = ChatStore(config)

    # Save 520 messages, should cap at 500
    for i in range(520):
        store.save_message("peer-2", "Charlie", "me", f"Message {i}")

    history = store.get_history("peer-2", limit=600)
    assert len(history) == 500
    assert history[-1]["text"] == "Message 519"
    assert history[0]["text"] == "Message 20"


def test_end_to_end_chat(tmp_path):
    """Test full P2P TLS chat message sending and receipt"""
    recv_dir = tmp_path / "receiver"
    send_dir = tmp_path / "sender"

    recv_config = ConfigManager(config_dir=recv_dir)
    recv_identity = DeviceIdentity(recv_config)
    recv_trust = TrustManager(recv_config)

    send_config = ConfigManager(config_dir=send_dir)
    send_identity = DeviceIdentity(send_config)
    send_trust = TrustManager(send_config)

    receiver = ReceiverServer(recv_config, recv_identity, recv_trust, port=0)
    receiver.start()
    time.sleep(0.2)
    port = receiver.actual_port

    try:
        ok, status, saved = send_chat(
            peer_ip="127.0.0.1",
            peer_port=port,
            text="Hello from sender!",
            config=send_config,
            identity=send_identity,
            trust_manager=send_trust,
            peer_id=recv_identity.device_id,
            peer_name=recv_identity.device_name,
        )

        assert ok is True
        assert status == "Delivered"
        assert saved is not None
        assert saved["text"] == "Hello from sender!"
        assert saved["sender"] == "me"

        # Check receiver's ChatStore
        recv_store = ChatStore(recv_config)
        recv_history = recv_store.get_history(send_identity.device_id)
        assert len(recv_history) == 1
        assert recv_history[0]["sender"] == "peer"
        assert recv_history[0]["text"] == "Hello from sender!"
        assert recv_history[0]["sender_name"] == send_identity.device_name

    finally:
        receiver.stop()
