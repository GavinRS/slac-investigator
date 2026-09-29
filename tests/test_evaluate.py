"""Truthful demo comparison reporting, including partial and failed runs."""
import json
from scripts import evaluate


def report(mode='grid'):
    return dict(event_id='slac-001', mode=mode, model='fixture', final={}, findings=[], evidence=[],
                metrics={'model_calls': 4, 'input_tokens': None, 'output_tokens': None},
                wall_latency_s=3.5, grid={'nodes_seen': 0, 'assignment': {}, 'fallback': True},
                data_shared={'raw_bytes_held': 1000, 'payload_bytes': 20, 'percent_shared': 2, 'raw_samples_shared': 0})


def test_demo_table_does_not_invent_accuracy_usage_or_raw_disclosure():
    rows = evaluate.summarize([report(), report('baseline')], {'slac-001': {'is_anom': True}})
    assert all(r['agreement'] is None and r['benchmark_eligible'] is False for r in rows)
    assert rows[0]['percent_shared'] == 2
    assert rows[0]['raw_samples_shared'] == 0
    assert rows[1]['percent_shared'] == 100
    assert rows[1]['sharing_basis'] == 'conceptual centralized access'
    rendered = evaluate.table(rows)
    assert 'N/A / N/A' in rendered
    assert 'not raw-sample disclosure' in rendered
    assert 'does not mean raw arrays were sent to the model' in rendered


def test_partial_artifact_records_failure_without_fabricated_metrics(tmp_path):
    failure = dict(event_id='slac-002', mode='baseline', model='fixture', status='failed')
    out, rows = evaluate.save_artifacts(tmp_path, 'comparison', [report()], [failure],
                                       {'slac-001': {'is_anom': True}}, 'fixture', 8)
    data = json.loads(out.read_text())
    assert data['completed_runs'] == data['failed_runs'] == 1
    assert data['all_runs_completed'] is False
    assert 'model_calls' not in data['rows'][1]
    assert '| slac-002 | baseline | failed | N/A | N/A | N/A / N/A | N/A | N/A | N/A |' in evaluate.table(rows)
    assert (tmp_path / 'comparison-claim-review.csv').exists()


def test_run_uses_same_model_address_and_persists_after_every_attempt(monkeypatch, tmp_path):
    monkeypatch.setattr(evaluate, 'event_ids', lambda: ['slac-001', 'slac-002'])
    calls = []
    def fake_run(event, mode, **kwargs):
        previous = json.loads((tmp_path / 'comparison.json').read_text())
        assert previous['completed_runs'] + previous['failed_runs'] == len(calls)
        calls.append((event, mode, kwargs))
        if event == 'slac-002':
            raise RuntimeError('secret-that-must-not-be-logged')
        return report(mode), 'series'
    monkeypatch.setattr(evaluate, 'run_flower', fake_run)
    assert evaluate.main(['--model', 'fixture', '--address', 'http://127.0.0.1:18000', '--output-dir', str(tmp_path)]) == 1
    assert [mode for _, mode, _ in calls] == ['grid', 'baseline', 'baseline', 'grid']
    assert all(kwargs == {'model': 'fixture', 'address': 'http://127.0.0.1:18000', 'node_timeout': 120} for _, _, kwargs in calls)
    data = (tmp_path / 'comparison.json').read_text()
    assert 'secret-that-must-not-be-logged' not in data
    assert json.loads(data)['failed_runs'] == 2


def test_smoke_does_not_require_model_identity(monkeypatch, tmp_path):
    monkeypatch.setattr(evaluate, 'event_ids', lambda: ['slac-001'])
    smoke = report('grid')
    smoke['execution_mode'] = 'smoke'
    smoke['model'] = 'none (deterministic check)'
    monkeypatch.setattr(evaluate, 'run_flower', lambda *a, **kw: (smoke, 'series'))
    assert evaluate.main(['--smoke-only', '--output-dir', str(tmp_path)]) == 0
    assert json.loads((tmp_path / 'smoke-evaluation.json').read_text())['all_runs_completed']


def test_grid_references_count_and_incomplete_sharing():
    r = report()
    r['node_reports'] = [{'tool_refs': ['T-node']}]
    r['findings'] = [{'tool_result_refs': ['T-node', 'T-invented']}]
    r['data_shared']['complete'] = False
    row = evaluate.summarize([r], {'slac-001': {'is_anom': True}})[0]
    assert row['invalid_references'] == 1
    assert row['percent_shared'] is None
    assert row['sharing_complete'] is False


def test_resume_reuses_success_and_retains_failure_history(monkeypatch, tmp_path):
    monkeypatch.setattr(evaluate, 'event_ids', lambda: ['slac-001'])
    calls = []
    def first_run(event, mode, **kwargs):
        calls.append(mode)
        if mode == 'baseline':
            raise RuntimeError('first attempt failed')
        return report(mode), 'series'
    monkeypatch.setattr(evaluate, 'run_flower', first_run)
    argv = ['--model', 'fixture', '--address', 'http://127.0.0.1:18000', '--output-dir', str(tmp_path)]
    assert evaluate.main(argv) == 1
    calls.clear()
    def retry(event, mode, **kwargs):
        calls.append(mode)
        return report(mode), 'series'
    monkeypatch.setattr(evaluate, 'run_flower', retry)
    assert evaluate.main(argv + ['--resume']) == 0
    assert calls == ['baseline']
    saved = json.loads((tmp_path / 'comparison.json').read_text())
    assert saved['all_runs_completed'] and saved['completed_runs'] == 2
    assert saved['failed_runs'] == 1
    assert len(saved['failed_attempts']) == 1
    assert len(saved['rows']) == 3
    calls.clear()
    assert evaluate.main(argv + ['--resume']) == 0
    assert calls == []


