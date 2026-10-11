"""
FM26 Save Database Parser & Instant Name-Only Player Search Engine.

Automatically locates and indexes Football Manager 26 (.fm) save files using Zstandard
stream decompression and the 3-table Name Dictionary (FirstName, SecondName, CommonName).
"""

import os
import pickle
import struct
import time
import unicodedata
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

try:
    import zstandard as zstd
except ImportError:
    zstd = None

from fm_catalog import get_star_catalog
from fm_schema import PlayerRecord

_CHAR_MAP = str.maketrans({
    "ø": "o", "Ø": "o",
    "æ": "ae", "Æ": "ae",
    "ß": "ss",
    "ł": "l", "Ł": "l",
    "đ": "d", "Đ": "d",
    "ı": "i", "İ": "i",
    "œ": "oe", "Œ": "oe",
})


def normalize_name(text: str) -> str:
    """Normalizes a player name to lowercase ASCII (stripping accents and diacritics)."""
    if not text:
        return ""
    mapped = text.translate(_CHAR_MAP)
    decomposed = unicodedata.normalize("NFKD", mapped)
    ascii_str = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(ascii_str.lower().split())


def list_fm26_saves() -> List[str]:
    """Finds all .fm save files in standard Football Manager 26 user directories."""
    home = Path.home()
    candidates_dirs = [
        home / "Documents" / "Sports Interactive" / "Football Manager 26" / "games",
        home / "OneDrive" / "Documents" / "Sports Interactive" / "Football Manager 26" / "games",
    ]
    saves: List[Path] = []
    for d in candidates_dirs:
        if d.is_dir():
            for f in d.glob("*.fm"):
                if f.is_file() and f.stat().st_size > 1_000_000:
                    saves.append(f)
    saves.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return [str(p) for p in saves]


def find_latest_fm26_save() -> Optional[str]:
    """Returns the path to the most recently modified FM26 .fm save file, if any."""
    saves = list_fm26_saves()
    return saves[0] if saves else None


