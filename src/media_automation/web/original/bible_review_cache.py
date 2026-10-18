"""Durable, content-bound Bible review receipts.

This is NOT an independent copyright/translation authority. A receipt
means a human explicitly attested a comparison with 개역개정 and the exact
source text. Only exactly matching units can reuse that review.
"""
import hashlib
import json


CACHE_VERSION = 1


def unit_fingerprint(unit):
    from media_automation.bible.json_source import parse_reference
    book, chapter, start, end = parse_reference(unit['reference'])
    # Require a complete, genuine verse unit. Matching only the visible text
    # or a book/chapter suffix could approve a different passage accidentally.
    if (book != unit['book'] or chapter != unit['chapter']
            or start != unit['start_verse'] or end != unit['end_verse']):
        raise ValueError('성경 구절의 참조 범위와 절 번호가 일치하지 않습니다.')
    source = unit.get('text')
    if not isinstance(source, str) or not source.strip():
        raise ValueError('검수할 성경 구절 본문이 없습니다.')
    body = dict(version=CACHE_VERSION, translation='개역개정',
                reference=f'{book}{chapter}:{start}'+(f'~{end}' if end!=start else ''),
                original_text=source)
    canonical = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(',',':'))
    return body['reference'], hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def units_for_manual_confirmation(bible, labels):
    """Collect precisely the unresolved displayed units the person confirms."""
    checked={}
    for label in labels:
        suffix=':bible_review'
        if not isinstance(label,str) or not label.endswith(suffix):
            continue
        entry=bible.get(label[:-len(suffix)],{})
        if not entry.get('units') or not entry.get('text_review_pending'):
            raise ValueError('수동 확인할 성경 본문이 생성본과 일치하지 않습니다.')
        for unit in entry['units']:
            reference,digest=unit_fingerprint(unit)
            if reference in checked and checked[reference]!=digest:
                raise ValueError('동일 구절의 서로 다른 본문을 확인할 수 없습니다.')
            checked[reference]=digest
    return checked


def apply_review_receipts(store, bible):
    """Suppress repeat review only for all-verse exact matches.

    The source_validated flag retains its original meaning (separately
    validated source), whereas previous_manual_review is explicitly NOT
    automatic translation verification.
    """
    for entry in bible.values():
        if not entry.get('units') or not entry.get('text_review_pending'):
            continue
        units=entry['units']
        try:
            fingerprints=[unit_fingerprint(unit) for unit in units]
        except (KeyError,TypeError,ValueError):
            continue
        if not fingerprints:
            continue
        records=store.bible_review_receipts([reference for reference,_ in fingerprints])
        if all(records.get(reference)==digest for reference,digest in fingerprints):
            entry['text_review_pending']=False
            entry['previous_manual_review']=True
            entry['source']='previous_manual_review'
            # Do NOT assert source_validated=True: a person checked these
            # exact verses, not an independent automatic reference parser.
    return bible
