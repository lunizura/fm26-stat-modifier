"""
FM26 Binary Struct Schema, Attribute Scaling, and Player Record Model.

Verified against Football Manager 26 (game_plugin.dll RTTI & ACTUAL_PLAYER@db vftable
at RVA 0x4435BB8 / write_to_stream at RVA 0x1295EF0) and active .fm Zstd database streams.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

# In-memory C++ object offsets (ACTUAL_PLAYER@db / ACTUAL_PLAYER_AND_NON_PLAYER@db)
CPP_POS_OFFSET = 0x150                   # 15 bytes: positional ratings (1-20 scale)
CPP_ATTR_OFFSET = 0x15F                  # 54 bytes: player attributes (1-100 internal scale)
CPP_POS_ATTR_SIZE = 69                   # 0x45 contiguous bytes (15 positions + 54 attributes)

CPP_CUR_REP_OFFSET = 0x25E               # uint16 (1-10000)
CPP_HOME_REP_OFFSET = 0x260              # uint16 (1-10000)
CPP_WORLD_REP_OFFSET = 0x262             # uint16 (1-10000)
CPP_CA_OFFSET = 0x264                    # uint16 Current Ability (1-200)
CPP_PA_OFFSET = 0x266                    # uint16 Potential Ability (1-200)
CPP_PERCEIVED_CA_OFFSET = 0x275          # uint8 Perceived CA (1-200)

CPP_UID_OFFSET_PLAYER = 0x290            # [uint32 uid, uint32 uid] in ACTUAL_PLAYER@db
CPP_UID_OFFSET_PLAYER_NON_PLAYER = 0x388 # [uint32 uid, uint32 uid] in ACTUAL_PLAYER_AND_NON_PLAYER@db

# Serialized DB record offsets (relative to [uint32 uid, uint32 uid, uint8 0x02] header)
SER_MARKER_OFFSET = 8                    # uint8 == 0x02
SER_CUR_REP_OFFSET = 9                   # uint16 (1-10000)
SER_HOME_REP_OFFSET = 11                 # uint16 (1-10000)
SER_WORLD_REP_OFFSET = 13                # uint16 (1-10000)
SER_CA_OFFSET = 15                       # uint16 Current Ability (1-200)
SER_PA_OFFSET = 17                       # uint16 Potential Ability (1-200)
SER_PERCEIVED_CA_OFFSET = 19             # uint8 Perceived CA (1-200)
SER_POS_OFFSET = 39                      # 15 bytes: positional ratings (1-20 scale)
SER_ATTR_OFFSET = 54                     # 54 bytes: player attributes (1-100 internal scale)


@dataclass(frozen=True)
class AttributeDef:
    index: int
    name: str
    category: str
    inverse: bool = False  # True when lower is better (e.g. Injury Proneness, Dirtiness)


@dataclass(frozen=True)
class PositionDef:
    index: int
    code: str
    name: str


# Exact 15 positional rating slots at +0x150 (C++) / +39 (Serialized DB)
POSITION_DEFS: Tuple[PositionDef, ...] = (
    PositionDef(0, "GK", "Goalkeeper"),
    PositionDef(1, "SW", "Sweeper"),
    PositionDef(2, "DL", "Defender Left"),
    PositionDef(3, "DC", "Defender Central"),
    PositionDef(4, "DR", "Defender Right"),
    PositionDef(5, "DM", "Defensive Midfielder"),
    PositionDef(6, "ML", "Midfielder Left"),
    PositionDef(7, "MC", "Midfielder Central"),
    PositionDef(8, "MR", "Midfielder Right"),
    PositionDef(9, "AML", "Attacking Midfielder Left"),
    PositionDef(10, "AMC", "Attacking Midfielder Central"),
    PositionDef(11, "AMR", "Attacking Midfielder Right"),
    PositionDef(12, "ST", "Striker"),
    PositionDef(13, "WBL", "Wing Back Left"),
    PositionDef(14, "WBR", "Wing Back Right"),
)

# Exact 54 player attribute slots at +0x15F (C++) / +54 (Serialized DB)
ATTRIBUTE_DEFS: Tuple[AttributeDef, ...] = (
    # Outfield Technicals Part 1 (0..10)
    AttributeDef(0, "Crossing", "Technical"),
    AttributeDef(1, "Dribbling", "Technical"),
    AttributeDef(2, "Finishing", "Technical"),
    AttributeDef(3, "Heading", "Technical"),
    AttributeDef(4, "Long Shots", "Technical"),
    AttributeDef(5, "Marking", "Technical"),
    AttributeDef(6, "Off The Ball", "Mental"),
    AttributeDef(7, "Passing", "Technical"),
    AttributeDef(8, "Penalty Taking", "Technical"),
    AttributeDef(9, "Tackling", "Technical"),
    AttributeDef(10, "Vision", "Mental"),
    # Goalkeeping Part 1 (11..16)
    AttributeDef(11, "Handling", "Goalkeeping"),
    AttributeDef(12, "Aerial Reach", "Goalkeeping"),
    AttributeDef(13, "Command of Area", "Goalkeeping"),
    AttributeDef(14, "Communication", "Goalkeeping"),
    AttributeDef(15, "Kicking", "Goalkeeping"),
    AttributeDef(16, "Throwing", "Goalkeeping"),
    # Mixed Mental / Technical / GK (17..33)
    AttributeDef(17, "Anticipation", "Mental"),
    AttributeDef(18, "Decisions", "Mental"),
    AttributeDef(19, "One on Ones", "Goalkeeping"),
    AttributeDef(20, "Positioning", "Mental"),
    AttributeDef(21, "Reflexes", "Goalkeeping"),
    AttributeDef(22, "First Touch", "Technical"),
    AttributeDef(23, "Technique", "Technical"),
    AttributeDef(24, "Left Foot", "Physical"),
    AttributeDef(25, "Right Foot", "Physical"),
    AttributeDef(26, "Flair", "Mental"),
    AttributeDef(27, "Corners", "Technical"),
    AttributeDef(28, "Teamwork", "Mental"),
    AttributeDef(29, "Work Rate", "Mental"),
    AttributeDef(30, "Long Throws", "Technical"),
    AttributeDef(31, "Eccentricity", "Goalkeeping", inverse=True),
    AttributeDef(32, "Rushing Out", "Goalkeeping"),
    AttributeDef(33, "Tendency to Punch", "Goalkeeping"),
    # Physical / Mental / Hidden (34..53)
    AttributeDef(34, "Acceleration", "Physical"),
    AttributeDef(35, "Free Kick Taking", "Technical"),
    AttributeDef(36, "Strength", "Physical"),
    AttributeDef(37, "Stamina", "Physical"),
    AttributeDef(38, "Pace", "Physical"),
    AttributeDef(39, "Jumping Reach", "Physical"),
    AttributeDef(40, "Leadership", "Mental"),
    AttributeDef(41, "Dirtiness", "Hidden", inverse=True),
    AttributeDef(42, "Balance", "Physical"),
    AttributeDef(43, "Bravery", "Mental"),
    AttributeDef(44, "Consistency", "Hidden"),
    AttributeDef(45, "Aggression", "Mental"),
    AttributeDef(46, "Agility", "Physical"),
    AttributeDef(47, "Important Matches", "Hidden"),
    AttributeDef(48, "Injury Proneness", "Hidden", inverse=True),
    AttributeDef(49, "Versatility", "Hidden"),
    AttributeDef(50, "Natural Fitness", "Physical"),
    AttributeDef(51, "Determination", "Mental"),
    AttributeDef(52, "Composure", "Mental"),
    AttributeDef(53, "Concentration", "Mental"),
)

ATTR_BY_INDEX: Dict[int, AttributeDef] = {a.index: a for a in ATTRIBUTE_DEFS}
ATTR_BY_NAME: Dict[str, AttributeDef] = {a.name.lower(): a for a in ATTRIBUTE_DEFS}

CATEGORIES: Tuple[str, ...] = ("Technical", "Mental", "Physical", "Goalkeeping", "Hidden")
ATTRS_BY_CATEGORY: Dict[str, List[AttributeDef]] = {
    cat: sorted([a for a in ATTRIBUTE_DEFS if a.category == cat], key=lambda x: x.name)
    for cat in CATEGORIES
}


def to_display_attr(raw_byte: int) -> int:
    """
    Converts FM26 internal attribute byte (1-100) to in-game display value (1-20).
    Matches game_plugin.dll RVA 0x12B4A90: ((raw * 0x6667 + 0xCCCE) >> 17) clamped to [1, 20].
    """
    val = (int(raw_byte) * 0x6667 + 0xCCCE) >> 17
    return max(1, min(20, val))


def to_raw_attr(display_val: int) -> int:
    """
    Converts in-game display attribute (1-20) to FM26 internal binary byte (5-100).
    """
    clamped = max(1, min(20, int(display_val)))
    return clamped * 5


@dataclass
class PlayerRecord:
    uid: int
    display_name: str
    full_name: str
    short_name: str
    birth_year: int
    ca: int
    pa: int
    current_rep: int
    home_rep: int
    world_rep: int
    positions: List[int] = field(default_factory=lambda: [1] * 15)      # 15 values (1-20)
    raw_attributes: List[int] = field(default_factory=lambda: [50] * 54) # 54 values (1-100)
    db_offset: int = -1

    @property
    def age(self) -> int:
        if 1960 <= self.birth_year <= 2015:
            return max(14, 2025 - self.birth_year)
        return 24

    @property
    def is_goalkeeper(self) -> bool:
        return len(self.positions) > 0 and self.positions[0] >= 15

    def best_positions_str(self, limit: int = 3) -> str:
        natural = [
            POSITION_DEFS[i].code
            for i, val in enumerate(self.positions[:15])
            if val >= 18
        ]
        if not natural:
            accomplished = sorted(
                range(min(15, len(self.positions))),
                key=lambda i: self.positions[i],
                reverse=True,
            )
            natural = [POSITION_DEFS[i].code for i in accomplished[:2] if self.positions[i] >= 12]
        return ", ".join(natural[:limit]) if natural else "ST"

    def get_display_attributes(self) -> Dict[int, int]:
        return {i: to_display_attr(raw) for i, raw in enumerate(self.raw_attributes[:54])}

    def set_display_attribute(self, idx: int, val_20: int) -> None:
        if 0 <= idx < len(self.raw_attributes):
            self.raw_attributes[idx] = to_raw_attr(val_20)

    def pos_attr_signature(self) -> bytes:
        pos_b = bytes(max(0, min(20, int(p))) for p in self.positions[:15])
        attr_b = bytes(max(1, min(100, int(a))) for a in self.raw_attributes[:54])
        return pos_b + attr_b
