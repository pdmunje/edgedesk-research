"""Made-up execution-timing and cost checks shared with the companion study."""
import argparse,hashlib,itertools,json,math,unittest
from pathlib import Path
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import engine as s

def independent_trade(op,hi,lo,cl,opening,atr,side,sweep):
    upper=max(hi[:opening]);lower=min(lo[:opening]);after=np.arange(opening,len(cl));touch=(lo[after]<=lower) if side=='long' else (hi[after]>=upper);earlier=np.r_[False,np.cumsum(touch[:-1])>0];breaks=(cl[after]>upper) if side=='long' else (cl[after]<lower);hits=np.flatnonzero(breaks&(earlier if sweep else True))
    if not len(hits):return None
    entry=after[hits[0]]+1
    if entry==len(cl):return None
    raw=min(op[0],upper-atr) if side=='long' else max(op[0],lower+atr);stop=math.floor(raw*4+1e-10)/4 if side=='long' else math.ceil(raw*4-1e-10)/4
    if (op[entry]<=stop if side=='long' else op[entry]>=stop):return None
    reached=np.flatnonzero(lo[entry:]<=stop if side=='long' else hi[entry:]>=stop);stopped=bool(len(reached));exit=entry+reached[0] if stopped else len(cl)-1;price=(min(op[exit],stop) if side=='long' else max(op[exit],stop)) if stopped else cl[-1];return ((price-op[entry]) if side=='long' else (op[entry]-price)),stopped

def fixture():
    q=pd.DataFrame({'session_minute':np.arange(6),'open':[100.,100,102,103,103,103],'high':[101.,103,103,104,105,105],'low':[99.,98,101,102,102,102],'close':[100.,102,102,103,104,104]});m={'start':0,'open':100.,'full':True,'strict_atr9_prior':1.};return q,m

class MathematicalChecks(unittest.TestCase):
    def test_earlier_touch_not_same_bar(self):
        q,m=fixture();plain,_=s.strict_trade(q,m,1,9,'long',False);sweep,_=s.strict_trade(q,m,1,9,'long',True);self.assertEqual(plain,(2.,False));self.assertEqual(sweep,(1.,False))
    def test_stop_active_on_entry_minute(self):
        q,m=fixture();q.loc[3,'low']=99.;self.assertEqual(s.strict_trade(q,m,1,9,'long',True)[0],(-3.,True))
    def test_gap_through_stop_uses_open(self):
        q,m=fixture();q.loc[4,['open','low']]=[98.,97.];self.assertEqual(s.strict_trade(q,m,1,9,'long',True)[0],(-5.,True))
    def test_invalid_open_risk_cancels(self):
        q,m=fixture();q.loc[3,'open']=99.;self.assertIsNone(s.strict_trade(q,m,1,9,'long',True)[0])
    def test_last_minute_break_has_no_next_open(self):
        q,m=fixture();q.loc[1:4,'close']=100.;self.assertIsNone(s.strict_trade(q,m,1,9,'long',True)[0])
    def test_short_symmetry(self):
        q,m=fixture();q['open']=200-q.open;q['close']=200-q.close;high=200-q.low;low=200-q.high;q['high']=high;q['low']=low;self.assertEqual(s.strict_trade(q,m,1,9,'short',True)[0],(1.,False))
    def test_tick_stop_rounding(self):
        q,m=fixture();m['strict_atr9_prior']=1.12;q.loc[3,'low']=99.8;self.assertEqual(s.strict_trade(q,m,1,9,'long',True)[0],(1.,False));q.loc[3,'low']=99.7;self.assertEqual(s.strict_trade(q,m,1,9,'long',True)[0],(-3.25,True))
    def test_sweep_must_be_after_opening_range(self):
        q,m=fixture();q.loc[1:,'low']=100.;self.assertIsNone(s.strict_trade(q,m,1,9,'long',True)[0])
    def test_missing_prior_atr(self):
        q,m=fixture();m['strict_atr9_prior']=np.nan;trade,eligible=s.strict_trade(q,m,1,9,'long',False);self.assertIsNone(trade);self.assertFalse(eligible)
    def test_incomplete_parent_rejected(self):
        q,m=fixture();m['full']=False;self.assertFalse(s.strict_trade(q,m,1,9,'long',False)[1])
    def test_wilder_seed_and_update(self):
        x=s.legacy.wilder(np.array([2.,4.,6.,8.]),3,np.zeros(4));np.testing.assert_allclose(x,[np.nan,np.nan,4,16/3],equal_nan=True)
    def test_cost_is_per_completed_round_trip(self):
        self.assertAlmostEqual(.25-s.CFG['cost_points'],-.34);self.assertAlmostEqual(.5+.09,s.CFG['cost_points'])

if __name__=='__main__':unittest.main(verbosity=2)
