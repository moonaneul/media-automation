"""Embed explicitly selected prayer audio; playback requires separate inspection."""
from pptx.oxml.ns import qn
from pptx.opc.constants import RELATIONSHIP_TYPE as RT
from pptx.util import Inches


def embed_prayer_audio(prs, path, *, slide_number, slide_count=1):
    slide = prs.slides[slide_number-1]
    audio = slide.shapes.add_movie(str(path), prs.slide_width-Inches(.65), prs.slide_height-Inches(.65),
                                   Inches(.4), Inches(.4), mime_type='audio/mpeg')
    audio.name='기도 배경음악'
    for node in audio._element.iter(qn('a:videoFile')):
        node.tag=qn('a:audioFile')
        relationship=slide.part.rels[node.get(qn('r:link'))]
        relationship._reltype=RT.AUDIO
        relationship.__dict__.pop('reltype',None)
    for node in slide._element.iter(qn('p:video')):node.tag=qn('p:audio')
    for node in slide._element.iter(qn('p:cMediaNode')):
        node.set('vol','20000');node.set('numSld',str(slide_count))
        for timing in node.iter(qn('p:cTn')):timing.set('repeatCount','indefinite')
    for node in slide._element.iter(qn('p:cond')):
        if node.get('delay')=='indefinite':node.set('delay','0')
    return audio
