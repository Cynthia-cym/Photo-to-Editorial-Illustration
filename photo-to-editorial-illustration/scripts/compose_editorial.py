#!/usr/bin/env python3
"""Deterministically compose a source photo and generated illustration.

The image model creates the illustration only. This compositor owns the final
photo/illustration geometry and two-line editorial footer.
"""

import argparse
import hashlib
import json
import math
import re
from pathlib import Path
from statistics import median
from typing import Dict, List, Tuple

from PIL import Image, ImageDraw, ImageFont, ImageOps


RGB = Tuple[int, int, int]

CONFIG = {
    "max_canvas_width": 2048,
    "motif_width_ratio": 0.72,
    "motif_max_height_ratio": 0.62,
    "panel_padding_ratio": 0.06,
    "font_size_ratio": 0.024,
    "line_gap_ratio": 0.525,
}

FONT_PATH = (
    Path(__file__).resolve().parents[1]
    / "assets"
    / "fonts"
    / "Caveat-Regular.ttf"
)

FALLBACK_TEXT_COLOR: RGB = (138, 105, 88)


def classify_orientation(width: int, height: int) -> str:
    return "landscape" if width >= height else "portrait"


def _open_oriented(path: Path) -> Image.Image:
    with Image.open(path) as image:
        return ImageOps.exif_transpose(image).convert("RGB")


def _resize_width(image: Image.Image, target_width: int) -> Image.Image:
    target_height = max(1, round(target_width * image.height / image.width))
    if image.size == (target_width, target_height):
        return image.copy()
    return image.resize((target_width, target_height), Image.Resampling.LANCZOS)


def _estimate_paper_color(image: Image.Image) -> RGB:
    sample = max(2, round(min(image.size) * 0.035))
    boxes = (
        (0, 0, sample, sample),
        (image.width - sample, 0, image.width, sample),
        (0, image.height - sample, sample, image.height),
        (image.width - sample, image.height - sample, image.width, image.height),
    )
    channels = [[], [], []]
    for box in boxes:
        patch = image.crop(box).resize((8, 8), Image.Resampling.BILINEAR)
        for pixel in patch.getdata():
            for index, value in enumerate(pixel):
                channels[index].append(value)
    return tuple(int(median(channel)) for channel in channels)


def _luminance(color: RGB) -> float:
    red, green, blue = color
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def _saturation(color: RGB) -> int:
    return max(color) - min(color)


def _is_near_paper(color: RGB) -> bool:
    return _luminance(color) > 232 and _saturation(color) < 24


def _ranked_illustration_colors(layer: Image.Image) -> List[Tuple[int, RGB]]:
    sample = layer.copy()
    sample.thumbnail((360, 360), Image.Resampling.LANCZOS)
    pixels = [
        pixel[:3]
        for pixel in sample.getdata()
        if pixel[3] >= 80 and not _is_near_paper(pixel[:3])
    ]
    if not pixels:
        return []

    strip = Image.new("RGB", (len(pixels), 1))
    strip.putdata(pixels)
    counts = strip.getcolors(maxcolors=4096)
    if counts is None:
        quantized = strip.quantize(colors=32, method=Image.Quantize.MEDIANCUT).convert("RGB")
        counts = quantized.getcolors(maxcolors=32)
    return sorted(
        (
            (count, color)
            for count, color in counts or []
            if not _is_near_paper(color)
        ),
        key=lambda item: item[0],
        reverse=True,
    )


def _select_text_color(layer: Image.Image, paper_color: RGB) -> RGB:
    ranked = _ranked_illustration_colors(layer)
    if not ranked:
        return FALLBACK_TEXT_COLOR

    total = sum(count for count, _ in ranked)
    candidates = []
    for count, color in ranked:
        luminance = _luminance(color)
        saturation = _saturation(color)
        warmth = color[0] - color[2]
        if not (42 <= luminance <= 168):
            continue
        if saturation > 105 or warmth < -12:
            continue
        if _luminance(paper_color) - luminance < 70:
            continue
        prevalence = count / total
        score = (
            prevalence * 160
            + warmth * 0.55
            - abs(luminance - 100) * 0.30
            - abs(saturation - 48) * 0.16
        )
        candidates.append((score, color))

    if not candidates:
        return FALLBACK_TEXT_COLOR
    return max(candidates, key=lambda item: item[0])[1]


