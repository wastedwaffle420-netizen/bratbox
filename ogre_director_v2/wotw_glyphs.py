def glyph_safe_text(text):
    return str(text)

def glyph_safe_char(ch):
    s = str(ch or " ")
    return s[0] if s else " "

class GlyphCertifiedScreen:
    def __init__(self, scr):
        self.scr = scr
    def __getattr__(self, name):
        return getattr(self.scr, name)

def certify_startup(*args, **kwargs):
    return True