class FMDatabase:
    """
    In-memory player database supporting sub-10ms accent-insensitive Name-Only search
    across all ~46,500 players in an active FM26 save file (with Star Catalog fallback).
    """

    CACHE_VERSION = 2

    def __init__(self) -> None:
        self.players_by_uid: Dict[int, PlayerRecord] = {}
        self._search_index: List[Tuple[str, str, str, PlayerRecord]] = []
        self.loaded_save_path: Optional[str] = None
        self.load_time_sec: float = 0.0
        self._load_builtin_catalog()

    def _load_builtin_catalog(self) -> None:
        for p in get_star_catalog():
            self.players_by_uid[p.uid] = p
        self._rebuild_search_index()

    def _rebuild_search_index(self) -> None:
        idx: List[Tuple[str, str, str, PlayerRecord]] = []
        for p in self.players_by_uid.values():
            n_disp = normalize_name(p.display_name)
            n_full = normalize_name(p.full_name)
            n_short = normalize_name(p.short_name)
            idx.append((n_disp, n_full, n_short, p))
        # Pre-sort by CA and reputation descending
        idx.sort(key=lambda item: (item[3].ca, item[3].current_rep, item[3].world_rep), reverse=True)
        self._search_index = idx

    @property
    def player_count(self) -> int:
        return len(self.players_by_uid)

    def get_player_by_uid(self, uid: int) -> Optional[PlayerRecord]:
        return self.players_by_uid.get(int(uid))

    def _get_cache_path(self, save_path: str) -> Path:
        local_app = os.environ.get("LOCALAPPDATA") or str(Path.home() / ".cache")
        cache_dir = Path(local_app) / "FM26StatModifier" / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        st = os.stat(save_path)
        safe_name = Path(save_path).stem.replace(" ", "_")
        return cache_dir / f"{safe_name}_{st.st_size}_{int(st.st_mtime)}_v{self.CACHE_VERSION}.pkl"

    def load_save_file(
        self,
        save_path: str,
        progress_cb: Optional[Callable[[str], None]] = None,
        use_cache: bool = True,
    ) -> int:
        """
        Decompresses and indexes all players from an FM26 .fm save file.
        Returns total number of indexed players.
        """
        if not save_path or not os.path.isfile(save_path):
            raise FileNotFoundError(f"Save file not found: {save_path}")

        t0 = time.time()
        cache_file = self._get_cache_path(save_path)

        if use_cache and cache_file.is_file():
            try:
                if progress_cb:
                    progress_cb(f"Loading cached player index for {Path(save_path).name}...")
                with open(cache_file, "rb") as f:
                    cached_players: List[PlayerRecord] = pickle.load(f)
                if cached_players and len(cached_players) > 1000:
                    for p in cached_players:
                        self.players_by_uid[p.uid] = p
                    self._rebuild_search_index()
                    self.loaded_save_path = save_path
                    self.load_time_sec = time.time() - t0
                    return len(self.players_by_uid)
            except Exception:
                pass

        if zstd is None:
            raise RuntimeError("zstandard library is required to parse .fm save files.")

        if progress_cb:
            progress_cb(f"Reading save file {Path(save_path).name}...")

        with open(save_path, "rb") as f:
            raw = f.read()

        # Locate the main DB Zstd frame (4th Zstd frame at ~8063..37.5MB, or largest frame)
        magics: List[int] = []
        pos = 0
        while len(magics) < 12:
            idx = raw.find(b"\x28\xb5\x2f\xfd", pos)
            if idx == -1:
                break
            magics.append(idx)
            pos = idx + 4

        if len(magics) >= 5:
            z_start, z_end = magics[3], magics[4]
        elif len(magics) >= 2:
            z_start, z_end = magics[-1], len(raw)
        else:
            raise ValueError("Invalid or unsupported FM26 save file container.")

        if progress_cb:
            progress_cb("Decompressing FM26 database stream...")

        dctx = zstd.ZstdDecompressor()
        reader = dctx.stream_reader(raw[z_start:z_end], read_across_frames=False)
        data = reader.read()
        del raw

        if progress_cb:
            progress_cb("Parsing FirstName, SecondName, and CommonName tables...")

        fn_start = data.find(b"\x00\x00\x00\x00\x08\x00\x00\x00Old\xc5\x99ich")
        if fn_start == -1:
            raise ValueError("Could not locate FM26 Name Tables in database stream.")

        fn_count = struct.unpack_from("<I", data, fn_start - 4)[0]
        cur = fn_start
        first_names = [b""] * fn_count
        for _ in range(fn_count):
            nid, slen = struct.unpack_from("<II", data, cur)
            if nid < fn_count:
                first_names[nid] = data[cur + 8 : cur + 8 + slen]
            cur += 8 + slen

        sn_count = struct.unpack_from("<I", data, cur)[0]
        cur += 4
        second_names = [b""] * sn_count
        for _ in range(sn_count):
            nid, slen = struct.unpack_from("<II", data, cur)
            if nid < sn_count:
                second_names[nid] = data[cur + 8 : cur + 8 + slen]
            cur += 8 + slen

        cn_count = struct.unpack_from("<I", data, cur)[0]
        cur += 4
        common_names = [b""] * cn_count
        for _ in range(cn_count):
            nid, slen = struct.unpack_from("<II", data, cur)
            if nid < cn_count:
                common_names[nid] = data[cur + 8 : cur + 8 + slen]
            cur += 8 + slen

        if progress_cb:
            progress_cb("Indexing all player records and 54-attribute vectors...")

        sig = b"\x01\x00\x6c\x07\x00\x01\x00\x6c\x07\x01\x00\x6c\x07"
        pos = cur
        common_dists = (204, 244, 277, 310, 343, 219, 236, 254, 376, 434)
        parsed_list: List[PlayerRecord] = []

        while True:
            idx = data.find(sig, pos)
            if idx == -1:
                break
            rec_off = -1
            for d in common_dists:
                r = idx - d
                if r >= 0 and data[r + 8] == 2:
                    u1, u2 = struct.unpack_from("<II", data, r)
                    if u1 == u2 and u1 > 100 and u1 != 0xFFFFFFFF:
                        rec_off = r
                        break
            if rec_off == -1:
                for d in range(180, 480):
                    r = idx - d
                    if r >= 0 and data[r + 8] == 2:
                        u1, u2 = struct.unpack_from("<II", data, r)
                        if u1 == u2 and u1 > 100 and u1 != 0xFFFFFFFF:
                            rec_off = r
                            break

            if rec_off != -1:
                uid = struct.unpack_from("<I", data, rec_off)[0]
                crep, hrep, wrep, ca, pa = struct.unpack_from("<HHHHH", data, rec_off + 9)
                if 0 <= ca <= 200 and 0 <= pa <= 200 and crep <= 10000:
                    slen = struct.unpack_from("<I", data, idx + 13)[0]
                    sname = (
                        data[idx + 17 : idx + 17 + slen].decode("utf-8", errors="replace")
                        if slen <= 64
                        else ""
                    )
                    scan_start = idx + 17 + (slen if slen <= 64 else 0)
                    scan_end = min(len(data) - 24, idx + 1350)
                    sub = data[scan_start:scan_end]
                    f_id = s_id = c_id = 0xFFFFFFFF
                    full_name = ""
                    byear = 2000

                    # Fast Path 1: CommonNameID == 0xFFFFFFFF
                    m_pos = 0
                    while True:
                        ff_idx = sub.find(b"\xff\xff\xff\xff\x00", m_pos)
                        if ff_idx == -1 or ff_idx + 9 > len(sub):
                            break
                        if ff_idx >= 10 and sub[ff_idx - 6] == 0 and sub[ff_idx - 1] == 0:
                            fn_len = struct.unpack_from("<I", sub, ff_idx + 5)[0]
                            end_fn = ff_idx + 9 + fn_len
                            if fn_len <= 120 and end_fn + 4 <= len(sub):
                                bday, byr = struct.unpack_from("<HH", sub, end_fn)
                                if 1 <= bday <= 366 and 1965 <= byr <= 2012:
                                    fid = struct.unpack_from("<I", sub, ff_idx - 10)[0]
                                    sid = struct.unpack_from("<I", sub, ff_idx - 5)[0]
                                    if fid < fn_count and sid < sn_count:
                                        f_id, s_id, c_id = fid, sid, 0xFFFFFFFF
                                        if fn_len > 0:
                                            full_name = sub[ff_idx + 9 : end_fn].decode("utf-8", errors="replace")
                                        byear = byr
                                        break
                        m_pos = ff_idx + 1

                    # Fast Path 2: Player has a CommonNameID (< cn_count)
                    if f_id == 0xFFFFFFFF:
                        m_pos = 19
                        while True:
                            n_idx = sub.find(b"\x00\x00\x00\x03", m_pos)
                            if n_idx == -1:
                                break
                            end_fn = n_idx - 9
                            if end_fn >= 19:
                                bday, byr = struct.unpack_from("<HH", sub, end_fn)
                                if 1 <= bday <= 366 and 1965 <= byr <= 2012:
                                    for p in range(max(0, end_fn - 120), end_fn - 18):
                                        if sub[p + 4] == 0 and sub[p + 9] == 0 and sub[p + 14] == 0:
                                            fn_len = struct.unpack_from("<I", sub, p + 15)[0]
                                            if p + 19 + fn_len == end_fn:
                                                fid = struct.unpack_from("<I", sub, p)[0]
                                                sid = struct.unpack_from("<I", sub, p + 5)[0]
                                                cid = struct.unpack_from("<I", sub, p + 10)[0]
                                                if fid < fn_count and sid < sn_count and cid < cn_count:
                                                    f_id, s_id, c_id = fid, sid, cid
                                                    if fn_len > 0:
                                                        full_name = sub[p + 19 : end_fn].decode("utf-8", errors="replace")
                                                    byear = byr
                                                    break
                                    if f_id != 0xFFFFFFFF:
                                        break
                            m_pos = n_idx + 1

                    fn_str = first_names[f_id].decode("utf-8", errors="replace") if f_id < fn_count else ""
                    sn_str = second_names[s_id].decode("utf-8", errors="replace") if s_id < sn_count else ""
                    cn_str = common_names[c_id].decode("utf-8", errors="replace") if c_id < cn_count else ""
                    first_last = f"{fn_str} {sn_str}".strip()
                    display_name = cn_str if cn_str else (first_last or sname or f"Player #{uid}")
                    if not full_name:
                        full_name = first_last or display_name

                    positions = list(data[rec_off + 39 : rec_off + 54])
                    raw_attrs = list(data[rec_off + 54 : rec_off + 108])

                    rec = PlayerRecord(
                        uid=uid,
                        display_name=display_name,
                        full_name=full_name,
                        short_name=sname or display_name,
                        birth_year=byear,
                        ca=ca,
                        pa=pa,
                        current_rep=crep,
                        home_rep=hrep,
                        world_rep=wrep,
                        positions=positions,
                        raw_attributes=raw_attrs,
                        db_offset=rec_off,
                    )
                    self.players_by_uid[uid] = rec
                    parsed_list.append(rec)

            pos = idx + 13

        self._rebuild_search_index()
        self.loaded_save_path = save_path
        self.load_time_sec = time.time() - t0

        if use_cache and parsed_list:
            try:
                with open(cache_file, "wb") as f:
                    pickle.dump(parsed_list, f, protocol=pickle.HIGHEST_PROTOCOL)
            except Exception:
                pass

        return len(self.players_by_uid)

    def search_players(
        self,
        query: str = "",
        limit: int = 40,
        filter_mode: str = "all",
    ) -> List[PlayerRecord]:
        """
        Searches players using ONLY the player name (accent-insensitive, multi-word,
        supporting display name, common name, shirt name, or full legal name).
        Also matches UID if the user enters a numeric ID.
        """
        q_raw = query.strip()

        # Numeric UID shortcut if user enters digits
        if q_raw.isdigit():
            uid_val = int(q_raw)
            exact = self.players_by_uid.get(uid_val)
            if exact:
                return [exact]

        q_norm = normalize_name(q_raw)
        tokens = q_norm.split()

        PORTUGAL_STAR_UIDS = {
            735107, 43124199, 55041623, 83174759, 83169004,
            83261909, 55070298, 83252882, 83287266, 83157298,
            55066238, 83232515, 83276450, 55082509, 83180839,
        }

        if not tokens:
            results: List[PlayerRecord] = []
            for _, _, _, p in self._search_index:
                if filter_mode == "wonderkids" and not (p.age <= 21 and p.pa >= 165):
                    continue
                if filter_mode == "portugal" and p.uid not in PORTUGAL_STAR_UIDS and "portugal" not in p.full_name.lower():
                    # Check typical Portuguese full names if full DB is loaded
                    if not any(w in p.full_name for w in ("Santos", "Silva", "Fernandes", "Ferreira", "Costa", "Mendes", "Dias", "Neves", "Conceição", "Leão", "Palhinha", "Inácio", "Ramos", "Jota", "Trincão", "Quenda", "Mora")):
                        continue
                results.append(p)
                if len(results) >= limit:
                    break
            return results

        scored: List[Tuple[float, PlayerRecord]] = []
        for n_disp, n_full, n_short, p in self._search_index:
            if filter_mode == "wonderkids" and not (p.age <= 21 and p.pa >= 160):
                continue

            combined = f"{n_disp} {n_full} {n_short}"
            if not all(tok in combined for tok in tokens):
                continue

            score = 0.0
            if n_disp == q_norm or n_short == q_norm:
                score += 1200.0
            elif n_disp.startswith(q_norm):
                score += 750.0
            elif f" {q_norm}" in f" {n_disp}":
                score += 550.0
            elif all(tok in n_disp for tok in tokens):
                score += 380.0
            elif all(tok in n_full for tok in tokens):
                score += 200.0
            else:
                score += 100.0

            # Boost by player quality (CA & Reputation) so world-class stars always rank #1
            score += p.ca * 1.6 + (p.current_rep / 50.0)
            scored.append((score, p))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [item[1] for item in scored[:limit]]
