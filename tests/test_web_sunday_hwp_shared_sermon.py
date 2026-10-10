"""Sunday bulletin study reference/title may be copied to PPT only by consent.

All tests use the original blue form, not a newly assembled replacement page.
"""
from __future__ import annotations

import shutil
import subprocess

import pytest

from media_automation.web import blue_original


def test_ui_has_an_explicit_confirmation_and_retains_original_fields():
    html = blue_original.page().decode("utf-8")
    js = blue_original.resource("/blue-original.js")[0].decode("utf-8")
    policy = blue_original.resource("/sunday-hwp-autofill.js")[0].decode("utf-8")
    assert 'id="form-groups"' in html
    assert 'id="notice-text"' in html
    assert "function form()" in js
    assert "function parse()" in js
    assert "목장 본문·제목을 주일 PPT에도 사용" in js
    assert "copySundaySharingToSermon()" in js
    assert "if(!confirm(" in js
    assert "function planSermonCopy(fields)" in policy
    assert "conflicts.length===0" in policy
    assert "목장 본문" in policy and "성경 본문" in policy
    assert "목장 제목" in policy and "설교 제목" in policy


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js unavailable")
def test_copy_policy_never_overwrites_existing_sermon():
    policy = blue_original.resource("/sunday-hwp-autofill.js")[0].decode("utf-8")
    probe = """
    const assert = require('node:assert/strict');
    const source = {
      '목장 본문': {state:'VALUE',value:'단 1:8~9'},
      '목장 제목': {state:'VALUE',value:'믿음과 상황이 충돌할 때'},
    };
    let plan = SundayHwpAutofill.planSermonCopy(source);
    assert.equal(plan.ready, true);
    assert.equal(plan.updates['성경 본문'].value,'단 1:8~9');
    assert.equal(plan.updates['설교 제목'].value,'믿음과 상황이 충돌할 때');
    plan = SundayHwpAutofill.planSermonCopy({
      ...source,'성경 본문':{state:'VALUE',value:'시편 24:3'},
    });
    assert.equal(plan.ready, false);
    assert.deepEqual(plan.updates, {});
    plan = SundayHwpAutofill.planSermonCopy({
      ...source,'성경 본문':{state:'VALUE',value:'단 1:8~9'},
      '설교 제목':{state:'VALUE',value:'믿음과 상황이 충돌할 때'},
    });
    assert.equal(plan.ready, false);
    assert.deepEqual(plan.updates, {});
    """
    result = subprocess.run(["node", "-e", policy+"\n"+probe], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
