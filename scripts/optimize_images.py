#!/usr/bin/env python3
"""Create deterministic WebP derivatives for public, content-bearing images."""

from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"
TARGETS = {
    "img/azizbek.png": [(256, "img/azizbek-256.webp")],
    "img/maqsudbek.png": [(256, "img/maqsudbek-256.webp")],
    "img/islomjon.png": [(256, "img/islomjon-256.webp")],
    "img/logo2.png": [
        (320, "img/iceberg-method-320.webp"),
        (640, "img/iceberg-method-640.webp"),
    ],
}


def build() -> None:
    for source_name, variants in TARGETS.items():
        source_path = STATIC / source_name
        with Image.open(source_path) as source:
            source = source.convert("RGB")
            for width, output_name in variants:
                ratio = min(width / source.width, 1)
                size = (round(source.width * ratio), round(source.height * ratio))
                output = source.resize(size, Image.Resampling.LANCZOS)
                output_path = STATIC / output_name
                output.save(output_path, "WEBP", quality=82, method=6)
                print(
                    f"{source_path.relative_to(ROOT)} -> "
                    f"{output_path.relative_to(ROOT)} ({size[0]}x{size[1]})"
                )


if __name__ == "__main__":
    build()
