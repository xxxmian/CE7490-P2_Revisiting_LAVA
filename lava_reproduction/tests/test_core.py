import unittest,json,math
from dataclasses import replace
from pathlib import Path
from lava.model import Request,Record,Predictor,trace,mixture_remaining
from lava.simulator import simulate,Host,POLICIES
from lava.stats import interval,t_critical,paired
C=json.loads(Path('configs/report_scale.json').read_text())
class Tests(unittest.TestCase):
 def test_conditional_mean(self):
  self.assertAlmostEqual(mixture_remaining([.5,1,10],0)[0],5.5)
  self.assertGreater(mixture_remaining([.5,1,10],10)[0],9.9)
 def test_underflow(self):self.assertTrue(math.isfinite(mixture_remaining([.5,1,10],1e7)[0]))
 def test_confidence(self):
  records=trace(C,1)
  for setting in ['synthetic','.25','.85','oracle']:
   p=Predictor(C,1,setting,records)
   for r in records[:30]:
    value,conf=p.predict(r.request,r.request.arrival)
    self.assertGreater(value,0);self.assertTrue(0<=conf<=1)
 def test_no_truth_access(self):
  records=trace(C,1);p=Predictor(C,1,'synthetic',records)
  altered=[replace(r,duration=r.duration*100) for r in records]
  q=Predictor(C,1,'synthetic',altered)
  self.assertEqual(p.predict(records[0].request,1),q.predict(records[0].request,1))
  self.assertFalse(hasattr(records[0].request,'duration'))
 def test_conditional_noise_ignores_bucket(self):
  records=trace(C,1);p=Predictor(C,1,'.25',records)
  self.assertFalse(hasattr(p,'buckets'))
  self.assertEqual(p.predict(records[0].request,1),p.predict(records[0].request,1))
 def test_seed(self):self.assertEqual(trace(C,42),trace(C,42));self.assertNotEqual(trace(C,41),trace(C,42))
 def test_resources(self):
  c=dict(C,vms=120,hosts=20)
  for policy in POLICIES:
   r=simulate(trace(c,0),c,0,'synthetic',policy)
   self.assertEqual(r['accepted'],120);self.assertEqual(r['failures'],0)
   self.assertLessEqual(r['max_cpu'],1+1e-9);self.assertLessEqual(r['max_mem'],1+1e-9)
 def test_time_integral(self):
  records=[Record(Request(0,0,.5,.5,'batch'),2),Record(Request(1,1,.5,.5,'batch'),2)]
  r=simulate(records,dict(C,hosts=2),0,'oracle','best_fit')
  self.assertAlmostEqual(r['empty_pct'],50);self.assertAlmostEqual(r['packing_density'],2/3)
 def test_departure_before_arrival(self):
  records=[Record(Request(0,0,1,1,'batch'),1),Record(Request(1,1,1,1,'batch'),1)]
  r=simulate(records,dict(C,hosts=1),0,'oracle','best_fit');self.assertEqual(r['accepted'],2)
 def test_host_isolation(self):
  c=dict(C,vms=300,hosts=180);r=simulate(trace(c,3),c,3,'synthetic','host_ca')
  self.assertEqual(r['cross_baseline_into_lava']+r['cross_lava_into_baseline'],0)
 def test_fallback(self):
  c=dict(C,hosts=1);records=[Record(Request(0,0,.25,.25,'interactive'),10),Record(Request(1,1,.25,.25,'service'),10)]
  # Force two different confidence gates with threshold between profile confidences.
  p=Predictor(c,0,'synthetic',records);confs=[p.predict(r.request,r.request.arrival)[1] for r in records]
  self.assertNotEqual(*confs)
  r=simulate(records,c,0,'synthetic','host_ca',sum(confs)/2)
  self.assertEqual(r['accepted'],2);self.assertEqual(r['capacity_fallback'],1)
 def test_oracle_equivalence(self):
  c=dict(C,vms=100);records=trace(c,3)
  vals=[simulate(records,c,3,'oracle',p)['empty_pct'] for p in ['lava','vm_ca','host_ca']]
  self.assertEqual(vals,[vals[0]]*3)
 def test_student_t(self):
  self.assertAlmostEqual(t_critical(19),2.093024054,places=7)
  self.assertAlmostEqual(t_critical(5),2.570581836,places=7)
  self.assertEqual(interval([1]*20),(1,1,1))
 def test_unpaired(self):
  with self.assertRaises(ValueError):paired([], 'lava','best_fit','oracle')
 def test_host_reset(self):
  h=Host(0);h.mode='lava';h.state='recycling';h.residual={1};h.reset()
  self.assertIsNone(h.mode);self.assertEqual(h.state,'empty');self.assertFalse(h.residual)
 def test_rejection(self):
  r=simulate([Record(Request(0,0,1.1,.5,'batch'),1)],dict(C,hosts=1),0,'oracle','best_fit')
  self.assertEqual(r['failures'],1)
if __name__=='__main__':unittest.main()
