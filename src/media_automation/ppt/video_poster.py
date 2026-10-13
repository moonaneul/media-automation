"""Use a decoded video frame instead of python-pptx's default speaker icon."""
import os
import shutil
import subprocess
from pathlib import Path


def video_poster(source):
    source = Path(source)
    poster = source.with_name(source.name + '.poster.png')
    if poster.is_file():
        return poster
    binary = os.environ.get('MEDIA_FFMPEG') or shutil.which('ffmpeg')
    if not binary:
        import imageio_ffmpeg
        binary = imageio_ffmpeg.get_ffmpeg_exe()
    temporary = poster.with_name(poster.stem + '.tmp.png')
    try:
        subprocess.run([binary, '-y', '-ss', '2', '-i', str(source),
                        '-frames:v', '1', str(temporary)],
                       check=True, capture_output=True, timeout=60)
        if not temporary.is_file():
            raise ValueError('영상의 미리보기 화면을 읽을 수 없습니다.')
        temporary.replace(poster)
    except subprocess.CalledProcessError as exc:
        raise ValueError('영상 파일을 해독할 수 없습니다. 정상 MP4 파일을 확인하세요.') from exc
    finally:
        temporary.unlink(missing_ok=True)
    return poster
