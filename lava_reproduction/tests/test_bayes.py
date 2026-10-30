import unittest,json,math,csv,bisect,statistics
from dataclasses import replace
from pathlib import Path
from lava.model import Request,Record,Predictor,BayesPredictor,trace,mixture_remaining
from lava.simulator import simulate,POLICIES,BAYES_POLICIES
from lava.stats import t_test,holm,t_critical
C=json.loads(Path('configs/report_scale.json').read_text())
class BayesTests(unittest.TestCase):
 def test_delegates_without_noisy_value(self):
  records=trace(C,1)
  for setting in ['synthetic','oracle']:
   p=Predictor(C,1,setting,records);q=BayesPredictor(C,1,setting,records)
   for r in records[:40]:
    for dt in [0,.5,7,90]:self.assertEqual(p.predict(r.request,r.request.arrival+dt),q.predict(r.request,r.request.arrival+dt))
 def test_policies_identical_without_noisy_value(self):
  c=dict(C,vms=300);records=trace(c,4)
  for setting in ['synthetic','oracle']:
   for policy in BAYES_POLICIES:
    a=simulate(records,c,4,setting,policy);b=simulate(records,c,4,setting,policy[:-6])
    self.assertEqual({k:v for k,v in a.items() if k!='policy'},{k:v for k,v in b.items() if k!='policy'})
 def test_accurate_value_trusted(self):
  req=Request(0,0,.125,.125,'batch');q=BayesPredictor(C,0,'1.0',[]);q.values={0:5.}
  self.assertAlmostEqual(q.predict(req,0)[0],5.,delta=.02);self.assertAlmostEqual(q.predict(req,2)[0],3.,delta=.02)
  self.assertGreater(q.predict(req,0)[1],.99)
 def test_implausible_value_falls_back_to_prior(self):
  req=Request(0,0,.125,.125,'interactive');prior=mixture_remaining(C['profiles']['interactive'],0)[0]
  for value in [300.,1e-6]:
   q=BayesPredictor(C,0,'0.25',[]);q.values={0:value}
   self.assertLess(abs(math.log(q.predict(req,0)[0]/prior)),math.log(3))
  # Raw controlled predictor trusts the same values.
  p=Predictor(C,0,'0.25',[]);p.values={0:300.};self.assertGreater(p.predict(req,0)[0],299)
 def test_plausible_value_moves_posterior(self):
  req=Request(0,0,.125,.125,'service');q=BayesPredictor(C,0,'0.5',[]);q.values={0:2.}
  self.assertLess(q.predict(req,0)[0],mixture_remaining(C['profiles']['service'],0)[0]/2)
 def test_censored_value(self):
  req=Request(0,0,.125,.125,'service');q=BayesPredictor(C,0,'1.0',[]);q.values={0:C['cap_hours']}
  r,conf=q.predict(req,0);self.assertEqual(r,C['cap_hours']);self.assertGreater(conf,.99)
  T,mass,_=q.post[0];self.assertLess(1-mass[bisect.bisect_left(T,C['cap_hours']*.99)]/mass[0],1e-9)
 def test_overdue_uses_survival(self):
  req=Request(0,0,.125,.125,'batch');q=BayesPredictor(C,0,'0.85',[]);q.values={0:2.}
  self.assertGreater(q.predict(req,40)[0],5)
  q=BayesPredictor(C,0,'1.0',[]);q.values={0:2.};r,conf=q.predict(req,40)
  self.assertTrue(r>0 and 0<=conf<=1)
 def test_no_truth_access(self):
  records=trace(C,2);p=BayesPredictor(C,2,'0.5',records)
  q=BayesPredictor(C,2,'0.5',[replace(r,duration=r.duration*50) for r in records]);q.values=dict(p.values)
  for r in records[:50]:self.assertEqual(p.predict(r.request,r.request.arrival+1),q.predict(r.request,r.request.arrival+1))
  self.assertFalse(any(hasattr(p,k) for k in ['records','durations','buckets']))
 def test_confidence_bounds(self):
  records=trace(C,3)
  for setting in ['0.25','0.85','1.0']:
   q=BayesPredictor(C,3,setting,records)
   for r in records[:60]:
    for dt in [0,3,30,400]:
     value,conf=q.predict(r.request,r.request.arrival+dt);self.assertGreater(value,0);self.assertTrue(0<=conf<=1)
 def test_bayes_policies_safe(self):
  c=dict(C,vms=150,hosts=40)
  for policy in BAYES_POLICIES:
   r=simulate(trace(c,0),c,0,'0.5',policy)
   self.assertEqual((r['accepted'],r['failures']),(150,0));self.assertLessEqual(max(r['max_cpu'],r['max_mem']),1+1e-9)
 def test_reconstruction_rows_unchanged(self):
  with open('results/heldout/raw.csv') as f:rows=list(csv.DictReader(f))
  for r in [x for x in rows if x['seed']=='27' and x['setting'] in ['synthetic','0.25']]:
   out=simulate(trace(C,27),C,27,r['setting'],r['policy'],float(r['threshold']))
   self.assertEqual(repr(out['empty_pct']),r['empty_pct']);self.assertEqual(str(out['high_gate']),r['high_gate'])
 def test_arrival_window_metric(self):
  records=[Record(Request(0,0,.5,.5,'batch'),4),Record(Request(1,2,.5,.5,'batch'),1)]
  r=simulate(records,dict(C,hosts=2),0,'oracle','best_fit');self.assertAlmostEqual(r['empty_pct_arrivals'],50)
 def test_t_test_and_holm(self):
  xs=[1+.1*(-1)**i for i in range(20)]
  mean,lo,hi,p=t_test(xs);self.assertAlmostEqual(mean,1);self.assertLess(p,1e-6)
  self.assertEqual(t_test([0.]*5)[3],1.);self.assertEqual(t_test([.2]*5)[3],0.)
  self.assertEqual([round(x,6) for x in holm([.01,.04,.03])],[.03,.06,.06])
  ys=[-1.,1.]*10;self.assertAlmostEqual(t_test(ys)[3],1.)
  alt=[(-1.)**i for i in range(20)];shift=t_critical(19)*statistics.stdev(alt)/math.sqrt(20)
  mean,lo,hi,p=t_test([x+shift for x in alt]);self.assertAlmostEqual(p,.05,places=6);self.assertAlmostEqual(lo,0,places=6)
if __name__=='__main__':unittest.main()
