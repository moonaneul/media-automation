from __future__ import annotations

import argparse
from pathlib import Path

import yaml
from pptx import Presentation

from media_automation.bible import (
    BiblePassage,
    BiblePassageNotFoundError,
    BibleVerse,
    InMemoryBibleProvider,
)
from media_automation.planning import BlockKind
from media_automation.planning.wednesday_operational import (
    build_wednesday_operational_plan,
)
from media_automation.ppt import (
    FilePreServiceSlideProvider,
    create_platform_slide_merger,
    load_song_asset_provider,
)
from media_automation.ppt.file_builder import (
    build_presentation_file_from_plan,
)
from media_automation.ppt.in_person_structure import (
    build_in_person_structure,
)
from media_automation.ppt.wednesday_qa import (
    validate_wednesday_structure,
)
from media_automation.weekly_data.models import (
    WednesdayData,
    parse_weekly_data,
)


def load_bible_provider(path: Path) -> InMemoryBibleProvider:
    raw = yaml.safe_load(path.read_text(encoding="utf-8-sig")) or {}
    passages_raw = raw.get("passages")
    if not isinstance(passages_raw, dict):
        raise ValueError("Bible YAML에 passages 객체가 필요합니다.")

    passages = {}
    for lookup_reference, data in passages_raw.items():
        verses_raw = data.get("verses", {})
        verses = [
            BibleVerse(number=int(number), text=text)
            for number, text in verses_raw.items()
        ]
        verses.sort(key=lambda verse: verse.number)
        passages[lookup_reference] = BiblePassage(
            reference=data["reference"],
            verses=tuple(verses),
        )

    return InMemoryBibleProvider(passages)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--weekly", type=Path, required=True)
    parser.add_argument("--songs", type=Path, required=True)
    parser.add_argument("--bible", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    for name, path in {
        "weekly": args.weekly,
        "songs": args.songs,
        "bible": args.bible,
        "source": args.source,
    }.items():
        if not path.exists():
            raise FileNotFoundError(f"{name} 파일을 찾을 수 없습니다: {path}")

    weekly_raw = yaml.safe_load(args.weekly.read_text(encoding="utf-8-sig"))
    weekly = parse_weekly_data(weekly_raw)
    if not isinstance(weekly, WednesdayData):
        raise TypeError("수요예배 Weekly Data가 필요합니다.")

    plan = build_wednesday_operational_plan(weekly)
    bible_provider = load_bible_provider(args.bible)
    song_provider = load_song_asset_provider(args.songs)
    pre_service_provider = FilePreServiceSlideProvider(
        {"pre_service": args.source},
        slide_counts={"pre_service": 4},
    )

    # Bible library에 없는 본문은 생성 전에 즉시 중단한다.
    scripture_passages = {}
    for block in plan:
        if block.kind != BlockKind.SCRIPTURE:
            continue
        try:
            scripture_passages[block.key] = bible_provider.get_passage(
                block.value.reference
            )
        except BiblePassageNotFoundError as error:
            raise RuntimeError(
                f"검수된 개역개정 본문이 없습니다: {block.value.reference}"
            ) from error

    args.output.parent.mkdir(parents=True, exist_ok=True)
    structure_path = args.output.with_name(args.output.stem + "_structure_check.pptx")

    # 실제 악보 장수와 같은 placeholder를 사용하여 최종 slide range를 먼저 확정한다.
    structure = build_in_person_structure(
        plan,
        structure_path,
        bible_provider=bible_provider,
        pre_service_provider=pre_service_provider,
        song_asset_provider=song_provider,
        skip_missing_songs=True,
        preserve_blank_after_pre_service=True,
    )

    structure_qa = validate_wednesday_structure(
        structure.output_path,
        slide_ranges=structure.slide_ranges,
        scripture_passages=scripture_passages,
    )
    if not structure_qa.ok:
        for issue in structure_qa.issues:
            print(f"STRUCTURE QA: [{issue.code}] {issue.message}")
        raise RuntimeError("수요예배 구조 QA 실패")

    merger = create_platform_slide_merger()
    result = build_presentation_file_from_plan(
        plan,
        args.output,
        bible_provider=bible_provider,
        pre_service_provider=pre_service_provider,
        song_asset_provider=song_provider,
        slide_merger=merger,
        skip_missing_songs=True,
        preserve_blank_after_pre_service=True,
    )

    # 구조 프리뷰와 실제 병합본은 같은 plan/악보 장수를 사용하므로 range가 동일하다.
    final_qa = validate_wednesday_structure(
        result,
        slide_ranges=structure.slide_ranges,
        scripture_passages=scripture_passages,
    )

    if not final_qa.ok:
        print("\n=== Wednesday Final QA: FAILED ===")
        for issue in final_qa.issues:
            location = f"slide {issue.slide_number}" if issue.slide_number else "presentation"
            print(f"- [{issue.code}] {location} | {issue.message}")
        raise RuntimeError("최종 수요예배 PPT QA 실패")

    reopened = Presentation(result)
    print("\n=== Wednesday Final QA: PASS ===")
    print(f"slides : {len(reopened.slides)}")
    print(f"output : {result}")
    print("- 4:3 / transition blanks / Bible / alignment / blue shapes / URLs: OK")
    print("- 실제 PowerPoint 렌더링에서 악보 잘림과 화면 가독성은 최종 확인 필요")


if __name__ == "__main__":
    main()
