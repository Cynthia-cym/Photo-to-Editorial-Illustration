#!/usr/bin/env python3
"""Detect and validate one photo-to-editorial-illustration source image."""

import argparse
import errno
import hashlib
import json
import os
import stat
import sys
import tempfile
import warnings
from pathlib import Path
from typing import Dict, Set, Tuple

from PIL import Image, ImageOps


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
HEIC_BRANDS = {b"heic", b"heix", b"hevc", b"hevx", b"heim", b"heis"}
HEIF_BRANDS = {b"mif1", b"msf1"}
AVIF_BRANDS = {b"avif", b"avis"}
STATIC_FORMATS = {"JPEG", "PNG", "WEBP"}
MAX_FTYP_BOX_SIZE = 1024 * 1024
FILE_READ_CHUNK = 1024 * 1024
MAX_SOURCE_BYTES = 50 * 1024 * 1024
MAX_IMAGE_PIXELS = 100_000_000
MAX_IMAGE_EDGE = 20_000
Snapshot = Tuple[int, int, int, int, int]


class SourceImageError(RuntimeError):
    """Raised when a source image cannot satisfy the preflight contract."""


def _validate_file_size(source_stat) -> None:
    if source_stat.st_size > MAX_SOURCE_BYTES:
        raise SourceImageError("source image exceeds 50 MiB limit")


def _validate_dimensions(size) -> None:
    width, height = size
    if width > MAX_IMAGE_EDGE or height > MAX_IMAGE_EDGE:
        raise SourceImageError("image dimensions exceed 20,000 px edge limit")
    if width * height > MAX_IMAGE_PIXELS:
        raise SourceImageError("image dimensions exceed 100 MP limit")


def _sha256_from_fd(source_fd: int) -> str:
    """Return SHA-256 using an already-open descriptor."""
    try:
        os.lseek(source_fd, 0, os.SEEK_SET)
    except OSError as error:
        raise SourceImageError(f"source image is unreadable: descriptor seek failed") from error

    digest = hashlib.sha256()
    try:
        while True:
            chunk = os.read(source_fd, FILE_READ_CHUNK)
            if not chunk:
                break
            digest.update(chunk)
    except OSError as error:
        raise SourceImageError(f"source image is unreadable: {error}") from error
    return digest.hexdigest()


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(FILE_READ_CHUNK), b""):
                digest.update(chunk)
    except OSError as error:
        raise SourceImageError(f"normalized PNG is unreadable: {error}") from error
    return digest.hexdigest()


def _read_up_to(source_fd: int, size: int) -> bytes:
    """Read up to ``size`` bytes, tolerating ordinary short reads."""
    chunks = []
    remaining = size
    while remaining:
        chunk = os.read(source_fd, remaining)
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _ftyp_box_layout(header: bytes, container_size: int):
    """Return the declared box size and brand offset for an ``ftyp`` box."""
    size_32 = int.from_bytes(header[:4], "big")
    if size_32 == 1:
        if len(header) < 16:
            raise SourceImageError("truncated ISO-BMFF ftyp box size")
        box_size = int.from_bytes(header[8:16], "big")
        brand_offset = 16
    elif size_32 == 0:
        box_size = container_size
        brand_offset = 8
    else:
        box_size = size_32
        brand_offset = 8

    minimum_size = brand_offset + 8
    if box_size < minimum_size:
        raise SourceImageError("invalid ISO-BMFF ftyp box size")
    if box_size > container_size:
        raise SourceImageError("truncated ISO-BMFF ftyp box")
    return box_size, brand_offset


def _ftyp_brands(data: bytes) -> Set[bytes]:
    """Return major and compatible brands from a complete ``ftyp`` box."""
    if len(data) < 8 or data[4:8] != b"ftyp":
        return set()

    box_size, brand_offset = _ftyp_box_layout(data, len(data))

    compatible_offset = brand_offset + 8
    compatible_length = box_size - compatible_offset
    if compatible_length % 4:
        raise SourceImageError("invalid ISO-BMFF ftyp brand table")

    brands = {data[brand_offset : brand_offset + 4]}
    brands.update(
        data[offset : offset + 4]
        for offset in range(compatible_offset, box_size, 4)
    )
    return brands


