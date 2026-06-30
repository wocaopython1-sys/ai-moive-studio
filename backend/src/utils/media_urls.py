from urllib.parse import quote


def media_url_for_object_key(object_key: str, disposition: str = "preview") -> str:
    clean_key = str(object_key or "").strip().lstrip("/")
    if not clean_key:
        return ""
    safe_key = quote(clean_key, safe="/")
    mode = disposition if disposition in {"preview", "download", "stream"} else "preview"
    return f"/api/v1/media/{mode}/{safe_key}"
