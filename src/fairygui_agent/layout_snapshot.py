"""将宿主原生 RGBA 纹理无损编码为 PNG，不重绘 UI，也不引入图像依赖。"""

from __future__ import annotations

import base64
import binascii
import struct
import zlib
from typing import Any


def encode_snapshot_png(capture: dict[str, Any]) -> bytes:
    if not isinstance(capture, dict):
        raise ValueError("预览像素数据必须是对象")
    width, height = capture.get("width"), capture.get("height")
    # 队列数据按不可信输入校验，先限制尺寸和编码长度，避免异常响应分配巨量内存。
    if (type(width) is not int or type(height) is not int or
            not 1 <= width <= 4096 or not 1 <= height <= 4096 or width * height > 4194304):
        raise ValueError("预览尺寸不合法或超过像素限制")
    if capture.get("format") != "RGBA32" or capture.get("rowOrder") != "bottom-up":
        raise ValueError("预览像素格式或行方向不支持")
    encoded = capture.get("rgbaBase64")
    expected = width * height * 4
    if not isinstance(encoded, str) or len(encoded) != ((expected + 2) // 3) * 4:
        raise ValueError("预览像素长度与尺寸不一致")
    try:
        rgba = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("预览像素不是有效 Base64") from exc
    if len(rgba) != expected:
        raise ValueError("预览像素长度与尺寸不一致")
    # Unity ReadPixels 自下向上，PNG 自上向下；只翻转行顺序，保留每个 RGBA 像素和透明度。
    stride = width * 4
    scanlines = b"".join(b"\x00" + rgba[row * stride:(row + 1) * stride] for row in range(height - 1, -1, -1))

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack("!I", len(data)) + kind + data + struct.pack("!I", zlib.crc32(kind + data))

    header = struct.pack("!2I5B", width, height, 8, 6, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(scanlines)) + chunk(b"IEND", b"")
