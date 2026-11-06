"""Independent column-array event extraction, matching recount and summary checks."""
import argparse,csv,datetime as dt,hashlib,json,math,unittest
from pathlib import Path
from zoneinfo import ZoneInfo
import numpy as np
import reproduce as r

def row(high,low):return {'high':high,'low':low}
def event(date='2026-06-01',touch=40,prior=8,k=300,radius=10):return {'date':date,'touch':touch,'prior_range':prior,'k':k,'radius':radius}

class Mechanics(unittest.TestCase):
    def test_classes_are_exclusive(self):self.assertEqual([r.level_class(k) for k in [300,301,302,303]],['100','25-only','50-only','25-only'])
    def test_touch_bar_extremes_excluded(self):self.assertEqual(r.extent([row(120,80),row(102,99),row(101,98)],0,100,2),2)
    def test_one_sided_future_zero(self):self.assertEqual(r.extent([row(100,100),row(110,101)],0,100,1),0)
    def test_exact_horizon_required(self):self.assertIsNone(r.extent([row(100,100),row(110,90)],0,100,2))
    def test_two_sided_extent_not_trade_return(self):self.assertEqual(r.extent([row(100,100),row(111,99),row(101,92)],0,100,2),8)
    def test_cannot_match_other_day(self):self.assertEqual(len(r.match([event()],[event(date='2026-06-02')])),0)
    def test_time_bin_excludes_near_boundary(self):self.assertEqual(len(r.match([event(touch=44)],[event(touch=45)])),0)
    def test_range_bin_excludes_mismatched_volatility(self):self.assertEqual(len(r.match([event(prior=9.75)],[event(prior=10)])),0)
    def test_no_prior_not_matched(self):self.assertEqual(len(r.match([event(prior=None)],[event()])),0)
    def test_control_not_reused(self):self.assertEqual(len(r.match([event(k=300),event(k=301)],[event(k=300)])),1)
    def test_matching_ignores_future_outcome(self):
        a=[event(k=300),event(touch=43,k=301)];b=[event(touch=42,k=300),event(touch=40,k=301)];one=[(x['k'],y['k']) for x,y in r.match(a,b)]
        for e in a+b:e['radius']*=17
        self.assertEqual(one,[(x['k'],y['k']) for x,y in r.match(a,b)])

def independent_events(path):
    # Independent raw parser/grouping: UTC timestamps and array-based first-hit positions.
    with path.open(encoding='utf-8-sig') as f:rows=list(csv.DictReader(f))
    dates={}
    for v in rows:
        t=dt.datetime.fromisoformat(v['time']).astimezone(ZoneInfo('America/New_York'));dates.setdefault(t.date().isoformat(),[]).append((t.hour*60+t.minute,float(v['high']),float(v['low'])))
    answer=[]
    for day,q in sorted(dates.items()):
        minute=np.array([x[0] for x in q]);hi=np.array([x[1] for x in q]);lo=np.array([x[2] for x in q]);assert np.array_equal(minute,np.arange(570,975))
        for shift in [0,6.25,12.5,18.75]:
            levels=np.arange(math.floor((lo.min()-shift)/25),math.ceil((hi.max()-shift)/25)+1)
            for k0 in levels:
                k=int(k0);level=25*k+shift;hits=np.where((lo<=level)&(hi>=level))[0]
                if not len(hits):continue
                t=int(hits[0]);prior=float(max(hi[t-30:t])-min(lo[t-30:t])) if t>=30 else None;kind='100' if (k/4).is_integer() else '50-only' if (k/2).is_integer() else '25-only'
                for h in [15,30,60,120]:
                    if t+h>=405:continue
                    radius=max(0.,min(float(max(hi[t+1:t+h+1])-level),float(level-min(lo[t+1:t+h+1]))));answer.append(dict(date=day,shift=float(shift),k=k,kind=kind,touch=t,horizon=h,prior_range=prior,radius=radius))
    return answer

