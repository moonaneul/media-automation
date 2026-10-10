import tempfile
import unittest
from pathlib import Path
import yaml
from bible_connection import resolve

class BibleConnectionTests(unittest.TestCase):
    def test_prayer_reference_expands_without_duplicating_supplied_text(self):
        blocks=[{'kind':'input','key':'첫 기도 내용 1','state':'VALUE','content':'- (빌 4:6~7)'},{'kind':'input','key':'첫 기도 내용 2','state':'VALUE','content':'[6] 직접 제공한 본문 (빌 4:6~7)'}]
        result=resolve(blocks)
        content=result['첫 기도 내용 1']['resolved_content']
        self.assertIn('[6] 아무 것도 염려하지 말고',content)
        self.assertIn('\n[7]',content)
        self.assertNotIn('첫 기도 내용 2',result)
    def test_plain_prayer_and_mixed_reference_are_distinguished(self):
        result=resolve([{'kind':'input','key':'첫 기도 내용 1','state':'VALUE','content':'가족과 이웃을 위해 기도합니다'},{'kind':'input','key':'첫 기도 내용 2','state':'VALUE','content':'염려 대신 기도하도록 (빌 4:6~7)'},{'kind':'input','key':'첫 기도 제목 1','state':'VALUE','content':'빌 4:6~7'}])
        self.assertNotIn('첫 기도 내용 1',result)
        self.assertNotIn('첫 기도 제목 1',result)
        self.assertIn('염려 대신 기도하도록',result['첫 기도 내용 2']['resolved_content'])
        self.assertIn('[7]',result['첫 기도 내용 2']['resolved_content'])
    def test_exact_range_and_multiple_references_from_validated_source(self):
        result=resolve([{'kind':'input','key':'성경 본문','state':'VALUE','content':'삼상 18:6~11'},{'kind':'input','key':'추가 말씀 1','state':'VALUE','content':'히 11:1, 히 11:2~3'}])
        self.assertEqual([v['start_verse'] for v in result['성경 본문']['units']],list(range(6,12)))
        self.assertEqual(len(result['추가 말씀 1']['units']),3)
        self.assertEqual([v['passage_reference'] for v in result['성경 본문']['units']],['삼상 18:6~11']*6)
    def test_missing_verse_does_not_insert_partial_passage(self):
        result=resolve([{'kind':'input','key':'성경 본문','state':'VALUE','content':'삼상 18:6~999'}])
        self.assertEqual(result['성경 본문']['units'],[])
        self.assertIn('error',result['성경 본문'])
    def test_unvalidated_source_and_empty_input_are_not_used(self):
        with tempfile.TemporaryDirectory() as folder:
            source={'translation':'개역개정','validated':False,'passages':{'히 11:1':{'reference':'히 11:1','verses':{1:'검수되지 않은 테스트 본문'}}}}
            Path(folder,'source.yaml').write_text(yaml.safe_dump(source,allow_unicode=True))
            result=resolve([{'kind':'input','key':'성경 본문','state':'VALUE','content':'히 11:1'},{'kind':'input','key':'추가 말씀 1','state':'NONE','content':''}],Path(folder))
            self.assertEqual(result['성경 본문']['units'],[])
            self.assertNotIn('추가 말씀 1',result)

    def test_provided_bible_reaches_additional_and_sunday_passages(self):
        result=resolve([{'kind':'input','key':'추가 말씀 1','state':'VALUE','content':'마 3:1~3'},{'kind':'input','key':'성경 본문','state':'VALUE','content':'마 5:43~48, '}])
        self.assertEqual(len(result['추가 말씀 1']['units']),3)
        self.assertEqual(len(result['성경 본문']['units']),6)
        self.assertEqual(result['성경 본문']['source'],'user_provided_bible')
        self.assertFalse(result['성경 본문']['source_validated'])