def _read_detection_bytes(source_fd: int, source_stat: os.stat_result) -> bytes:
    """Read a short signature or one complete, bounded ``ftyp`` box."""
    try:
        os.lseek(source_fd, 0, os.SEEK_SET)
        header = _read_up_to(source_fd, 16)
        if len(header) < 8 or header[4:8] != b"ftyp":
            return header

        box_size, _ = _ftyp_box_layout(header, source_stat.st_size)
        if box_size > MAX_FTYP_BOX_SIZE:
            raise SourceImageError("ISO-BMFF ftyp box exceeds safety limit")

        os.lseek(source_fd, 0, os.SEEK_SET)
        data = _read_up_to(source_fd, box_size)
    except SourceImageError:
        raise
    except OSError as error:
        raise SourceImageError(f"source image is unreadable: descriptor read failed") from error

    if len(data) != box_size:
        raise SourceImageError("truncated ISO-BMFF ftyp box")
    return data


def detect_container_bytes(header: bytes) -> str:
    """Detect a supported image container using bytes rather than its name."""
    if header.startswith(b"\xff\xd8"):
        return "JPEG"
    if header.startswith(PNG_SIGNATURE):
        return "PNG"
    if len(header) >= 12 and header.startswith(b"RIFF") and header[8:12] == b"WEBP":
        return "WEBP"

    brands = _ftyp_brands(header)
    if brands & AVIF_BRANDS:
        raise SourceImageError("AVIF: unsupported source image format")
    if brands & HEIC_BRANDS:
        return "HEIC"
    if brands & HEIF_BRANDS:
        return "HEIF"
    raise SourceImageError("unsupported source image format")


def jpeg_has_mpf(data: bytes) -> bool:
    """Return whether JPEG metadata contains an MPF APP2 signature."""
    if not data.startswith(b"\xff\xd8"):
        return False
    offset = 2
    while offset < len(data):
        if data[offset] != 0xFF:
            raise SourceImageError("malformed JPEG marker stream")
        while offset < len(data) and data[offset] == 0xFF:
            offset += 1
        if offset >= len(data):
            raise SourceImageError("truncated JPEG marker stream")
        marker = data[offset]
        offset += 1
        if marker in (0xD9, 0xDA):
            return False
        if marker in range(0xD0, 0xD8) or marker in (0x01, 0xD8):
            continue
        if offset + 2 > len(data):
            raise SourceImageError("truncated JPEG segment length")
        length = int.from_bytes(data[offset : offset + 2], "big")
        if length < 2 or offset + length > len(data):
            raise SourceImageError("invalid JPEG segment length")
        payload = data[offset + 2 : offset + length]
        if marker == 0xE2 and payload.startswith(b"MPF\x00"):
            return True
        offset += length
    return False


def _resolve_source(source_photo) -> Path:
    try:
        return Path(source_photo).expanduser().resolve()
    except (OSError, RuntimeError) as error:
        raise SourceImageError(
            f"source path could not be resolved: {source_photo}"
        ) from error


def _resolve_output(normalized_output) -> Path:
    try:
        return Path(normalized_output).expanduser().resolve()
    except (OSError, RuntimeError) as error:
        raise SourceImageError(
            f"normalized output path could not be resolved: {normalized_output}"
        ) from error


def _validate_output_path(source: Path, output: Path) -> None:
    if source == output:
        raise SourceImageError("normalized output must differ from source")
    if output.suffix.lower() != ".png":
        raise SourceImageError("normalized output must end in .png")


