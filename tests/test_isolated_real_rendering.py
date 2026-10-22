"""Run REAL PPTX/PDF generation and LibreOffice/PyMuPDF rendering offline.

All images, opening decks, and scripture fixture texts are SYNTHETIC.
No original worship/bulletin images, licensed Bible text, Microsoft credentials,
OneDrive folders, cloud services or operating project assets are accessed.
Nothing created here is a church-service deliverable or ready for printing.
"""
import json
import os
import shutil
import socket
from copy import deepcopy
from pathlib import Path

import pymupdf
import pytest
from pptx import Presentation
from pptx.util import Inches

from media_automation.cloud.worker import render_artifact
from media_automation.web.original.bulletin_generation import generate_bulletin
from media_automation.web.original.generation import generate
from media_automation.web.original.work_store import WorkStore


DAY = "2026-10-25"
SYNTHETIC_TITLE = "합성 테스트 설교 제목 - 실제 예배 사용 금지"


@pytest.fixture(autouse=True)
def block_network(monkeypatch):
    def deny(*_args, **_kwargs):
        raise AssertionError("This rendering smoke test cannot call the network")
    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(socket.socket, "connect_ex", deny)


def field(value):
    return {"state": "VALUE", "value": value}


def create_dummy_intro(path, *, wide):
    # A minimal newly generated deck, NOT any historic/approved worship score.
    prs = Presentation()
    prs.slide_width = Inches(13.333333 if wide else 10)
    prs.slide_height = Inches(7.5)
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    box = slide.shapes.add_textbox(Inches(0.6), Inches(1.7),
                                   prs.slide_width - Inches(1.2), Inches(2.5))
    box.text = "시험 전용 · 실제 예배 원본 아님"
    prs.save(path)