def _hex(color: RGB) -> str:
    return "#{:02X}{:02X}{:02X}".format(*color)


def _load_font(size: int) -> Tuple[ImageFont.ImageFont, str]:
    if not FONT_PATH.is_file():
        raise FileNotFoundError(f"packaged font is missing: {FONT_PATH}")
    return ImageFont.truetype(FONT_PATH, size=size), str(FONT_PATH)


def _validate_copy(title: str, subtitle: str) -> None:
    word_pattern = r"[A-Za-z]+(?:[-'][A-Za-z]+)?"
    title_words = re.findall(word_pattern, title)
    subtitle_words = re.findall(word_pattern, subtitle)
    if not 2 <= len(title_words) <= 4 or " ".join(title_words) != title.strip():
        raise ValueError("title must contain 2–4 English words")
    normalized_subtitle = subtitle.strip().rstrip(".!?")
    if not 4 <= len(subtitle_words) <= 8 or " ".join(subtitle_words) != normalized_subtitle:
        raise ValueError("subtitle must contain 4–8 English words")


def _fit_font(lines: Tuple[str, str], preferred_size: int, maximum_width: int):
    size = preferred_size
    while size >= 18:
        font, font_used = _load_font(size)
        widths = [font.getbbox(line)[2] - font.getbbox(line)[0] for line in lines]
        if max(widths) <= maximum_width:
            return font, font_used, size
        size -= 1
    raise ValueError("footer copy is too long for the illustration board")