def _open_source_fd(source: Path) -> int:
    try:
        flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0)
        return os.open(str(source), flags)
    except OSError as error:
        if error.errno == errno.ENOENT:
            raise SourceImageError(f"source does not exist: {source}")
        if error.errno == errno.EISDIR:
            raise SourceImageError(f"source is not a regular file: {source}")
        raise SourceImageError(f"source image is unreadable: {source}") from error


def _snapshot_source(source_stat: os.stat_result) -> Snapshot:
    return (
        source_stat.st_dev,
        source_stat.st_ino,
        source_stat.st_size,
        source_stat.st_mtime_ns,
        source_stat.st_ctime_ns,
    )


def _open_static(source_fd: int) -> Tuple[list, int]:
    """Decode JPEG/PNG/WEBP and reject animated or multi-frame files."""
    try:
        with os.fdopen(os.dup(source_fd), "rb") as source_handle:
            with Image.open(source_handle) as image:
                _validate_dimensions(image.size)
                image.load()
                is_animated = bool(getattr(image, "is_animated", False))
                frame_count = int(getattr(image, "n_frames", 1))
                if is_animated or frame_count != 1:
                    raise SourceImageError("animated or multi-frame source image")
                return list(image.size), frame_count
    except SourceImageError:
        raise
    except Image.DecompressionBombError as error:
        raise SourceImageError(f"unreadable or corrupt source image: {error}") from error
    except (OSError, SyntaxError, ValueError) as error:
        raise SourceImageError(f"unreadable or corrupt source image: {error}") from error


def _verify_file_stable(path: Path, baseline: Snapshot) -> None:
    try:
        current = path.stat()
    except OSError as error:
        raise SourceImageError("source changed during validation") from error

    if _snapshot_source(current) != baseline:
        raise SourceImageError("source changed during validation")


def _pass_through(
    path: Path,
    detected_format: str,
    source_dimensions: list,
    frame_count: int,
    digest: str,
) -> Dict[str, object]:
    source = str(path)
    return {
        "schema_version": 1,
        "original_source": source,
        "runtime_source": source,
        "detected_format": detected_format,
        "action": "passthrough",
        "decoder": "Pillow",
        "converted": False,
        "primary_image": 0,
        "frame_count": frame_count,
        "orientation_applied": False,
        "source_dimensions": source_dimensions,
        "runtime_dimensions": source_dimensions,
        "original_sha256": digest,
        "runtime_sha256": digest,
    }


