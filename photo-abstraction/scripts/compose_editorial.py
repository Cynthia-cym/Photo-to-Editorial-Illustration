#!/usr/bin/env python3
"""Deterministically compose a source photo and generated illustration.

The image model creates the illustration only. This compositor owns the final
photo/panel geometry, title, and four-color palette.
"""

import argparse
import hashlib
import json
import math
import re
from collections import deque
from pathlib import Path
from statistics import median
from typing import Dict, List, Sequence, Tuple

from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageOps


RGB = Tuple[int, int, int]

CONFIG = {
    "near_square_min": 0.90,
    "near_square_max": 1.10,
    "max_canvas_width": 2048,
    "paper_color": (249, 247, 241),
    "motif_width_ratio": 0.72,
    "motif_max_height_ratio": 0.62,
    "panel_padding_ratio": 0.06,
    "footer_padding_ratio": 0.055,
    "footer_height_ratio": 0.18,
    "chip_size_ratio": 0.036,
    "chip_gap_ratio": 0.014,
    "font_size_ratio": 0.036,
    "paper_distance_low": 10,
    "paper_distance_high": 42,
    "component_thumbnail_max": 512,
    "component_relative_area": 0.001,
}

FONT_PATH = Path(__file__).resolve().parents[1] / "assets" / "fonts" / "NotoSans-Regular.ttf"

FALLBACK_PALETTE: Tuple[RGB, ...] = (
    (138, 105, 88),
    (57, 48, 54),
    (221, 215, 202),
    (205, 169, 105),
)


def classify_orientation(width: int, height: int) -> str:
    ratio = width / height
    if ratio > CONFIG["near_square_max"]:
        return "landscape"
    if ratio < CONFIG["near_square_min"]:
        return "portrait"
    return "near-square"


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


def _distance_mask(image: Image.Image, paper_color: RGB) -> Image.Image:
    paper = Image.new("RGB", image.size, paper_color)
    difference = ImageChops.difference(image, paper)
    red, green, blue = difference.split()
    return ImageChops.lighter(ImageChops.lighter(red, green), blue)


def _component_bboxes(mask: Image.Image) -> List[Tuple[int, Tuple[int, int, int, int]]]:
    width, height = mask.size
    pixels = mask.load()
    visited = bytearray(width * height)
    components = []

    for y in range(height):
        for x in range(width):
            offset = y * width + x
            if visited[offset] or pixels[x, y] == 0:
                continue
            queue = deque([(x, y)])
            visited[offset] = 1
            area = 0
            left = right = x
            top = bottom = y

            while queue:
                current_x, current_y = queue.popleft()
                area += 1
                left = min(left, current_x)
                right = max(right, current_x)
                top = min(top, current_y)
                bottom = max(bottom, current_y)
                for next_x, next_y in (
                    (current_x - 1, current_y),
                    (current_x + 1, current_y),
                    (current_x, current_y - 1),
                    (current_x, current_y + 1),
                ):
                    if not (0 <= next_x < width and 0 <= next_y < height):
                        continue
                    next_offset = next_y * width + next_x
                    if visited[next_offset] or pixels[next_x, next_y] == 0:
                        continue
                    visited[next_offset] = 1
                    queue.append((next_x, next_y))

            components.append((area, (left, top, right + 1, bottom + 1)))
    return components


def _primary_content_bbox(image: Image.Image, distance: Image.Image) -> Tuple[int, int, int, int]:
    scale = min(1.0, CONFIG["component_thumbnail_max"] / max(image.size))
    thumbnail_size = (
        max(1, round(image.width * scale)),
        max(1, round(image.height * scale)),
    )
    binary = distance.point(lambda value: 255 if value >= CONFIG["paper_distance_high"] else 0)
    thumbnail = binary.resize(thumbnail_size, Image.Resampling.NEAREST)
    components = _component_bboxes(thumbnail)
    if not components:
        return (0, 0, image.width, image.height)

    largest_area = max(area for area, _ in components)
    minimum_area = max(3, round(largest_area * CONFIG["component_relative_area"]))
    selected = [box for area, box in components if area >= minimum_area]
    if not selected:
        selected = [max(components, key=lambda item: item[0])[1]]

    left = min(box[0] for box in selected)
    top = min(box[1] for box in selected)
    right = max(box[2] for box in selected)
    bottom = max(box[3] for box in selected)
    inverse_scale = 1.0 / scale
    padding = max(2, round(min(image.size) * 0.008))
    return (
        max(0, math.floor(left * inverse_scale) - padding),
        max(0, math.floor(top * inverse_scale) - padding),
        min(image.width, math.ceil(right * inverse_scale) + padding),
        min(image.height, math.ceil(bottom * inverse_scale) + padding),
    )


