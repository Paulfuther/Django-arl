from io import BytesIO
from PIL import Image, ImageOps


def normalize_to_jpeg(
    fileobj,
    target_long_edge: int = 1800,
    target_bytes: int = 850_000,
    min_q: int = 60,
    max_q: int = 92,
    progressive: bool = True,
    return_meta: bool = False,
):
    """
    Convert HEIC/PNG/WEBP/JPEG -> optimized JPEG near target_bytes.
    Returns (BytesIO, ".jpg")  or  (BytesIO, ".jpg", {"quality": int, "bytes": int, "size": (w,h)})

    Notes:
    - Respects EXIF orientation.
    - Drops alpha (converts to RGB).
    - Binary-searches JPEG quality in [min_q, max_q] to approach target_bytes.
    """
    # Open & orient
    img = Image.open(fileobj)
    try:
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass

    # Color mode
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")

    # Resize if needed (cap long edge)
    w, h = img.size
    long_edge = max(w, h)
    if long_edge > target_long_edge:
        scale = target_long_edge / float(long_edge)
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

    # Safety clamps
    min_q = max(1, int(min_q))
    max_q = min(95, int(max_q))
    if min_q > max_q:
        min_q, max_q = max_q, min_q  # swap if passed reversed

    # Guard: absurdly small targets -> force min quality
    target_bytes = max(10_000, int(target_bytes))  # don't try below ~10KB

    lo, hi = min_q, max_q
    best_buf = None
    best_q = min_q

    while lo <= hi:
        q = (lo + hi) // 2
        out = BytesIO()
        img.save(
            out,
            format="JPEG",
            quality=q,
            optimize=True,
            progressive=progressive,
            subsampling="4:2:0",  # typical for photos; reduces size
        )
        size = out.tell()

        if size <= target_bytes:
            best_buf, best_q = out, q
            lo = q + 1  # try higher quality within budget
        else:
            hi = q - 1  # too big -> reduce quality

    if best_buf is None:
        # Couldn’t hit target; fall back to min_q
        best_buf = BytesIO()
        img.save(
            best_buf,
            format="JPEG",
            quality=min_q,
            optimize=True,
            progressive=progressive,
            subsampling="4:2:0",
        )

    final_bytes = best_buf.tell()
    best_buf.seek(0)

    if return_meta:
        return best_buf, ".jpg", {"quality": best_q, "bytes": final_bytes, "size": img.size}
    return best_buf, ".jpg"
