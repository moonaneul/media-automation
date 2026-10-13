"""Remove accidental line-leading list marks without changing the supplied words."""
import re

_LEADING_MARKS = re.compile(r"^[\s\u200b\ufeff.．。·•‧∙⋅…⋯,，;；:：!！?？*＊#＃+＋=＝_＿~～\-–—−▪▫■□●○◆◇▶▷►▸>›»/\\|]+")

def clean_leading_marks(text):
    """Keep numbering, quotes, parentheses and all interior punctuation intact."""
    return '\n'.join(_LEADING_MARKS.sub('', line).rstrip() for line in text.splitlines())
