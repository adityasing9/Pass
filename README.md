# PASS — Peer-to-peer Automated Secure Sharing

> **Cross-platform, zero-configuration, terminal-only peer-to-peer file transfer CLI.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20Termux-brightgreen.svg)]()

PASS allows nearby devices to discover each other automatically and transfer files directly across local networks without manually configuring IP addresses, ports, subnets, SSH, SMB, servers, or cloud accounts.

---

## 1. Features

- **Zero Manual Network Configuration**: No need to type IP addresses, port numbers, or setup SSH/SMB shares. PASS automatically discovers nearby peers.
- **Direct Local P2P Transfer**: Data travels directly from machine to machine over local Wi-Fi or Ethernet. Transfers function completely offline without Internet access.
- **High-Performance Streaming**: Files are transferred in 256 KB streaming chunks. Multi-gigabyte files (1 GB, 5 GB, 10 GB+) stream without consuming system RAM.
- **Cryptographic File Integrity**: Every transferred file is verified end-to-end with SHA-256 hashes computed on the fly.
- **Resumable Transfers**: Interrupted transfers automatically resume from the last verified byte offset rather than restarting from scratch.
- **Strong Transport Security**: Direct connections are encrypted with TLS 1.3/1.2 using self-signed ECDSA (P-256) certificates. Certificate fingerprints are pinned against advertised discovery beacons to defend against MITM attacks.
- **Strict Path Traversal Defense**: Prevents directory traversal attacks (`../`, `/etc/passwd`, `C:\Windows`) and Windows-reserved device names (`CON`, `PRN`, `AUX`, `NUL`).
- **Interactive Acceptance & Device Trust**: Inbound transfers from unknown machines require explicit terminal confirmation (`[y/N]`). Trusted devices can be whitelisted for seamless automatic transfers.
- **Cross-Platform**: First-class support for Windows 10/11, Linux (Ubuntu/Debian), Android (Termux), and virtual machines (VMware/VirtualBox).

---

## 2. CLI Command Name Decision

The project name is **PASS**. To avoid conflicting with the standard Linux password manager (`pass`), the terminal command is:

```bash
passx
```

---

## 3. Installation

### From Source (Editable Mode)

```bash
git clone https://github.com/adityasing9/SettleHub.git
cd SettleHub
pip install -e .
```

### Verification

```bash
passx version
passx status
```

---

## 4. Quick Start

### Interactive Mode

Simply run `passx` with no arguments to launch the interactive terminal interface:

```text
passx
```

Output:

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│ PASS — Peer-to-peer Automated Secure Sharing                                │
│ Version: 0.1.0 | Device: AADI-PC | Platform: windows                        │
└─────────────────────────────────────────────────────────────────────────────┘

1. Send file(s) or folder
2. Receive mode (Wait for transfers)
3. Discover nearby PASS devices
4. Manage trusted devices
5. Device settings & status
6. Exit

Select an option [1-6]:
```

---

### Sending Files

#### Send a single file:

```bash
passx send project.zip
```

PASS discovers nearby devices on your local network and prompts you to select the target:

```text
Discovered PASS Devices (2)
┌───┬─────────────┬───────────────┬───────┬──────────┬──────────────────┐
│ # │ Device Name │ IP Address    │ Port  │ Platform │ Fingerprint      │
├───┼─────────────┼───────────────┼───────┼──────────┼──────────────────┤
│ 1 │ LINUX-PC    │ 192.168.1.84  │ 42425 │ linux    │ 7b9a0c2e3f4d5e6a │
│ 2 │ IQOO-NEO-10 │ 192.168.1.105 │ 42425 │ android  │ f2e4b6c8a0d2e4f6 │
└───┴─────────────┴───────────────┴───────┴──────────┴──────────────────┘

Select device number to send to: 1
```

#### Send multiple files or entire directories:

```bash
passx send document.pdf photo.jpg project_folder/
```

PASS recursively bundles directory structures and preserves relative folder hierarchies on the receiving device.

#### Send directly to a known device:

```bash
passx send dataset.tar.gz --to LINUX-PC
```

---

### Receiving Files

To listen for incoming file transfers from other machines:

```bash
passx receive
```

Output:

```text
PASS Receiver Ready
Device Name: LINUX-PC
Download Directory: /home/user/Downloads/PASS
Transfer Port: 42425
Listening for incoming file transfers... (Press Ctrl+C to exit)
```

When another device sends files, an acceptance prompt appears:

```text
Incoming transfer request!
From: AADI-PC (192.168.1.50)
Files: 3 file(s) (1.45 GB)
Accept transfer? [Y/n]: y
Trust 'AADI-PC' for future transfers? [y/N]: y
```

To automatically accept transfers in scripts or automated pipelines:

```bash
passx receive --yes
```

---

### Discovering Devices

Scan the local network for live PASS peers:

```bash
passx devices
```

---

### Managing Trusted Devices

List currently trusted peers:

```bash
passx trust
```

Remove trust from a device:

```bash
passx untrust LINUX-PC
```

---

## 5. Protocol Architecture

PASS operates via two independent networking pipelines:

```
 Discovery Phase (UDP 42424)           Direct Transfer Phase (TCP 42425)
 ─────────────────────────────         ──────────────────────────────────
 Sender              Receiver          Sender                  Receiver
   │                     │               │                         │
   │── UDP BEACON/PROBE ─>               │── TCP Connect + TLS ───>│
   │<─ UDP BEACON Resp ──│               │<─ Handshake (FP Pin) ──>│
   │                     │               │── TRANSFER_MANIFEST ───>│
   │                     │               │<─ TRANSFER_DECISION ────│
   │                     │               │── FILE_START ──────────>│
   │                     │               │=== 256 KB DATA CHUNKS ==│
   │                     │               │── FILE_END (SHA-256) ──>│
   │                     │               │<─ FILE_VERIFIED (OK) ───│
   │                     │               │── TRANSFER_COMPLETE ───>│
