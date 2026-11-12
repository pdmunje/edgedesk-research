"""Verify invented examples against explicit answers and independent arithmetic."""
import copy,csv,json
from datetime import datetime,timedelta
from fractions import Fraction
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def main():
    data=json.loads((ROOT/'illustration.json').read_text());saved=list(csv.DictReader((ROOT/'results/decision-checks.csv').open()));expected={
      'before':('H0','VALID',False),'at_completion':('H1','VALID',True),'after_completion':('H1','VALID',True),'no_previous':('', 'NO_AVAILABLE_OBSERVATION',None),
      'delayed_at_close':('','NO_AVAILABLE_OBSERVATION',None),'delayed_before_ready':('','NO_AVAILABLE_OBSERVATION',None),'delayed_ready':('L1','VALID',True),
      'missing_completion':('','NO_AVAILABLE_OBSERVATION',None),'ambiguous_completion':('','NO_AVAILABLE_OBSERVATION',None),'missing_value':('M1','MISSING_VALUE',None),
      'valid_numeric_zero':('Z1','VALID',0),'developing_rejected':('','NO_AVAILABLE_OBSERVATION',None),'missing_known_time':('','NO_AVAILABLE_OBSERVATION',None),
      'next_completion':('H2','VALID',False),'expired':('','NO_AVAILABLE_OBSERVATION',None),'target_before':('','NO_AVAILABLE_OBSERVATION',None),'valid_false':('H0','VALID',False),'equivalent_utc':('H1','VALID',True)}
    checks=0;assert len(saved)==len(expected)==18
    for r in saved:
        sid,status,value=expected[r['id']];assert r['selected_id']==sid;assert r['status']==status;assert json.loads(r['value'])==value and type(json.loads(r['value'])) is type(value);checks+=3
    excluded=list(csv.DictReader((ROOT/'results/exclusions.csv').open()));assert {(r['observation_id'],r['reason']) for r in excluded}=={('U1','MISSING_COMPLETION'),('A1','AMBIGUOUS_COMPLETION'),('D1','INCOMPATIBLE_MODE'),('K1','MISSING_AVAILABILITY')};checks+=4
    for r in csv.DictReader((ROOT/'results/repetition-summary.csv').open()):
        long=r['panel']=='sixty_views_then_one';n=61 if long else 2;m=60 if long else 1
        wanted={'view_rows':n,'matching_view_rows':m,'view_agreement_pct':float(100*Fraction(m,n)),'distinct_A':1,'distinct_B':2,'distinct_pairs':2,'matching_pairs':1,'pair_agreement_pct':50,'distinct_sessions':1}
        for k,v in wanted.items():assert abs(float(r[k])-v)<1e-10;checks+=1
    import reproduce as p
    decisions,_,panels=p.calculate(data);byid={r['id']:r for r in decisions};groups=[]
    assert byid['target_before']['selected_id'] is None and byid['at_completion']['selected_id']==byid['after_completion']['selected_id']=='H1';groups.append('Before, at and after exact completion retain correct source identities')
    assert byid['delayed_at_close']['selected_id'] is None and byid['delayed_before_ready']['selected_id'] is None and byid['delayed_ready']['selected_id']=='L1';groups.append('Delayed receipt blocks use until known time')
    mutated=copy.deepcopy(data);next(o for o in mutated['observations'] if o['observation_id']=='H2')['value']=True;changed,_,_=p.calculate(mutated)
    for old,new in zip(decisions,changed):
        if datetime.fromisoformat(old['decision_at'])<datetime.fromisoformat('2026-01-06T11:00:00-05:00'):assert old==new
    groups.append('Changing a later observation cannot alter earlier decisions')
    reversed_data=copy.deepcopy(data);reversed_data['observations'].reverse();assert p.calculate(reversed_data)==p.calculate(data);groups.append('Input order cannot select a future observation')
    q=copy.deepcopy(data['observations']);h0=next(o for o in q if o['observation_id']=='H0');h0['valid_until']='2026-01-06T11:00:00-05:00';next(o for o in q if o['observation_id']=='H1')['value']=None;r=p.select(q,'H','2026-01-06T10:00:00-05:00');assert r=={'selected_id':'H1','status':'MISSING_VALUE','value':None};groups.append('Latest missing value stays missing instead of falling back to an older value')
    assert type(byid['valid_false']['value']) is bool and byid['valid_false']['value'] is False and type(byid['valid_numeric_zero']['value']) is int and byid['valid_numeric_zero']['value']==0;groups.append('False and numeric zero remain valid, distinct values')
    assert byid['no_previous']['selected_id'] is None and byid['expired']['selected_id'] is None;groups.append('No previous observation and expiry boundary stay unavailable')
    assert byid['at_completion']['selected_id']==byid['equivalent_utc']['selected_id'];groups.append('Equivalent UTC and fixed-offset times select the same observation')
    q=copy.deepcopy(data['observations']);q.append(copy.deepcopy(q[0]))
    try:p.select(q,'H','2026-01-06T10:00:00-05:00')
    except ValueError:pass
    else:raise AssertionError('Duplicate identity accepted')
    groups.append('Duplicate source identities are rejected')
    q=copy.deepcopy(data['observations']);clone=copy.deepcopy(next(o for o in q if o['observation_id']=='H1'));clone['observation_id']='ambiguous-latest-other-id';q.append(clone);assert p.select(q,'H','2026-01-06T10:00:00-05:00')['status']=='AMBIGUOUS_LATEST';groups.append('Unresolved latest-source ties stay unavailable')
    for change in [{'known_at':'2026-01-06T09:59:59-05:00'},{'valid_until':'2026-01-06T10:00:00-05:00'}]:
        o=copy.deepcopy(next(o for o in data['observations'] if o['observation_id']=='H1'));o.update(change);assert p.metadata_reason(o) in ['INVALID_TIME_ORDER','INVALID_VALIDITY_WINDOW']
    try:p.stamp('2026-01-06T10:00:00')
    except ValueError:pass
    else:raise AssertionError('Offset-free time accepted')
    groups.append('Invalid time order, validity and offset-free timestamps fail explicitly')
    raw=panels['sixty_views_then_one']['rows'];unique=p.deduplicate(raw);assert len(unique)==2 and p.deduplicate(list(reversed(raw)))==unique and p.deduplicate(raw*4)==unique;groups.append('Repeated views and input order do not change earliest distinct-pair rows')
    same_values=copy.deepcopy(unique);same_values[1]['value_B']=True;assert len(p.deduplicate(same_values))==2;groups.append('Different observation identities remain separate when values happen to match')
    two_sessions=copy.deepcopy(unique)+[{**r,'session':'invented-session-B'} for r in unique];assert len(p.deduplicate(two_sessions))==4;groups.append('Session is retained in the distinct-pair key')
    assert byid['developing_rejected']['status']=='NO_AVAILABLE_OBSERVATION' and byid['missing_completion']['status']=='NO_AVAILABLE_OBSERVATION' and byid['ambiguous_completion']['status']=='NO_AVAILABLE_OBSERVATION';groups.append('Completed selector rejects developing or unknown-completion observations')
    result={'invented_decision_rows':18,'explicit_output_and_fraction_checks':checks,'property_groups':len(groups),'properties':groups,'inputs':'Only invented dated examples, no market observations.','limits':'Checks establish the stated teaching contract, not private-engine correctness, actual source timing, independent sample size or trading value.'};(ROOT/'results/verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
