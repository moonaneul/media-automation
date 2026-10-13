"""Fit a supplied cover photo into the original artwork area, retaining typography."""
import base64
from io import BytesIO
from PIL import Image, ImageOps


def photo_bytes(photo):
    if photo is None:return None
    if not isinstance(photo,dict) or not isinstance(photo.get('filename'),str):raise ValueError('표지 사진 형식을 확인하세요.')
    data=photo.get('data','')
    if not isinstance(data,str) or not data.startswith(('data:image/png;base64,','data:image/jpeg;base64,')):raise ValueError('JPG 또는 PNG 사진을 선택하세요.')
    raw=base64.b64decode(data.split(',',1)[1],validate=True)
    if not 0<len(raw)<=6*1024*1024:raise ValueError('표지 사진은 6MB 이하여야 합니다.')
    with Image.open(BytesIO(raw)) as image:
        if image.format not in ('PNG','JPEG') or image.width*image.height>24000000:raise ValueError('사진 형식 또는 해상도를 확인하세요.')
        image.verify()
    return raw


def fitted_photo(photo):
    raw=photo_bytes(photo)
    if raw is None:return None
    with Image.open(BytesIO(raw)) as source:
        image=ImageOps.fit(ImageOps.exif_transpose(source).convert('RGB'),(1015,743),centering=(.5,.5))
    # Blend only against white, never against the old seasonal photo.
    mask=Image.new('L',image.size)
    for y in range(image.height):
        edge=min(1,y/110,(image.height-1-y)/220)
        alpha=round(255*edge*edge*(3-2*edge))
        mask.paste(alpha,(0,y,image.width,y+1))
    result=Image.composite(image,Image.new('RGB',image.size,'white'),mask)
    stream=BytesIO();result.save(stream,format='PNG');return stream.getvalue()


def replace_cover_photo(page, photo):
    """Remove the complete seasonal background, retaining the footer ink only."""
    import pymupdf as pdf
    footer=pdf.Rect(425.19,472,831.58,570)
    pix=page.get_pixmap(matrix=pdf.Matrix(3,3),clip=footer,alpha=False)
    image=Image.frombytes('RGB',(pix.width,pix.height),pix.samples)
    # The original footer is baked into the seasonal photograph. Isolate its
    # dark lettering/logo; pale lake colours must never survive a replacement.
    alpha=ImageOps.grayscale(image).point(lambda v: round(255*max(0,min(1,(160-v)/80))))
    # Above the contact lines only the centred logo belongs to the footer.
    # Exclude any darker ripples at the old photograph's bottom edge.
    alpha.paste(0,(0,0,alpha.width,9))
    alpha.paste(0,(0,0,round((530-footer.x0)*3),84))
    alpha.paste(0,(round((750-footer.x0)*3),0,alpha.width,84))
    ink=Image.new('RGBA',image.size,(0,0,0,0));ink.putalpha(alpha)
    stream=BytesIO();ink.save(stream,format='PNG')
    page.draw_rect(pdf.Rect(425.19,175,831.58,580),color=None,fill=(1,1,1),overlay=True)
    page.insert_image(pdf.Rect(425.19,175,831.58,472),stream=fitted_photo(photo),keep_proportion=False,overlay=True)
    ink_rect=pdf.Rect(pix.x/3,pix.y/3,(pix.x+pix.width)/3,(pix.y+pix.height)/3)
    page.insert_image(ink_rect,stream=stream.getvalue(),keep_proportion=False,overlay=True)
