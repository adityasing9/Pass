"""TLS context creation and certificate fingerprint verification"""
import hashlib
import ssl
from pathlib import Path
from typing import Tuple


def compute_der_fingerprint(cert_der: bytes) -> str:
    """Compute SHA-256 hex fingerprint of binary DER certificate"""
    return hashlib.sha256(cert_der).hexdigest()


def create_server_ssl_context(cert_file: Path, key_file: Path) -> ssl.SSLContext:
    """Create SSLContext for inbound TLS server socket"""
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.load_cert_chain(certfile=str(cert_file), keyfile=str(key_file))
    return ctx


def create_client_ssl_context() -> ssl.SSLContext:
    """
    Create SSLContext for outbound TLS client connection.
    Peer verification is performed cryptographically via certificate fingerprint pinning
    against the peer's announced discovery beacon.
    """
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def verify_peer_fingerprint(ssl_sock: ssl.SSLSocket, expected_fingerprint: str) -> bool:
    """
    Extract the peer's DER certificate from the established TLS connection
    and verify that its SHA-256 fingerprint matches the expected beacon fingerprint.
    """
    cert_der = ssl_sock.getpeercert(binary_form=True)
    if not cert_der:
        return False
    actual_fingerprint = compute_der_fingerprint(cert_der)
    return actual_fingerprint.lower().strip() == expected_fingerprint.lower().strip()
