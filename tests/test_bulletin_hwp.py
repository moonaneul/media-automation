import zipfile

from media_automation.bulletin.hwp import (
    HwpFormat,
    OLE_MAGIC,
    detect_hwp_format,
)


def test_detect_hwp5(tmp_path):
    path = tmp_path / "sample.hwp"

    path.write_bytes(
        OLE_MAGIC + b"\x00" * 32
    )

    assert (
        detect_hwp_format(path)
        == HwpFormat.HWP5
    )


def test_detect_hwpx(tmp_path):
    path = tmp_path / "sample.hwpx"

    with zipfile.ZipFile(
        path,
        "w",
    ) as archive:
        archive.writestr(
            "version.xml",
            "<version />",
        )
        archive.writestr(
            "Contents/section0.xml",
            "<section />",
        )

    assert (
        detect_hwp_format(path)
        == HwpFormat.HWPX
    )


def test_unknown_format(tmp_path):
    path = tmp_path / "unknown.hwp"

    path.write_bytes(
        b"not-hwp"
    )

    assert (
        detect_hwp_format(path)
        == HwpFormat.UNKNOWN
    )
