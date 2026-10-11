"""
Football Manager 26 Live Memory Engine & Struct Resolver.

Implements Win32 process memory inspection and modification targeting verified
ACTUAL_PLAYER@db / ACTUAL_PLAYER_AND_NON_PLAYER@db C++ instances and serialized DB records.
"""

import ctypes
from ctypes import wintypes
from dataclasses import dataclass
import struct
from typing import Dict, List, Optional, Tuple

from fm_schema import (
    ATTRIBUTE_DEFS,
    CPP_ATTR_OFFSET,
    CPP_CA_OFFSET,
    CPP_CUR_REP_OFFSET,
    CPP_HOME_REP_OFFSET,
    CPP_PA_OFFSET,
    CPP_PERCEIVED_CA_OFFSET,
    CPP_POS_OFFSET,
    CPP_UID_OFFSET_PLAYER,
    CPP_UID_OFFSET_PLAYER_NON_PLAYER,
    CPP_WORLD_REP_OFFSET,
    PlayerRecord,
    SER_ATTR_OFFSET,
    SER_CA_OFFSET,
    SER_CUR_REP_OFFSET,
    SER_HOME_REP_OFFSET,
    SER_MARKER_OFFSET,
    SER_PA_OFFSET,
    SER_PERCEIVED_CA_OFFSET,
    SER_POS_OFFSET,
    SER_WORLD_REP_OFFSET,
    to_raw_attr,
)

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
PROCESS_VM_WRITE = 0x0020
PROCESS_VM_OPERATION = 0x0008

MEM_COMMIT = 0x1000
PAGE_READWRITE = 0x04
PAGE_WRITECOPY = 0x08
PAGE_EXECUTE_READWRITE = 0x40
PAGE_GUARD = 0x100
PAGE_NOACCESS = 0x01

TH32CS_SNAPPROCESS = 0x00000002

LAYOUT_CPP_OBJECT = "cpp_object"
LAYOUT_SERIALIZED = "serialized_record"


class PROCESSENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.POINTER(wintypes.ULONG)),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", wintypes.LONG),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", ctypes.c_char * wintypes.MAX_PATH),
    ]


class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_void_p),
        ("AllocationBase", ctypes.c_void_p),
        ("AllocationProtect", wintypes.DWORD),
        ("PartitionId", wintypes.WORD),
        ("RegionSize", ctypes.c_size_t),
        ("State", wintypes.DWORD),
        ("Protect", wintypes.DWORD),
        ("Type", wintypes.DWORD),
    ]


@dataclass
class PlayerMemoryTarget:
    uid: int
    base_address: int
    layout: str
    pos_address: int
    attr_address: int
    cur_rep_address: int
    home_rep_address: int
    world_rep_address: int
    ca_address: int
    pa_address: int
    perceived_ca_address: int

    @classmethod
    def from_cpp_object(cls, uid: int, this_addr: int) -> "PlayerMemoryTarget":
        return cls(
            uid=uid,
            base_address=this_addr,
            layout=LAYOUT_CPP_OBJECT,
            pos_address=this_addr + CPP_POS_OFFSET,
            attr_address=this_addr + CPP_ATTR_OFFSET,
            cur_rep_address=this_addr + CPP_CUR_REP_OFFSET,
            home_rep_address=this_addr + CPP_HOME_REP_OFFSET,
            world_rep_address=this_addr + CPP_WORLD_REP_OFFSET,
            ca_address=this_addr + CPP_CA_OFFSET,
            pa_address=this_addr + CPP_PA_OFFSET,
            perceived_ca_address=this_addr + CPP_PERCEIVED_CA_OFFSET,
        )

    @classmethod
    def from_serialized_record(cls, uid: int, rec_addr: int) -> "PlayerMemoryTarget":
        return cls(
            uid=uid,
            base_address=rec_addr,
            layout=LAYOUT_SERIALIZED,
            pos_address=rec_addr + SER_POS_OFFSET,
            attr_address=rec_addr + SER_ATTR_OFFSET,
            cur_rep_address=rec_addr + SER_CUR_REP_OFFSET,
            home_rep_address=rec_addr + SER_HOME_REP_OFFSET,
            world_rep_address=rec_addr + SER_WORLD_REP_OFFSET,
            ca_address=rec_addr + SER_CA_OFFSET,
            pa_address=rec_addr + SER_PA_OFFSET,
            perceived_ca_address=rec_addr + SER_PERCEIVED_CA_OFFSET,
        )