def _illustration_layer(image: Image.Image) -> Tuple[Image.Image, Tuple[int, int, int, int]]:
    paper_color = _estimate_paper_color(image)
    distance = _distance_mask(image, paper_color)
    bbox = _primary_content_bbox(image, distance)
    cropped = image.crop(bbox)
    cropped_distance = distance.crop(bbox)
    low = CONFIG["paper_distance_low"]
    high = CONFIG["paper_distance_high"]
    span = high - low
    alpha = cropped_distance.point(
        lambda value: 0
        if value <= low
        else 255
        if value >= high
        else round((value - low) * 255 / span)
    )
    layer = cropped.convert("RGBA")
    layer.putalpha(alpha)
    return layer, bbox


def _luminance(color: RGB) -> float:
    red, green, blue = color
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def _color_distance(first: RGB, second: RGB) -> float:
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(first, second)))


def _saturation(color: RGB) -> int:
    return max(color) - min(color)


def _is_near_paper(color: RGB) -> bool:
    return _luminance(color) > 232 and _saturation(color) < 24


def _extract_palette(layer: Image.Image) -> List[RGB]:
    sample = layer.copy()
    sample.thumbnail((360, 360), Image.Resampling.LANCZOS)
    pixels = [
        pixel[:3]
        for pixel in sample.getdata()
        if pixel[3] >= 80 and not _is_near_paper(pixel[:3])
    ]
    if not pixels:
        return list(FALLBACK_PALETTE)

    strip = Image.new("RGB", (len(pixels), 1))
    strip.putdata(pixels)
    counts = strip.getcolors(maxcolors=4096)
    if counts is None:
        quantized = strip.quantize(colors=24, method=Image.Quantize.MEDIANCUT).convert("RGB")
        counts = quantized.getcolors(maxcolors=24)
    ranked = sorted(counts or [], key=lambda item: item[0], reverse=True)
    ranked = [(count, color) for count, color in ranked if not _is_near_paper(color)]
    if not ranked:
        return list(FALLBACK_PALETTE)

    total = sum(count for count, _ in ranked)
    substantial = [
        color for count, color in ranked if count >= max(1, round(total * 0.04))
    ]
    candidates = [color for _, color in ranked]
    role_pool = substantial or candidates

    dominant = role_pool[0]
    remaining = [color for color in role_pool if _color_distance(color, dominant) >= 20]
    dark = min(remaining or candidates, key=_luminance)

    remaining = [
        color
        for color in role_pool
        if all(_color_distance(color, selected) >= 20 for selected in (dominant, dark))
    ]
    neutral = [
        color for color in remaining if _luminance(color) >= 160 and _saturation(color) <= 65
    ]
    light = max(neutral or remaining or candidates, key=_luminance)

    remaining = [
        color
        for color in role_pool
        if all(
            _color_distance(color, selected) >= 20
            for selected in (dominant, dark, light)
        )
        and _saturation(color) <= 140
    ]
    accent = max(
        remaining or candidates,
        key=lambda color: (_saturation(color), _color_distance(color, dominant)),
    )

    role_choices = (dominant, dark, light, accent)
    palette: List[RGB] = []
    for index, choice in enumerate(role_choices):
        options = [choice, FALLBACK_PALETTE[index], *candidates, *FALLBACK_PALETTE]
        selected = next(
            (
                color
                for color in options
                if all(_color_distance(color, existing) >= 20 for existing in palette)
            ),
            FALLBACK_PALETTE[index],
        )
        palette.append(selected)
    return palette


def _hex(color: RGB) -> str:
    return "#{:02X}{:02X}{:02X}".format(*color)


def _load_font(size: int) -> Tuple[ImageFont.ImageFont, str]:
    if not FONT_PATH.is_file():
        raise FileNotFoundError(f"packaged font is missing: {FONT_PATH}")
    return ImageFont.truetype(FONT_PATH, size=size), str(FONT_PATH)


def _title_color(palette: Sequence[RGB]) -> RGB:
    non_black = [color for color in palette if _luminance(color) >= 22]
    return min(non_black or list(palette), key=_luminance)


def _validate_title(title: str) -> None:
    words = re.findall(r"[A-Za-z]+(?:[-'][A-Za-z]+)?", title)
    if len(words) not in (2, 3) or " ".join(words) != title.strip():
        raise ValueError("title must contain exactly 2–3 English words")


