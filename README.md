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

## 3. Installation & Usage (No Git Clone Required)

PASS can be installed and operated **without manually cloning the GitHub repository**. Choose whichever method best suits your environment:

### Method A: One-Line Automatic Installers (Recommended)

#### Windows (PowerShell):
Open PowerShell and run:
```powershell
irm tinyurl.com/passx-win | iex
```
> *(Optional direct GitHub link: `irm https://raw.githubusercontent.com/adityasing9/Pass/main/install.ps1 | iex`)*

#### Linux & Android Termux (Bash):
Open terminal and run:
```bash
curl -sSL tinyurl.com/passx-linux | bash
```
> *(Optional direct GitHub link: `curl -sSL https://raw.githubusercontent.com/adityasing9/Pass/main/install.sh | bash`)*
> 
> *Termux note: ensure dependencies are installed first: `pkg install python python-pip python-cryptography curl -y`*

---

### Method B: Direct `pip install` from GitHub (No Git Needed)

If you have Python installed, you do not need Git at all. Install directly from GitHub's release tarball:

```bash
pip install https://github.com/adityasing9/Pass/archive/refs/heads/main.zip
```

Or if Git is installed on your machine:
```bash
pip install git+https://github.com/adityasing9/Pass.git
```

---

### Method C: Standalone Executable (No Python or Git Needed)

You can run PASS as a self-contained single-file binary without installing Python or Git:

