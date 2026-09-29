"""Run a matched-budget comparison; labels are loaded only by this external evaluator."""
import argparse,json,csv
from pathlib import Path
from slac_assistant.data import ROOT,event_ids
from slac_assistant.runtime import run_flower

def summarize(reports,labels):
    rows=[]
    for report in reports:
        # Source anomaly labels are not independently adjudicated labels for beam
        # disturbance and unique causation. Never score the old mixed-scope enum.
        expected=labels[report['event_id']]['is_anom']
        refs={r['ref'] for r in report['evidence']}
        invalid=sum(ref not in refs for f in report['findings'] for ref in f['tool_result_refs'])
        rows.append(dict(event_id=report['event_id'],mode=report['mode'],model=report['model'],source_anomaly_label=expected,beam_disturbance=report['final'].get('beam_disturbance',{'status':'not_assessed'}),unique_cause=report['final'].get('unique_cause',{'status':'not_assessed'}),benchmark_eligible=False,prediction=None,agreement=None,scoring_note='No dimension-specific adjudicated labels; legacy mixed-scope assessments are not scores.',invalid_references=invalid,unsupported_claims=None,unsupported_claims_status='Pending human review; citation existence does not prove support',**{k:report['metrics'][k] for k in ['model_calls','tool_calls','latency_s','input_tokens','output_tokens','cost_usd']},wall_latency_s=report['wall_latency_s']))
    return rows

def table(reports):
    """Grid vs single-agent side by side. No accuracy column: labels are not adjudicated per verdict dimension."""
    out=['| event | mode | agents | beam_disturbance | unique_cause | model calls | latency s | raw data shared |','|'+'---|'*8]
    for r in reports:
        m=r['metrics'];nodes=r.get('node_observation_source') or {};d=r.get('data_shared')
        calls=m['model_calls']+sum(v=='model' for v in nodes.values())
        share=f"{d['percent_shared']}% ({d['payload_bytes']}/{d['raw_bytes_held']} B)" if d else '100% (one agent reads all raw)'
        out.append(f"| {r['event_id']} | {r['mode']} | {1+len(nodes)} | {r['final']['beam_disturbance']['status']} | {r['final']['unique_cause']['status']} | {calls} | {r.get('wall_latency_s',m['latency_s'])} | {share} |")
    return '\n'.join(out)

def main():
    p=argparse.ArgumentParser();p.add_argument('--model');p.add_argument('--smoke-only',action='store_true');p.add_argument('--events',nargs='*');args=p.parse_args()
    reports=[]
    for i,event in enumerate(args.events or event_ids()):
        modes=['smoke'] if args.smoke_only else (['collaborative','baseline'] if i%2==0 else ['baseline','collaborative'])
        for mode in modes:
            report,_=run_flower(event,mode,model=args.model);reports.append(report);print(event,mode,report['final']['beam_disturbance']['status'],report['final']['unique_cause']['status'],flush=True)
    labels=json.loads((ROOT/'data/evaluation_labels.json').read_text());rows=summarize(reports,labels)
    name='smoke-evaluation' if args.smoke_only else 'comparison';out=ROOT/'artifacts'/f'{name}.json'
    out.write_text(json.dumps(dict(selection='Four label-selected demonstrations; not representative or held-out; no superiority claim is supported.',budget='Same model, 12 total model requests, 1600 output tokens per request, 300000 cumulative input characters, 24 tool calls per run. Actual usage reported; no extra baseline deprivation.',rows=rows,reports=reports),indent=2))
    with (ROOT/'artifacts'/f'{name}-claim-review.csv').open('w') as f:
        writer=csv.writer(f);writer.writerow(['event_id','mode','finding_id','observation','refs','supported_yes_no_uncertain','reviewer_notes'])
        for r in reports:
            for finding in r['findings']:writer.writerow([r['event_id'],r['mode'],finding['finding_id'],finding['observation'],';'.join(finding['tool_result_refs']),'',''])
    print(table(reports));print('Four hand-picked cases: a demo, not a benchmark. Model calls include node models.');print(out)
if __name__=='__main__':main()
