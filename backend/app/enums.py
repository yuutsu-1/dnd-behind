import enum


class CreatureSize(str, enum.Enum):
    tiny   = "tiny"
    small  = "small"
    medium = "medium"
    large  = "large"
    huge   = "huge"
    gargantuan = "gargantuan"


class AbilityScore(str, enum.Enum):
    STR = "STR"
    DEX = "DEX"
    CON = "CON"
    INT = "INT"
    WIS = "WIS"
    CHA = "CHA"