"""Run a matched-budget comparison; labels are loaded only by this external evaluator."""
import argparse,json,csv
from pathlib import Path
from slac_assistant.data import ROOT,event_ids
from slac_assistant.runtime import run_flower

def summarize(reports,labels):
    rows=[]
    for report in reports:
        expected=labels[report['event_id']]['is_anom']; assessment=report['final']['assessment']
        prediction={'corroborated':True,'not_corroborated':False,'insufficient_evidence':None}[assessment]
        refs={r['ref'] for r in report['evidence']}
        invalid=sum(ref not in refs for f in report['findings'] for ref in f['tool_result_refs'])
        rows.append(dict(event_id=report['event_id'],mode=report['mode'],model=report['model'],label=expected,prediction=prediction,abstained=prediction is None,agreement=prediction==expected if prediction is not None else None,invalid_references=invalid,unsupported_claims=None,unsupported_claims_status='Pending human review; citation existence does not prove support',**{k:report['metrics'][k] for k in ['model_calls','tool_calls','latency_s','input_tokens','output_tokens','cost_usd']},wall_latency_s=report['wall_latency_s']))
    return rows

def main():
    p=argparse.ArgumentParser();p.add_argument('--model',default='openai/gpt-5.6-sol');p.add_argument('--smoke-only',action='store_true');args=p.parse_args()
    reports=[]
    for i,event in enumerate(event_ids()):
        modes=['smoke'] if args.smoke_only else (['collaborative','baseline'] if i%2==0 else ['baseline','collaborative'])
        for mode in modes:
            report,_=run_flower(event,mode,model=args.model);reports.append(report);print(event,mode,report['final']['assessment'],flush=True)
    labels=json.loads((ROOT/'data/evaluation_labels.json').read_text());rows=summarize(reports,labels)
    name='smoke-evaluation' if args.smoke_only else 'comparison';out=ROOT/'artifacts'/f'{name}.json'
    out.write_text(json.dumps(dict(selection='Four label-selected demonstrations; not representative or held-out; no superiority claim is supported.',budget='Same model, 12 total model requests, 1600 output tokens per request, 300000 cumulative input characters, 24 tool calls per run. Actual usage reported; no extra baseline deprivation.',rows=rows,reports=reports),indent=2))
    with (ROOT/'artifacts'/f'{name}-claim-review.csv').open('w') as f:
        writer=csv.writer(f);writer.writerow(['event_id','mode','finding_id','observation','refs','supported_yes_no_uncertain','reviewer_notes'])
        for r in reports:
            for finding in r['findings']:writer.writerow([r['event_id'],r['mode'],finding['finding_id'],finding['observation'],';'.join(finding['tool_result_refs']),'',''])
    print(out)
if __name__=='__main__':main()