kernel32 = ctypes.windll.kernel32
OpenProcess = kernel32.OpenProcess
CloseHandle = kernel32.CloseHandle
ReadProcessMemory = kernel32.ReadProcessMemory
WriteProcessMemory = kernel32.WriteProcessMemory
VirtualQueryEx = kernel32.VirtualQueryEx
CreateToolhelp32Snapshot = kernel32.CreateToolhelp32Snapshot
Process32First = kernel32.Process32First
Process32Next = kernel32.Process32Next


def get_fm_process() -> Tuple[Optional[int], Optional[str]]:
    """Detects active Football Manager 26 process."""
    targets = ("fm.exe", "footballmanager.exe", "fm26.exe", "fm2026.exe")
    snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snapshot == -1:
        return None, None

    pe32 = PROCESSENTRY32()
    pe32.dwSize = ctypes.sizeof(PROCESSENTRY32)
    found_pid: Optional[int] = None
    found_name: Optional[str] = None

    if Process32First(snapshot, ctypes.byref(pe32)):
        while True:
            exe_name = pe32.szExeFile.decode("utf-8", errors="ignore")
            exe_lower = exe_name.lower()
            if any(exe_lower == t or exe_lower.endswith("\\" + t) for t in targets):
                found_pid = int(pe32.th32ProcessID)
                found_name = exe_name
                break
            if not Process32Next(snapshot, ctypes.byref(pe32)):
                break

    CloseHandle(snapshot)
    return found_pid, found_name


def apply_preset_to_player(player: PlayerRecord, preset: str) -> str:
    """
    Applies a tactical modification preset to a PlayerRecord in-place.
    Properly handles FM26's 1-100 internal scale and keeps inverse attributes low.
    """
    if preset == "super_boost":
        player.ca = 200
        player.pa = 200
        player.current_rep = 10000
        player.home_rep = 10000
        player.world_rep = 10000
        for attr in ATTRIBUTE_DEFS:
            if attr.inverse:
                player.set_display_attribute(attr.index, 1)
            elif attr.category == "Goalkeeping" and not player.is_goalkeeper:
                continue
            else:
                player.set_display_attribute(attr.index, 20)
        return "Applied Super Boost (All 20s, 200 CA/PA, 10000 Reputation, 1 Injury Proneness)"

    if preset == "max_capa":
        player.ca = 200
        player.pa = 200
        return "Locked Current Ability (CA) and Potential Ability (PA) to 200"

    if preset == "max_attributes":
        for attr in ATTRIBUTE_DEFS:
            if attr.inverse:
                player.set_display_attribute(attr.index, 1)
            elif attr.category == "Goalkeeping" and not player.is_goalkeeper:
                continue
            else:
                player.set_display_attribute(attr.index, 20)
        return "Set all positive attributes to 20 and Injury Proneness / Dirtiness to 1"

    if preset == "peak_physical":
        for attr in ATTRIBUTE_DEFS:
            if attr.category == "Physical":
                player.set_display_attribute(attr.index, 20)
        player.set_display_attribute(48, 1)  # Injury Proneness = 1
        player.set_display_attribute(44, 20) # Consistency = 20
        return "Applied Peak Physical & Ironman (All Physicals 20, Injury Proneness 1)"

    if preset == "clinical_finisher":
        finisher_indices = (1, 2, 3, 4, 6, 8, 17, 18, 22, 23, 26, 34, 38, 42, 46, 47, 52)
        for idx in finisher_indices:
            player.set_display_attribute(idx, 20)
        return "Applied Clinical Finisher (20 Finishing, Composure, Dribbling, Pace, Off The Ball)"

    if preset == "playmaker_maestro":
        maestro_indices = (0, 6, 7, 10, 17, 18, 22, 23, 26, 27, 28, 29, 35, 42, 44, 46, 52, 53)
        for idx in maestro_indices:
            player.set_display_attribute(idx, 20)
        return "Applied Playmaker Maestro (20 Passing, Vision, Technique, First Touch, Decisions)"

    return "Preset applied"