def normalize_primary_with_pillow(
    source_fd: int,
    source: Path,
    output: Path,
    detected_format: str,
) -> Dict[str, object]:
    """Convert the primary MPO frame to one verified RGB PNG."""
    if output.exists():
        raise SourceImageError(f"normalized output already exists: {output}")
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise SourceImageError("normalized output directory is unavailable") from error

    original_digest = _sha256_from_fd(source_fd)
    temporary_path = None
    primary = None
    oriented = None
    try:
        os.lseek(source_fd, 0, os.SEEK_SET)
        with os.fdopen(os.dup(source_fd), "rb") as source_handle:
            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore",
                    message="Image appears to be a malformed MPO file",
                    category=UserWarning,
                )
                opened = Image.open(source_handle)
            with opened:
                if opened.format != "MPO":
                    raise SourceImageError("MPO decoder confirmation failed")
                frame_count = int(getattr(opened, "n_frames", 1))
                if frame_count < 2:
                    raise SourceImageError("MPO does not contain multiple images")
                opened.seek(0)
                _validate_dimensions(opened.size)
                source_dimensions = list(opened.size)
                source_orientation = opened.getexif().get(274, 1)
                icc_profile = opened.info.get("icc_profile")
                primary = opened.copy()

        transposed = ImageOps.exif_transpose(primary)
        oriented = transposed.convert("RGB")
        if transposed is not primary:
            transposed.close()
        runtime_dimensions = list(oriented.size)

        with tempfile.NamedTemporaryFile(
            prefix=f".{output.name}.",
            suffix=".tmp",
            dir=output.parent,
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
        save_options = {"icc_profile": icc_profile} if icc_profile else {}
        oriented.save(temporary_path, format="PNG", **save_options)
        with Image.open(temporary_path) as verified:
            verified.load()
            if (
                verified.format != "PNG"
                or verified.mode != "RGB"
                or int(getattr(verified, "n_frames", 1)) != 1
                or list(verified.size) != runtime_dimensions
            ):
                raise SourceImageError("normalized PNG verification failed")

        runtime_digest = _sha256_path(temporary_path)
        os.replace(temporary_path, output)
        temporary_path = None
    except SourceImageError:
        raise
    except Image.DecompressionBombError as error:
        raise SourceImageError(f"primary image conversion failed: {error}") from error
    except (OSError, SyntaxError, ValueError) as error:
        raise SourceImageError(f"primary image conversion failed: {error}") from error
    finally:
        if primary is not None:
            primary.close()
        if oriented is not None:
            oriented.close()
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)

    return {
        "schema_version": 1,
        "original_source": str(source),
        "runtime_source": str(output),
        "detected_format": detected_format,
        "action": "converted",
        "decoder": "Pillow",
        "converted": True,
        "primary_image": 0,
        "frame_count": frame_count,
        "orientation_applied": source_orientation not in (None, 1),
        "source_dimensions": source_dimensions,
        "runtime_dimensions": runtime_dimensions,
        "original_sha256": original_digest,
        "runtime_sha256": runtime_digest,
    }


def normalize_primary_with_heif(
    source_fd: int,
    source: Path,
    output: Path,
    detected_format: str,
) -> Dict[str, object]:
    """Convert the primary HEIC/HEIF image to one verified RGB PNG."""
    try:
        import pillow_heif
    except ImportError as error:
        setup_script = Path(__file__).with_name("setup_image_runtime.py")
        raise SourceImageError(
            f"{detected_format} requires pillow-heif; authorize the isolated "
            f"runtime with {setup_script}"
        ) from error

    if output.exists():
        raise SourceImageError(f"normalized output already exists: {output}")
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise SourceImageError("normalized output directory is unavailable") from error

    original_digest = _sha256_from_fd(source_fd)
    temporary_path = None
    primary = None
    oriented = None
    try:
        os.lseek(source_fd, 0, os.SEEK_SET)
        with os.fdopen(os.dup(source_fd), "rb") as source_handle:
            container = pillow_heif.open_heif(source_handle)

        frame_count = len(container)
        primary_index = next(
            (
                index
                for index, image in enumerate(container)
                if image.info.get("primary")
            ),
            0,
        )
        primary = container[primary_index].to_pillow()
        _validate_dimensions(primary.size)
        source_dimensions = list(primary.size)
        source_orientation = primary.getexif().get(274, 1)
        icc_profile = primary.info.get("icc_profile")

        transposed = ImageOps.exif_transpose(primary)
        oriented = transposed.convert("RGB")
        if transposed is not primary:
            transposed.close()
        runtime_dimensions = list(oriented.size)

        with tempfile.NamedTemporaryFile(
            prefix=f".{output.name}.",
            suffix=".tmp",
            dir=output.parent,
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
        save_options = {"icc_profile": icc_profile} if icc_profile else {}
        oriented.save(temporary_path, format="PNG", **save_options)
        with Image.open(temporary_path) as verified:
            verified.load()
            if (
                verified.format != "PNG"
                or verified.mode != "RGB"
                or int(getattr(verified, "n_frames", 1)) != 1
                or list(verified.size) != runtime_dimensions
            ):
                raise SourceImageError("normalized PNG verification failed")

        runtime_digest = _sha256_path(temporary_path)
        os.replace(temporary_path, output)
        temporary_path = None
    except SourceImageError:
        raise
    except (OSError, SyntaxError, ValueError) as error:
        raise SourceImageError(f"primary image conversion failed: {error}") from error
    finally:
        if primary is not None:
            primary.close()
        if oriented is not None:
            oriented.close()
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)

    return {
        "schema_version": 1,
        "original_source": str(source),
        "runtime_source": str(output),
        "detected_format": detected_format,
        "action": "converted",
        "decoder": "pillow-heif",
        "converted": True,
        "primary_image": primary_index,
        "frame_count": frame_count,
        "orientation_applied": source_orientation not in (None, 1),
        "source_dimensions": source_dimensions,
        "runtime_dimensions": runtime_dimensions,
        "original_sha256": original_digest,
        "runtime_sha256": runtime_digest,
    }


