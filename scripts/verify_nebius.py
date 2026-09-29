"""Gated live validation, in order, through a separately started Flower runtime."""
import argparse,json
from pathlib import Path
from slac_assistant.nebius import require_nebius_environment
from slac_assistant.runtime import run_flower
from slac_assistant.data import ROOT

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--address',default='http://127.0.0.1:8001')
    parser.add_argument('--event',default='slac-001')
    args=parser.parse_args()
    # This local assertion does not independently verify event billing coverage.
    _,model=require_nebius_environment()
    result={'provider':'nebius-chat','model':model,'credit_coverage':'operator-confirmed via environment',
            'stages':[],'complete':False}
    path=ROOT/'artifacts/nebius-live-verification.json'
    for stage in ('text','tool','investigation'):
        try:
            report,_=run_flower(args.event,provider='nebius-chat',address=args.address,
                probe=None if stage=='investigation' else stage)
            result['stages'].append({'stage':stage,'status':'passed','report':report})
            print(stage+': passed; Flower run '+report['flower_run_id'],flush=True)
        except Exception:
            # No remote response bodies, auth headers, token values or traceback.
            result['stages'].append({'stage':stage,'status':'failed',
                'detail':'Check the sanitized provider error in the local Flower run log.'})
            path.write_text(json.dumps(result,indent=2))
            print(stage+': failed; stopped before subsequent tests.',flush=True)
            return 1
        path.write_text(json.dumps(result,indent=2))
    result['complete']=True
    path.write_text(json.dumps(result,indent=2))
    print(path)
    return 0

if __name__=='__main__':
    try:
        raise SystemExit(main())
    except Exception:
        print('Preflight blocked. Confirm event credits and set NEBIUS_API_KEY and NEBIUS_MODEL in this shell; do not print the token.')
        raise SystemExit(1) from None
