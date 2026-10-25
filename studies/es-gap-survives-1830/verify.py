"""Independent CSV/date selection, price-path arithmetic and invented mechanics tests."""
import argparse,csv,io,json,math,statistics,unittest,zipfile
from datetime import datetime,timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import pandas as pd
import reproduce as subject

NY=ZoneInfo('America/New_York')

def scan(bars,entry,target,direction,exit_price,distance=None):
    reward=abs(target-entry);stop=entry-direction*distance if distance is not None else None
    for b in bars:
        opened,high,low=b[1:4]
        if stop is not None and ((direction==1 and opened<stop) or (direction==-1 and opened>stop)):
            return direction*(opened-entry),'stop_gap',0
        if stop is not None and ((direction==1 and opened>=target) or (direction==-1 and opened<=target)):
            return reward,'target',0
        ht=high>=target if direction==1 else low<=target
        hs=(low<=stop if direction==1 else high>=stop) if stop is not None else False
        if hs:return -distance,'stop',int(ht)
        if ht:return reward,'target',0
    return min(reward,direction*(exit_price-entry)),'time',0

def independent(source):
    sessions={};closes={};prev=None;source_rows=0
    with zipfile.ZipFile(source) as z:
        names=[n for n in z.namelist() if n.lower().endswith('.csv')];assert len(names)==1
        for r in csv.DictReader(io.TextIOWrapper(z.open(names[0]),encoding='utf-8-sig')):
            source_rows+=1;t=datetime.fromisoformat(r['timestamp_utc'].replace('Z','+00:00'));et=t.astimezone(NY)
            assert prev is None or t>prev;prev=t;assert r['is_complete'].lower()=='true'
            b=(t,float(r['open']),float(r['high']),float(r['low']),float(r['close']),r['underlying_contract'],r['data_condition']=='degraded' or r['roll_transition'].lower()=='true')
            assert all(math.isfinite(x) and x>0 for x in b[1:5]) and b[3]<=min(b[1],b[4])<=max(b[1],b[4])<=b[2]
            g=sessions.setdefault(r['session_date'],{'bars':[],'entry':None});g['bars'].append(b)
            if (et.hour,et.minute)==(18,0):assert g['entry'] is None;g['entry']=b
            if (et.hour,et.minute)==(16,59):assert et.date() not in closes;closes[et.date()]=b
    ex=dict.fromkeys(['missing_required_close','target_contract_change','opening_or_1830_boundary_unusable','zero_initial_gap','touched_before_1830','crossed_at_1830_open'],0)
    candidates=0;signals=[]
    def hits(bars,target,d):return [i for i,b in enumerate(bars) if (b[2]>=target if d==1 else b[3]<=target)]
    for day,g in sorted(sessions.items()):
        a=g['entry']
        if a is None:continue
        candidates+=1;start=a[0];et=start.astimezone(NY);t30=start+timedelta(minutes=30);t930=start+timedelta(minutes=930)
        targetbar=closes.get(et.date()-timedelta(days=2 if et.weekday()==6 else 0))
        if targetbar is None:ex['missing_required_close']+=1;continue
        if targetbar[5]!=a[5]:ex['target_contract_change']+=1;continue
        opening=[b for b in g['bars'] if start<=b[0]<t30];e30=next((b for b in g['bars'] if b[0]==t30),None)
        if len(opening)!=30 or e30 is None or targetbar[6] or any(b[6] or b[5]!=a[5] for b in opening) or e30[5]!=a[5]:
            ex['opening_or_1830_boundary_unusable']+=1;continue
        target=targetbar[4];gap=a[1]-target
        if gap==0:ex['zero_initial_gap']+=1;continue
        direction=1 if gap<0 else -1
        if hits(opening,target,direction):ex['touched_before_1830']+=1;continue
        entry=e30[1];residual=direction*(target-entry)
        if residual<=0:ex['crossed_at_1830_open']+=1;continue
        later=[b for b in g['bars'] if t30<=b[0]<t930];end=next((b for b in g['bars'] if b[0]==t930),None)
        good=(len(later)==900 and all(not b[6] and b[5]==a[5] for b in later) and end is not None and not end[6] and end[5]==a[5])
        full=[b for b in g['bars'] if t30<=b[0]<start+timedelta(minutes=1380)]
        fullgood=len(full)==1350 and all(not b[6] and b[5]==a[5] for b in full)
        r={'date':day,'initial_gap':gap,'residual':residual,'movement':'toward' if residual<abs(gap) else 'away' if residual>abs(gap) else 'unchanged',
           'overnight_quality':good,'full_day_quality':fullgood,'first_minute_touch':False}
        if good:
            h=hits(later,target,direction);first=h[0] if h else None;r.update(touch=bool(h),first_touch=first,first_minute_touch=first==0)
            for name,distance in [('no_stop',None),('stop_1_distance',max(residual,1.)),('stop_2_distance',max(residual*2,1.))]:
                r[name],r[name+'_outcome'],r[name+'_ties']=scan(later,entry,target,direction,end[1],distance)
            r['delayed_one_minute']=None
            if first!=0 and direction*(target-later[1][1])>0:r['delayed_one_minute']=scan(later[1:],later[1][1],target,direction,end[1])[0]
        if fullgood:r['full_day_touch']=bool(hits(full,target,direction));r['hold_to_1700']=scan(full,entry,target,direction,full[-1][4])[0]
        signals.append(r)
    return signals,ex,candidates,source_rows

