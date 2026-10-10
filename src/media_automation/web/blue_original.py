"""Serve the unmodified original blue UI through strict, locally authenticated routes.

Source-of-truth remains _legacy_migration/ui/index.html. We only externalize
the inline CSS/JS at request time to honor the canonical server's CSP.
Never replace its field forms with a reduced replica.
"""
from __future__ import annotations

from pathlib import Path
import re

ORIGINAL = Path(__file__).resolve().parent.parent / "_legacy_migration" / "ui"
_INDEX = ORIGINAL / "index.html"
_STYLE = re.compile(r"<style>([\s\S]*?)</style>")
_INLINE = re.compile(r"<script>([\s\S]*?)</script>")


def _parts():
    source = _INDEX.read_text(encoding="utf-8")
    style = _STYLE.search(source)
    scripts = list(_INLINE.finditer(source))
    if not style or len(scripts) != 1 or "form-groups" not in source:
        raise RuntimeError("원래 파란색 UI 파일 구성이 예상과 다릅니다.")
    return source, style, scripts[0]


def page() -> bytes:
    original, style, script = _parts()
    # The same original DOM and exact application JavaScript, no field deletion.
    rendered = original.replace(style.group(0), '<link rel="stylesheet" href="/blue-original.css">', 1)
    rendered = rendered.replace(script.group(0), '<script src="/blue-original.js"></script>', 1)
    rendered = rendered.replace(
        '<script src="bulletin-number.js">',
        '<script src="/blue-auth.js"></script>\n<script src="/bulletin-number.js">',
        1,
    )
    rendered = rendered.replace(
        '<p class="preview-only">화면 시안 · 실제 제작과 클라우드 연결 전</p>',
        '<p class="preview-only">원본 입력 화면 · 서버 저장 시험 중 · PPT 제작/OneDrive 연결 전</p>',
        1,
    )
    return rendered.encode("utf-8")


def _guided_notice_script(original_script: str) -> str:
    """Keep original blue input schema and parser; clarify review/apply workflow."""
    attach_old = (
        "$('parse-review').hidden=true;"
        "msg('파일 내용을 읽었습니다. 포맷 채우기를 눌러 반영할 내용을 확인하세요.');"
    )
    attach_new = (
        "$('parse-review').hidden=true;"
        "parse();"
        "msg('파일을 읽고 항목을 찾았습니다. 아래 해석 결과를 확인한 뒤 "
        "[선택 항목 반영]을 눌러야 입력칸에 저장됩니다.');"
    )
    form_old = "const root=$('form-groups');root.replaceChildren();"
    form_new = (
        form_old +
        "if(service==='sunday'&&record().noticeSongList){"
        "const note=node('p','전달 주보에 적힌 찬양: '+record().noticeSongList+"
        "' · 시작 찬양 또는 별도 찬송에 자동 배정하지 않습니다."
        " 이번 주 주일예배 안내에서 순서를 확인해 입력하세요.','status warning');"
        "root.append(note);}"
    )
    if original_script.count(attach_old) != 1 or original_script.count(form_old) != 1:
        raise RuntimeError("원본 안내 처리 코드가 변경되어 안전하게 연결할 수 없습니다.")
    return original_script.replace(attach_old, attach_new, 1).replace(form_old, form_new, 1)


def resource(path: str) -> tuple[bytes, str]:
    original, style, script = _parts()
    if path == "/blue-original.css":
        return style.group(1).encode("utf-8"), "text/css; charset=utf-8"
    if path == "/blue-original.js":
        return _guided_notice_script(script.group(1)).encode("utf-8"), "application/javascript; charset=utf-8"
    if path == "/blue-auth.js":
        return _AUTH_BOOTSTRAP.encode("utf-8"), "application/javascript; charset=utf-8"
    permitted = {
        "/bulletin-number.js", "/notice-parser.js", "/song-search.js"
    }
    if path in permitted:
        return (ORIGINAL / path[1:]).read_bytes(), "application/javascript; charset=utf-8"
    raise FileNotFoundError("등록되지 않은 UI 파일입니다.")


_AUTH_BOOTSTRAP = r"""(()=>{'use strict';
const rawToken=location.hash.slice(1);
const token=rawToken||sessionStorage.getItem('media-token')||'';
if(token){sessionStorage.setItem('media-token',token);
  if(rawToken)history.replaceState(null,'',location.pathname+location.search);}
const baseFetch=window.fetch.bind(window);
window.fetch=function(input,options={}){
  const url=new URL(input instanceof Request?input.url:String(input),location.href);
  if(url.origin!==location.origin||!url.pathname.startsWith('/api/'))return baseFetch(input,options);
  if(!token)return baseFetch(input,options);
  const headers=new Headers(input instanceof Request?input.headers:undefined);
  if(options.headers)new Headers(options.headers).forEach((value,key)=>headers.set(key,value));
  headers.set('Authorization','Bearer '+token);
  return baseFetch(input,{...options,headers});
};
})();"""
