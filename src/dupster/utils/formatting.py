def human_size(n: int) -> str:
    try:
        n = int(n)
    except Exception:
        return "—"
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(n)
    for u in units:
        if size < 1024 or u == units[-1]:
            return f"{size:.1f} {u}"
        size /= 1024
    return f"{n} B"
