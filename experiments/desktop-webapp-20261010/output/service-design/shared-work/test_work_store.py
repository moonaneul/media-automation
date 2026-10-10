import tempfile
import unittest
from pathlib import Path
from work_store import WorkStore, RevisionConflict

class StoreTests(unittest.TestCase):
    def test_clients_conflict_and_week_isolation(self):
        with tempfile.TemporaryDirectory() as directory:
            a = WorkStore(Path(directory) / 'work.db')
            b = WorkStore(Path(directory) / 'work.db')
            first = {'fields': {'본문': {'state': 'VALUE', 'value': '시 24:3~5'}}}
            a.save('2026-10-07', 'wednesday', 0, first)
            self.assertEqual(b.get('2026-10-07', 'wednesday')['data'], first)
            with self.assertRaises(RevisionConflict) as error:
                b.save('2026-10-07', 'wednesday', 0, {'fields': {}})
            self.assertEqual(error.exception.current['revision'], 1)
            self.assertEqual(a.get('2026-10-07', 'wednesday')['data'], first)
            self.assertEqual(a.get('2026-10-14', 'wednesday')['data'], {})
            self.assertEqual(a.get('2026-10-07', 'sunday')['data'], {})
            b.save('2026-10-07', 'wednesday', 1, {'fields': {'본문': {'state': 'NONE', 'value': ''}}})
            self.assertEqual(a.get('2026-10-07', 'wednesday')['data']['fields']['본문']['state'], 'NONE')
            c = WorkStore(Path(directory) / 'work.db')
            self.assertEqual(c.get('2026-10-07', 'wednesday')['revision'], 2)

    def test_original_persistence_dedup_and_isolation(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'work.db'
            store=WorkStore(path)
            first=store.attach('2026-10-07','wednesday','시작 찬양 1','원본.pptx',b'file-content')
            duplicate=store.attach('2026-10-09','friday','시작 찬양 1','다른이름.pptx',b'file-content')
            self.assertFalse(first['duplicate'])
            self.assertTrue(duplicate['duplicate'])
            self.assertEqual(len(list(path.with_suffix('.files').iterdir())),1)
            reloaded=WorkStore(path)
            self.assertEqual(reloaded.attachments('2026-10-07','wednesday')[0]['filename'],'원본.pptx')
            self.assertEqual(reloaded.attachments('2026-10-14','wednesday'),[])
            with self.assertRaises(ValueError):
                store.attach('2026-10-07','wednesday','시작 찬양 1','../원본.pptx',b'x')
            self.assertEqual(reloaded.attachments('2026-10-07','wednesday')[0]['digest'],first['digest'])

    def test_song_original_link_and_preview_lookup(self):
        with tempfile.TemporaryDirectory() as directory:
            store=WorkStore(Path(directory)/'work.db')
            song=store.register_song({'title':'검증용 곡'})
            asset=store.attach('2026-10-07','wednesday','시작 찬양 1','원본.pdf',b'%PDF-test',song['id'])
            store.attach('2026-10-09','friday','시작 찬양 1','원본.pdf',b'%PDF-test',song['id'])
            self.assertEqual(len(store.songs()[0]['assets']),1)
            self.assertEqual(store.songs()[0]['assets'][0]['review_status'],'unreviewed')
            path,filename=store.original(asset['digest'])
            self.assertEqual(path.read_bytes(),b'%PDF-test')
            self.assertEqual(filename,'원본.pdf')
            with self.assertRaises(ValueError):
                store.original('../file')
            with self.assertRaises(ValueError):
                store.attach('2026-10-07','wednesday','시작 찬양 1','원본.pdf',b'x','unknown-song')

    def test_review_states_and_automatic_eligibility(self):
        with tempfile.TemporaryDirectory() as directory:
            store=WorkStore(Path(directory)/'work.db')
            song=store.register_song({'title':'검증용 곡'})
            asset=store.attach('2026-10-07','wednesday','찬양 1','악보.pptx',b'content',song['id'])
            self.assertFalse(store.songs()[0]['assets'][0]['eligible'])
            review={'technical':True,'church':True,'permission':'unknown','note':'확인 내용'}
            store.review_asset(song['id'],asset['digest'],review)
            self.assertFalse(store.songs()[0]['assets'][0]['eligible'])
            review['permission']='allowed'
            store.review_asset(song['id'],asset['digest'],review)
            self.assertTrue(store.songs()[0]['assets'][0]['eligible'])
            review['technical']=False
            store.review_asset(song['id'],asset['digest'],review)
            self.assertFalse(store.songs()[0]['assets'][0]['eligible'])
            with self.assertRaises(ValueError):
                store.review_asset('missing',asset['digest'],review)

    def test_song_registration_and_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            store = WorkStore(Path(directory) / 'work.db')
            song = store.register_song({'title':'검증용 곡','aliases':['다른 표기'],'edition':'new','number':223})
            self.assertEqual(store.songs()[0]['id'], song['id'])
            self.assertEqual(store.songs()[0]['assets'], [])
            with self.assertRaises(ValueError):
                store.register_song({'title':'검증용 곡','edition':'new','number':0})
            self.assertEqual(len(store.songs()),1)

    def test_inconsistent_state_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            store = WorkStore(Path(directory) / 'work.db')
            for field in ({'state':'NONE','value':'지난주'}, {'state':'VALUE','value':''}):
                with self.assertRaises(ValueError):
                    store.save('2026-10-07','wednesday',0,{'fields':{'본문':field}})
            self.assertEqual(store.get('2026-10-07','wednesday')['revision'],0)

if __name__ == '__main__':
    unittest.main()
