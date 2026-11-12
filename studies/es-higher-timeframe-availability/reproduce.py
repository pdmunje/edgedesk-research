"""Reproduce INVENTED availability and repeated-view examples, not market results."""
import csv,hashlib,json
from datetime import datetime,timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def stamp(s):
    d=datetime.fromisoformat(s)
    if d.tzinfo is None or d.utcoffset() is None:raise ValueError('Timestamp must include its UTC offset')
    return d

def metadata_reason(o):
    if o['mode']!='completed':return 'INCOMPATIBLE_MODE'
    if o.get('completion_ambiguous'):return 'AMBIGUOUS_COMPLETION'
    if o['completed_at'] is None:return 'MISSING_COMPLETION'
    if o['known_at'] is None:return 'MISSING_AVAILABILITY'
    start,end,known,until=(stamp(o[k]) for k in ['source_start','completed_at','known_at','valid_until'])
    if start>=end or known<end:return 'INVALID_TIME_ORDER'
    if until<=known:return 'INVALID_VALIDITY_WINDOW'
    return None

def select(observations,feature,decision,required_id=None):
    t=stamp(decision);ids=[(o['feature'],o['session'],o['observation_id']) for o in observations]
    if len(ids)!=len(set(ids)):raise ValueError('Duplicate source identity')
    chosen=[o for o in observations if o['feature']==feature and (required_id is None or o['observation_id']==required_id) and metadata_reason(o) is None and stamp(o['completed_at'])<=t and stamp(o['known_at'])<=t<stamp(o['valid_until'])]
    if not chosen:return {'selected_id':None,'status':'NO_AVAILABLE_OBSERVATION','value':None}
    latest=max((stamp(o['completed_at']),stamp(o['known_at'])) for o in chosen);chosen=[o for o in chosen if (stamp(o['completed_at']),stamp(o['known_at']))==latest]
    if len(chosen)!=1:return {'selected_id':None,'status':'AMBIGUOUS_LATEST','value':None}
    o=chosen[0]
    return {'selected_id':o['observation_id'],'status':'MISSING_VALUE' if o['value'] is None else 'VALID','value':o['value']}

def deduplicate(rows):
    kept={}
    for r in sorted(rows,key=lambda x:stamp(x['decision_at'])):kept.setdefault((r['session'],r['id_A'],r['id_B']),r)
    return list(kept.values())

def calculate(data):
    obs=data['observations'];decisions=[]
    for q in data['queries']:decisions.append({**q,**select(obs,q['feature'],q['decision_at'],q['required_id'])})
    exclusions=[{'feature':o['feature'],'observation_id':o['observation_id'],'reason':metadata_reason(o)} for o in obs if metadata_reason(o)]
    exclusions.sort(key=lambda r:(r['feature'],r['observation_id']))
    rep=data['repetition'];start=stamp(rep['start']);last=stamp(rep['last']);panels={}
    for name,times in [('one_view_per_pair',[start,last]),('sixty_views_then_one',[start+timedelta(minutes=i) for i in range(rep['repeat_minutes'])]+[last])]:
        rr=[]
        for t in times:
            a,b=[select(obs,f,t.isoformat()) for f in rep['features']]
            if a['status']!=b['status'] or a['status']!='VALID':raise ValueError('Both compared values must be available')
            rr.append({'session':rep['session'],'decision_at':t.isoformat(),'id_A':a['selected_id'],'id_B':b['selected_id'],'value_A':a['value'],'value_B':b['value']})
        unique=deduplicate(rr);panels[name]={'rows':rr,'unique':unique,'summary':{'panel':name,'view_rows':len(rr),'matching_view_rows':sum(r['value_A']==r['value_B'] for r in rr),'view_agreement_pct':100*sum(r['value_A']==r['value_B'] for r in rr)/len(rr),'distinct_A':len({r['id_A'] for r in rr}),'distinct_B':len({r['id_B'] for r in rr}),'distinct_pairs':len(unique),'matching_pairs':sum(r['value_A']==r['value_B'] for r in unique),'pair_agreement_pct':100*sum(r['value_A']==r['value_B'] for r in unique)/len(unique),'distinct_sessions':len({r['session'] for r in rr})}}
    return decisions,exclusions,panels

def main():
    config=json.loads((ROOT/'config.json').read_text());source=ROOT/'illustration.json';assert hashlib.sha256(source.read_bytes()).hexdigest()==config['input_sha256'];data=json.loads(source.read_text());decisions,excluded,panels=calculate(data);out=ROOT/'results';out.mkdir(exist_ok=True)
    serial=[{**r,'required_id':r['required_id'] or '', 'selected_id':r['selected_id'] or '', 'value':json.dumps(r['value'])} for r in decisions]
    for filename,rows in [('decision-checks.csv',serial),('exclusions.csv',excluded),('repetition-summary.csv',[v['summary'] for v in panels.values()])]:
        with (out/filename).open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    audit={'input_sha256':config['input_sha256'],'invented_observations':len(data['observations']),'invented_decision_checks':len(decisions),'metadata_exclusions':len(excluded),'repetition_panels':len(panels),'validity':'These exact known/expiry timestamps are invented input contracts, not an inferred ES session calendar.','not_tested':['Historical features or protected checkpoints','Actual feed/receipt latency or source completion schedules','Trading performance, similarity thresholds or statistical independence']};(out/'audit.json').write_text(json.dumps(audit,indent=2)+'\n');print(json.dumps(audit,indent=2))
if __name__=='__main__':main()
