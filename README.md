# Football Manager 26 Live Stat & Rating Modifier

[![Platform](https://img.shields.io/badge/Platform-Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white)](https://www.microsoft.com/windows)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![GUI](https://img.shields.io/badge/UI-CustomTkinter-1f6aa5?style=for-the-badge)](https://github.com/TomSchimansky/CustomTkinter)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg?style=for-the-badge)](LICENSE)

A lightweight Windows desktop trainer and real-time process memory modifier for **Football Manager 26**. Designed to inspect and modify player attributes, Current Ability (CA), and Potential Ability (PA) dynamically during an active career save without requiring external DLC editors.

---

## Core Capabilities

- **Real-Time Process Hook:** Attaches directly to `fm.exe` / `fm26.exe` via Windows API (`kernel32.dll` `OpenProcess`, `VirtualQueryEx`, `ReadProcessMemory`, and `WriteProcessMemory`).
- **Multi-Mode Player Resolution:**
  - **UID Lookup:** Resolves player entities via unique 32-bit/64-bit database identifiers while filtering out cached localization strings.
  - **Attribute Fingerprint Scanner:** Scans committed read-write heap regions (`MEM_COMMIT` | `PAGE_READWRITE`) for contiguous or strided attribute combinations (e.g., Finishing, Passing, Pace, Determination) to locate active player structures across dynamic memory reallocations.
- **CA/PA Decay Prevention:** Synchronizes Current Ability (1-200) and Potential Ability (1-200) ceilings when modifying individual technical, mental, and physical attributes (1-20), preventing the simulation engine's monthly weight recalculation from reverting edited stats.
- **Direct Memory Inspector:** Built-in hexadecimal viewer and writer supporting 1-Byte (`uint8`), 2-Byte (`int16`), and 4-Byte (`int32`) operations with live audit logging.
- **Dual Interface:** Supports both a dark-mode **CustomTkinter Glass GUI** (`app_gui.py`) and a headless **CLI utility** (`fm_modifier.py`).

---

## System Requirements

- **Operating System:** Windows 10 / Windows 11 (64-bit)
- **Runtime:** Python 3.10 or higher
- **Privileges:** Administrator privileges recommended for cross-process virtual memory access (`PROCESS_VM_READ | PROCESS_VM_WRITE | PROCESS_VM_OPERATION`)

---

## Quick Start

### 1. Clone the Repository
```bash
git clone https://github.com/lunizura/fm26-stat-modifier.git
cd fm26-stat-modifier
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Launch the Application
```bash
python app_gui.py
```

---

## Workflow Overview

1. Start **Football Manager 26** and load a single-player career save.
2. Open the modifier utility and verify the process attachment indicator reads `CONNECTED: fm.exe`.
3. Navigate to the target player's profile inside Football Manager.
4. Search using either the player's **UID** or a **4-to-6 Attribute Fingerprint** sequence.
5. Select the verified memory structure from the candidate list and apply custom slider values or preset ability locks.

---

## Standalone Executable Build

To package the modifier into a standalone Windows executable using PyInstaller:

```bash
pyinstaller --noconsole --onefile --collect-all customtkinter --name "FM26_Stat_Modifier" app_gui.py
```

The resulting binary will be placed inside the `dist/` directory.

---

## Disclaimer

This project is an independent open-source software engineering and memory research tool created strictly for educational and single-player offline use.
- Not affiliated with, endorsed by, or connected to Sports Interactive or SEGA.
- *Football Manager* is a registered trademark of Sports Interactive and SEGA.

---

## License

Distributed under the [MIT License](LICENSE).