def prepare_source(source_photo, normalized_output) -> Dict[str, object]:
    """Validate a source and return pass-through metadata when supported."""
    source = _resolve_source(source_photo)
    output = _resolve_output(normalized_output)
    _validate_output_path(source, output)

    source_fd = _open_source_fd(source)
    validation_succeeded = False
    try:
        try:
            source_stat = os.fstat(source_fd)
        except OSError as error:
            raise SourceImageError(f"source is unreadable: {source}") from error

        if not stat.S_ISREG(source_stat.st_mode):
            raise SourceImageError(f"source is not a regular file: {source}")
        _validate_file_size(source_stat)

        snapshot = _snapshot_source(source_stat)
        detected_format = detect_container_bytes(
            _read_detection_bytes(source_fd, source_stat)
        )
        if detected_format == "JPEG":
            try:
                os.lseek(source_fd, 0, os.SEEK_SET)
                jpeg_bytes = _read_up_to(source_fd, source_stat.st_size)
            except OSError as error:
                raise SourceImageError("JPEG: source image is unreadable") from error
            if len(jpeg_bytes) != source_stat.st_size:
                raise SourceImageError("JPEG: truncated source image")
            try:
                if jpeg_has_mpf(jpeg_bytes):
                    detected_format = "MPO"
            except SourceImageError as error:
                raise SourceImageError(
                    f"JPEG: unreadable or corrupt source image: {error}"
                ) from error

        if detected_format == "MPO":
            try:
                payload = normalize_primary_with_pillow(
                    source_fd, source, output, detected_format
                )
                _verify_file_stable(source, snapshot)
            except SourceImageError as error:
                raise SourceImageError(f"{detected_format}: {error}") from error
            validation_succeeded = True
            return payload
        if detected_format in {"HEIC", "HEIF"}:
            try:
                payload = normalize_primary_with_heif(
                    source_fd, source, output, detected_format
                )
                _verify_file_stable(source, snapshot)
            except SourceImageError as error:
                raise SourceImageError(f"{detected_format}: {error}") from error
            validation_succeeded = True
            return payload
        if detected_format not in STATIC_FORMATS:
            raise SourceImageError(
                f"decoder unavailable for detected format: {detected_format}"
            )

        try:
            source_dimensions, frame_count = _open_static(source_fd)
            digest = _sha256_from_fd(source_fd)
            _verify_file_stable(source, snapshot)
        except SourceImageError as error:
            raise SourceImageError(f"{detected_format}: {error}") from error
        except OSError as error:
            raise SourceImageError(
                f"{detected_format}: source image is unreadable: {source}"
            ) from error

        payload = _pass_through(
            source, detected_format, source_dimensions, frame_count, digest
        )
        validation_succeeded = True
        return payload
    finally:
        try:
            os.close(source_fd)
        except OSError as error:
            if validation_succeeded:
                raise SourceImageError(
                    f"{detected_format}: source image close failed"
                ) from error


def _parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-photo", required=True)
    parser.add_argument("--normalized-output", required=True)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        payload = prepare_source(args.source_photo, args.normalized_output)
    except SourceImageError as error:
        print(f"source image preflight failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
