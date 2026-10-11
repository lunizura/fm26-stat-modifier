# FM26 Memory Architecture & Reverse-Engineered Binary Layout

This document details the exact reverse-engineered C++ class layout (`ACTUAL_PLAYER@db`), internal `1-100` attribute scaling formula, and Zstandard save-file (`*.fm`) database structure used by the **Football Manager 26 Tactical Scout & Live Stat Modifier**.

---

## 1. Internal Attribute Scale (`1-100` Binary vs `1-20` Display)

In Football Manager 26 (`game_plugin.dll`), player attributes are stored in binary memory and save streams as `uint8` values on a **`1-100` internal scale**, not `1-20`.

Disassembly of `ACTUAL_PLAYER@db` virtual getter `VF_0[23]` (`RVA 0x12B4A90` in `game_plugin.dll`) reveals the exact fixed-point division-by-5 conversion used by the game engine:

```text
movsx  rax, al
movzx  eax, byte ptr [rsi + rax + 0x150]   ; Read raw uint8 attribute (1..100)
imul   eax, eax, 0x6667
add    eax, 0xCCCE
sar    eax, 17                             ; Fixed-point round(raw / 5.0)
```

- **Display to Internal Conversion:** $\text{raw\_byte} = \text{clamp}(\text{display\_20}, 1, 20) \times 5$
  - `20` in-game = `100` (`0x64`) in memory
  - `16` in-game = `80` (`0x50`) in memory
  - `1` in-game = `5` (`0x05`) in memory
- **Inverse / Negative Attributes:**
  - `Injury Proneness` (Index `48`), `Dirtiness` (Index `41`), and `Eccentricity` (Index `31`) are inverse attributes where lower values are superior (`1` display = `5` raw byte).

---

## 2. Live C++ Object Layout (`ACTUAL_PLAYER@db`)

Inspection of RTTI Complete Object Locators (`COL RVA 0x4436A80` for `.?AVACTUAL_PLAYER@db@@` and `COL RVA 0x46B2880` for `.?AVACTUAL_PLAYER_AND_NON_PLAYER@db@@`) and virtual method `ACTUAL_PLAYER::write_to_stream` (`RVA 0x1295EF0`) establishes the exact in-memory struct offsets relative to `this`:

| Offset (`this + ...`) | Type | Field Description |
| :--- | :--- | :--- |
| `+0x000` | `uint64` | Primary `vftable` pointer (`game_plugin.dll + 0x4435BB8` or `+0x46B1AD8`) |
| `+0x008` | `uint64` | Virtual base table (`vbtable`) pointer |
| `+0x150` (`+336`) | `uint8[15]` | **15 Positional Ratings** (`1-20` scale, `20` = Natural role) |
| `+0x15F` (`+351`) | `uint8[54]` | **54 Player Attributes** (`1-100` internal scale) |
| `+0x25E` (`+606`) | `uint16` | **Current Reputation** (`1-10000`) |
| `+0x260` (`+608`) | `uint16` | **Home Reputation** (`1-10000`) |
| `+0x262` (`+610`) | `uint16` | **World Reputation** (`1-10000`) |
| `+0x264` (`+612`) | `uint16` | **Current Ability (`CA`, `1-200`)** |
| `+0x266` (`+614`) | `uint16` | **Potential Ability (`PA`, `1-200`)** |
| `+0x275` (`+629`) | `uint8` | **Perceived Current Ability (`1-200`)** |
| `+0x288` (`+648`) | `uint64` | `DATABASE_RECORD@db` base subobject `vftable` (`+0x380` for Player/Non-Player) |
| `+0x290` (`+656`) | `uint32[2]` | **Player Unique ID pair `[uid, uid]`** (`+0x388` for Player/Non-Player) |

---

## 3. Serialized Database Record Layout (`*.fm` Zstd Stream)

During save serialization (`ACTUAL_PLAYER::write_to_stream`), `DATABASE_RECORD` writes the 8-byte `[uid, uid]` header first, followed by marker byte `0x02`, the 10-byte reputation/ability block (`this + 0x25E..0x267`), and the 69-byte (`0x45`) contiguous `[Positions(15B) + Attributes(54B)]` array (`this + 0x150..0x194`):

| Offset (`rec + ...`) | Type | Field Description |
| :--- | :--- | :--- |
| `+0` | `uint32` | Player Unique ID (`uid`) |
| `+4` | `uint32` | Repeated Unique ID (`uid_repeat == uid`) |
| `+8` | `uint8` | Record type marker (`0x02`) |
| `+9` | `uint16` | Current Reputation (`1-10000`) |
| `+11` | `uint16` | Home Reputation (`1-10000`) |
| `+13` | `uint16` | World Reputation (`1-10000`) |
| `+15` | `uint16` | **Current Ability (`CA`, `1-200`)** |
| `+17` | `uint16` | **Potential Ability (`PA`, `1-200`)** |
| `+19` | `uint8` | Perceived Current Ability (`1-200`) |
| `+39..+53` | `uint8[15]` | **15 Positional Ratings** (`GK, SW, DL, DC, DR, DM, ML, MC, MR, AML, AMC, AMR, ST, WBL, WBR`) |
| `+54..+107` | `uint8[54]` | **54 Player Attributes** (`1-100` scale) |
| `+217` (`+0xD9`) | `uint32 + char[]` | Inline Shirt / Display Name (`len + UTF-8 bytes`) |

---

## 4. Name-Only Search via the 3 Contiguous Name Tables

Immediately preceding the player table in the decompressed `DB` Zstd frame (`offset 8063..37496913`) are three back-to-back dictionary tables formatted as `[uint32 count]` followed by `count` entries of `[uint32 id][uint32 len][UTF-8 string]`:

1. **FirstName Table:** ~294,138 given names (starts at `ID 0 = "Oldřich"`).
2. **SecondName Table:** ~599,973 surnames (starts immediately after FirstName at `ID 0 = "Nejedlý"`).
3. **CommonName Table:** ~94,094 nicknames/mononyms (e.g. `"Vitinha"`, `"Pedri"`, `"Rodri"`).

Each player record stores `[FirstNameID (4B)][0x00][SecondNameID (4B)][0x00][CommonNameID (4B)][0x00][FullNameLen (4B)][FullName][BirthDay (2B)][BirthYear (2B)]`, enabling instant accent-insensitive lookup of all ~46,500 players using only their name.
