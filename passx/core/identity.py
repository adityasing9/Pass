"""Device identity, UUID, and TLS certificate management"""
import datetime
import hashlib
import json
import uuid
from pathlib import Path
from typing import Optional, Tuple
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
from passx.core.config import ConfigManager


class DeviceIdentity:
    """Manages unique device identity and TLS credentials"""

    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self.config_dir = config_manager.config_dir
        self.identity_file = self.config_dir / "identity.json"
        self.cert_file = self.config_dir / "cert.pem"
        self.key_file = self.config_dir / "key.pem"
        
        self.device_id: str = self._load_or_create_device_id()
        self._ensure_certificates()
        self.fingerprint: str = self._compute_cert_fingerprint()

    def _load_or_create_device_id(self) -> str:
        if self.identity_file.exists():
            try:
                with open(self.identity_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if "device_id" in data:
                        return data["device_id"]
            except Exception:
                pass
        
        new_id = str(uuid.uuid4())
        with open(self.identity_file, "w", encoding="utf-8") as f:
            json.dump({"device_id": new_id, "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat()}, f, indent=2)
        return new_id

    def _ensure_certificates(self) -> None:
        """Generate self-signed ECDSA certificate and private key if not already present"""
        if self.cert_file.exists() and self.key_file.exists():
            return

        # Generate ECDSA private key (P-256)
        private_key = ec.generate_private_key(ec.SECP256R1())

        # Subject & Issuer
        subject = issuer = x509.Name([
            x509.NameAttribute(x509.NameOID.COMMON_NAME, f"PASS-{self.device_id[:8]}"),
            x509.NameAttribute(x509.NameOID.ORGANIZATION_NAME, "PASS Peer-to-Peer"),
        ])

        now = datetime.datetime.now(datetime.timezone.utc)
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(private_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(days=1))
            .not_valid_after(now + datetime.timedelta(days=3650))  # 10 years validity
            .add_extension(
                x509.BasicConstraints(ca=False, path_length=None),
                critical=True,
            )
            .sign(private_key, hashes.SHA256())
        )

        # Write private key
        with open(self.key_file, "wb") as f:
            f.write(
                private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption(),
                )
            )

        # Write certificate
        with open(self.cert_file, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))

    def _compute_cert_fingerprint(self) -> str:
        """Compute SHA-256 fingerprint in hex format from the PEM certificate"""
        with open(self.cert_file, "rb") as f:
            cert_pem = f.read()
        cert = x509.load_pem_x509_certificate(cert_pem)
        raw_digest = cert.fingerprint(hashes.SHA256())
        return raw_digest.hex()

    @property
    def device_name(self) -> str:
        return self.config_manager.device_name

    def get_tls_paths(self) -> Tuple[Path, Path]:
        """Return (cert_path, key_path)"""
        return self.cert_file, self.key_file
