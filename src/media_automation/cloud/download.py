"""HTTP/1.1 chunked files for Cloud Run's large-response streaming path."""
import mimetypes
from pathlib import Path


def send_file(handler, file):
    file = Path(file)
    mime = mimetypes.guess_type(file.name)[0] or 'application/octet-stream'
    handler.protocol_version = 'HTTP/1.1'
    handler.close_connection = True
    handler.send_response(200)
    handler.send_header('Content-Type', mime)
    handler.send_header('Transfer-Encoding', 'chunked')
    handler.send_header('Connection', 'close')
    handler.send_header('Cache-Control', 'no-store')
    handler.send_header('X-Content-Type-Options', 'nosniff')
    handler.send_header('Referrer-Policy', 'no-referrer')
    handler.end_headers()
    with file.open('rb') as stream:
        while chunk := stream.read(1024 * 1024):
            handler.wfile.write(format(len(chunk), 'x').encode() + b'\r\n')
            handler.wfile.write(chunk)
            handler.wfile.write(b'\r\n')
            handler.wfile.flush()
    handler.wfile.write(b'0\r\n\r\n')
    handler.wfile.flush()
