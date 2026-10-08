from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest
import yaml

from media_automation.bible.json_source import build_index
from media_automation.ppt import create_4x3_presentation
from media_automation.ppt.scripture import add_scripture_passage_slides
from media_automation.ppt.in_person_structure import InPersonSlideRange
from media_automation.ppt.in_person_qa import validate_in_person_structure


def script(name):
    spec = spec_from_file_location(name, Path(__file__).resolve().parents[1] / "scripts" / f"{name}.py")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_shared_resolver_uses_json_and_preserves_range_library_priority():
    resolver = script("resolve_bible_requests")
    index = build_index({"요3:16": "JSON 본문", "요3:17": "다음 절"})
    requests = {"requests": [{"reference": "요 3:16~17"}]}
    passages, missing = resolver.resolve_requests(requests, {}, {}, index)
    assert not missing
    assert passages["요 3:16~17"]["verses"] == {16: "JSON 본문", 17: "다음 절"}
    registered = {"reference": "요 3:16~17", "verses": {16: "등록 본문", 17: "등록 다음 절"}}
    passages, missing = resolver.resolve_requests(requests, {"passages": {"요 3:16-17": registered}}, {}, index)
    assert not missing
    assert passages["요 3:16~17"] == registered


def test_missing_json_verse_does_not_fall_back_to_master():
    resolver = script("resolve_bible_requests")
    master = {"translation": "개역개정", "validated": True, "books": {"요": {3: {17: "대체 본문"}}}}
    passages, missing = resolver.resolve_requests(
        {"requests": [{"reference": "요 3:17"}]}, {}, master, build_index({"요3:16": "본문"})
    )
    assert passages == {}
    assert missing


@pytest.mark.parametrize("builder", ["build_wednesday", "build_wednesday_operational", "build_sunday"])
def test_in_person_builders_preserve_combined_verse_labels(tmp_path, builder):
    resolver = script("resolve_bible_requests")
    passages, missing = resolver.resolve_requests(
        {"requests": [{"reference": "신 6:17~20"}]}, {}, {},
        build_index({"신6:17": "앞 절", "신6:18-19": "통합 본문", "신6:20": "뒤 절"}),
    )
    assert not missing
    source = tmp_path / "bible.yaml"
    source.write_text(yaml.safe_dump({"passages": passages}, allow_unicode=True), encoding="utf-8")
    provider = script(builder).load_bible_provider(source)
    passage = provider.get_passage("신 6:17~20")
    assert [v.display_number for v in passage.verses] == ["17", "18~19", "20"]
    prs = create_4x3_presentation()
    slides = add_scripture_passage_slides(prs, passage)
    assert len(slides) == 3
    text = "\n".join(s.text for slide in slides for s in slide.shapes if s.has_text_frame)
    assert "18~19." in text
    assert text.count("통합 본문") == 1
    output = tmp_path / "scripture.pptx"
    prs.save(output)
    qa = validate_in_person_structure(
        output,
        slide_ranges={"scripture": InPersonSlideRange(start=1, end=3)},
        scripture_passages={"scripture": passage},
    )
    assert qa.ok, qa.issues
