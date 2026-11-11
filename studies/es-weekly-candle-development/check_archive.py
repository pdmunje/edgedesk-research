"""Optional read-only comparison with an authorized original profile workbook."""
import argparse,csv,hashlib,json,math
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def main():
    from openpyxl import load_workbook
    ap=argparse.ArgumentParser();ap.add_argument('--workbook',required=True);a=ap.parse_args();p=Path(a.workbook);cfg=json.loads((ROOT/'config.json').read_text());assert hashlib.sha256(p.read_bytes()).hexdigest()==cfg['archive_sha256']
    current=list(csv.DictReader((ROOT/'results/summary.csv').open()));look={(int(r['stage']),r['prefix']):r for r in current if r['period']=='full'};w=load_workbook(p,read_only=True,data_only=True);data=list(w['Progressive Profiles'].iter_rows(values_only=True));headers=data[2];comparisons=[]
    for r in data[3:]:
        if int(r[0])>4:continue
        now=look[int(r[0]),r[1]];assert int(now['n'])==r[headers.index('N')]
        assert math.isclose(float(now['week_green_pct']),100*r[headers.index('Final Green %')],abs_tol=1e-9,rel_tol=1e-11)
        assert math.isclose(float(now['week_mean_points']),r[headers.index('Avg Week Change (pts)')],abs_tol=1e-9,rel_tol=1e-11)
        comparisons.append({'stage':r[0],'prefix':r[1],'count':r[2],'green_weeks':int(now['week_green']),'mean_week_points':float(now['week_mean_points']),'matched':True})
    timing=list(csv.DictReader((ROOT/'results/high-low-timing.csv').open()))
    for row,r in zip(timing,list(w['Dashboard'].iter_rows(values_only=True))[3:8]):
        assert math.isclose(float(row['high_pct']),r[9]*100,abs_tol=1e-9)
        assert math.isclose(float(row['low_pct']),r[10]*100,abs_tol=1e-9)
    result={'archived_prefix_rows_compared':len(comparisons),'fields_per_row':3,'all_matched':True,'high_low_timing_percentages_matched':10,'scope':'Counts, final green shares and mean whole-week change for every observed daily-color prefix of length 1-4. No claim to reproduce other workbook factors, exact five-day patterns or statistical inference.','comparisons':comparisons}
    assert result==json.loads((ROOT/'results/archive-reconciliation.json').read_text());print('82 prefix rows and ten high/low timing shares match the authorized archive.')
if __name__=='__main__':main()