def test_resume_refuses_mismatch_before_calls_or_artifact_changes(monkeypatch, tmp_path):
    import pytest
    monkeypatch.setattr(evaluate, 'event_ids', lambda: ['slac-001'])
    path, _ = evaluate.save_artifacts(tmp_path, 'comparison', [report()], [],
                                     {'slac-001': {'is_anom': True}}, 'fixture', 2,
                                     address='http://127.0.0.1:18000')
    original = path.read_bytes()
    def no_calls(*args, **kwargs):
        pytest.fail('Resume mismatch must not launch an investigation')
    monkeypatch.setattr(evaluate, 'run_flower', no_calls)
    for model, address in [('other', 'http://127.0.0.1:18000'), ('fixture', 'http://127.0.0.1:8000')]:
        with pytest.raises(SystemExit):
            evaluate.main(['--resume', '--model', model, '--address', address, '--output-dir', str(tmp_path)])
        assert path.read_bytes() == original


def test_interruption_saves_attempt_and_stops(monkeypatch, tmp_path):
    monkeypatch.setattr(evaluate, 'event_ids', lambda: ['slac-001'])
    calls = []
    def interrupted(*args, **kwargs):
        calls.append(args)
        raise KeyboardInterrupt()
    monkeypatch.setattr(evaluate, 'run_flower', interrupted)
    assert evaluate.main(['--model', 'fixture', '--output-dir', str(tmp_path)]) == 130
    assert len(calls) == 1
    saved = json.loads((tmp_path / 'comparison.json').read_text())
    assert saved['completed_runs'] == 0
    assert saved['failed_attempts'][0]['error_type'] == 'KeyboardInterrupt'


def test_rev2_smoke_resume_uses_execution_mode(monkeypatch, tmp_path):
    monkeypatch.setattr(evaluate, 'event_ids', lambda: ['slac-001'])
    calls = []
    def smoke_run(event, mode, **kwargs):
        calls.append(mode)
        result = report('grid')
        result['execution_mode'] = 'smoke'
        return result, 'series'
    monkeypatch.setattr(evaluate, 'run_flower', smoke_run)
    argv = ['--smoke-only', '--model', 'fixture', '--output-dir', str(tmp_path)]
    assert evaluate.main(argv) == 0
    assert evaluate.main(argv + ['--resume']) == 0
    assert calls == ['smoke']
    saved = json.loads((tmp_path / 'smoke-evaluation.json').read_text())
    assert saved['reports'][0]['mode'] == 'grid'
    assert saved['rows'][0]['execution_mode'] == 'smoke'
    assert 'grid (smoke)' in (tmp_path / 'smoke-evaluation.md').read_text()


def test_model_comparison_rejects_smoke_grid_report(monkeypatch, tmp_path):
    monkeypatch.setattr(evaluate, 'event_ids', lambda: ['slac-001'])
    def unexpected_smoke(event, mode, **kwargs):
        result = report('grid')
        result['execution_mode'] = 'smoke'
        return result, 'series'
    monkeypatch.setattr(evaluate, 'run_flower', unexpected_smoke)
    assert evaluate.main(['--model', 'fixture', '--output-dir', str(tmp_path)]) == 1
    saved = json.loads((tmp_path / 'comparison.json').read_text())
    assert saved['completed_runs'] == 0
    assert saved['failed_runs'] == 2


def test_partial_accounting_does_not_present_known_calls_as_totals():
    r = report()
    r['metrics'].update(accounting_complete=False, model_calls=3, tool_calls=2, input_tokens=40,
                        output_tokens=20, cost_usd=0.1, latency_s=3)
    row = evaluate.summarize([r], {'slac-001': {'is_anom': True}})[0]
    for key in ('model_calls', 'tool_calls', 'input_tokens', 'output_tokens', 'cost_usd'):
        assert row[key] is None
    assert row['latency_s'] == 3 and row['wall_latency_s'] == 3.5
    assert 'Incomplete node accounting' in row['accounting_note']
    assert r['metrics']['model_calls'] == 3  # Source report retained for audit.


def test_partial_grid_retried_on_resume_with_report_and_attempt_retained(monkeypatch, tmp_path):
    monkeypatch.setattr(evaluate, 'event_ids', lambda: ['slac-001'])
    calls = []
    partial = report('grid')
    partial['flower_run_id'] = '123'
    partial['data_shared']['complete'] = False
    partial['metrics']['accounting_complete'] = False
    def first(event, mode, **kwargs):
        return (partial if mode == 'grid' else report('baseline')), 'series'
    monkeypatch.setattr(evaluate, 'run_flower', first)
    argv = ['--model', 'fixture', '--output-dir', str(tmp_path)]
    assert evaluate.main(argv) == 1
    saved = json.loads((tmp_path / 'comparison.json').read_text())
    assert saved['completed_runs'] == 1 and saved['partial_runs'] == 1
    assert saved['all_runs_completed'] is False
    assert next(row for row in saved['rows'] if row['mode'] == 'grid')['status'] == 'partial'
    assert saved['failed_attempts'][0]['flower_run_id'] == '123'
    def complete(event, mode, **kwargs):
        calls.append(mode)
        return report(mode), 'series'
    monkeypatch.setattr(evaluate, 'run_flower', complete)
    assert evaluate.main(argv + ['--resume']) == 0
    assert calls == ['grid']
    saved = json.loads((tmp_path / 'comparison.json').read_text())
    assert saved['completed_runs'] == 2 and saved['partial_runs'] == 1
    assert saved['all_runs_completed'] is True and len(saved['reports']) == 3
    calls.clear()
    assert evaluate.main(argv + ['--resume']) == 0
    assert calls == []
