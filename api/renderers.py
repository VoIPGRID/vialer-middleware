from rest_framework import renderers


class PlainTextRenderer(renderers.BaseRenderer):
    """
    Custom renderer to return a plain text response for asterisk.
    """
    media_type = 'text/plain'
    format = 'txt'

    def render(self, data, media_type=None, renderer_context=None):
        return data.encode(self.charset)
