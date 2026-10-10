import json
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from pathlib import Path
from server import make_server
from work_store import WorkStore

class ProductionOrderTests(unittest.TestCase):
    def test_saved_extra_songs_reach_engine_order_in_each_service(self):
        with tempfile.TemporaryDirectory() as d:
            store=WorkStore(Path(d)/'test.db')
            server=make_server(store)
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                url=f'http://127.0.0.1:{server.server_port}/api/production-order'
                groups=[['시작 찬양',['시작 찬양 1','추가 찬양 1','추가 찬양 2']],['말씀',['설교 제목']]]
                for service in ('wednesday','friday','sunday'):
                    fields={'시작 찬양 1':{'state':'VALUE','value':'원래 곡'},'추가 찬양 1':{'state':'VALUE','value':'추가한 곡'},'추가 찬양 2':{'state':'UNSET','value':''},'설교 제목':{'state':'VALUE','value':'제목'}}
                    saved=store.save('2026-10-09',service,0,{'fields':fields})
                    body={'date':'2026-10-09','service':service,'revision':saved['revision'],'groups':groups}
                    def request(body):return urllib.request.Request(url,data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
                    with urllib.request.urlopen(request(body)) as response:result=json.load(response)
                    songs=[b for b in result['order'] if b['kind']=='song']
                    self.assertEqual([b['key'] for b in songs],['시작 찬양 1','추가 찬양 1','추가 찬양 2'])
                    self.assertEqual(songs[1]['content'],'추가한 곡')
                    self.assertIsNone(songs[2]['content'])
                    self.assertFalse(result['file_generated'])
                    body['revision']=0
                    with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(request(body))
                    self.assertEqual(error.exception.code,409)
            finally:server.shutdown();server.server_close();thread.join()

if __name__=='__main__':unittest.main()