@pytest.fixture
def isolated_assets(tmp_path, monkeypatch):
    templates = tmp_path / "only-synthetic-ppt-templates"
    bible_dir = tmp_path / "only-synthetic-bible"
    reference = tmp_path / "no-original-friday-reference"
    music = tmp_path / "no-original-friday-music"
    for folder in (templates, bible_dir, reference, music):
        folder.mkdir()
    for service, wide in (
        ("wednesday", False), ("sunday", False),
        ("friday-in-person", False), ("friday-zoom", True),
    ):
        create_dummy_intro(templates / (service + "-start.pptx"), wide=wide)
    bible_json = tmp_path / "SYNTHETIC_NOT_SCRIPTURE.json"
    bible_json.write_text(json.dumps({
        "요 3:16": "시험 전용 가상 문장입니다. 실제 개역개정 성경 원문이 아닙니다. 세례 표기 시험.",
        "요 3:17": "두 번째 가상 시험 문장입니다. 실제 성경 구절을 인용하지 않습니다.",
    }, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("MEDIA_WORSHIP_TEMPLATES", str(templates))
    monkeypatch.setenv("MEDIA_BIBLE_FILE", str(bible_json))
    monkeypatch.setenv("MEDIA_BIBLE_SOURCES", str(bible_dir))
    monkeypatch.setenv("MEDIA_FRIDAY_REFERENCE", str(reference))
    monkeypatch.setenv("MEDIA_FRIDAY_MUSIC", str(music))
    return tmp_path


def _safe_output_copy(path, kind, index):
    destination = os.environ.get("STAGING_SMOKE_OUTPUT_DIR")
    if not destination:
        return
    root = Path(destination)
    root.mkdir(parents=True, exist_ok=True)
    # GitHub Action artifact is a short-lived technical preview, not a church deliverable.
    stem = f"synthetic-{kind}-{index:02d}"
    with pymupdf.open(path) as pdf:
        page = pdf[min(index, len(pdf) - 1)]
        page.get_pixmap(matrix=pymupdf.Matrix(1.25, 1.25), alpha=False).save(root / (stem + ".png"))
    # Avoid archiving an original design, token, lyric, Bible original, or generated output.


@pytest.mark.parametrize("service,mode,wide", [
    ("wednesday", None, False),
    ("sunday", None, False),
    ("friday", "in-person", False),
    ("friday", "zoom", True),
])
def test_real_ppt_generation_and_rendering_with_synthetic_templates(
    isolated_assets, service, mode, wide,
):
    # Must use actual conversion, not a fake rendered PDF or mocked generator.
    assert shutil.which("soffice") or shutil.which("libreoffice"), (
        "Install LibreOffice Impress to inspect real PPTX rendering."
    )
    store = WorkStore(isolated_assets / (service + "-" + (mode or "normal") + ".db"))
    fields = {
        "성경 본문": field("요 3:16~17"),
        "설교 제목": field(SYNTHETIC_TITLE),
        "시작 찬양 1": field("합성 악보 미첨부 - 빈 화면 처리"),
        "기도 담당자": field("가상 담당자"),
    }
    data = {"fields": fields}
    if mode is not None:
        data["fridayMode"] = mode
    revision = store.save(DAY, service, 0, data)["revision"]
    body = {
        "date": DAY, "service": service, "revision": revision,
        "groups": [["시험 전용 순서", ["시작 찬양 1", "기도 담당자", "성경 본문", "설교 제목"]]],
        "output": "ppt",
    }
    result = generate(store, deepcopy(body))
    generated = Path(store.path).with_suffix(".generated")
    pptx = generated / (result["file_id"] + ".pptx")
    assert pptx.is_file() and pptx.stat().st_size > 5000
    deck = Presentation(str(pptx))
    assert len(deck.slides) == result["slide_count"]
    ratio = deck.slide_width / deck.slide_height
    assert abs(ratio - (16 / 9 if wide else 4 / 3)) < .02
    texts = [
        shape.text for slide in deck.slides for shape in slide.shapes
        if shape.has_text_frame and shape.text.strip()
    ]
    all_text = "\n".join(texts)
    assert SYNTHETIC_TITLE in all_text
    assert "침례" in all_text and "세례" not in all_text
    assert "실제 개역개정 성경 원문이 아닙니다" in all_text
    assert "시작 찬양 1:score_asset" in result["unresolved"]
    assert result["complete"] is False
    assert result["visual_review_pending"] is True
    report = json.loads((generated / (result["file_id"] + ".json")).read_text(encoding="utf-8"))
    assert any(part["kind"] == "blank" for part in report["mapping"])
    assert any(part["status"] == "bible_inserted" for part in report["mapping"])
    pdf, verification = render_artifact(pptx, "ppt", result)
    assert verification["rendered"] is True
    assert verification["page_count"] == len(deck.slides)
    assert verification["visual_review_pending"] is True
    assert verification["actual_playback_verified"] is False
    with pymupdf.open(pdf) as rendered:
        assert len(rendered) == len(deck.slides)
        assert all(page.rect.width > page.rect.height for page in rendered)
        # Ensure the native renderer drew real pixels, not only blank white sheets.
        assert any(len(page.get_text().strip()) > 2 for page in rendered)
    _safe_output_copy(pdf, service + "-" + (mode or "standard"), 0)


def test_real_bulletin_generator_and_a4_imposition_with_synthetic_template(
    isolated_assets, monkeypatch,
):
    # Original bulletin background/font FILES are NOT loaded. The engine gets
    # a new 2-page blank A4 PDF in a temp directory and system test fonts.
    fonts = Path("/usr/share/fonts/truetype/nanum")
    regular, bold = fonts / "NanumGothic.ttf", fonts / "NanumGothicBold.ttf"
    assert regular.is_file() and bold.is_file(), (
        "Install fonts-nanum for synthetic offline bulletin layout smoke tests"
    )
    assets = isolated_assets / "only-synthetic-bulletin"
    assets.mkdir()
    reference = pymupdf.open()
    for _ in range(2):
        reference.new_page(width=841.89, height=595.28)
    reference.save(assets / "original-design.pdf")
    reference.close()
    shutil.copyfile(regular, assets / "original-regular.ttf")
    shutil.copyfile(bold, assets / "original-bold.ttf")
    monkeypatch.setenv("MEDIA_BULLETIN_ASSETS", str(assets))

    store = WorkStore(isolated_assets / "sunday-bulletin.db")
    base = json.loads(
        (Path(__file__).resolve().parents[1]
         / "src/media_automation/web/original/bulletin-base-reference.json")
        .read_text(encoding="utf-8")
    )
    # Runtime code checks the church's fixed contact fields against an image.
    # We only use this existing config in memory; no original church PDF or
    # original fonts are loaded, and no result can be approved for worship.
    base["status"] = "confirmed"
    base["annual"]["표어"] = "합성 테스트 표어"
    base["annual"]["표어 보조 문구"] = "합성 시험용 문구"
    base["annual"]["관련 성경 구절"] = "시험 전용"
    base["church"]["사명선언문"] = "실제 주보용 사명선언문이 아닌 테스트 문구"
    base["church"]["핵심가치"] = []
    base["meeting_times"] = {}
    with store.connect() as db:
        db.execute("CREATE TABLE bulletin_settings (id INTEGER PRIMARY KEY, revision INTEGER, payload TEXT)")
        db.execute("INSERT INTO bulletin_settings VALUES (1,1,?)", (json.dumps(base, ensure_ascii=False),))

    fields = {
        "확정 주보 호수": field("TEST-000"),
        "성경 본문": field("요 3:16~17"),
        "설교 제목": field(SYNTHETIC_TITLE),
        "주일 인도자": {"state": "NONE", "value": ""},
        "설교자": {"state": "NONE", "value": ""},
        "질문 1": field("합성 질문 하나"),
        "질문 2": field("합성 질문 둘"),
        "질문 3": field("합성 질문 셋"),
        "질문 4": field("합성 질문 넷"),
        "교회 소식": field("모든 내용은 합성 데이터입니다."),
    }
    revision = store.save(DAY, "sunday", 0, {"fields": fields})["revision"]
    result = generate_bulletin(store, {
        "date": DAY, "service": "sunday", "revision": revision,
        "groups": [], "output": "pdf",
    })
    path = Path(store.path).with_suffix(".generated") / (result["file_id"] + ".pdf")
    assert path.is_file() and path.stat().st_size > 1000
    with pymupdf.open(path) as doc:
        assert len(doc) == 2
        assert all(abs(page.rect.width - 841.89) < 2 and
                   abs(page.rect.height - 595.28) < 2 for page in doc)
        for page in doc:
            pixels = page.get_pixmap(matrix=pymupdf.Matrix(.75, .75), alpha=False)
            assert pixels.width > 600 and pixels.height > 400
            assert len(page.get_text().strip()) > 2
        all_text = "\n".join(page.get_text() for page in doc)
        assert "TEST-000" in all_text
    rendered, verification = render_artifact(path, "pdf", {"slide_count": 0})
    assert rendered == path
    assert verification["page_count"] == 2
    assert verification["visual_review_pending"] is True
    assert verification["actual_playback_verified"] is False
    assert result["complete"] is False
    assert result["visual_review_pending"] is True
    # Synthetic template does not prove correct 4|1 / 2|3 original art imposition.
    # The engine reorders two input sides; this checks dimensions/renderability only.
    _safe_output_copy(path, "bulletin", 0)
    _safe_output_copy(path, "bulletin", 1)
