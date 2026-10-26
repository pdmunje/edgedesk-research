"""Independent five-minute construction, running averages, signals and trade arithmetic."""
import argparse,csv,io,json,math,statistics,unittest,zipfile
from pathlib import Path
import numpy as np
import pandas as pd
import gap_base
import gap_recount
import reproduce as subject
import rules

def read_paths(source,eligible):
    paths={d:[] for d in eligible}
    with zipfile.ZipFile(source) as z:
        names=[n for n in z.namelist() if n.lower().endswith('.csv')];assert len(names)==1
        for r in csv.DictReader(io.TextIOWrapper(z.open(names[0]),encoding='utf-8-sig')):
            if r['session_date'] in paths:paths[r['session_date']].append(tuple(float(r[k]) for k in ['open','high','low','close','volume']))
    return paths

def bars_and_signals(path):
    minute_vw=[];hi=[];lo=[];weighted=vol=0.;high=-math.inf;low=math.inf
    for o,h,l,c,v in path:
        weighted+=(h+l+c)/3*v;vol+=v;assert vol>0
        minute_vw.append(weighted/vol);high=max(high,h);low=min(low,l);hi.append(high);lo.append(low)
    bars=[];vw_sum=v_sum=0.;up_anchor=down_anchor=None;up_run=down_run=False;up_used=down_used=False;prev=None
    for i in range(0,len(path),5):
        chunk=path[i:i+5];assert len(chunk)==5
        o=chunk[0][0];h=max(x[1] for x in chunk);l=min(x[2] for x in chunk);c=chunk[-1][3];v=sum(x[4] for x in chunk)
        vw_sum+=(h+l+c)/3*v;v_sum+=v
        if c>o:
            if not up_run:up_anchor=o;up_used=False
            up_run=True
        else:up_run=False
        if c<o:
            if not down_run:down_anchor=o;down_used=False
            down_run=True
        else:down_run=False
        bearish=up_anchor is not None and not up_used and prev is not None and prev>=up_anchor and c<up_anchor
        bullish=down_anchor is not None and not down_used and prev is not None and prev<=down_anchor and c>down_anchor
        bars.append({'i':i+5,'close':c,'vwap':minute_vw[i+4],'vwap5':vw_sum/v_sum,'high':hi[i+4],'low':lo[i+4],
                     'bearish':bearish,'bullish':bullish,'short_anchor':up_anchor,'long_anchor':down_anchor})
        if bearish:up_used=True
        if bullish:down_used=True
        prev=c
    return bars

def outcome(path,i,d,target,stop):
    entry=path[i][0]
    for k in range(i,len(path)):
        o,h,l,c,v=path[k]
        if stop is not None:
            if (o<stop if d==1 else o>stop):return d*(o-entry),'stop',k,0
            if (o>=target if d==1 else o<=target):return d*(target-entry),'target',k,0
        ht=h>=target if d==1 else l<=target;hs=(l<=stop if d==1 else h>=stop) if stop is not None else False
        if hs:return d*(stop-entry),'stop',k,int(ht)
        if ht:return d*(target-entry),'target',k,0
    return d*(path[-1][3]-entry),'time',len(path)-1,0

def independent_trades(paths,events):
    trades=[]
    for e in events:
        path=paths[e['date']];assert len(path)==1380
        bars=bars_and_signals(path);target=path[0][0]-e['initial_gap'];d=1 if e['initial_gap']<0 else -1
        upper=max(target,path[0][0]);lower=min(target,path[0][0])
        touched=[i for i,b in enumerate(path) if (b[1]>=target if d==1 else b[2]<=target)];first=touched[0] if touched else len(path)
        for scope in ['all_session','overnight']:
            for rule in ['vwap','vwap5','cisd','both']:
                for b in bars:
                    i=b['i']
                    if i<30 or i>=len(path) or (scope=='overnight' and i>=930):continue
                    if first<i:break
                    outside=b['close']>upper if d==-1 else b['close']<lower
                    vw=b['close']<b['vwap'] if d==-1 else b['close']>b['vwap']
                    vw5=b['close']<b['vwap5'] if d==-1 else b['close']>b['vwap5']
                    ci=(b['bearish'] and b['short_anchor']>upper) if d==-1 else (b['bullish'] and b['long_anchor']<lower)
                    if not outside or not {'vwap':vw,'vwap5':vw5,'cisd':ci,'both':vw and ci}[rule]:continue
                    entry=path[i][0]
                    if not (entry>upper if d==-1 else entry<lower):continue
                    stop=b['high']+.25 if d==-1 else b['low']-.25
                    if not (stop>entry if d==-1 else stop<entry):continue
                    gross,out,exitidx,_=outcome(path,i,d,target,None);stopped,stopout,_,amb=outcome(path,i,d,target,stop)
                    trades.append({'session_date':e['date'],'rule':rule,'scope':scope,'entry_idx':i,'entry':entry,'target':target,'stop':stop,
                                   'pnl_gross':gross,'pnl_net':gross-1,'outcome':out,'pnl_stop_gross':stopped,'pnl_stop_net':stopped-1,
                                   'stop_outcome':stopout,'ambiguous_stop_target_bar':amb,'reward_points':abs(target-entry),'risk_points':abs(stop-entry)})
                    break
    return trades

