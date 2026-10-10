import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from work_store import WorkStore
from weekly_assets import resolve_attachment
from production_order import build_order

class WeeklyAssetTests(unittest.TestCase):
    def test_legacy_original_requires_conversion(self):
        with tempfile.TemporaryDirectory() as d:
            store=WorkStore(Path(d)/'test.db')
            store.attach('2026-10-07','wednesday','추가 찬양','원본.ppt',bytes.fromhex('d0cf11e0a1b11ae1')+b'legacy')
            with patch('ppt_conversion.convert_original',side_effect=RuntimeError('conversion unavailable')):
                result=resolve_attachment(store.attachments('2026-10-07','wednesday')[0],Path(store.path).with_suffix('.files'))
            self.assertEqual(result['status'],'conversion_failed')

    def test_person_metadata_and_ad_details_do_not_become_slides(self):
        fields={k:{'state':'VALUE','value':v} for k,v in [('기도 담당자','담당자 A'),('주일 인도자','인도자 A'),('2부 봉헌기도 담당자','담당자 B'),('설교 제목','설교 제목 예시'),('성경 본문','삼상 18:6~11'),('교회 소식','주보 전용 상세 광고')]}
        result=build_order([['예배',list(fields)]],fields,'sunday')
        blocks={b['key']:b for b in result if b['kind']=='input'}
        self.assertNotIn('주일 인도자',blocks)
        self.assertEqual(blocks['기도 담당자']['content'],'기도\n담당자 A')
        self.assertEqual(blocks['2부 봉헌기도 담당자']['content'],'봉헌기도\n담당자 B')
        self.assertEqual(blocks['교회 소식']['content'],'광고시간')
        self.assertEqual(blocks['설교 제목']['subtitle'],'삼상 18:6~11')


    def test_wednesday_ads_follow_prayer_even_for_old_client_order(self):
        groups=[['기도',['기도 담당자','추가 찬양']],['마무리',['결단 찬송','광고 순서']]]
        fields={label:{'state':'VALUE','value':'포함'} for _,labels in groups for label in labels}
        order=build_order(groups,fields,'wednesday')
        keys=[block['key'] for block in order if block['kind']!='blank']
        self.assertEqual(keys,['기도 담당자','광고 순서','추가 찬양','결단 찬송'])