class FMController:
    """Win32 Process Memory Controller for Football Manager 26."""

    def __init__(self, pid: int, name: str) -> None:
        self.pid = pid
        self.name = name
        self.cached_targets: Dict[int, List[PlayerMemoryTarget]] = {}
        access = PROCESS_QUERY_INFORMATION | PROCESS_VM_READ | PROCESS_VM_WRITE | PROCESS_VM_OPERATION
        self.handle = OpenProcess(access, False, pid)
        if not self.handle:
            raise PermissionError(f"Cannot attach to {name} (PID: {pid}). Run as Administrator.")

    def close(self) -> None:
        if self.handle:
            CloseHandle(self.handle)
            self.handle = None

    def is_alive(self) -> bool:
        if not self.handle:
            return False
        exit_code = wintypes.DWORD()
        if kernel32.GetExitCodeProcess(self.handle, ctypes.byref(exit_code)):
            return exit_code.value == 259  # STILL_ACTIVE
        return False

    def read_bytes(self, address: int, size: int) -> Optional[bytes]:
        if not self.handle or address <= 0 or size <= 0:
            return None
        buf = (ctypes.c_char * size)()
        bytes_read = ctypes.c_size_t()
        res = ReadProcessMemory(self.handle, ctypes.c_void_p(address), buf, size, ctypes.byref(bytes_read))
        if res and bytes_read.value == size:
            return bytes(buf)
        return None

    def write_bytes(self, address: int, data: bytes) -> bool:
        if not self.handle or address <= 0 or not data:
            return False
        buf = (ctypes.c_char * len(data)).from_buffer_copy(data)
        bytes_written = ctypes.c_size_t()
        res = WriteProcessMemory(self.handle, ctypes.c_void_p(address), buf, len(data), ctypes.byref(bytes_written))
        return bool(res and bytes_written.value == len(data))

    def write_uint8(self, address: int, value: int) -> bool:
        data = struct.pack("B", max(0, min(255, int(value))))
        return self.write_bytes(address, data)

    def write_uint16(self, address: int, value: int) -> bool:
        data = struct.pack("<H", max(0, min(65535, int(value))))
        return self.write_bytes(address, data)

    def write_uint32(self, address: int, value: int) -> bool:
        data = struct.pack("<I", max(0, min(0xFFFFFFFF, int(value))))
        return self.write_bytes(address, data)

    def _validate_target(self, target: PlayerMemoryTarget) -> bool:
        """Verifies that a candidate PlayerMemoryTarget holds valid FM26 player data."""
        rep_ca_pa = self.read_bytes(target.cur_rep_address, 10)
        if not rep_ca_pa:
            return False
        crep, hrep, wrep, ca, pa = struct.unpack_from("<HHHHH", rep_ca_pa, 0)
        if not (1 <= ca <= 200 and 1 <= pa <= 200 and crep <= 10000 and hrep <= 10000 and wrep <= 10000):
            return False

        pos_attr = self.read_bytes(target.pos_address, 69)
        if not pos_attr or len(pos_attr) != 69:
            return False
        pos_bytes = pos_attr[:15]
        attr_bytes = pos_attr[15:69]
        if not all(0 <= b <= 20 for b in pos_bytes):
            return False
        if not all(1 <= b <= 100 for b in attr_bytes):
            return False
        return True

    def locate_player_targets(
        self,
        player: PlayerRecord,
        force_rescan: bool = False,
    ) -> List[PlayerMemoryTarget]:
        """
        Locates all live C++ ACTUAL_PLAYER@db instances and serialized DB records for `player`
        in `fm.exe` memory using a single-pass multi-pattern scan ([UID, UID] + 54-attribute vector).
        """
        if not force_rescan and player.uid in self.cached_targets:
            valid_cached = [t for t in self.cached_targets[player.uid] if self._validate_target(t)]
            if valid_cached:
                self.cached_targets[player.uid] = valid_cached
                return valid_cached

        uid_pair = struct.pack("<II", int(player.uid), int(player.uid))
        attr_sig = bytes(max(1, min(100, int(a))) for a in player.raw_attributes[:36])
        has_attr_sig = len(attr_sig) == 36

        found_by_attr_addr: Dict[int, PlayerMemoryTarget] = {}
        address = 0
        mbi = MEMORY_BASIC_INFORMATION()

        while VirtualQueryEx(self.handle, ctypes.c_void_p(address), ctypes.byref(mbi), ctypes.sizeof(mbi)):
            is_committed = mbi.State == MEM_COMMIT
            is_writable = bool(mbi.Protect & (PAGE_READWRITE | PAGE_WRITECOPY | PAGE_EXECUTE_READWRITE))
            is_guarded = bool(mbi.Protect & (PAGE_GUARD | PAGE_NOACCESS))

            if is_committed and is_writable and not is_guarded and mbi.RegionSize > 0:
                base = mbi.BaseAddress or 0
                size = mbi.RegionSize
                chunk_size = 8 * 1024 * 1024

                for offset in range(0, size, chunk_size):
                    read_len = min(chunk_size, size - offset)
                    chunk_addr = base + offset
                    data = self.read_bytes(chunk_addr, read_len)
                    if not data:
                        continue

                    # 1. Check [UID, UID] occurrences in chunk
                    pos = 0
                    while True:
                        idx = data.find(uid_pair, pos)
                        if idx == -1:
                            break
                        match_addr = chunk_addr + idx

                        # Case 1A: ACTUAL_PLAYER@db (UID pair at this + 0x290)
                        cand_cpp1 = PlayerMemoryTarget.from_cpp_object(
                            player.uid, match_addr - CPP_UID_OFFSET_PLAYER
                        )
                        if cand_cpp1.attr_address not in found_by_attr_addr and self._validate_target(cand_cpp1):
                            found_by_attr_addr[cand_cpp1.attr_address] = cand_cpp1

                        # Case 1B: ACTUAL_PLAYER_AND_NON_PLAYER@db (UID pair at this + 0x388)
                        cand_cpp2 = PlayerMemoryTarget.from_cpp_object(
                            player.uid, match_addr - CPP_UID_OFFSET_PLAYER_NON_PLAYER
                        )
                        if cand_cpp2.attr_address not in found_by_attr_addr and self._validate_target(cand_cpp2):
                            found_by_attr_addr[cand_cpp2.attr_address] = cand_cpp2

                        # Case 1C: Serialized DB record ([UID, UID, 0x02] at +0..+8)
                        if idx + 9 <= len(data) and data[idx + SER_MARKER_OFFSET] == 2:
                            cand_ser = PlayerMemoryTarget.from_serialized_record(player.uid, match_addr)
                            if cand_ser.attr_address not in found_by_attr_addr and self._validate_target(cand_ser):
                                found_by_attr_addr[cand_ser.attr_address] = cand_ser

                        pos = idx + 4

                    # 2. Check 36-byte attribute signature occurrences in chunk
                    if has_attr_sig:
                        pos = 0
                        while True:
                            idx = data.find(attr_sig, pos)
                            if idx == -1:
                                break
                            attr_addr = chunk_addr + idx
                            if attr_addr not in found_by_attr_addr:
                                cand_cpp = PlayerMemoryTarget.from_cpp_object(
                                    player.uid, attr_addr - CPP_ATTR_OFFSET
                                )
                                if self._validate_target(cand_cpp):
                                    found_by_attr_addr[attr_addr] = cand_cpp
                                else:
                                    cand_ser = PlayerMemoryTarget.from_serialized_record(
                                        player.uid, attr_addr - SER_ATTR_OFFSET
                                    )
                                    if self._validate_target(cand_ser):
                                        found_by_attr_addr[attr_addr] = cand_ser
                            pos = idx + 1

            address = (mbi.BaseAddress or 0) + mbi.RegionSize

        targets = sorted(
            found_by_attr_addr.values(),
            key=lambda t: (0 if t.layout == LAYOUT_CPP_OBJECT else 1, t.base_address),
        )
        if targets:
            self.cached_targets[player.uid] = targets
        return targets

    def sync_player_from_memory(
        self,
        player: PlayerRecord,
        targets: List[PlayerMemoryTarget],
    ) -> bool:
        """Reads live attributes, positions, CA, PA, and reputation from FM26 memory into `player`."""
        if not targets:
            return False
        primary = targets[0]
        rep_ca_pa = self.read_bytes(primary.cur_rep_address, 10)
        pos_attr = self.read_bytes(primary.pos_address, 69)
        if not rep_ca_pa or not pos_attr:
            return False

        crep, hrep, wrep, ca, pa = struct.unpack_from("<HHHHH", rep_ca_pa, 0)
        player.current_rep = crep
        player.home_rep = hrep
        player.world_rep = wrep
        player.ca = ca
        player.pa = pa
        player.positions = list(pos_attr[:15])
        player.raw_attributes = list(pos_attr[15:69])
        return True

    def write_player_stats(
        self,
        player: PlayerRecord,
        targets: List[PlayerMemoryTarget],
    ) -> int:
        """
        Writes `player`'s CA, PA, Reputation, 15 Positions, and 54 Attributes (1-100 scale)
        to all resolved memory targets in `fm.exe`.
        Returns the number of successfully patched struct instances.
        """
        if not targets:
            return 0

        ca_clamped = max(1, min(200, int(player.ca)))
        pa_clamped = max(1, min(200, int(player.pa)))
        crep_clamped = max(1, min(10000, int(player.current_rep)))
        hrep_clamped = max(1, min(10000, int(player.home_rep)))
        wrep_clamped = max(1, min(10000, int(player.world_rep)))

        rep_ca_pa_bytes = struct.pack(
            "<HHHHH", crep_clamped, hrep_clamped, wrep_clamped, ca_clamped, pa_clamped
        )
        pos_attr_bytes = player.pos_attr_signature()

        patched_count = 0
        for target in targets:
            ok_rep = self.write_bytes(target.cur_rep_address, rep_ca_pa_bytes)
            ok_pca = self.write_uint8(target.perceived_ca_address, ca_clamped)
            ok_attr = self.write_bytes(target.pos_address, pos_attr_bytes)
            if ok_rep and ok_attr and ok_pca:
                patched_count += 1

        return patched_count