def independent_pairs(a,b):
    cells={}
    for i,e in enumerate(a):
        if e['prior_range'] is not None:cells.setdefault((e['date'],e['touch']//15,int(e['prior_range']//5)),[[],[]])[0].append(i)
    for j,e in enumerate(b):
        if e['prior_range'] is not None:cells.setdefault((e['date'],e['touch']//15,int(e['prior_range']//5)),[[],[]])[1].append(j)
    result=[]
    for aa,bb in cells.values():
        while aa and bb:
            i,j=min(((i,j) for i in aa for j in bb),key=lambda ij:(abs(a[ij[0]]['touch']-b[ij[1]]['touch']),abs(a[ij[0]]['prior_range']-b[ij[1]]['prior_range']),a[ij[0]]['k'],b[ij[1]]['k'],ij[0],ij[1]));result.append((a[i],b[j]));aa.remove(i);bb.remove(j)
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--input',required=True,type=Path);a=p.parse_args();test=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Mechanics));assert test.wasSuccessful();assert hashlib.sha256(a.input.read_bytes()).hexdigest()==r.C['source_sha256'];ev=independent_events(a.input);saved=json.loads((r.P/'results/summary.json').read_text());assert hashlib.sha256(json.dumps(ev,sort_keys=True,separators=(',',':')).encode()).hexdigest()==saved['event_fingerprint'];checks=0
    def eq(a,b,tol=1e-9):
        nonlocal checks
        if a in ['',None]:assert b is None,(a,b)
        else:assert math.isclose(float(a),float(b),abs_tol=tol,rel_tol=1e-10),(a,b)
        checks+=1
    raw=list(csv.DictReader((r.P/'results/raw-summary.csv').open()));matched=list(csv.DictReader((r.P/'results/matched-summary.csv').open()))
    for q in raw:
        e=[x for x in ev if x['horizon']==int(q['horizon']) and x['shift']==float(q['shift']) and (q['kind']=='all' or x['kind']==q['kind'])];v=sorted(x['radius'] for x in e);n=len(v);median=(v[(n-1)//2]+v[n//2])/2 if n else None
        for k,val in {'events':n,'sessions':len({x['date'] for x in e}),'median_points':median,'mean_points':sum(v)/n if n else None,'q25_points':float(np.quantile(v,.25)) if n else None,'q75_points':float(np.quantile(v,.75)) if n else None,**{'both_'+str(d):len([v0 for v0 in v if v0>=d]) for d in [1,2,4,6,8,10,12]}}.items():eq(q[k],val)
    for q in matched:
        e=[x for x in ev if x['horizon']==int(q['horizon']) and (q['kind']=='all' or x['kind']==q['kind'])];real=[x for x in e if not x['shift']];control=[x for x in e if x['shift']==float(q['shift'])];pairs=independent_pairs(real,control);canonical=lambda pair:(pair[0]['date'],pair[0]['k'],pair[1]['k']);expected=r.match(real,control);assert sorted(map(canonical,pairs))==sorted(map(canonical,expected));n=len(pairs)
        med=lambda values:(lambda v:(v[(len(v)-1)//2]+v[len(v)//2])/2 if v else None)(sorted(values))
        for k,val in {'real_events':len(real),'control_events':len(control),'real_with_prior':sum(x['prior_range'] is not None for x in real),'control_with_prior':sum(x['prior_range'] is not None for x in control),'pairs':n,'paired_sessions':len({x['date'] for x,y in pairs}),'real_both8':sum(x['radius']>=8 for x,y in pairs),'control_both8':sum(y['radius']>=8 for x,y in pairs),'real_median_points':med([x['radius'] for x,y in pairs]),'control_median_points':med([y['radius'] for x,y in pairs]),'mean_pair_radius_difference':sum(x['radius']-y['radius'] for x,y in pairs)/n if n else None,'hit_difference_pp':100*sum(int(x['radius']>=8)-int(y['radius']>=8) for x,y in pairs)/n if n else None,'maximum_touch_time_difference':max((abs(x['touch']-y['touch']) for x,y in pairs),default=None),'maximum_prior_range_difference':max((abs(x['prior_range']-y['prior_range']) for x,y in pairs),default=None)}.items():eq(q[k],val)
        key=f"{q['horizon']}|{q['kind']}|{float(q['shift'])}"
        assert hashlib.sha256(json.dumps(expected,sort_keys=True,separators=(',',':')).encode()).hexdigest()==saved['pair_fingerprints'][key]
    old=json.loads((r.P/'earlier-reported-checks.json').read_text());baseline=0
    for q in old['round_all']:
        new=next(x for x in raw if x['horizon']==str(q['horizon']) and x['kind']=='all' and float(x['shift'])==0)
        for k in ['events','median_points','q25_points','q75_points']:eq(new[k],q[k],.00500001);baseline+=1
    for q in old['round_60_classes']:
        new=next(x for x in raw if x['horizon']=='60' and x['kind']==q['kind'] and float(x['shift'])==0)
        for k in ['events','median_points']:eq(new[k],q[k],.00500001);baseline+=1
        eq(100*float(new['both_8'])/float(new['events']),q['both8_pct'],.05000001);baseline+=1
    new=next(x for x in raw if x['horizon']=='60' and x['kind']=='all' and float(x['shift'])==12.5);eq(new['median_points'],old['pooled_control_60']['median_points']);eq(100*float(new['both_8'])/float(new['events']),old['pooled_control_60']['both8_pct'],.05000001);baseline+=2
    result={'passed':True,'mathematical_fixtures':test.testsRun,'independent_event_rows':len(ev),'event_fingerprint_match':True,'raw_summary_rows':len(raw),'matched_summary_rows':len(matched),'independent_numeric_checks':checks,'earlier_reported_aggregate_matches':baseline,'independent_matching_groups':len(matched),'source_sha256_unchanged':hashlib.sha256(a.input.read_bytes()).hexdigest()==r.C['source_sha256'],'limitations':'Independent event extraction and matching identities; all raw summary measures and selected matched counts/means recounted. Bootstrap intervals are not independently reimplemented, and tiny matched samples are inadequate for reliable inference. Original class-specific control matching and range-midpoint/recrossing calculations are not reproduced.'};(r.P/'results/verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result,indent=2))

if __name__=='__main__':main()