def compose_editorial(
    source_photo_path,
    generated_illustration_path,
    title: str,
    subtitle: str,
    output_path,
) -> Dict[str, object]:
    """Create one deterministic photo-plus-illustration editorial composition."""

    _validate_copy(title, subtitle)
    source_path = Path(source_photo_path).expanduser().resolve()
    illustration_path = Path(generated_illustration_path).expanduser().resolve()
    destination = Path(output_path).expanduser().resolve()

    source = _open_oriented(source_path)
    illustration = _open_oriented(illustration_path)
    source_dimensions = list(source.size)
    illustration_dimensions = list(illustration.size)
    orientation = classify_orientation(*source.size)

    board_width = min(source.width, CONFIG["max_canvas_width"])
    photo = _resize_width(source, board_width)
    board_width, board_height = photo.size
    if orientation == "landscape":
        layout = "stacked"
        photo_origin = (0, 0)
        illustration_origin = (0, board_height)
        final_dimensions = (board_width, board_height * 2)
    else:
        layout = "side-by-side"
        photo_origin = (0, 0)
        illustration_origin = (board_width, 0)
        final_dimensions = (board_width * 2, board_height)

    board_left, board_top = illustration_origin
    paper_color = _estimate_paper_color(illustration)
    canvas = Image.new("RGB", final_dimensions, paper_color)
    canvas.paste(photo, photo_origin)

    layer = illustration.convert("RGBA")
    illustration_bbox = (0, 0, illustration.width, illustration.height)
    text_color = _select_text_color(layer, paper_color)

    target_width = round(board_width * CONFIG["motif_width_ratio"])
    target_height = round(board_height * CONFIG["motif_max_height_ratio"])
    requested_scale = min(target_width / layer.width, target_height / layer.height)
    panel_padding = round(
        min(board_width, board_height) * CONFIG["panel_padding_ratio"]
    )
    maximum_width = max(1, board_width - panel_padding * 2)
    contain_scale = maximum_width / layer.width
    scale = min(requested_scale, contain_scale)
    motif_size = (
        max(1, round(layer.width * scale)),
        max(1, round(layer.height * scale)),
    )
    motif = layer.resize(motif_size, Image.Resampling.LANCZOS)

    preferred_font_size = max(
        36,
        round(min(final_dimensions) * CONFIG["font_size_ratio"]),
    )
    text_width = motif.width
    font, font_used, font_size = _fit_font(
        (title, subtitle), preferred_font_size, text_width
    )
    line_gap = round(font_size * CONFIG["line_gap_ratio"])
    title_bbox = font.getbbox(title)
    subtitle_bbox = font.getbbox(subtitle)
    text_block_height = (
        title_bbox[3]
        - title_bbox[1]
        + line_gap
        + subtitle_bbox[3]
        - subtitle_bbox[1]
    )

    remaining_space = board_height - motif.height - text_block_height
    if remaining_space < 5:
        adjusted_height = max(1, board_height - text_block_height - 5)
        scale = adjusted_height / layer.height
        motif_size = (
            max(1, round(layer.width * scale)),
            adjusted_height,
        )
        motif = layer.resize(motif_size, Image.Resampling.LANCZOS)
        remaining_space = board_height - motif.height - text_block_height

    height_adjustment = (5 - remaining_space % 5) % 5
    if height_adjustment:
        adjusted_height = motif.height - height_adjustment
        scale = adjusted_height / layer.height
        motif_size = (
            max(1, round(layer.width * scale)),
            adjusted_height,
        )
        motif = layer.resize(motif_size, Image.Resampling.LANCZOS)
        remaining_space = board_height - motif.height - text_block_height

    illustration_text_gap = remaining_space // 5
    vertical_safe_margin = illustration_text_gap * 2
    text_bottom = board_top + board_height - vertical_safe_margin
    subtitle_position_y = text_bottom - subtitle_bbox[3]
    subtitle_rendered_top = subtitle_position_y + subtitle_bbox[1]
    title_rendered_bottom = subtitle_rendered_top - line_gap
    title_position_y = title_rendered_bottom - title_bbox[3]
    text_top = title_position_y + title_bbox[1]

    motif_x = board_left + round((board_width - motif.width) / 2)
    motif_y = board_top + vertical_safe_margin
    canvas.paste(motif, (motif_x, motif_y), motif)
    illustration_image_box = [
        motif_x,
        motif_y,
        motif_x + motif.width,
        motif_y + motif.height,
    ]

    draw = ImageDraw.Draw(canvas)
    text_right = illustration_image_box[2]

    title_position = (text_right - title_bbox[2], title_position_y)
    subtitle_position = (
        text_right - subtitle_bbox[2],
        subtitle_position_y,
    )
    draw.text(title_position, title, font=font, fill=text_color)
    draw.text(subtitle_position, subtitle, font=font, fill=text_color)
    rendered_title_box = list(draw.textbbox(title_position, title, font=font))
    rendered_subtitle_box = list(
        draw.textbbox(subtitle_position, subtitle, font=font)
    )

    destination.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(destination, format="PNG", optimize=False, compress_level=6)

    return {
        "source_dimensions": source_dimensions,
        "source_aspect_ratio": round(source.width / source.height, 8),
        "illustration_dimensions": illustration_dimensions,
        "orientation": orientation,
        "layout": layout,
        "photo_dimensions": list(photo.size),
        "illustration_board_dimensions": [board_width, board_height],
        "photo_illustration_board_dimensions_match": list(photo.size)
        == [board_width, board_height],
        "photo_aspect_ratio_preserved": math.isclose(
            source.width / source.height,
            photo.width / photo.height,
            rel_tol=0,
            abs_tol=1 / max(photo.size),
        ),
        "photo_box": [
            photo_origin[0],
            photo_origin[1],
            photo_origin[0] + board_width,
            photo_origin[1] + board_height,
        ],
        "illustration_board_box": [
            board_left,
            board_top,
            board_left + board_width,
            board_top + board_height,
        ],
        "final_dimensions": list(final_dimensions),
        "illustration_source_bbox": list(illustration_bbox),
        "illustration_image_box": illustration_image_box,
        "illustration_image_dimensions": list(motif.size),
        "illustration_effective_scale": scale,
        "canvas_paper_color": _hex(paper_color),
        "text_color": _hex(text_color),
        "font_used": font_used,
        "preferred_font_size": preferred_font_size,
        "font_size": font_size,
        "line_gap": line_gap,
        "footer_box": [
            board_left,
            text_top,
            board_left + board_width,
            text_bottom,
        ],
        "vertical_safe_margin": vertical_safe_margin,
        "illustration_text_gap": illustration_text_gap,
        "title": title,
        "subtitle": subtitle,
        "title_box": rendered_title_box,
        "subtitle_box": rendered_subtitle_box,
        "output_sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-photo", required=True)
    parser.add_argument("--illustration", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--subtitle", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    metadata = compose_editorial(
        source_photo_path=args.source_photo,
        generated_illustration_path=args.illustration,
        title=args.title,
        subtitle=args.subtitle,
        output_path=args.output,
    )
    print(json.dumps(metadata, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
