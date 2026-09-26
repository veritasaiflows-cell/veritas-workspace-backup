from config_loader import load_threshold


def flag(value):
    """Return True when value is above the configured threshold."""
    return value > load_threshold()
