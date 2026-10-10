# Contributing to FM26 Live Stat & Rating Modifier

Thank you for your interest in contributing to **fm26-stat-modifier**. This document outlines our development environment setup, coding standards, and safety protocols for process memory instrumentation.

---

## 1. Development Environment Setup

### Requirements
- **OS:** Windows 10 or Windows 11 (x64)
- **Python:** 3.10+
- **Dependencies:** `pymem`, `customtkinter`, `psutil`, `pyinstaller`

### Local Setup
```bash
git clone https://github.com/lunizura/fm26-stat-modifier.git
cd fm26-stat-modifier
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

---

## 2. Coding & Documentation Standards

1. **Zero-Emoji Policy:** All source code, comments, UI labels, documentation files, and Git commit messages must contain strictly zero emoji characters.
2. **Conventional Commits:** Prefix all commit messages with standard types:
   - `feat:` for new scanning capabilities or UI features
   - `fix:` for offset corrections, pointer validation fixes, or exception handling
   - `docs:` for architecture and usage documentation updates
   - `refactor:` for non-breaking structural improvements
   - `chore:` for build scripts, `.gitignore`, or dependency updates
3. **Non-Blocking UI Threads:** All memory scanning operations (`VirtualQueryEx` / `ReadProcessMemory` loops) must execute on background worker threads (`threading.Thread(..., daemon=True)`) so the CustomTkinter main loop never freezes.

---

## 3. Memory Safety & Validation Guidelines

When submitting updates to structure offsets or scanning heuristics:
- **Bounds Checking:** Clamp all attribute writes to `[1, 20]` (or `[1, 100]` for internal scaled fields) and ability writes (`CA`/`PA`) to `[1, 200]` before calling `WriteProcessMemory`.
- **Pointer Verification:** Always verify that the target memory page remains committed (`MEM_COMMIT`) and writable (`PAGE_READWRITE`) immediately prior to any write operation to avoid crashing the host game process.
- **Single-Player Scope:** Contributions must strictly target offline, single-player career saves. Features designed for online or multiplayer tampering will not be accepted.

---

## 4. Submitting a Pull Request

1. Fork the repository and create a descriptive feature branch (`git checkout -b feat/offset-validation`).
2. Verify that all files adhere to UTF-8 encoding and zero-emoji compliance.
3. Submit a Pull Request detailing the game build version tested and the memory layout verification steps performed.