def stats(values):
    if not values:return {'events':0}
    return {'events':len(values),'mean':statistics.mean(values),'median':statistics.median(values),'sum':sum(values),
            'positive_events':sum(x>0 for x in values),'flat_events':sum(x==0 for x in values),'positive_pct':100*sum(x>0 for x in values)/len(values),'minimum':min(values),'maximum':max(values)}

class MadeUpTests(unittest.TestCase):
    def run_subject(self,records,entry=100,target=110,d=1,end=99,stop=None):return subject.simulate(pd.DataFrame(records,columns=['open','high','low','close']),entry,target,d,end,stop)
    def test_target(self):self.assertEqual(self.run_subject([[100,111,99,105]])[:2],(10.,'target'))
    def test_short_target(self):self.assertEqual(self.run_subject([[100,101,89,95]],target=90,d=-1)[:2],(10.,'target'))
    def test_time(self):self.assertEqual(self.run_subject([[100,101,99,100]],end=98)[:2],(-2.,'time'))
    def test_stop(self):self.assertEqual(self.run_subject([[100,105,94,95]],stop=5)[:2],(-5.,'stop'))
    def test_both_in_minute_stop_first(self):self.assertEqual(self.run_subject([[100,111,94,100]],stop=5),(-5.,'stop',1))
    def test_gap_beyond_long_stop(self):self.assertEqual(self.run_subject([[93,94,92,93]],stop=5)[:2],(-7.,'stop_gap'))
    def test_gap_beyond_short_stop(self):self.assertEqual(self.run_subject([[107,108,106,107]],target=90,d=-1,stop=5)[:2],(-7.,'stop_gap'))
    def test_open_beyond_target_known_before_low(self):self.assertEqual(self.run_subject([[112,113,94,100]],stop=5)[:2],(10.,'target'))
    def test_target_credit_is_capped(self):self.assertEqual(self.run_subject([[100,101,99,100]],end=115)[0],10.)
    def test_exact_stop_open(self):self.assertEqual(self.run_subject([[95,96,94,95]],stop=5)[:2],(-5.,'stop'))
    def test_forward_bars_do_not_change_signal_selection(self):
        # Complete invented first half-hour, same contract; a later flag only removes measurable outcomes.
        start=pd.Timestamp('2026-01-05 18:00',tz='America/New_York').tz_convert('UTC')
        dates=[start-pd.Timedelta(minutes=61)]+[start+pd.Timedelta(minutes=i) for i in range(1380)]
        raw=pd.DataFrame({'timestamp_utc':dates,'session_date':['2026-01-05']+['2026-01-06']*1380,
                          'open':[100]+[101]*1380,'high':[100]+[102]*1380,'low':[100]+[101]*1380,'close':[100]+[101]*1380,
                          'underlying_contract':'ESH6','data_condition':'ok','bad':False})
        raw['date']=raw.timestamp_utc.dt.tz_convert('America/New_York').dt.strftime('%Y-%m-%d');raw['clock']=raw.timestamp_utc.dt.tz_convert('America/New_York').dt.hour*60+raw.timestamp_utc.dt.tz_convert('America/New_York').dt.minute
        a=subject.extract(raw)[0];raw.loc[100,'bad']=True;b=subject.extract(raw)[0]
        self.assertEqual(len(a),1);self.assertEqual(len(b),1);self.assertTrue(a[0]['overnight_quality']);self.assertFalse(b[0]['overnight_quality'])

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',required=True,type=Path);p.add_argument('--summary',required=True,type=Path);p.add_argument('--original-events',type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args()
    tests=unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(MadeUpTests));assert tests.wasSuccessful()
    saved=json.loads(a.summary.read_text());before=subject.fingerprint(a.input);assert before==saved['source_sha256']
    signals,ex,candidates,source_rows=independent(a.input);original,legacy,_=subject.extract(subject.load(a.input));assert signals==original
    assert ex==saved['checks']['sequential_signal_exclusions'] and candidates==saved['checks']['evening_candidates'] and source_rows==saved['checks']['source_rows']
    rows=[r for r in signals if r['overnight_quality']];matches=0
    def equal(value,want):
        nonlocal matches
        assert math.isclose(value,want,rel_tol=1e-12,abs_tol=1e-10),(value,want);matches+=1
    def check_stats(values,want):
        for k,v in stats(values).items():equal(v,want[k])
    def check_group(chosen,want):
        equal(len(chosen),want['events']);equal(sum(r['touch'] for r in chosen),want['touches']);equal(100*sum(r['touch'] for r in chosen)/len(chosen),want['touch_pct'])
        equal(sum(r['first_minute_touch'] for r in chosen),want['first_minute_touches'])
        equal(statistics.median([abs(r['initial_gap']) for r in chosen]),want['initial_gap_median']);equal(statistics.median([r['residual'] for r in chosen]),want['residual_gap_median'])
        for name in ['no_stop','stop_1_distance','stop_2_distance']:
            x=want['rules'][name];check_stats([r[name] for r in chosen],x['gross']);check_stats([r[name]-1 for r in chosen],x['net_one_point'])
            for out,count in x['outcomes'].items():equal(sum(r[name+'_outcome']==out for r in chosen),count)
            equal(sum(r[name+'_ties'] for r in chosen),x['ambiguous_minutes_stop_first'])
        for flag,key in [(True,'no_stop_touch_group'),(False,'no_stop_no_touch_group')]:check_stats([r['no_stop'] for r in chosen if r['touch']==flag],want[key])
    filters={'toward':lambda r:r['movement']=='toward','away':lambda r:r['movement']=='away','unchanged':lambda r:r['movement']=='unchanged',
             'sunday':lambda r:datetime.fromisoformat(r['date']).weekday()==0,'other_weekdays':lambda r:datetime.fromisoformat(r['date']).weekday()!=0,
             'first_year':lambda r:r['date']<'2025-08-29','second_year':lambda r:r['date']>='2025-08-29',
             'away_first_year':lambda r:r['movement']=='away' and r['date']<'2025-08-29',
             'away_second_year':lambda r:r['movement']=='away' and r['date']>='2025-08-29'}
    check_group(rows,saved['main'])
    for name,test in filters.items():check_group([r for r in rows if test(r)],saved['groups'][name]);equal(sum(test(r) for r in signals),saved['signal_groups_before_outcome_quality'][name])
    for cost,want in saved['cost_scenarios'].items():check_stats([r['no_stop']-float(cost) for r in rows],want)
    full=[r for r in signals if r['full_day_quality']];equal(len(full),saved['full_day']['events']);equal(sum(r['full_day_touch'] for r in full),saved['full_day']['touches_before_1700'])
    check_stats([r['hold_to_1700']-1 for r in full],saved['full_day']['net_one_point']);check_stats([r['no_stop']-1 for r in full if r['overnight_quality']],saved['full_day']['same_events_0930_net'])
    check_stats([r['delayed_one_minute']-1 for r in rows if r['delayed_one_minute'] is not None],saved['delayed_to_1831']['net_one_point'])
    audit={'performed':False}
    if a.original_events:
        with a.original_events.open(encoding='utf-8-sig',newline='') as f:old={r['session_date']:r for r in csv.DictReader(f)}
        assert set(old)==set(r['date'] for r in legacy);count=0
        for r in legacy:
            prior=old[r['date']]
            for k,oldk in [('initial_gap','gap'),('residual','residual_gap_abs'),('no_stop','pnl_1830_0930'),('hold_to_1700','pnl_1830_to_17'),('stop_1_distance','pnl_stop1r'),('stop_2_distance','pnl_stop2r')]:
                assert math.isclose(r[k],float(prior[oldk]),abs_tol=1e-10);count+=1
            t=prior['touch_min_after_1830'];assert r['first_touch']==(int(float(t)) if t else None);count+=1
            assert r['touch']==(prior['filled_overnight'].lower()=='true');count+=1
        audit={'performed':True,'saved_events':len(old),'event_value_matches':count,'shared_with_current_measurable_events':len(set(old)&set(r['date'] for r in rows)),
               'note':'Original saved 122-event gaps, residual distances, first touches, touch flags and all four gross trade outcomes freshly reproduced. Original future-data selection is not used for current signals.'}
    assert subject.fingerprint(a.input)==before
    out={'passed':True,'checked_date':'2026-10-16','source_sha256':before,'independent_numeric_matches':matches,'made_up_tests_passed':tests.testsRun,
         'signals_selected':len(signals),'measurable_overnight_events':len(rows),'original_event_audit':audit,
         'scope':'Separate standard-library CSV/time parser and stop/target arithmetic matched every current signal and available outcome. Aggregate statistics checked; weekly resampling range is not independently recomputed; no vendor/order audit.'}
    a.output.write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8');print(json.dumps(out,indent=2))

if __name__=='__main__':main()
