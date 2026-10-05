from __future__ import annotations

from enum import Enum
from pathlib import Path
import re
import struct
import zipfile
import zlib


OLE_MAGIC = bytes.fromhex(
    "D0CF11E0A1B11AE1"
)

HWPTAG_PARA_TEXT = 0x43


class HwpFormat(str, Enum):
    HWP5 = "HWP5"
    HWPX = "HWPX"
    UNKNOWN = "UNKNOWN"


def detect_hwp_format(
    path: str | Path,
) -> HwpFormat:
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(
            f"HWP 파일을 찾을 수 없습니다: {path}"
        )

    with path.open("rb") as file:
        header = file.read(8)

    if header == OLE_MAGIC:
        return HwpFormat.HWP5

    if zipfile.is_zipfile(path):
        try:
            with zipfile.ZipFile(path) as archive:
                names = set(
                    archive.namelist()
                )

            if (
                "version.xml" in names
                or any(
                    name.startswith("Contents/")
                    for name in names
                )
            ):
                return HwpFormat.HWPX

        except zipfile.BadZipFile:
            pass

    return HwpFormat.UNKNOWN


def _iter_hwp_records(
    data: bytes,
):
    """
    HWP5 레코드 스트림을 순서대로 읽는다.

    header:
      bits 0~9   : tag id
      bits 10~19 : level
      bits 20~31 : size

    size == 0xFFF인 경우 다음 UINT32가 실제 크기.
    """
    offset = 0

    while offset + 4 <= len(data):
        header = int.from_bytes(
            data[offset:offset + 4],
            "little",
        )
        offset += 4

        tag_id = header & 0x3FF
        level = (
            header >> 10
        ) & 0x3FF
        size = (
            header >> 20
        ) & 0xFFF

        if size == 0xFFF:
            if offset + 4 > len(data):
                raise ValueError(
                    "잘못된 HWP5 확장 레코드 헤더입니다."
                )

            size = int.from_bytes(
                data[offset:offset + 4],
                "little",
            )
            offset += 4

        end = offset + size

        if end > len(data):
            raise ValueError(
                "HWP5 레코드 크기가 "
                "스트림 범위를 벗어났습니다."
            )

        payload = data[offset:end]
        offset = end

        yield tag_id, level, payload


# 8 WCHAR를 사용하는 inline / extended control
_EIGHT_WCHAR_CONTROLS = {
    0x01,
    0x02,
    0x03,
    0x04,
    0x05,
    0x06,
    0x07,
    0x08,
    0x09,
    0x0B,
    0x0C,
    0x0E,
    0x0F,
    0x10,
    0x11,
    0x12,
    0x13,
    0x14,
    0x15,
    0x16,
    0x17,
}


def _decode_para_text(
    payload: bytes,
) -> str:
    """
    PARA_TEXT의 UTF-16LE 문자와 HWP 제어문자를
    사람이 읽을 수 있는 일반 텍스트로 변환한다.
    """
    if len(payload) % 2:
        payload = payload[:-1]

    if not payload:
        return ""

    units = struct.unpack(
        "<" + "H" * (len(payload) // 2),
        payload,
    )

    result: list[str] = []
    index = 0

    while index < len(units):
        code = units[index]

        # inline/extended control은 총 8 WCHAR
        if code in _EIGHT_WCHAR_CONTROLS:
            if code == 0x09:
                result.append("\t")

            index += 8
            continue

        # 일반 문자
        if code >= 0x20:
            try:
                result.append(chr(code))
            except ValueError:
                pass

            index += 1
            continue

        # 줄바꿈
        if code == 0x0A:
            result.append("\n")

        # 문단 끝
        elif code == 0x0D:
            pass

        # 하이픈
        elif code == 0x18:
            result.append("-")

        # grouped / fixed-width space
        elif code in {
            0x1E,
            0x1F,
        }:
            result.append(" ")

        # 나머지 예약/NULL 컨트롤은 버림

        index += 1

    return "".join(result)


def _is_compressed(
    file_header: bytes,
) -> bool:
    if len(file_header) < 40:
        raise ValueError(
            "HWP5 FileHeader가 너무 짧습니다."
        )

    flags = int.from_bytes(
        file_header[36:40],
        "little",
    )

    return bool(flags & 0x01)


def _section_number(
    name: str,
) -> int:
    match = re.fullmatch(
        r"Section(\d+)",
        name,
    )

    if not match:
        return 10**9

    return int(match.group(1))


def extract_hwp5_text(
    path: str | Path,
) -> str:
    """
    일반 HWP5 문서의 BodyText/Section*에서
    PARA_TEXT 레코드를 추출한다.
    """
    import olefile

    path = Path(path)

    if detect_hwp_format(path) != HwpFormat.HWP5:
        raise ValueError(
            f"HWP5 파일이 아닙니다: {path}"
        )

    paragraphs: list[str] = []

    with olefile.OleFileIO(str(path)) as ole:
        if not ole.exists("FileHeader"):
            raise ValueError(
                "HWP5 FileHeader가 없습니다."
            )

        file_header = (
            ole.openstream(
                "FileHeader"
            ).read()
        )

        compressed = _is_compressed(
            file_header
        )

        section_paths = []

        for parts in ole.listdir(
            streams=True,
            storages=False,
        ):
            if (
                len(parts) == 2
                and parts[0] == "BodyText"
                and parts[1].startswith(
                    "Section"
                )
            ):
                section_paths.append(
                    parts
                )

        section_paths.sort(
            key=lambda parts: (
                _section_number(
                    parts[1]
                )
            )
        )

        if not section_paths:
            raise ValueError(
                "HWP5 BodyText/Section 스트림이 "
                "없습니다."
            )

        for parts in section_paths:
            stream_name = "/".join(
                parts
            )

            raw = (
                ole.openstream(
                    stream_name
                ).read()
            )

            if compressed:
                try:
                    raw = zlib.decompress(
                        raw,
                        -15,
                    )
                except zlib.error as exc:
                    raise ValueError(
                        f"{stream_name} 압축 해제 실패"
                    ) from exc

            for (
                tag_id,
                _level,
                payload,
            ) in _iter_hwp_records(raw):
                if (
                    tag_id
                    != HWPTAG_PARA_TEXT
                ):
                    continue

                text = _decode_para_text(
                    payload
                )

                # PARA_TEXT 내부 line break 유지
                # 레코드 간에는 문단 경계 추가
                paragraphs.append(
                    text.rstrip()
                )

    return "\n".join(
        paragraphs
    )


def extract_hwp_text(
    path: str | Path,
) -> str:
    detected = detect_hwp_format(path)

    if detected == HwpFormat.HWP5:
        return extract_hwp5_text(path)

    if detected == HwpFormat.HWPX:
        raise NotImplementedError(
            "현재 이 단계에서는 HWP5 추출만 "
            "구현되어 있습니다."
        )

    raise ValueError(
        "지원하지 않는 HWP 형식입니다."
    )
