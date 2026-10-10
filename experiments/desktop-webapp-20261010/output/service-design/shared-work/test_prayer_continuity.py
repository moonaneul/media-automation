import unittest
from production_order import build_order

class PrayerContinuityTests(unittest.TestCase):
    def test_topics_are_contiguous_but_song_boundary_remains(self):
        groups=[['첫 기도',['첫 기도 제목 1','첫 기도 내용 1','첫 기도 제목 2','첫 기도 내용 2']],['찬양',['찬양 3']],['말씀',['설교 제목']],['말씀 관련 기도',['말씀 관련 기도 제목 1','말씀 관련 기도 내용 1']]]
        fields={key:{'state':'VALUE','value':'내용'} for _,keys in groups for key in keys}
        fields['첫 기도 제목 1']['value']='7. 첫 제목'
        order=build_order(groups,fields,'friday')
        self.assertEqual([b['kind'] for b in order[:4]],['input']*4)
        self.assertEqual(order[4]['kind'],'blank')
        titles=[b['content'] for b in order if b['kind']=='input' and '기도 제목' in b['key']]
        self.assertEqual(titles,['1. 첫 제목','2. 내용','1. 내용'])

if __name__=='__main__':unittest.main()