def compose_editorial(
    source_photo_path,
    generated_illustration_path,
    title: str,
    output_path,
) -> Dict[str, object]:
    """Create one deterministic photo-plus-illustration editorial composition."""

    _validate_title(title)
    source_path = Path(source_photo_path).expanduser().resolve()
    illustration_path = Path(generated_illustration_path).expanduser().resolve()
    destination = Path(output_path).expanduser().resolve()

    source = _open_oriented(source_path)
    illustration = _open_oriented(illustration_path)
    source_dimensions = list(source.size)
    illustration_dimensions = list(illustration.size)
    orientation = classify_orientation(*source.size)

    canvas_width = min(source.width, CONFIG["max_canvas_width"])
    photo = _resize_width(source, canvas_width)
    panel_height = photo.height
    final_height = photo.height + panel_height
    panel_top = photo.height

    canvas = Image.new("RGB", (canvas_width, final_height), CONFIG["paper_color"])
    canvas.paste(photo, (0, 0))

    layer, illustration_bbox = _illustration_layer(illustration)
    palette = _extract_palette(layer)

    footer_padding = round(canvas_width * CONFIG["footer_padding_ratio"])
    chip_size = max(24, round(canvas_width * CONFIG["chip_size_ratio"]))
    chip_gap = max(8, round(canvas_width * CONFIG["chip_gap_ratio"]))
    font_size = max(28, round(canvas_width * CONFIG["font_size_ratio"]))
    footer_height = round(panel_height * CONFIG["footer_height_ratio"])
    illustration_area_height = panel_height - footer_height

    target_width = round(canvas_width * CONFIG["motif_width_ratio"])
    target_height = round(panel_height * CONFIG["motif_max_height_ratio"])
    requested_scale = min(target_width / layer.width, target_height / layer.height)
    panel_padding = round(min(canvas_width, panel_height) * CONFIG["panel_padding_ratio"])
    maximum_width = max(1, canvas_width - panel_padding * 2)
    maximum_height = max(1, illustration_area_height - panel_padding * 2)
    contain_scale = min(maximum_width / layer.width, maximum_height / layer.height)
    scale = min(requested_scale, contain_scale)
    motif_size = (
        max(1, round(layer.width * scale)),
        max(1, round(layer.height * scale)),
    )
    motif = layer.resize(motif_size, Image.Resampling.LANCZOS)

    motif_x = round((canvas_width - motif.width) / 2)
    visible_alpha = motif.getchannel("A").point(
        lambda value: 255 if value >= 80 else 0
    )
    visible_bbox = visible_alpha.getbbox() or (0, 0, motif.width, motif.height)
    visible_center_y = (visible_bbox[1] + visible_bbox[3]) / 2
    usable_top = panel_top + panel_padding
    usable_bottom = panel_top + illustration_area_height
    motif_y = round((usable_top + usable_bottom) / 2 - visible_center_y)
    canvas.paste(motif, (motif_x, motif_y), motif)

    draw = ImageDraw.Draw(canvas)
    font, font_used = _load_font(font_size)
    title_color = _title_color(palette)
    footer_bottom = final_height - footer_padding
    chip_y = footer_bottom - chip_size
    total_chip_width = chip_size * 4 + chip_gap * 3
    chip_x = canvas_width - footer_padding - total_chip_width
    chip_boxes = []
    for index, color in enumerate(palette):
        left = chip_x + index * (chip_size + chip_gap)
        box = (left, chip_y, left + chip_size, chip_y + chip_size)
        draw.rectangle(box, fill=color)
        chip_boxes.append(list(box))

    title_bbox = draw.textbbox((0, 0), title, font=font)
    title_height = title_bbox[3] - title_bbox[1]
    title_y = footer_bottom - max(chip_size, title_height)
    draw.text((footer_padding, title_y), title, font=font, fill=title_color)

    destination.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(destination, format="PNG", optimize=False, compress_level=6)

    return {
        "source_dimensions": source_dimensions,
        "source_aspect_ratio": round(source.width / source.height, 8),
        "illustration_dimensions": illustration_dimensions,
        "orientation": orientation,
        "photo_ratio": 0.5,
        "panel_ratio": 0.5,
        "photo_dimensions": list(photo.size),
        "panel_dimensions": [canvas_width, panel_height],
        "photo_panel_dimensions_match": list(photo.size) == [canvas_width, panel_height],
        "photo_panel_aspect_ratio_match": photo.width * panel_height
        == canvas_width * photo.height,
        "final_dimensions": [canvas_width, final_height],
        "illustration_source_bbox": list(illustration_bbox),
        "motif_box": [motif_x, motif_y, motif_x + motif.width, motif_y + motif.height],
        "motif_dimensions": list(motif.size),
        "motif_effective_scale": scale,
        "palette_hex": [_hex(color) for color in palette],
        "title_color": _hex(title_color),
        "font_used": font_used,
        "font_size": font_size,
        "chip_size": chip_size,
        "chip_gap": chip_gap,
        "footer_box": [
            0,
            panel_top + illustration_area_height,
            canvas_width,
            final_height,
        ],
        "title_position": [footer_padding, title_y],
        "chip_boxes": chip_boxes,
        "output_sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-photo", required=True)
    parser.add_argument("--illustration", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    metadata = compose_editorial(
        source_photo_path=args.source_photo,
        generated_illustration_path=args.illustration,
        title=args.title,
        output_path=args.output,
    )
    print(json.dumps(metadata, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
