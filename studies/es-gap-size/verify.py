"""Independent source parsing, volatility calculations and threshold recount."""
import argparse,csv,io,json,math,statistics,unittest,zipfile
from datetime import datetime,timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import gap_recount

NY=ZoneInfo('America/New_York')


def features(days):
    answer={};trs=[];clean=[];prior=None;average=None
    for date,d in sorted(days.items()):
        if d['fragment']:prior=None;continue
        width=d['high']-d['low']
        tr=width
        if prior and prior['close'] is not None and d['contract'] is not None and prior.get('close_contract',prior['contract'])==d['contract']:
            tr=max(width,abs(d['high']-prior['close']),abs(d['low']-prior['close']))
        trs.append(tr);clean.append(d['clean'])
        if len(trs)==14:average=math.fsum(trs)/14
        if len(trs)>14:average=(average*13+tr)/14
        answer[date]={'range':width,'atr':average,'last14_clean':len(clean)>=14 and all(clean[-14:])}
        prior=d
    return answer


def minute_rows(source):
    days={}
    with zipfile.ZipFile(source) as z:
        name=[n for n in z.namelist() if n.lower().endswith('.csv')][0]
        with z.open(name) as stream:
            for r in csv.DictReader(io.TextIOWrapper(stream,encoding='utf-8-sig')):
                t=datetime.fromisoformat(r['timestamp_utc'].replace('Z','+00:00'));local=t.astimezone(NY)
                clock=(local.hour,local.minute)
                d=days.setdefault(r['session_date'],{'high':-math.inf,'low':math.inf,'close':None,'contract':r['underlying_contract'],
                     'count':0,'contracts':set(),'bad':False,'entry_date':None,'fragment':False})
                d['high']=max(d['high'],float(r['high']));d['low']=min(d['low'],float(r['low']));d['count']+=1
                d['contracts'].add(r['underlying_contract']);d['bad'] |= r['data_condition']=='degraded' or r['roll_transition'].lower()=='true'
                if clock==(18,0):d['entry_date']=local.date();d['contract']=r['underlying_contract']
                if clock==(16,59):d['close']=float(r['close']);d['close_contract']=r['underlying_contract']
    for i,(date,d) in enumerate(sorted(days.items())):
        d['fragment']=i==0 and d['entry_date'] is None
        d['clean']=d['count']==1380 and len(d['contracts'])==1 and not d['bad']
        d['contract']=next(iter(d['contracts'])) if len(d['contracts'])==1 else None
    f=features(days);rows=[]
    for r in gap_recount.recount(source):
        if not r['window_quality']:continue
        entry_date=days[r['date']]['entry_date']
        required=entry_date-timedelta(days=2 if entry_date.weekday()==6 else 0)
        q=f.get(required.isoformat(),{})
        rows.append({**r,'gap_range':r['abs_gap']/q['range'] if q.get('range') else None,
                     'gap_atr':r['abs_gap']/q['atr'] if q.get('atr') else None,
                     'last14_clean':q.get('last14_clean',False)})
    return rows


def history_rows(source):
    groups={}
    with source.open(encoding='utf-8-sig',newline='') as stream:
        for r in csv.DictReader(stream):
            r={**r,'start':datetime.fromisoformat(r['time']),'end':datetime.fromisoformat(r['end_time']),
               'eligible':r['eligible'].lower()=='true','observed':int(r['observed_minutes']),
               **{k:float(r[k]) for k in ['open','high','low','close']}}
            g=groups.setdefault(r['trade_date'],{});assert r['slot_id'] not in g;g[r['slot_id']]=r
    expected={'T01':120,'T02':240,'T03':120,'T04':60,'T05':180,'T06':150,'T07':60,'T08':60,'T09':90,'T10':120,'T11':90,'T12':30,'T13':60}
    segment=lambda r:r['source']+'|'+(r['roll_segments'] or 'nan')
    days={};closes={}
    for date,g in sorted(groups.items()):
        a=g.get('T01');b=g.get('T13')
        if b and b['end'].astimezone(NY).strftime('%H:%M')=='17:00':closes[b['end'].astimezone(NY).date()]=(date,b)
        known_label=lambda r:segment(r) if r['source'] and r['roll_segments'] else None
        labels={known_label(r) for r in g.values()}
        days[date]={'high':max(r['high'] for r in g.values()),'low':min(r['low'] for r in g.values()),
                    'close':b['close'] if b else None,'contract':next(iter(labels)) if len(labels)==1 else None,
                    'close_contract':known_label(b) if b else None,'fragment':a is None,
                    'clean':set(g)==set(expected) and all(r['eligible'] for r in g.values()) and sum(r['observed'] for r in g.values())>=.95*1380}
    f=features(days);rows=[]
    for date,g in sorted(groups.items()):
        if set(g)!=set(expected) or not all(r['eligible'] for r in g.values()):continue
        on=[g[f'T{i:02}'] for i in range(1,8)];rth=[g[f'T{i:02}'] for i in range(8,14)]
        if sum(r['observed'] for r in on)<.95*930 or sum(r['observed'] for r in rth)<.95*450:continue
        a=on[0];end=rth[0];local=a['start'].astimezone(NY)
        ordered=[g[k] for k in sorted(g)]
        if local.strftime('%H:%M')!='18:00' or end['start'].astimezone(NY).strftime('%H:%M')!='09:30' or end['start'].astimezone(NY).date().isoformat()!=date or end['start']-a['start']!=timedelta(minutes=930):continue
        if any(r['end']-r['start']!=timedelta(minutes=expected[r['slot_id']]) for r in ordered):continue
        if any(left['end']!=right['start'] for left,right in zip(ordered,ordered[1:])):continue
        required=local.date()-timedelta(days=2 if local.weekday()==6 else 0)
        prior=closes.get(required)
        if prior is None:continue
        prior_date,b=prior
        if not b['eligible'] or any(segment(r)!=segment(a) for r in [b,*on,end]):continue
        gap=a['open']-b['close'];direction=-1 if gap>0 else 1
        touched=any(r['low']<=b['close'] if direction==-1 else r['high']>=b['close'] for r in on) if gap else False
        gross=min(abs(gap),direction*((b['close'] if touched else end['open'])-a['open'])) if gap else None
        q=f.get(prior_date,{})
        rows.append({'date':date,'abs_gap':abs(gap),'zero':gap==0,'touch':touched,'gross_points':gross,
                     'gap_range':abs(gap)/q['range'] if q.get('range') else None,
                     'gap_atr':abs(gap)/q['atr'] if q.get('atr') else None,'last14_clean':q.get('last14_clean',False)})
    return rows