```

### 1. Zero-Configuration UDP Discovery (Port 42424)
- Nodes periodically broadcast discovery beacons and reply to active probe queries.
- Interfaces are dynamically enumerated, targeting `255.255.255.255`, specific subnet broadcasts (`192.168.1.255`), and the multicast group (`239.255.77.88`).
- Beacons carry device UUID, friendly hostname, TLS certificate fingerprint, and capabilities.

### 2. Direct TLS 1.3 Transfer Engine (Port 42425)
- Transport is wrapped in TLS with ephemeral or persistent ECDSA (P-256) certificates.
- The client pins the receiver's TLS certificate against the fingerprint received in the discovery beacon, guaranteeing protection against LAN spoofing and rogue peers.
- Streaming runs in 256 KB chunk frames (`0x01` binary frame prefix) to ensure minimal memory footprint.
- End-of-transfer SHA-256 digests are compared; files are only finalized when the receiver verifies bit-for-bit cryptographic equality.

---

## 6. Supported Platforms & Environments

### Windows 10/11
- Automatically derives device name from host computer name.
- Default downloads saved to `%USERPROFILE%\Downloads\PASS`.
- **Firewall Note**: Allow Python or `passx` through Windows Defender Firewall for UDP port 42424 and TCP port 42425.

### Linux (Ubuntu / Debian / Arch / Fedora)
- Default downloads saved to `~/Downloads/PASS`.
- Works on wired Ethernet and Wi-Fi. Check `ufw` or `iptables` if local traffic is blocked.

### Android via Termux
PASS runs natively inside Termux without requiring a separate Android APK:
1. Install Termux from F-Droid.
2. Grant storage access so PASS can write to Android's `Downloads` folder:
   ```bash
   termux-setup-storage
   ```
3. Install Python and dependencies:
   ```bash
   pkg install python git
   pip install git+https://github.com/adityasing9/SettleHub.git
   ```
4. Run `passx`:
   ```bash
   passx
   ```
   Files are saved to `~/storage/downloads/PASS`.

### Virtual Machines (VMware & VirtualBox)
- **Bridged Networking**: Recommended. The VM receives an IP on your physical LAN and discovers host/other machines seamlessly.
- **NAT Networking**: Discovery broadcast packets may be blocked across the NAT boundary. Use direct IP specification or port forwarding if bridged mode is not available.

### WSL (Windows Subsystem for Linux)
- In WSL2 with mirrored networking (`networkingMode=mirrored` in `.wslconfig`), PASS discovery and transfers work directly between Windows and WSL.

---

## 7. Security Model

| Threat | Mitigation |
|---|---|
| **Eavesdropping / Packet Sniffing** | TLS 1.3/1.2 end-to-end socket encryption. |
| **LAN MITM / ARP Spoofing** | Certificate SHA-256 fingerprint announced via beacon and pinned during TLS handshake. |
| **Path Traversal Attacks** | Strict sanitization: blocks `..`, drive letters, leading slashes, null bytes, and Windows reserved names (`CON`, `NUL`, `AUX`). Path resolution enforces destination containment. |
| **Data Corruption** | Streaming SHA-256 calculation and mandatory pre-finalization verification. |
| **Unauthorized File Writes** | Incoming transfers require interactive confirmation `[y/N]` unless sender is explicitly trusted. |

---

## 8. Development & Testing

Run the comprehensive test suite with `pytest`:

```bash
python -m pytest tests/ -v
```

### Test Coverage
- `test_identity.py`: UUID generation, config persistence, and ECDSA certificate creation.
- `test_sanitizer.py`: Directory traversal and malicious path injection vectors.
- `test_protocol.py`: Wire framing, binary headers, and message validation.
- `test_discovery.py`: Beacon encoding/decoding, peer cache expiration.
- `test_manifest.py`: Single file, multi-file, and directory hierarchy bundling.
- `test_resume.py`: Partial transfer state and resume offset calculation.
- `test_transfer_e2e.py`: Loopback TLS transfer integration tests, fingerprint verification, and resumption.
- `test_cli.py`: Command line parsing and execution.

---

## 9. License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