class Mechanics(unittest.TestCase):
    def test_stop_target_tie(self):
        g=pd.DataFrame([[100,111,94,100]],columns=['open','high','low','close']);self.assertEqual(rules.simulate(g,0,1,110,95)['pnl'],-5)
    def test_open_beyond_target_precedes_later_stop(self):
        g=pd.DataFrame([[112,113,94,100]],columns=['open','high','low','close']);self.assertEqual(rules.simulate(g,0,1,110,95)['outcome'],'target')
    def test_adverse_stop_gap(self):
        g=pd.DataFrame([[100,102,99,101],[93,94,92,93]],columns=['open','high','low','close']);self.assertEqual(rules.simulate(g,0,1,110,95)['pnl'],-7)
    def test_short_target(self):
        g=pd.DataFrame([[100,101,89,90]],columns=['open','high','low','close']);self.assertEqual(rules.simulate(g,0,-1,90,None)['pnl'],10)
    def test_time_exit(self):
        g=pd.DataFrame([[100,102,99,101]],columns=['open','high','low','close']);self.assertEqual(rules.simulate(g,0,1,110,None)['pnl'],1)
    def test_minute_weighted_average(self):
        p=[(10,12,9,12,2),(12,15,12,15,1)]+[(14,14,14,14,1)]*3
        self.assertAlmostEqual(bars_and_signals(p)[0]['vwap'],(11*2+14+14*3)/6)
    def test_candle_run_cross_and_single_use(self):
        p=[]
        for o,c in [(100,102),(102,104),(104,99),(99,98),(98,98),(98,99)]:p += [(o,max(o,c),min(o,c),c,1)]*5
        b=bars_and_signals(p);self.assertFalse(b[1]['bearish']);self.assertTrue(b[2]['bearish']);self.assertEqual(b[2]['short_anchor'],100);self.assertFalse(b[3]['bearish'])

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',required=True,type=Path);p.add_argument('--summary',required=True,type=Path);p.add_argument('--original-trades',type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args()
    tests=unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(Mechanics));assert tests.wasSuccessful()
    before=gap_base.fingerprint(a.input);saved=json.loads(a.summary.read_text());assert before==saved['source_sha256']
    signals,_,_,_=gap_recount.independent(a.input);events=[r for r in signals if r['full_day_quality']]
    paths=read_paths(a.input,{r['date'] for r in events});actual=independent_trades(paths,events)
    expected,legacy,current_events,checks,data=subject.calculate(a.input);assert events==current_events
    key=lambda r:(r['scope'],r['rule'],r['session_date']);actual.sort(key=key);expected.sort(key=key);assert len(actual)==len(expected)
    matches=0
    def eq(x,y):
        nonlocal matches
        if isinstance(x,(int,float)):assert math.isclose(x,y,rel_tol=1e-11,abs_tol=1e-8),(x,y)
        else:assert x==y,(x,y)
        matches+=1
    for x,y in zip(actual,expected):
        for k,v in x.items():eq(v,y[k])
        assert y['entry_idx']>=30 and y['entry_idx']%5==0 and (y['scope']!='overnight' or y['entry_idx']<930)
    for name,r in saved['results'].items():
        chosen=[x for x in actual if x['scope']+'_'+x['rule']==name];eq(len(chosen),r['trades'])
        for label,col in [('net_no_stop','pnl_net'),('net_with_stop','pnl_stop_net')]:
            values=[t[col] for t in chosen];want=r[label]
            for k,value in [('mean',statistics.mean(values)),('median',statistics.median(values)),('sum',sum(values)),('minimum',min(values)),('maximum',max(values)),('positive_events',sum(v>0 for v in values))]:eq(value,want[k])
        values=[t['pnl_net'] for t in chosen];eq((sum(values)-max(values))/(len(values)-1),r['without_largest_no_stop_winner_mean']);eq(sum(values)/len(events),r['mean_per_eligible_gap_no_trade_zero'])
        eq(sum(x['outcome']=='target' for x in chosen),r['target_exits'])
        for period,mask in [('first_year',lambda t:t['session_date']<'2025-08-29'),('second_year',lambda t:t['session_date']>='2025-08-29')]:
            subset=[t for t in chosen if mask(t)];eq(len(subset),r['periods'][period]['trades']);eq(statistics.mean(t['pnl_net'] for t in subset),r['periods'][period]['net_no_stop']['mean'])
    audit={'performed':False}
    if a.original_trades:
        with a.original_trades.open(encoding='utf-8-sig',newline='') as f:old=list(csv.DictReader(f))
        old.sort(key=key);legacy.sort(key=key);assert len(old)==len(legacy);count=0
        for x,y in zip(old,legacy):
            assert key(x)==key(y)
            for k in ['entry_idx','entry','target','stop','pnl_gross','pnl_stop_gross','reward_points','risk_points']:
                assert math.isclose(float(x[k]),y[k],rel_tol=1e-11,abs_tol=1e-8),(key(x),k,x[k],y[k]);count+=1
        audit={'performed':True,'saved_trade_records':len(old),'legacy_trade_value_matches':count,'scope':'Original 122-event sample, all eight rule/window combinations; saved entry/target/stop/reward/risk and both gross outcomes reproduced. Original selection and stop sequencing kept only for this audit.'}
    assert gap_base.fingerprint(a.input)==before
    out={'passed':True,'checked_date':'2026-10-16','source_sha256':before,'independent_value_matches':matches,'made_up_tests_passed':tests.testsRun,
         'measurable_full_day_gaps':len(events),'current_trade_records':len(actual),'original_trade_audit':audit,
         'scope':'Separate CSV/date qualification plus separately constructed minute/five-minute averages, candle-run signals and price paths. All current event/trade keys and reported trade fields compared. No order-execution audit or untouched-date validation.'}
    a.output.write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8');print(json.dumps(out,indent=2))

if __name__=='__main__':main()
