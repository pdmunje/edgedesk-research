"""Rebuild descriptive weekly profiles from two hash-matched authorized exports."""
import argparse,csv,hashlib,json,statistics
from collections import defaultdict,Counter
from datetime import date,timedelta
from decimal import Decimal
from pathlib import Path
ROOT=Path(__file__).resolve().parent
CONFIG=json.loads((ROOT/'config.json').read_text())
FIELDS=['period','stage','prefix','n','week_green','week_red','week_doji','week_green_pct','week_mean_points','week_median_points','elapsed_mean_points','remaining_up','remaining_down','remaining_flat','remaining_up_pct','remaining_mean_points','remaining_median_points','remaining_mean_pct','remaining_median_pct','next_open_up','next_open_down','next_open_flat','next_open_up_pct','next_open_mean_points','next_open_median_points','next_open_mean_pct','next_open_median_pct','next_day_green','next_day_red','next_day_doji','event_fingerprint']
def color(o,c):return 'G' if c>o else 'R' if c<o else 'D'
def load(path,kind):
    if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=CONFIG[kind+'_sha256']:raise ValueError('Input fingerprint differs: '+kind)
    out=[]
    with Path(path).open(newline='',encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            d=date.fromisoformat(r['time']);v={k:Decimal(r[k]) for k in ['open','high','low','close']}
            if not all(x.is_finite() and x>0 for x in v.values()) or not(v['low']<=min(v['open'],v['close'])<=max(v['open'],v['close'])<=v['high']):raise ValueError('Invalid OHLC')
            if out and d<=out[-1]['date']:raise ValueError('Dates must be unique and ordered')
            out.append({'date':d,**v})
    return out

def group_and_match(daily,weekly):
    groups=defaultdict(list)
    for r in daily:groups[r['date']-timedelta(days=r['date'].weekday())].append(r)
    wm={r['date']-timedelta(days=r['date'].weekday()):r for r in weekly}
    if len(wm)!=len(weekly):raise ValueError('Duplicate calendar week in weekly export')
    if set(groups)!=set(wm):raise ValueError('Calendar week coverage differs')
    for key,rows in groups.items():
        agg={'open':rows[0]['open'],'high':max(x['high'] for x in rows),'low':min(x['low'] for x in rows),'close':rows[-1]['close']}
        if any(agg[k]!=wm[key][k] for k in agg):raise ValueError('Daily/weekly OHLC disagreement')
    return groups

def summary(period,k,prefix,events):
    n=len(events);wd=[];elapsed=[];remaining=[];rempct=[];nextopen=[];nextpct=[];wc=Counter();rc=Counter();nc=Counter();dc=Counter()
    for _,rs in events:
        o=rs[0]['open'];c=rs[-1]['close'];mark=rs[k-1]['close'];no=rs[k]['open']
        wd.append(c-o);elapsed.append(mark-o);remaining.append(c-mark);rempct.append(100*(c-mark)/mark);nextopen.append(c-no);nextpct.append(100*(c-no)/no)
        wc[color(o,c)]+=1;rc[color(mark,c)]+=1;nc[color(no,c)]+=1;dc[color(no,rs[k]['close'])]+=1
        assert c-o==(mark-o)+(c-mark)
    mean=lambda xs:float(sum(xs)/len(xs));med=lambda xs:float(statistics.median(xs))
    return dict(zip(FIELDS,[period,k,prefix,n,wc['G'],wc['R'],wc['D'],100*wc['G']/n,mean(wd),med(wd),mean(elapsed),rc['G'],rc['R'],rc['D'],100*rc['G']/n,mean(remaining),med(remaining),mean(rempct),med(rempct),nc['G'],nc['R'],nc['D'],100*nc['G']/n,mean(nextopen),med(nextopen),mean(nextpct),med(nextpct),dc['G'],dc['R'],dc['D'],hashlib.sha256('\n'.join(str(key) for key,_ in events).encode()).hexdigest()]))

def calculate(daily,weekly):
    groups=group_and_match(daily,weekly);complete=[(key,rs) for key,rs in sorted(groups.items()) if len(rs)==5]
    if any(r['date'].weekday()>4 for _,rs in complete for r in rs):raise ValueError('Unexpected weekend label')
    rows=[]
    for period,year in CONFIG['periods'].items():
        events=[(key,rs) for key,rs in complete if year is None or key.year>=year]
        for k in CONFIG['prefix_lengths']:
            rows.append(summary(period,k,'ALL',events));parts=defaultdict(list)
            for key,rs in events:parts[''.join(color(x['open'],x['close']) for x in rs[:k])].append((key,rs))
            for prefix,selected in sorted(parts.items()):rows.append(summary(period,k,prefix,selected))
    timing=[]
    for k in range(1,6):
        high=sum(next(i for i,x in enumerate(rs,1) if x['high']==max(y['high'] for y in rs))==k for _,rs in complete)
        low=sum(next(i for i,x in enumerate(rs,1) if x['low']==min(y['low'] for y in rs))==k for _,rs in complete)
        timing.append({'session':k,'n':len(complete),'first_week_high':high,'first_week_low':low,'high_pct':100*high/len(complete),'low_pct':100*low/len(complete)})
    audit={'daily_rows':len(daily),'weekly_rows':len(weekly),'daily_dates':[str(daily[0]['date']),str(daily[-1]['date'])],'weekly_labels':[str(weekly[0]['date']),str(weekly[-1]['date'])],'calendar_weeks':len(groups),'weekly_ohlc_matches':len(groups),'weekly_non_monday_labels':sum(r['date'].weekday()!=0 for r in weekly),'daily_rows_per_week':dict(sorted(Counter(map(len,groups.values())).items())),'exactly_five_row_weeks':len(complete),'other_row_count_weeks':len(groups)-len(complete),'first_complete_week':str(complete[0][0]),'last_complete_week':str(complete[-1][0]),'last_complete_session_date':str(complete[-1][1][-1]['date']),'week_green':sum(color(rs[0]['open'],rs[-1]['close'])=='G' for _,rs in complete),'week_red':sum(color(rs[0]['open'],rs[-1]['close'])=='R' for _,rs in complete),'week_doji':sum(color(rs[0]['open'],rs[-1]['close'])=='D' for _,rs in complete),'high_tied_weeks':sum(sum(r['high']==max(x['high'] for x in rs) for r in rs)>1 for _,rs in complete),'low_tied_weeks':sum(sum(r['low']==min(x['low'] for x in rs) for r in rs)>1 for _,rs in complete),'nonquarter_ohlc_rows':{name:sum(any(v[k]%Decimal('.25') for k in ['open','high','low','close']) for v in source) for name,source in [('daily',daily),('weekly',weekly)]},'period_weeks':{p:next(x['n'] for x in rows if x['period']==p and x['prefix']=='ALL') for p in CONFIG['periods']},'summary_rows':len(rows),'limitations':['Five rows is a retrospective source-count rule, not proof of full-length holiday sessions or live week eligibility.','Date-only session labels; exchange close and fill timing not verified.','All dates previously explored; overlapping periods are not new validation.']}
    return rows,timing,audit

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--daily',required=True);ap.add_argument('--weekly',required=True);ap.add_argument('--output',default=str(ROOT/'results'));args=ap.parse_args();out=Path(args.output);out.mkdir(exist_ok=True,parents=True)
    rows,timing,audit=calculate(load(args.daily,'daily'),load(args.weekly,'weekly'))
    for filename,data,fields in [('summary.csv',rows,FIELDS),('high-low-timing.csv',timing,list(timing[0]))]:
        with (out/filename).open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(data)
    (out/'audit.json').write_text(json.dumps(audit,indent=2)+'\n');print(json.dumps(audit,indent=2))
if __name__=='__main__':main()
