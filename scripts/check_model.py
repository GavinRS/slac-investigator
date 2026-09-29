"""Check the configured Responses provider's tool protocol without printing secrets."""
import argparse
import json
import os
from pathlib import Path
import time

from openai import OpenAI
from start_flower import ROOT, flower_environment


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    started = time.perf_counter()
    result = {'passed': False}
    try:
        env = flower_environment(os.environ, ROOT / '.env')
        endpoint = env['FLWR_MODEL_API_ENDPOINT']
        result.update(endpoint=endpoint, model=env['INVESTIGATOR_MODEL'])
        with OpenAI(base_url=endpoint.removesuffix('/responses'),
                    api_key=env['FLWR_MODEL_API_KEY'] or 'local-no-auth', max_retries=0, timeout=120) as client:
            response = client.responses.create(model=env['INVESTIGATOR_MODEL'],
                input='Call protocol_check with value exactly 7. Do not provide other output.',
                tools=[{'type':'function','name':'protocol_check','description':'Check a read-only tool-call protocol.',
                        'parameters':{'type':'object','properties':{'value':{'type':'integer'}},'required':['value'],'additionalProperties':False}}],
                tool_choice={'type':'function','name':'protocol_check'}, max_output_tokens=1024)
        calls = [item for item in response.output if item.type == 'function_call']
        result['passed'] = response.status == 'completed' and len(calls) == 1 and calls[0].name == 'protocol_check' and json.loads(calls[0].arguments) == {'value':7}
    except Exception as exc:
        result['error_type'] = type(exc).__name__
    result['latency_s'] = round(time.perf_counter()-started,3)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result,indent=2)+'\n')
    print('Model tool protocol: ' + ('PASS' if result['passed'] else 'FAIL'))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
