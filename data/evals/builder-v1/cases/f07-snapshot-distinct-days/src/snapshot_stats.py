import os


def coverage(dir_path):
    """Summarize price snapshot files (*.json) in dir_path."""
    files = [name for name in os.listdir(dir_path) if name.endswith(".json")]
    return {"snapshots": len(files), "days": len(files)}
