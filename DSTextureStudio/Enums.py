from enum import Enum, auto

class ExportMode(Enum):
    ATLAS = auto()
    SUBTEXTURE = auto()

class GameType(Enum):
    OLD = auto()
    MODERN = auto()
    PS = auto()

class Modified(Enum):
    FALSE = auto()
    ADDED = auto()
    REPLACED = auto()

class Game():
    OLD_GAMES = {"Dark Souls 1", "Dark Souls 2", "Dark Souls 3"}
    PS_GAMES = {"Bloodborne", "Demon's Souls"}

    def __init__(self, name: str):
        self.name = name
        self.type = self.classify(name)

    def classify(self, name: str) -> GameType:
        if name in self.OLD_GAMES:
            return GameType.OLD
        elif name in self.PS_GAMES:
            return GameType.PS
        else:
            return GameType.MODERN

    def __repr__(self):
        return f"Game({self.name}, {self.type.name})"

class ResFormat(Enum):
    NIGHTREIGN = ("Nightreign", {"H": "High", "L": "Low"})
    ELDEN_RING = ("Elden Ring", {"H": "Hi", "L": "Low"})
    SEKIRO = ("Sekiro", {"H": "Hi", "L": "Low"})

    def __init__(self, game_name: str, mapping: dict[str, str]):
        self.game_name = game_name
        self.mapping = mapping

    def get(self, res: str) -> str:
        return self.mapping.get(res, res)

    @classmethod
    def from_name(cls, name: str):
        for g in cls:
            if g.game_name == name:
                return g
        raise ValueError(f"Unknown game: {name}")
