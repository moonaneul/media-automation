import struct

from media_automation.bulletin.hwp import (
    HWPTAG_PARA_TEXT,
    _decode_para_text,
    _iter_hwp_records,
)


def make_record(
    tag_id: int,
    payload: bytes,
    level: int = 0,
) -> bytes:
    size = len(payload)

    header = (
        tag_id
        | (level << 10)
        | (size << 20)
    )

    return (
        header.to_bytes(
            4,
            "little",
        )
        + payload
    )


def test_iter_para_text_record():
    payload = (
        "안녕하세요"
        .encode("utf-16le")
    )

    data = make_record(
        HWPTAG_PARA_TEXT,
        payload,
    )

    records = list(
        _iter_hwp_records(data)
    )

    assert len(records) == 1

    tag_id, level, body = records[0]

    assert tag_id == HWPTAG_PARA_TEXT
    assert level == 0
    assert body == payload


def test_decode_para_text_controls():
    units = [
        ord("가"),

        # TAB inline control:
        # 총 8 WCHAR
        0x09,
        0,
        0,
        0,
        0,
        0,
        0,
        0x09,

        ord("나"),
        0x0A,
        ord("다"),
        0x1E,
        ord("라"),
        0x0D,
    ]

    payload = struct.pack(
        "<" + "H" * len(units),
        *units,
    )

    result = _decode_para_text(
        payload
    )

    assert result == (
        "가\t나\n다 라"
    )
