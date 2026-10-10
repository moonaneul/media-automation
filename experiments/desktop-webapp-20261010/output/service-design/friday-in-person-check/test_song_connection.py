import hashlib
import tempfile
import unittest
from pathlib import Path
from song_connection import resolve_song

class SongConnectionTests(unittest.TestCase):
    def test_blank_and_typo_do_not_choose_another_song(self):
        library=[{'id':'s1','title':'푯대를 향하여','aliases':[]}]
        self.assertEqual(resolve_song(None,library,'.')['status'],'missing_song_input')
        self.assertEqual(resolve_song('푯대를 향하야',library,'.')['status'],'song_not_registered')

    def test_review_and_actual_file_required(self):
        with tempfile.TemporaryDirectory() as directory:
            data=(Path(__file__).parent/'output/friday-prayer-topics.pptx').read_bytes()
            digest=hashlib.sha256(data).hexdigest()
            Path(directory,digest).write_bytes(data)
            asset={'digest':digest,'filename':'시험용.pptx','review':{'technical':True,'church':True,'permission':'unknown'}}
            song={'id':'test','title':'가상 곡','assets':[asset]}
            self.assertEqual(resolve_song('가상곡',[song],directory)['status'],'no_eligible_original')
            asset['review']['permission']='allowed'
            result=resolve_song('가상곡',[song],directory)
            self.assertEqual(result['status'],'connected')
            self.assertEqual(result['slide_count'],3)
            Path(directory,digest).write_bytes(b'changed')
            self.assertEqual(resolve_song('가상곡',[song],directory)['reasons'],['file_missing_or_changed'])

    def test_duplicate_song_requires_confirmation(self):
        songs=[{'id':'a','title':'곡'},{'id':'b','title':'곡'}]
        self.assertEqual(resolve_song('곡',songs,'.')['status'],'confirm_song')

if __name__=='__main__':unittest.main()
