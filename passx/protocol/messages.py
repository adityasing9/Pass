"""Protocol message constructors and type definitions"""
import time
from typing import Dict, List, Any, Optional

PROTOCOL_VERSION = 1

# Message action types
MSG_HANDSHAKE_INIT = "HANDSHAKE_INIT"
MSG_HANDSHAKE_RESP = "HANDSHAKE_RESP"
MSG_TRANSFER_MANIFEST = "TRANSFER_MANIFEST"
MSG_TRANSFER_DECISION = "TRANSFER_DECISION"
MSG_FILE_START = "FILE_START"
MSG_FILE_END = "FILE_END"
MSG_FILE_VERIFIED = "FILE_VERIFIED"
MSG_TRANSFER_COMPLETE = "TRANSFER_COMPLETE"
MSG_PAIR_REQUEST = "PAIR_REQUEST"
MSG_PAIR_RESP = "PAIR_RESP"
MSG_CHAT = "CHAT_MSG"
MSG_CHAT_ACK = "CHAT_ACK"
MSG_ERROR = "ERROR"


def make_chat_msg(
    sender_id: str,
    sender_name: str,
    fingerprint: str,
    text: str,
    msg_id: str = "",
    msg_type: str = "text",
    file_info: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "action": MSG_CHAT,
        "version": PROTOCOL_VERSION,
        "msg_id": msg_id,
        "sender_id": sender_id,
        "sender_name": sender_name,
        "fingerprint": fingerprint,
        "text": text,
        "msg_type": msg_type,
        "file_info": file_info,
        "timestamp": time.time(),
    }


def make_chat_ack(
    msg_id: str,
    status: str = "DELIVERED",
    device_id: str = "",
    device_name: str = "",
) -> Dict[str, Any]:
    return {
        "action": MSG_CHAT_ACK,
        "version": PROTOCOL_VERSION,
        "msg_id": msg_id,
        "status": status,
        "device_id": device_id,
        "device_name": device_name,
        "timestamp": time.time(),
    }


def make_pair_request(device_id: str, device_name: str, fingerprint: str) -> Dict[str, Any]:
    return {
        "action": MSG_PAIR_REQUEST,
        "version": PROTOCOL_VERSION,
        "device_id": device_id,
        "device_name": device_name,
        "fingerprint": fingerprint,
    }


def make_pair_resp(status: str, device_id: str, device_name: str, fingerprint: str, message: str = "") -> Dict[str, Any]:
    return {
        "action": MSG_PAIR_RESP,
        "version": PROTOCOL_VERSION,
        "status": status,
        "device_id": device_id,
        "device_name": device_name,
        "fingerprint": fingerprint,
        "message": message,
    }


def make_handshake_init(sender_id: str, sender_name: str, fingerprint: str) -> Dict[str, Any]:
    return {
        "action": MSG_HANDSHAKE_INIT,
        "version": PROTOCOL_VERSION,
        "sender_id": sender_id,
        "sender_name": sender_name,
        "fingerprint": fingerprint,
    }


def make_handshake_resp(status: str, receiver_id: str, receiver_name: str, message: str = "") -> Dict[str, Any]:
    return {
        "action": MSG_HANDSHAKE_RESP,
        "version": PROTOCOL_VERSION,
        "status": status,  # "OK" or "REJECT"
        "receiver_id": receiver_id,
        "receiver_name": receiver_name,
        "message": message,
    }


def make_transfer_manifest(transfer_id: str, files: List[Dict[str, Any]], total_bytes: int) -> Dict[str, Any]:
    return {
        "action": MSG_TRANSFER_MANIFEST,
        "transfer_id": transfer_id,
        "files": files,  # [{"index": 0, "path": "sub/file.txt", "size": 1024, "sha256": "..."}]
        "file_count": len(files),
        "total_bytes": total_bytes,
    }


def make_transfer_decision(status: str, reason: str = "", resume_offsets: Optional[Dict[str, int]] = None) -> Dict[str, Any]:
    return {
        "action": MSG_TRANSFER_DECISION,
        "status": status,  # "ACCEPT" or "REJECT"
        "reason": reason,
        "resume_offsets": resume_offsets or {},
    }


def make_file_start(file_index: int, relative_path: str, size: int, resume_offset: int = 0) -> Dict[str, Any]:
    return {
        "action": MSG_FILE_START,
        "file_index": file_index,
        "relative_path": relative_path,
        "size": size,
        "resume_offset": resume_offset,
    }


def make_file_end(file_index: int, sha256_hash: str) -> Dict[str, Any]:
    return {
        "action": MSG_FILE_END,
        "file_index": file_index,
        "sha256_hash": sha256_hash,
    }


def make_file_verified(file_index: int, status: str, error: str = "") -> Dict[str, Any]:
    return {
        "action": MSG_FILE_VERIFIED,
        "file_index": file_index,
        "status": status,  # "OK" or "HASH_MISMATCH"
        "error": error,
    }


def make_transfer_complete(transfer_id: str) -> Dict[str, Any]:
    return {
        "action": MSG_TRANSFER_COMPLETE,
        "transfer_id": transfer_id,
    }


def make_error(code: str, message: str) -> Dict[str, Any]:
    return {
        "action": MSG_ERROR,
        "code": code,
        "message": message,
    }
