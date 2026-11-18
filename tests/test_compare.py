"""核对试点比较的三条渠道、证据缺口、建议复现与判断改写。"""
import json
import unittest
from pathlib import Path
from pilot_economics.evidence import connect, receive
from pilot_economics.compare import compare
from pilot_economics.recommend import recommend, diff

DATA = json.loads((Path(__file__).resolve().parents[1] / 'data' / 'pilots.json').read_text(encoding='utf-8'))
T1 = DATA['previous_known_at']
T2 = DATA['known_at']


def load(db, documents):
    for item in documents:
        receive(db, item)


class PilotCompare(unittest.TestCase):
    def setUp(self):
        self.db = connect()
        load(self.db, DATA['documents'])

    def tearDown(self):
        self.db.close()

    def pilot(self, rows, pid):
        return next(row for row in rows if row['pilot'] == pid)

    def test_channels_separated(self):
        row = self.pilot(compare(self.db, T2), 'P1')
        # 效率改善：部门自报 540 小时，剔除人员调整解释的 120 小时
        self.assertEqual(row['efficiency']['reported_saved_hours'], 540)
        self.assertEqual(row['efficiency']['staff_explained_hours'], 120)
        self.assertEqual(row['efficiency']['net_ai_hours'], 420)
        self.assertEqual(row['efficiency']['value_per_period'], 25200)
        # 收入增量：按基线价格重述，调价影响单列不计入
        self.assertAlmostEqual(row['revenue']['increment_per_period'], 8090.91, places=2)
        self.assertAlmostEqual(row['revenue']['price_effect_per_period'], 8909.09, places=2)
        # 费用转移：账面成本变化 9250，转出 1000 单列后真实服务成本 10250
        self.assertEqual(row['service_cost']['booked_delta_per_period'], 9250)
        self.assertEqual(row['cost_transfer']['net_out_per_period'], 1000)
        self.assertEqual(row['service_cost']['ai_cost_per_period'], 10250)
        self.assertEqual(row['closed_loop'], '闭环成立')
        self.assertAlmostEqual(row['net_benefit_per_period'], 23040.91, places=2)

    def test_adoption_aligned_to_coverage(self):
        row = self.pilot(compare(self.db, T2), 'P1')
        self.assertEqual(row['adoption']['eligible_users'], 39)
        self.assertEqual(row['adoption']['active_users'], 27)
        self.assertAlmostEqual(row['adoption']['adoption_rate'], 27 / 39, places=4)

    def test_evidence_gaps(self):
        rows = compare(self.db, T2)
        p3 = self.pilot(rows, 'P3')
        self.assertIn('缺少可比对照', p3['gaps'])
        self.assertEqual(p3['closed_loop'], '证据不足')
        self.assertIsNone(p3['net_benefit_per_period'])
        early = compare(self.db, T1)
        p1 = self.pilot(early, 'P1')
        self.assertIn('成本账单未结清: 2026-10', p1['gaps'])
        self.assertEqual(p1['closed_loop'], '证据不足')

    def test_recommendation_reproducible(self):
        # 全部资料（含后补账单与冲销）入库后，按原已知时间重算的建议不变
        late = recommend(self.db, T1)
        other = connect()
        try:
            load(other, [d for d in DATA['documents'] if d['received_at'] <= T1])
            early = recommend(other, T1)
        finally:
            other.close()
        self.assertEqual(early, late)
        self.assertEqual(early['digest'], late['digest'])

    def test_judgments_rewritten(self):
        result = diff(self.db, T1, T2)
        self.assertEqual(result['rewritten'], ['P1', 'P2'])
        items = {item['pilot']: item for item in result['items']}
        p1 = items['P1']
        self.assertEqual(p1['before']['closed_loop'], '证据不足')
        self.assertEqual(p1['after']['closed_loop'], '闭环成立')
        self.assertTrue(any('云账单到账' in change for change in p1['changes']))
        p2 = items['P2']
        self.assertEqual(p2['before']['closed_loop'], '闭环成立')
        self.assertEqual(p2['after']['closed_loop'], '闭环不成立')
        self.assertTrue(any('订单冲销' in change for change in p2['changes']))
        p3 = items['P3']
        self.assertFalse(p3['rewritten'])
        self.assertTrue(p3['changes'])

    def test_sources_traceable(self):
        row = self.pilot(compare(self.db, T2), 'P1')
        self.assertTrue(row['sources'])
        for period in row['periods']:
            self.assertTrue(period['sources'])


if __name__ == '__main__':
    unittest.main()