- **Windows**: Download `passx-windows-amd64.exe` from [GitHub Releases](https://github.com/adityasing9/Pass/releases), rename to `passx.exe`, and run directly in any terminal:
  ```powershell
  .\passx.exe
  ```
- **Linux**: Download `passx-linux-amd64` from [GitHub Releases](https://github.com/adityasing9/Pass/releases), make it executable, and move it to your path:
  ```bash
  chmod +x passx-linux-amd64
  sudo mv passx-linux-amd64 /usr/local/bin/passx
  ```

#### Build Your Own Standalone Binary
To compile a standalone binary yourself:
```bash
pip install pyinstaller
pyinstaller --onefile --name passx passx/__main__.py
# Binary is generated at dist/passx.exe (Windows) or dist/passx (Linux)
```

---

### Method D: Install from Source (For Developers)

```bash
git clone https://github.com/adityasing9/Pass.git
cd Pass
pip install -e .
```

---

### Verification

Check that PASS is installed and ready:

```bash
passx version
passx status
```

---

### Updating PASS

To update PASS to the latest version at any time, run:

```bash
passx update
```

Or re-run the one-line installer:
- **Linux & Android (Termux)**:
  ```bash
  curl -sSL tinyurl.com/passx-linux | bash
  ```
- **Windows (PowerShell)**:
  ```powershell
  irm tinyurl.com/passx-win | iex
  ```

Inside the interactive menu (`passx`), you can also simply type `update` at the prompt.

---

## 4. How to Use PASS

PASS can be used in two different ways depending on your preference:
1. **Interactive Menu Mode** (`passx`) — Guided prompts, ideal for everyday use.
2. **Direct CLI Commands** (`passx send ...`, `passx receive`) — Fast one-liners run straight from your normal terminal prompt.

---

### Mode 1: Interactive Menu Mode (`passx`)

When you run `passx` with no arguments, it opens the interactive terminal menu:

```powershell
passx
```

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

Select an option [1/2/3/4/5/6] (1):
```

#### Step-by-Step: How to Send a File in the Menu:

1. **Select Option 1**: Type `1` and press **Enter** (or simply press **Enter** for default).
2. **Select File(s) or Folders Visually (No Typing Needed!)**:
   PASS displays an interactive menu so you can pick files with numbers instead of typing paths:
   ```text
   Select where to pick files from:
   1. 📸 Camera Photos (on Termux / Android)
   2. 📥 Downloads Folder
   3. 🖥️ Desktop Folder (on Windows)
   4. 📂 Browse Current Directory
   5. 🗂️ Browse Any Directory
   6. ✍️ Enter path manually
   ```
   - Selecting **Camera** or **Downloads** displays a numbered list of your recent files (`1, 2, 3...`). Simply type the number(s) to send!
   - Selecting **Browse Directory** lets you explore folders and send entire directories.
   - On Windows, you can even open the native File Explorer chooser!
3. **Select Target Device**: PASS automatically discovers nearby devices and shows a numbered list:
   ```text
   Discovered PASS Devices (2)
   ┌───┬─────────────┬───────────────┬───────┬──────────┬──────────────────┐
   │ # │ Device Name │ IP Address    │ Port  │ Platform │ Fingerprint      │
   ├───┼─────────────┼───────────────┼───────┼──────────┼──────────────────┤
   │ 1 │ LINUX-PC    │ 192.168.1.84  │ 42425 │ linux    │ 7b9a0c2e3f4d5e6a │
   │ 2 │ IQOO-NEO-10 │ 192.168.1.105 │ 42425 │ android  │ f2e4b6c8a0d2e4f6 │
   └───┴─────────────┴───────────────┴───────┴──────────┴──────────────────┘

   Select device number to send to (1): 1
   ```
4. **Transfer Streams**: The progress bar shows live transfer speed (MB/s), ETA, and verifies SHA-256 upon completion!

> 💡 **Smart Input Support:** You can also type commands directly into the menu prompt! For example, typing `send C:\path\file.txt` or `devices` or `receive` directly into `Select an option:` will immediately execute that action.

---

### Mode 2: Direct CLI Commands (from PowerShell / Bash)

> ⚠️ **Important:** Run these commands directly in your standard **PowerShell** or **Bash** terminal prompt (do **not** type `passx send ...` inside the interactive menu prompt).

#### 1. Send a single file:
```powershell
passx send C:\Users\AADI\Desktop\project.zip
```

#### 2. Send multiple files or entire folders:
```powershell
passx send document.pdf photo.jpg C:\Users\AADI\Desktop\my_folder\
```
PASS automatically walks folders recursively and preserves the entire directory tree on the receiving device!

#### 3. Send directly to a specific device (skip selection prompt):
```powershell
passx send dataset.tar.gz --to LINUX-PC
# Or direct to IP address without discovery:
passx send dataset.tar.gz --to 192.168.1.105
```

#### 4. High-Speed Turbo Streaming (`--turbo`):
For large transfers (movies, videos, ISOs, datasets), use `--turbo` to enable 2 MB streaming pipelines:
```powershell
passx send movie.mp4 --turbo
```

#### 5. Start in Receive Mode:
```powershell
passx receive
```
To automatically accept all incoming transfers without confirmation prompts (useful for headless servers):
```powershell
passx receive --yes
```

#### 5. Discover nearby devices:
```powershell
passx devices
```

#### 6. Check system status & network interfaces:
```powershell
passx status
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

### WhatsApp of the Terminal (💬 Live P2P Chat & Messaging)

PASS turns your terminal into a secure, offline, peer-to-peer messenger:

#### 1. Interactive WhatsApp Mode (`passx chat`):
Launch an interactive real-time chat with formatted chat bubbles, contact status, and inline file transfers:
```bash
passx chat
```
Or start chatting with a specific device directly:
```bash
passx chat Pixel-7
# Or by IP:
passx chat 192.168.1.105
```

**Inside the chat room:**
- **Send messages:** Type any text and press `[Enter]`.
- **Attach files/folders:** Type `/send <path>` (e.g. `/send photo.jpg` or `/send ~/Documents`) to transfer files directly inside the conversation!
- **Share clipboard:** Type `/clip` to send copied text across devices instantly.
- **Older messages:** Type `/history` to view past chat history.
- **Clear screen:** Type `/clear`.
- **Exit:** Type `/exit` or `/quit`.

#### 2. Quick Instant Messages (`passx msg`):
Send a message without opening the full chat interface:
```bash
passx msg Pixel-7 "Hey, dinner is ready!"
passx msg 192.168.1.105 "Check out the repo updates"
```

#### 3. Cross-Device Clipboard Sharing (`passx clip`):
Copy code, URLs, or text on your PC and send it straight to your phone's clipboard:
```bash
passx clip Pixel-7
```

- **100% Offline & Private:** Messages travel directly over local Wi-Fi / Hotspot via mutual TLS encryption. Zero cloud servers.
- **Background Push Notifications:** Incoming messages trigger native Android notifications and Windows desktop toasts.
- **Persistent History:** Conversations are preserved locally in `~/.pass/chats/`.

---

### Easy 1-Click Device Pairing (`passx pair`)

Pair your devices once, and all future transfers between them will be **automatically transferred without any confirmation prompts**:

```bash
passx pair
```
PASS scans your local network, displays nearby devices, and lets you pair in 1 click!

You can also pair directly by IP:
```bash
passx pair 192.168.1.105
```

---

### Device Renaming & Nicknames (`passx rename` / `passx alias`)

Customize how devices appear across PASS (in device discovery tables, chat contact lists, transfers, and notifications):

#### 1. Rename your own device:
```bash
passx rename --self "My PC"
# Or simply:
passx rename "My PC"
```

#### 2. Assign a friendly nickname to another device:
```bash
passx rename IQOO-NEO-10 "My Phone"
passx alias 192.168.1.105 "Work Laptop"
passx nickname DESKTOP-XYZ "Dad's PC"
```
Once a nickname is set, PASS will recognize it everywhere:
- `passx send document.pdf --to "My Phone"`
- `passx chat "My Phone"`
- `passx msg "My Phone" "Hello!"`
- `passx clip "My Phone"`

#### 3. View or remove nicknames:
```bash
passx rename --list              # View all configured nicknames
passx rename --remove "My Phone" # Remove nickname
```
*(Running `passx rename` with no arguments opens the interactive nickname manager wizard!)*

---

### 24/7 Background Receiver Service (`passx daemon`)

Never wait in the receiving terminal again! Run PASS as a background service so your device is **always ready to receive files automatically**:

- **Start background receiver**:
  ```bash
  passx daemon start
  ```
  *(On Android Termux, this automatically maintains wake-lock so transfers arrive even when the phone screen is locked!)*
- **Check service status**:
  ```bash
  passx daemon status
  ```
- **Stop background receiver**:
  ```bash
  passx daemon stop
  ```

---

### Instant Auto-Accept Mode (`passx auto-accept`)

If you are on a private home network or personal hotspot, you can enable auto-accept so **any device** on your LAN can send you files with zero prompts:

```bash
passx auto-accept on     # Turn on zero-prompt auto-accept
passx auto-accept off    # Require pairing or confirmation
passx auto-accept status # Check current mode
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
- Default downloads saved to `%USERPROFILE%\Desktop`.
- **Firewall Note**: Allow Python or `passx` through Windows Defender Firewall for UDP port 42424 and TCP port 42425.

### Linux (Ubuntu / Debian / Arch / Fedora)
- Default downloads saved to `~/Downloads/PASS`.
- Works on wired Ethernet and Wi-Fi. Check `ufw` or `iptables` if local traffic is blocked.

### Android via Termux
PASS runs natively inside Termux on Android without requiring any graphical app:

1. **Install Termux**: Download Termux from [F-Droid](https://f-droid.org/en/packages/com.termux/) or GitHub Releases (do not use the obsolete Google Play version).
2. **Grant Storage Permission**:
   ```bash
   termux-setup-storage
   ```
   *(Tap "Allow" on the popup. This links Android's shared storage to `~/storage`)*
3. **Install Dependencies & PASS**:
   ```bash
   pkg update && pkg install python python-pip python-cryptography curl -y
   curl -sSL tinyurl.com/passx-linux | bash
   ```
4. **Sending a File from Phone to PC**:
   ```bash
   passx send ~/storage/shared/DCIM/Camera/photo.jpg
   # or send any file from Android Downloads:
   passx send ~/storage/downloads/document.pdf
   ```
5. **Receiving a File on Phone from PC**:
   ```bash
   passx receive --yes
   ```
   Transferred files land directly in **`~/storage/downloads/PASS/`** (visible immediately in your Android Files / Downloads app).
6. **Interactive Menu Mode**:
   ```bash
   passx
   ```
7. **Updating PASS on Termux**:
   ```bash
   passx update
   ```
   *(Or simply run: `curl -sSL tinyurl.com/passx-linux | bash`)*

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
