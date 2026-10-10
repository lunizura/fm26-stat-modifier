# Memory Architecture & Scanning Pipeline

This document outlines the internal reverse-engineering methodology, heap scanning algorithms, and safety guardrails implemented in the **Football Manager 26 Live Stat & Rating Modifier**.

---

## 1. Process Attachment & Virtual Memory Enumeration

Football Manager 26 allocates its active database entities—including clubs, staff, and player records—across dynamically managed 64-bit heap segments rather than static module offsets. Because Address Space Layout Randomization (ASLR) and save-file deserialization shift base pointers on every session load, static pointer chains alone are fragile across game patches.

To resolve player records reliably, the modifier queries the Windows kernel virtual memory manager via `VirtualQueryEx`:

1. **Region Filtering:** Only memory pages matching the following bitmask criteria are queued for scanning:
   - `State == MEM_COMMIT` (`0x1000`)
   - `Protect` includes read/write access (`PAGE_READWRITE` `0x04` or `PAGE_WRITECOPY` `0x08`)
   - Excludes `PAGE_GUARD` (`0x100`) and `PAGE_NOACCESS` (`0x01`) pages to prevent access violations.
2. **Chunked Buffer Reads:** Eligible memory regions are read into local Python byte buffers using `ReadProcessMemory` in aligned chunks (up to 64 MB per read operation) to minimize syscall overhead.

---

## 2. Player Resolution Strategies

### 2.1 Attribute Fingerprint Scanning
Visible player attributes in the user interface are displayed on a `1–20` scale. Internally, the simulation engine stores attributes either as:
- **Direct 1-Byte Integers (`uint8`):** Range `1..20`
- **Scaled Internal Integers (`uint8`):** Range `1..100` (where UI value = $\lfloor \text{Internal} / 5 \rfloor$)

When a user inputs a fingerprint vector $F = [a_1, a_2, \dots, a_k]$ (where $k \ge 4$), the scanner searches committed heap buffers for matching byte sequences and validates structural invariants around candidate addresses.

### 2.2 UID Resolution & Text Cache Filtering
Every database entity in Football Manager possesses a unique 32-bit unsigned integer identifier (`UID`). However, scanning raw memory for a 4-byte little-endian UID often yields multiple false positives:
- **UI String Caches:** UTF-16LE / UTF-8 localization buffers or formatted UI display strings adjacent to the ID.
- **Historical Index Tables:** Read-only lookup arrays indexing past season records.

To isolate the live player struct from text caches, the resolver evaluates the surrounding 128-byte neighborhood of each UID hit:
1. Rejects hits embedded inside printable ASCII/UTF-16 string sequences.
2. Verifies valid 64-bit heap vtable pointers at the structure header.
3. Cross-checks realistic Current Ability (`1 <= CA <= 200`) and Potential Ability (`CA <= PA <= 200`) 16-bit integer fields (`int16`) at expected relative offsets.

---

## 3. Current Ability (CA) & Potential Ability (PA) Synchronization

In the Football Manager simulation engine, each player's individual attributes are governed by an overarching **Current Ability (CA)** budget (`1–200`), weighted by positional role coefficients (e.g., Pace and Acceleration carry heavy CA weights for wingers, while Positioning and Tackling carry heavy weights for central defenders).

If individual attributes are written to `20` in memory without adjusting the underlying `CA` and `PA` integers:
- During the next monthly development tick, the engine detects that the weighted sum of attributes exceeds the player's current `CA` allotment.
- The engine automatically scales down all technical, mental, and physical attributes to match the unmodified `CA` value.

To prevent attribute decay:
1. The modifier locates the 2-byte `CA` (`int16`) and `PA` (`int16`) fields within the resolved player structure.
2. When applying attribute boosts, `CA` and `PA` are simultaneously updated (up to `200`) so the internal ability budget remains consistent with the modified attribute array.
