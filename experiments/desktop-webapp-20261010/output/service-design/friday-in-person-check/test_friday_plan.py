import copy
import json
import unittest
from pathlib import Path
from friday_plan import build_plan


class FridayPlanTests(unittest.TestCase):
    def setUp(self):
        self.data=json.loads((Path(__file__).parent/'notice-0828.json').read_text())

    def test_delivered_order_preserves_missing_songs_and_prayers(self):
        before=copy.deepcopy(self.data)
        result=build_plan(self.data)
        self.assertEqual(self.data,before)
        actual=[b['key'] for b in result.blocks if b['kind']!='blank']
        self.assertEqual(actual,['song_1','song_2','song_3','song_4','song_5','message','message_scripture','song_6','word_prayer','song_7','song_8'])
        self.assertEqual(result.unresolved,['date','song_1','song_2','song_3','song_4','song_5','song_7','song_8'])
        self.assertFalse(result.ready)
        missing=[b for b in result.blocks if b.get('render')=='blank_slot']
        self.assertEqual(len(missing),7)
        prayers=next(b['screens'] for b in result.blocks if b['kind']=='prayer_topics')
        self.assertEqual(prayers,self.data['order'][9]['content']['value'])
        self.assertEqual(len(prayers),3)

    def test_explicitly_added_scripture_has_only_one_boundary(self):
        item=next(i for i in self.data['order'] if i['key']=='additional_scripture')
        item['content']={'state':'VALUE','value':'사용자가 별도로 지정한 범위'}
        result=build_plan(self.data)
        self.assertIn('additional_scripture',[b['key'] for b in result.blocks])
        self.assertTrue(all(not(a['kind']==b['kind']=='blank') for a,b in zip(result.blocks,result.blocks[1:])))

    def test_reject_empty_value_and_duplicate_order(self):
        self.data['order'][0]['content']={'state':'VALUE','value':''}
        with self.assertRaises(ValueError): build_plan(self.data)
        self.setUp()
        self.data['order'].append(self.data['order'][0])
        with self.assertRaises(ValueError): build_plan(self.data)


if __name__=='__main__': unittest.main()
