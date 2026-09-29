"""Four-case demonstration comparison; labels never enter model inputs."""
import argparse
import csv
import json
import os
import time
import tomllib
from pathlib import Path

from slac_assistant.data import ROOT, event_ids
from slac_assistant.runtime import run_flower

SELECTION = 'Four label-selected demonstrations; not representative or held-out; no superiority claim is supported.'
SCORING = 'N/A: source RF anomaly labels are not adjudicated beam-disturbance or unique-cause labels.'
LOCALITY = ('Grid percentage is serialized summary payload bytes / raw instrument bytes held, not raw-sample disclosure. '
            'Baseline 100% denotes conceptual centralized access to all instrument data; it does not mean raw arrays were sent to the model. '
            'Local fallback is explicitly identified and does not demonstrate remote data locality.')
METRICS = ('model_calls', 'tool_calls', 'latency_s', 'input_tokens', 'output_tokens', 'cost_usd')


def summarize(reports, labels):
    rows = []
    for report in reports:
        refs = {r['ref'] for r in report.get('evidence', [])}
        refs.update(ref for node in report.get('node_reports', []) for ref in node.get('tool_refs', []))
        invalid = sum(ref not in refs for f in report.get('findings', []) for ref in f['tool_result_refs'])
        sharing = report.get('data_shared', {})
        baseline = report['mode'] == 'baseline'
        rows.append(dict(
            event_id=report['event_id'], mode=report['mode'], model=report['model'], status='completed',
            source_anomaly_label=labels[report['event_id']]['is_anom'],
            beam_disturbance=report['final'].get('beam_disturbance', {'status': 'not_assessed'}),
            unique_cause=report['final'].get('unique_cause', {'status': 'not_assessed'}),
            benchmark_eligible=False, prediction=None, agreement=None, scoring_note=SCORING,
            invalid_references=invalid, unsupported_claims=None,
            unsupported_claims_status='Pending human review; citation existence does not prove support',
            **{k: report.get('metrics', {}).get(k) for k in METRICS},
            wall_latency_s=report.get('wall_latency_s'), grid=report.get('grid'),
            percent_shared=100.0 if baseline else sharing.get('percent_shared') if sharing.get('complete', True) else None,
            sharing_basis='conceptual centralized access' if baseline else 'summary/raw byte ratio',
            raw_bytes_held=sharing.get('raw_bytes_held'), payload_bytes=sharing.get('payload_bytes'),
            raw_samples_shared=sharing.get('raw_samples_shared'), sharing_complete=sharing.get('complete'),
            accounting_complete=report.get('metrics', {}).get('accounting_complete'), locality_note=LOCALITY,
        ))
    return rows


def table(rows):
    lines = ['| Event | Mode | Status | Agreement | Model calls | Input / output tokens | End-to-end s | Data shared %* | Grid |',
             '| --- | --- | --- | --- | --- | --- | --- | --- | --- |']
    def value(v):
        return 'N/A' if v is None else str(round(v, 3) if isinstance(v, float) else v)
    for row in rows:
        lines.append('| ' + ' | '.join([
            row['event_id'], row['mode'], row['status'], 'N/A', value(row.get('model_calls')),
            f"{value(row.get('input_tokens'))} / {value(row.get('output_tokens'))}",
            value(row.get('wall_latency_s')), value(row.get('percent_shared')),
            str(row.get('grid') or ('centralized' if row['mode'] == 'baseline' and row['status'] == 'completed' else 'N/A')).replace('|', '/'),
        ]) + ' |')
    return '\n'.join(lines) + '\n\n*' + LOCALITY + '\n\n' + SCORING