def stats(values):
    if not values:return {'events':0}
    return {'events':len(values),'mean':math.fsum(values)/len(values),'median':statistics.median(values),'sum':math.fsum(values),
            'positive_events':sum(v>0 for v in values),'flat_events':sum(v==0 for v in values),
            'positive_pct':100*sum(v>0 for v in values)/len(values),'minimum':min(values),'maximum':max(values)}


class MadeUpChecks(unittest.TestCase):
    def day(self,high=110,low=100,close=105,contract='A',fragment=False):
        return {'high':high,'low':low,'close':close,'contract':contract,'fragment':fragment,'clean':True}

    def test_true_range_includes_gap_from_comparable_close(self):
        days={str(i):self.day() for i in range(10,24)}
        days['10']=self.day(close=90)
        self.assertEqual(features(days)['23']['atr'],(13*10+20)/14)

    def test_contract_change_uses_own_range_not_roll_price_jump(self):
        days={str(i):self.day(contract='B') for i in range(10,24)};days['10']=self.day(close=10,contract='A')
        self.assertEqual(features(days)['23']['atr'],10)

    def test_seed_requires_fourteen_observed_sessions(self):
        days={str(i):self.day() for i in range(10,24)};f=features(days)
        self.assertIsNone(f['22']['atr']);self.assertEqual(f['23']['atr'],10)

    def test_initial_fragment_is_not_part_of_seed(self):
        days={str(i):self.day() for i in range(10,24)};days['09']=self.day(high=1000,fragment=True)
        self.assertEqual(features(days)['23']['atr'],10)

    def test_recursive_update_uses_previous_value(self):
        days={str(i):self.day() for i in range(10,24)};days['24']=self.day(high=120)
        self.assertEqual(features(days)['24']['atr'],(13*10+20)/14)

    def test_previous_closing_contract_must_match_current_range(self):
        days={str(i):self.day() for i in range(10,24)}
        days['10']={**self.day(close=90),'close_contract':'B'}
        self.assertEqual(features(days)['23']['atr'],10)

    def test_missing_labels_use_own_ranges_in_both_implementations(self):
        import pandas as pd
        from reproduce import scales
        days={str(i):{**self.day(close=90,contract=None),'close_contract':None} for i in range(10,24)}
        frame=pd.DataFrame([{**d,'date':date,'end':date} for date,d in days.items()]).set_index('date')
        self.assertEqual(features(days)['23']['atr'],10)
        self.assertEqual(scales(frame)['23']['atr14'],10)

    def test_adding_future_session_does_not_change_past_features(self):
        days={str(i):self.day() for i in range(10,24)};before=features(days)
        days['24']=self.day(high=10000)
        self.assertEqual(features(days)['23'],before['23'])

    def test_zero_is_in_frequency_denominator_not_trade_numerator(self):
        import pandas as pd
        from reproduce import threshold
        f=pd.DataFrame({'date':['2026-01-05','2026-01-06'],'abs_gap':[0.,2.],'zero':[True,False],'touch':[False,True],'gross_points':[None,2.]})
        r=threshold(f,'abs_gap',1.)
        self.assertEqual(r['eligible_sessions_including_zero'],2);self.assertEqual(r['selected_nonzero_events'],1)
        self.assertEqual(r['frequency_pct'],50);self.assertEqual(r['touch_pct'],100)

    def test_unavailable_scale_does_not_enter_its_frequency_denominator(self):
        import pandas as pd
        from reproduce import threshold
        f=pd.DataFrame({'date':['2026-01-05','2026-01-06'],'gap_atr':[None,.1],'zero':[False,False],'touch':[False,True],'gross_points':[0.,2.]})
        self.assertEqual(threshold(f,'gap_atr',.05)['eligible_sessions_including_zero'],1)

    def test_production_scale_matches_made_up_recursive_path(self):
        import pandas as pd
        from reproduce import scales
        days={str(i):self.day() for i in range(10,24)};days['24']=self.day(high=120)
        frame=pd.DataFrame([{**d,'date':date,'end':date} for date,d in days.items()]).set_index('date')
        a=scales(frame);b=features(days)
        for date in days:self.assertEqual(a[date]['atr14'],b[date]['atr'])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,required=True);p.add_argument('--history-input',type=Path,required=True)
    p.add_argument('--summary',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    tests=unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(MadeUpChecks))
    if not tests.wasSuccessful():raise AssertionError('Made-up tests failed.')
    minute=minute_rows(args.input);history=history_rows(args.history_input)
    source=json.loads(args.summary.read_text());matches=0
    def equal(a,b):
        nonlocal matches
        if a is None or b is None:assert a is b,(a,b)
        else:assert math.isclose(a,b,rel_tol=1e-12,abs_tol=1e-9),(a,b)
        matches+=1
    for name,rows in [('minute',minute),('history',history),('minute_last14_complete_unflagged',[r for r in minute if r['last14_clean']])]:
        for metric,col in [('points','abs_gap'),('prior_range_fraction','gap_range'),('atr14_fraction','gap_atr')]:
            eligible=[r for r in rows if r[col] is not None]
            for expected in source[name][metric]:
                selected=[r for r in eligible if not r['zero'] and r[col]>=expected['threshold']]
                n=len(selected);denom=len(eligible);touches=sum(r['touch'] for r in selected)
                equal(denom,expected['eligible_sessions_including_zero']);equal(n,expected['selected_nonzero_events'])
                equal(100*n/denom if denom else None,expected['frequency_pct']);equal(touches,expected['touch_events'])
                equal(100*touches/n if n else None,expected['touch_pct'])
                for key,value in stats([r['gross_points'] for r in selected]).items():equal(value,expected['gross_points'][key])
                for key,value in stats([r['gross_points']-1 for r in selected]).items():equal(value,expected['net_one_point'][key])
    a={r['date']:r for r in minute};b={r['date']:r for r in history};shared=set(a)&set(b)
    equal(len(shared),source['overlap']['shared_sessions_including_zero'])
    common=[d for d in shared if not a[d]['zero'] and not b[d]['zero']]
    equal(len(common),source['overlap']['shared_nonzero_events'])
    equal(sum(abs(a[d]['abs_gap']-b[d]['abs_gap'])>1e-9 for d in common),source['overlap']['gap_disagreement_events'])
    equal(sum(a[d]['touch']!=b[d]['touch'] for d in common),source['overlap']['touch_disagreement_events'])
    equal(max(abs(a[d]['gross_points']-b[d]['gross_points']) for d in common),source['overlap']['max_gross_points_difference'])
    periods=[('minute_earlier_year',minute,'2024-08-29','2025-08-28'),('minute_later_year',minute,'2025-08-29','2026-08-28'),
             ('history_2017_2020',history,'2017-01-01','2020-12-31'),('history_2021_2023',history,'2021-01-01','2023-12-31'),
             ('history_2024_oct2026',history,'2024-01-01','2026-10-06')]
    for label,rows,start,end in periods:
        eligible=[r for r in rows if start<=r['date']<=end]
        selected=[r for r in eligible if not r['zero'] and r['abs_gap']>=2]
        expected=source['period_checks_two_point_threshold'][label]
        equal(len(eligible),expected['eligible_sessions_including_zero']);equal(len(selected),expected['selected_nonzero_events'])
        equal(sum(r['touch'] for r in selected),expected['touch_events'])
        equal(100*len(selected)/len(eligible),expected['frequency_pct'])
        equal(100*sum(r['touch'] for r in selected)/len(selected),expected['touch_pct'])
        for name,values in [('gross_points',[r['gross_points'] for r in selected]),('net_one_point',[r['gross_points']-1 for r in selected])]:
            for key,value in stats(values).items():equal(value,expected[name][key])
    result={'passed':True,'checked_date':'2026-10-15','independent_numeric_matches':matches,'made_up_tests_passed':tests.testsRun,
            'minute_eligible_sessions':len(minute),'historical_eligible_sessions':len(history),'shared_nonzero_events':len(common),
            'source_sha256':source['source_sha256'],
            'scope':'Separate CSV/date/path parsing, Wilder volatility and threshold/count arithmetic. Mean intervals and vendor prices are not independently audited.',
            'python':'3.12.14','numpy':'2.3.5','pandas':'3.0.1','tzdata':'2026.5'}
    args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result,indent=2))


if __name__=='__main__':main()
