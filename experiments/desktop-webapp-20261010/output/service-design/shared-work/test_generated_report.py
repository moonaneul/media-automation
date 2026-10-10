import json
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from pathlib import Path
from server import make_server
from work_store import WorkStore

class GeneratedReportTests(unittest.TestCase):
    def test_report_returns_only_public_mapping_and_rejects_invalid_files(self):
        with tempfile.TemporaryDirectory() as folder:
            store=WorkStore(Path(folder)/'work.db')
            directory=Path(store.path).with_suffix('.generated');directory.mkdir()
            identifier='a'*32
            (directory/(identifier+'.pptx')).write_bytes(b'test fixture')
            (directory/(identifier+'.json')).write_text(json.dumps({'slide_count':3,'mapping':[{'key':'찬양 1','kind':'song','start':1,'end':3,'status':'original_inserted','digest':'private'}],'connections':{'path':'private'},'unresolved':[]}))
            server=make_server(store);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                base=f'http://127.0.0.1:{server.server_port}/api/generated-report?id='
                with urllib.request.urlopen(base+identifier) as response:data=json.load(response)
                self.assertEqual(data['slide_count'],3)
                self.assertEqual(data['mapping'][0]['end'],3)
                self.assertNotIn('digest',data['mapping'][0]);self.assertNotIn('connections',data)
                for value,code in [('invalid',400),('b'*32,404)]:
                    with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(base+value)
                    self.assertEqual(error.exception.code,code)
            finally:server.shutdown();server.server_close();thread.join()