def save_artifacts(output_dir, name, reports, failures, labels, model, expected_runs, address=None):
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = summarize(reports, labels) + failures
    rows.sort(key=lambda r: (r['event_id'], r['mode']))
    payload = dict(selection=SELECTION, model=model, address=address, expected_runs=expected_runs,
                   completed_runs=len(reports), failed_runs=len(failures),
                   all_runs_completed=len(reports) == expected_runs,
                   budget='Same model; actual aggregate model calls, tokens and latency reported. Missing provider usage remains null. Protocols may use different call counts; no equal-usage claim.',
                   scoring_note=SCORING, locality_note=LOCALITY, rows=rows, reports=reports, failed_attempts=failures)
    out = output_dir / f'{name}.json'
    tmp = out.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(payload, indent=2))
    tmp.replace(out)
    (output_dir / f'{name}.md').write_text('# Four-case demonstration comparison\n\n' + SELECTION + '\n\nModel: `' + model + '`.\n\nFailed attempts remain in this table even when a later retry succeeds.\n\n' + table(rows) + '\n')
    with (output_dir / f'{name}-claim-review.csv').open('w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['event_id', 'mode', 'finding_id', 'observation', 'refs', 'supported_yes_no_uncertain', 'reviewer_notes'])
        for report in reports:
            for finding in report.get('findings', []):
                writer.writerow([report['event_id'], report['mode'], finding['finding_id'], finding['observation'], ';'.join(finding['tool_result_refs']), '', ''])
    return out, rows


def load_resume(path, model, address, pairs):
    """Fail closed before any live request if saved comparison identity differs."""
    saved = json.loads(path.read_text())
    if saved.get('model') != model or saved.get('address') != address:
        raise ValueError('Resume requires the exact saved model and SuperLink address; use a separate output directory for a new comparison.')
    reports = saved.get('reports', [])
    if not isinstance(reports, list):
        raise ValueError('Invalid saved reports')
    seen = set()
    for report in reports:
        pair = (report.get('event_id'), report.get('mode'))
        if pair not in pairs or pair in seen or not isinstance(report.get('final'), dict):
            raise ValueError('Invalid, duplicate or unexpected completed report in resume artifact')
        if pair[1] != 'smoke' and report.get('model') != model:
            raise ValueError('Saved report model differs from comparison model')
        seen.add(pair)
    failures = saved.get('failed_attempts', [row for row in saved.get('rows', []) if row.get('status') == 'failed'])
    if not isinstance(failures, list) or any((row.get('event_id'), row.get('mode')) not in pairs or row.get('status') != 'failed' for row in failures):
        raise ValueError('Invalid saved failed attempts')
    return reports, failures


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model')
    p.add_argument('--smoke-only', action='store_true')
    p.add_argument('--resume', action='store_true', help='Reuse completed reports for the same model/address, retry unfinished pairs, and retain failed-attempt history.')
    p.add_argument('--address', default=os.environ.get('SLAC_SUPERLINK_ADDRESS', 'http://127.0.0.1:8000'))
    p.add_argument('--output-dir', type=Path, default=ROOT / 'artifacts')
    args = p.parse_args(argv)
    configured = tomllib.loads((ROOT / 'pyproject.toml').read_text())['tool']['flwr']['app']['config']['model']
    model = args.model or os.environ.get('INVESTIGATOR_MODEL') or configured
    reports, failures = [], []
    events = event_ids()
    expected = len(events) * (1 if args.smoke_only else 2)
    name = 'smoke-evaluation' if args.smoke_only else 'comparison'
    pairs = {(event, mode) for event in events for mode in (['smoke'] if args.smoke_only else ['collaborative', 'baseline'])}
    if args.resume:
        try:
            reports, failures = load_resume(args.output_dir / f'{name}.json', model, args.address, pairs)
        except (OSError, ValueError, KeyError, TypeError):
            p.error('Cannot resume: artifact missing, invalid, or model/address/event selection differs. Use the original settings or a new output directory.')
    completed = {(r['event_id'], r['mode']) for r in reports}
    def save():
        # Evaluation labels are read only after completed investigations.
        labels = json.loads((ROOT / 'data/evaluation_labels.json').read_text()) if reports else {}
        return save_artifacts(args.output_dir, name, reports, failures, labels, model, expected, address=args.address)
    out, rows = save()
    for i, event in enumerate(events):
        modes = ['smoke'] if args.smoke_only else (['collaborative', 'baseline'] if i % 2 == 0 else ['baseline', 'collaborative'])
        for mode in modes:
            if (event, mode) in completed:
                print(event, mode, 'reused completed report', flush=True)
                continue
            started = time.perf_counter()
            interrupted = False
            try:
                report, _ = run_flower(event, mode, model=model, address=args.address)
                if report.get('event_id') != event or report.get('mode') != mode:
                    raise ValueError('Returned event or mode differs from requested comparison pair')
                if mode != 'smoke' and report.get('model') != model:
                    raise ValueError('Returned model differs from the requested comparison model')
                reports.append(report)
                completed.add((event, mode))
                print(event, mode, 'completed', flush=True)
            except (Exception, KeyboardInterrupt) as exc:
                interrupted = isinstance(exc, KeyboardInterrupt)
                # Do not persist arbitrary provider exceptions: they may contain credentials.
                failures.append(dict(event_id=event, mode=mode, model=model, status='failed',
                                     error_type=type(exc).__name__, benchmark_eligible=False,
                                     prediction=None, agreement=None, scoring_note=SCORING,
                                     attempt_elapsed_s=round(time.perf_counter() - started, 3)))
                print(event, mode, 'failed', type(exc).__name__, flush=True)
            out, rows = save()
            if interrupted:
                print('Interrupted attempt saved. Check SuperLink for an unfinished run before resuming.', flush=True)
                return 130
    print(table(rows), flush=True)
    print(out)
    return 0 if completed == pairs else 1


if __name__ == '__main__':
    raise SystemExit(main())
