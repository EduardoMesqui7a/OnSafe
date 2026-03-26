PERSON_CLASS = "person"
HELMET_CLASS = "helmet"
VEST_CLASS = "vest"

ALIASES = {
    PERSON_CLASS: {"person", "pessoa"},
    HELMET_CLASS: {"helmet", "capacete", "hardhat"},
    VEST_CLASS: {"vest", "colete", "safety vest"},
}

SUPPORTED_CLASSES = {PERSON_CLASS, HELMET_CLASS, VEST_CLASS}


def normalize_class_name(name: str) -> str | None:
    normalized = name.strip().lower()
    if normalized.startswith("no "):
        return None
    for canonical, aliases in ALIASES.items():
        if normalized in aliases:
            return canonical
    return None
