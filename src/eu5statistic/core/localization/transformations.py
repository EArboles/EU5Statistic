def transform_culture_name(name: str, language: str) -> str:
    """
    Adjusts culture name for the target language.

    Russian EU5 localization stores cultures as truncated adjectives
    ("Шведск", "Турецк", "Чешск"). We restore the feminine adjective form
    for display in statistics ("Шведская", "Турецкая", "Чешская").

    Names that are not adjectives (e.g., "Фарси") are returned unchanged.
    """
    if language != "russian":
        return name

    # Russian EU5 localization uses truncated adjectives: "Шведск", "Турецк", "Чешск".
    # We restore the feminine adjective form for display in statistics.
    if name.endswith(("ск", "цк")):
        return name + "ая"
    return name  # "Фарси", "Маори" (if not adjective) stay as is


def transform_country_name(name: str, is_revolt: bool, language: str) -> str:
    """Adds a prefix for revolts, localized."""
    if not is_revolt:
        return name
    prefixes = {
        "russian": "Восстание: ",
        "english": "Revolt: ",
    }
    return prefixes.get(language, "Revolt: ") + name


def get_terra_nullius_name(language: str) -> str:
    """Returns the localized name for unclaimed territory (TERRA_NULLIUS)."""
    names = {
        "russian": "Ничейная земля",
        "english": "No Man's Land",
    }
    return names.get(language, "No Man's Land")
