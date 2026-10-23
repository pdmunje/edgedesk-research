"""Independent CSV/date/path recount, plus invented target/entry mechanics tests."""
import argparse
import csv
from datetime import datetime,timedelta
import io
import json
import math
from pathlib import Path
import statistics
import tempfile
import unittest
import zipfile
from zoneinfo import ZoneInfo

NY=ZoneInfo('America/New_York')
FIXTURES=None


def path_result(bars,entry,target,direction,time_exit):
    hits=[i for i,b in enumerate(bars) if (b['high']>=target if direction==1 else b['low']<=target)]
    touched=bool(hits)
    gross=direction*((target if touched else time_exit)-entry)
    return touched,hits[0] if hits else None,min(direction*(target-entry),gross)


def recount(source):
    sessions={};closes={};previous=None
    with zipfile.ZipFile(source) as z:
        names=[n for n in z.namelist() if n.lower().endswith('.csv')];assert len(names)==1
        with z.open(names[0]) as handle:
            for row in csv.DictReader(io.TextIOWrapper(handle,encoding='utf-8-sig')):
                t=datetime.fromisoformat(row['timestamp_utc'].replace('Z','+00:00'))
                assert previous is None or t>previous;previous=t
                assert row['is_complete'].lower()=='true'
                local=t.astimezone(NY);clock=(local.hour,local.minute)
                s=sessions.setdefault(row['session_date'],{'on':[],'entry':None,'exit':None,'rth_count':0,'degraded':False})
                s['degraded'] |= row['data_condition']=='degraded'
                if (9,30)<=clock<=(16,59):s['rth_count']+=1
                if clock>=(18,0) or clock<=(9,30) or clock==(16,59):
                    b={'time':t,'local':local,'open':float(row['open']),'high':float(row['high']),
                       'low':float(row['low']),'close':float(row['close']),'contract':row['underlying_contract'],
                       'bad':row['data_condition']=='degraded' or row['roll_transition'].lower()=='true'}
                    assert all(math.isfinite(b[k]) and b[k]>0 for k in ['open','high','low','close'])
                    assert b['low']<=min(b['open'],b['close'])<=max(b['open'],b['close'])<=b['high']
                    if clock>=(18,0) or clock<(9,30):s['on'].append(b)
                    if clock==(18,0):assert s['entry'] is None;s['entry']=b
                    if clock==(9,30):assert s['exit'] is None;s['exit']=b
                    if clock==(16,59):assert local.date() not in closes;closes[local.date()]=b
    ordered=sorted(sessions);rows=[]
    for i,day in enumerate(ordered):
        s=sessions[day];a=s['entry'];end=s['exit']
        if a is None:continue
        assert a['local'].weekday() in [0,1,2,3,6]
        required=a['local'].date()-timedelta(days=2 if a['local'].weekday()==6 else 0)
        t=closes.get(required)
        if t is None or t['contract']!=a['contract'] or end is None:continue
        if end['time']-a['time']!=timedelta(minutes=930) or end['contract']!=a['contract']:continue
        assert end['local'].date().isoformat()==day and t['time']+timedelta(minutes=1)<=a['time']
        bars=[b for b in s['on'] if a['time']<=b['time']<end['time']]
        same=all(b['contract']==a['contract'] for b in bars)
        window=len(bars)==930 and same and not t['bad'] and not end['bad'] and not any(b['bad'] for b in bars)
        prior=sessions[ordered[i-1]] if i else {'degraded':False}
        legacy=len(bars)==930 and s['rth_count']==450 and same and not s['degraded'] and not prior['degraded']
        gap=a['open']-t['close']
        rec={'date':day,'abs_gap':abs(gap),'zero':gap==0,'window_quality':window,'legacy_quality':legacy}
        if gap!=0:
            direction=1 if gap<0 else -1
            touch,first,gross=path_result(bars,a['open'],t['close'],direction,end['open'])
            delay=None
            later=[b for b in bars if b['time']>=a['time']+timedelta(minutes=1)]
            if first!=0 and later and later[0]['time']==a['time']+timedelta(minutes=1) and direction*(t['close']-later[0]['open'])>0:
                _,_,delay=path_result(later,later[0]['open'],t['close'],direction,end['open'])
            rec.update({'touch':touch,'entry_minute_touch':first==0,'gross_points':gross,'delayed_gross':delay,
                        'capped_time_exit':not touch and direction*(end['open']-a['open'])>abs(gap)})
        rows.append(rec)
    return rows


def stats(x):
    return {'events':len(x),'mean':math.fsum(x)/len(x),'median':statistics.median(x),'sum':math.fsum(x),
            'positive_events':sum(v>0 for v in x),'flat_events':sum(v==0 for v in x),
            'positive_pct':100*sum(v>0 for v in x)/len(x),'minimum':min(x),'maximum':max(x)}

