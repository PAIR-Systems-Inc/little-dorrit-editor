"""Tests for prompt image preparation."""

import base64
import os

from PIL import Image

from little_dorrit_editor.prompt import create_image_message_part


def test_create_image_message_part_respects_max_bytes(tmp_path):
    image_path = tmp_path / "large.png"
    image = Image.frombytes("RGB", (256, 256), os.urandom(256 * 256 * 3))
    image.save(image_path, format="PNG")

    max_bytes = 50_000
    image_part = create_image_message_part(str(image_path), max_bytes=max_bytes)

    assert image_part["type"] == "image_url"
    url = image_part["image_url"]["url"]
    assert url.startswith("data:image/jpeg;base64,")

    encoded = url.split(",", 1)[1]
    decoded = base64.b64decode(encoded)
    assert len(decoded) <= max_bytes
