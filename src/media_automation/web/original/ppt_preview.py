"""Preview saved artifacts through the official renderer, with a hash cache."""
import json
import hashlib
from pathlib import Path
import threading
import subprocess
import shutil
import os
from media_automation.web.pptx_preview import convert_pptx
LOCK = threading.Lock()


def preview(store, identifier, page):
    if len(identifier)!=32 or any(c not in '0123456789abcdef' for c in identifier): raise ValueError('파일을 확인하세요.')
    directory=Path(store.path).with_suffix('.generated')
    ppt=directory/(identifier+'.pptx')
    report=json.loads((directory/(identifier+'.json')).read_text(encoding='utf-8'))
    is_pdf=report.get('format')=='pdf'
    source=directory/(identifier+'.pdf') if is_pdf else ppt
    if is_pdf:
        from pypdf import PdfReader
        count=len(PdfReader(source).pages)
    else:count=report['slide_count']
    if not isinstance(page,int) or not 1<=page<=count:raise ValueError('페이지 번호를 확인하세요.')
    digest=hashlib.sha256(source.read_bytes()).hexdigest()
    pdf=source if is_pdf else directory/(identifier+'-'+digest+'.preview.pdf')
    png=directory/(identifier+'-'+digest+f'-mupdf-v1-{page}.png')
    return render_pdf_page(pdf, page, png, ppt if not is_pdf else None)


def render_pdf_page(pdf, page, png, ppt=None):
    with LOCK:
        if not pdf.is_file(): convert_pptx(ppt,pdf)
        if not png.is_file():
            # PowerPoint PDF fonts can disappear in Poppler despite valid text.
            # MuPDF preserves those glyphs in the actual preview image.
            try:
                import pymupdf
            except ImportError:
                pymupdf = None
            if pymupdf is not None:
                with pymupdf.open(pdf) as document:
                    rendered_page = document[page - 1]
                    scale = 1200 / max(rendered_page.rect.width, rendered_page.rect.height)
                    rendered_page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False).save(png)
                return png.read_bytes()
            binary = os.environ.get('MEDIA_PDF_RENDERER') or shutil.which('pdftoppm')
            if not binary:
                bundled = Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/override/pdftoppm'
                binary = str(bundled) if bundled.is_file() else None
            if not binary: raise ValueError('PDF 화면 렌더링 도구 pdftoppm이 필요합니다.')
            subprocess.run([binary, '-f', str(page), '-l', str(page), '-singlefile', '-scale-to', '1200', '-png', str(pdf), str(png.with_suffix(''))], check=True, capture_output=True, timeout=60)
    return png.read_bytes()
