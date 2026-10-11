# Football Manager 26 Tactical Scout & Live Stat Modifier

[![Platform](https://img.shields.io/badge/Platform-Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white)](https://www.microsoft.com/windows)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![GUI](https://img.shields.io/badge/UI-CustomTkinter-10B981?style=for-the-badge)](https://github.com/TomSchimansky/CustomTkinter)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg?style=for-the-badge)](LICENSE)

A high-precision Windows desktop trainer, save-database scout, and real-time process memory modifier for **Football Manager 26**. Built around FM26's native `ACTUAL_PLAYER@db` C++ memory layout and Zstandard database stream so you can search any player **using only their name** and modify all 54 attributes, 15 positional ratings, Current Ability (CA), and Potential Ability (PA).

---

## Key Highlights

- **Instant Name-Only Player Search:**
  - Automatically decompresses and indexes your active `.fm` career save (`~46,500+` players and `988,000+` First, Second, and Common Name dictionary entries).
  - Type **only the player's name** (e.g., `"Cristiano Ronaldo"`, `"Bruno Fernandes"`, `"Bernardo Silva"`, `"Vitinha"`, `"Mbappe"`, `"Odegaard"`, `"Yamal"`). Supports accent-insensitive, multi-word, nickname, and surname queries with local index caching (`<0.15s` reload).
- **Verified `ACTUAL_PLAYER@db` Memory Engine (`1-100` Internal Scale):**
  - Resolves live `ACTUAL_PLAYER@db` and `ACTUAL_PLAYER_AND_NON_PLAYER@db` C++ objects in `fm.exe` via single-pass `[UID, UID]` header and 54-attribute vector verification.
  - Properly converts `1-20` display stats to FM26's internal `5-100` (`display * 5`) binary scale (`this + 0x15F`) and writes 16-bit `CA` (`this + 0x264`), `PA` (`this + 0x266`), and `Reputation` (`this + 0x25E`).
  - Automatically keeps inverse traits (`Injury Proneness`, `Dirtiness`, `Eccentricity`) at `1` (`5` internal) during stat boosts.
- **3-Column Tactical Attribute Matrix GUI:**
  - Authentic Football Manager 3-column layout (**Technical**, **Mental**, **Physical & Hidden**) with color-coded tier badges (`16-20` Emerald, `11-15` Cyan, `6-10` Amber, `1-5` Slate) plus dedicated **Goalkeeping & 15 Positional Roles** editor.
  - One-click presets: **Super Boost (All 20s + 200 CA/PA)**, **Max CA/PA (200)**, **Peak Physical + No Injury**, **Clinical Finisher**, and **Playmaker Maestro**.

---

## Project Structure

| File | Description |
| :--- | :--- |
| `app_gui.py` | Main CustomTkinter desktop application with split-pane Name-Only search and 3-column attribute editor |
| `ui_components.py` | Tactical telemetry theme palette, Windows 11 DWM Mica/Dark integration, and custom stepper/card widgets |
| `fm_database.py` | Zstandard `.fm` save stream parser, 3-table Name Dictionary resolver, and accent-insensitive search engine |
| `fm_core.py` | Win32 `ReadProcessMemory` / `WriteProcessMemory` engine targeting `ACTUAL_PLAYER@db` structs |
| `fm_schema.py` | Binary offset constants, `1-100` scale conversion helpers, 54-attribute catalog, and `PlayerRecord` model |
| `fm_catalog.py` | Built-in offline catalog of 66 verified FM26 world stars with genuine UIDs and attribute vectors |
| `fm_modifier.py` | Command-line interface (CLI) for terminal player lookup, telemetry inspection, and preset patching |
| `build_exe.py` | Automated PyInstaller build script generating standalone `FM26_Stat_Modifier.exe` |
| `tests/test_fm26_engine.py` | Unit and integration test suite verifying scaling, struct offsets, and name search |

---

## Quick Start

### 1. Clone & Install Dependencies
```bash
git clone https://github.com/lunizura/fm26-stat-modifier.git
cd fm26-stat-modifier
pip install -r requirements.txt
```

### 2. Launch the Desktop GUI
```bash
python app_gui.py
```
Or double-click `Run_FM26_Modifier.bat`.

### 3. CLI Usage
```bash
# Inspect any player's full 54-attribute telemetry by name
python fm_modifier.py --search "Cristiano Ronaldo"

# Apply Super Boost to a player in live FM26 memory
python fm_modifier.py --search "Bruno Fernandes" --preset super_boost
```

---

## Building the Standalone `.exe`

```bash
python build_exe.py
```

This compiles `dist/FM26_Stat_Modifier.exe` (bundling `customtkinter` and `zstandard`) and copies the updated executable to your Windows Desktop.

---

## Running Tests

```bash
python -m unittest discover -s tests -v
```

---

## Disclaimer

This project is an independent open-source software engineering and memory research tool created strictly for educational and single-player offline use.
- Not affiliated with, endorsed by, or connected to Sports Interactive or SEGA.
- *Football Manager* is a registered trademark of Sports Interactive and SEGA.

---

## License

Distributed under the [MIT License](LICENSE).
