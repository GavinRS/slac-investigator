"""Deterministic, read-only evidence tools. No label access, writes, or alignment fitting."""
import hashlib, json
import numpy as np
from .data import load_event
KINDS=('quality','equipment','beam','charge_validity','timing','neighbors')

def timing_quality(t):
    d=np.diff(t)/1e9
    return dict(samples=len(t),nonmonotonic=int(np.sum(d<0)),duplicates=int(np.sum(d==0)),median_dt_s=float(np.median(d)) if len(d) else None,max_gap_s=float(np.max(d)) if len(d) else None,fraction_120hz=float(np.mean(np.abs(d-1/120)<=2.5e-4)) if len(d) else 0)

def sustained(mask,t,min_samples=10):
    best=run=0; first=None; onset=None
    for i,flag in enumerate(mask):
        if flag:
            if i and (t[i]-t[i-1]>1.5e9/120 or t[i]<=t[i-1]): run=0
            if run==0: onset=int(t[i])
            run+=1;best=max(best,run)
            if run==min_samples and first is None: first=onset
        else: run=0
    return dict(longest_consecutive_samples=best,sustained=best>=min_samples,first_sustained_ns=first)

def equipment_summary(m,a,station=None):
    channel=(station or m['station'])+':AMPL'; j=m['channels']['health'].index(channel)
    t=a['health_time_ns'];x=a['health'][:,j]; valid=np.isfinite(x); t=t[valid];x=x[valid]
    start=m['candidate_start_ns'];end=m['candidate_end_ns']
    # Time-weighted baseline of known held values. Never backfill unknown leading data.
    cutoff=start-5_000_000_000; stop=np.minimum(np.r_[t[1:],cutoff],cutoff); weights=np.maximum(stop-t,0)/1e9
    if not np.any(weights>0): baseline=None
    else:
        order=np.argsort(x); total=weights.sum(); baseline=float(x[order][np.searchsorted(np.cumsum(weights[order]),total/2)])
    window=(t>=start)&(t<=end+5_300_000_000)
    deviation=None if baseline is None or baseline==0 or not np.any(window) else float(np.max(np.abs(x[window]-baseline))/abs(baseline)*100)
    updates=[dict(time_ns=int(tt),relative_s=float((tt-end)/1e9),value=float(xx)) for tt,xx in zip(t[window],x[window])]
    return dict(channel=channel,finite_updates=len(x),no_update_fraction=float(1-valid.mean()),baseline_time_weighted_median=baseline,max_abs_deviation_pct=deviation,suspicious=deviation is not None and deviation>=.5,updates=updates,window_includes_postcandidate_rf_updates=True)

def beam_summary(m,a,charge_only=False):
    t=a['bpm_time_ns'];x=a['bpm']; baseline=t<m['candidate_start_ns'];window=(t>=m['candidate_start_ns'])&(t<=m['candidate_end_ns']);rows=[]
    for j,c in enumerate(m['channels']['bpm']):
        is_charge=c.endswith('TMIT')
        if charge_only and not is_charge:continue
        valid=np.isfinite(x[:,j]);invalid_charge=np.zeros(len(t),bool)
        if not is_charge:
            invalid_charge=(x[:,j-1]<1e8)|~np.isfinite(x[:,j-1]);valid &= ~invalid_charge
            valid &= x[:,j]!=100
        b=x[baseline&valid,j]; med=float(np.median(b)) if len(b) else None
        mad=float(1.4826*np.median(np.abs(b-med))) if len(b) else None
        usable=med is not None and mad is not None and mad>1e-12 and len(b)>=120
        z=np.abs(x[:,j]-med)/mad if usable else np.full(len(t),np.nan)
        anomaly=window&valid&(z>=6) if usable else np.zeros(len(t),bool)
        if is_charge: anomaly |=window&valid&(x[:,j]<1e8)
        s=sustained(anomaly,t)
        rows.append(dict(channel=c,baseline_samples=len(b),baseline_median=med,baseline_robust_sigma=mad,score_available=usable,peak_robust_z=float(np.max(z[window&valid])) if usable and np.any(window&valid) else None,invalid_position_samples=int(np.sum(window&invalid_charge)),low_charge_samples=int(np.sum(window&valid&(x[:,j]<1e8))) if is_charge else None,**s))
    q=timing_quality(t); adequate=q['nonmonotonic']==0 and q['duplicates']==0 and q['fraction_120hz']>=.85 and all(r['baseline_samples']>=120 for r in rows if r['channel'].endswith('TMIT')) and np.isfinite(x[window]).mean()>=.95
    return dict(channels=rows,disturbance_detected=any(r['sustained'] for r in rows),quality_adequate=bool(adequate),threshold='6 robust sigmas or TMIT <1e8, sustained >=10 consecutive samples; exploratory heuristic, not a reproduction of the published detector',samples_in_candidate=int(window.sum()))

def analyze(event_id,kind):
    if kind not in KINDS:raise ValueError('Unknown analysis')
    m,a=load_event(event_id); limitations=list(m['limitations'])
    if kind=='quality':
        result={k:dict(**timing_quality(a[k+'_time_ns']),nonfinite_values=int(np.sum(~np.isfinite(a[k]))),channels=a[k].shape[1]) for k in ['health','bpm']}
        result['rf_missing_semantics']='NaN means no new update; hold only a known previous value; no backfill. RF row cadence is NOT per-station sampling rate.'
    elif kind=='equipment':result=equipment_summary(m,a)
    elif kind in ('beam','charge_validity'):result=beam_summary(m,a,charge_only=kind=='charge_validity')
    elif kind=='neighbors':
        all_stations=[equipment_summary(m,a,c.removesuffix(':AMPL')) for c in m['channels']['health']]
        result=dict(available_columns=len(all_stations),unknown_baselines=sum(r['baseline_time_weighted_median'] is None for r in all_stations),suspicious=[r for r in all_stations if r['suspicious']],caution='Column presence does not establish continuous station operation or complete neighboring records.')
    else:
        eq=equipment_summary(m,a);beam=beam_summary(m,a)
        onsets=[r['first_sustained_ns'] for r in beam['channels'] if r['first_sustained_ns'] is not None]
        result=dict(recorded_rf_updates=eq['updates'],beam_onsets_ns=onsets,candidate_interval_ns=[m['candidate_start_ns'],m['candidate_end_ns']],documented_rf_reporting_delay_s=[0,5],delay_is_approximate=True,applied_shift_s=0,causal_attribution='Not established; asynchronous observations and candidate association alone cannot identify a unique cause.')
    body=dict(event_id=event_id,analysis=kind,source=m['source_url'],hdf5_group=m['hdf5_group'],interval_ns=[int(a['health_time_ns'][0]) if kind in ('equipment','neighbors','quality') else int(a['bpm_time_ns'][0]),int(a['health_time_ns'][-1]) if kind in ('equipment','neighbors','quality','timing') else int(a['bpm_time_ns'][-1])],result=result,limitations=limitations)
    body['ref']='T-'+hashlib.sha256(json.dumps(body,sort_keys=True).encode()).hexdigest()[:12]
    return body


def serialize_node_report(report):
    """Serialize a node reply with its exact UTF-8 wire size, including the size."""
    report['payload_bytes'] = 0
    while True:
        payload = json.dumps(report, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
        size = len(payload.encode('utf-8'))
        if report['payload_bytes'] == size:
            return payload
        report['payload_bytes'] = size


def node_summary(event_id, instrument, arrays, role_source='assigned', *, meta=None):
    """Run instrument-local checks and return compact evidence, never raw samples.

    The instrument assessment is a local heuristic result, not a combined beam /
    RF causality assessment. The orchestrator must assess those two independently.
    """
    from .instruments import INSTRUMENTS, load_slice
    if instrument not in INSTRUMENTS:
        raise ValueError('Unknown instrument')
    if role_source not in ('local_data', 'assigned'):
        raise ValueError('Unknown role source')
    if meta is None:
        meta, _ = load_slice(event_id, instrument)
    family = 'health' if instrument == 'rf' else 'bpm'
    expected = {family, family + '_time_ns'}
    if set(arrays) != expected or set(meta['channels']) != {family}:
        raise ValueError('Node checks require an instrument-only data slice')
    channels = meta['channels'][family]
    prefix = 'BPMS:LTUH:' if instrument == 'ltu' else 'BPMS:DMPH:'
    if instrument != 'rf' and not all(c.startswith(prefix) for c in channels):
        raise ValueError('Node checks cannot access another instrument')
    if arrays[family].shape != (len(arrays[family + '_time_ns']), len(channels)):
        raise ValueError('Instrument array dimensions do not match the channel catalog')
    limitations = list(meta.get('limitations', []))
    quality = timing_quality(arrays[family + '_time_ns'])
    quality['nonfinite_values'] = int(np.sum(~np.isfinite(arrays[family])))
    summary = {'quality': quality}
    if instrument == 'rf':
        equipment = equipment_summary(meta, arrays)
        neighbors = [equipment_summary(meta, arrays, c.removesuffix(':AMPL')) for c in channels]
        baseline = equipment['baseline_time_weighted_median']
        onset = next((u['time_ns'] for u in equipment['updates']
                      if baseline not in (None, 0) and abs(u['value'] - baseline) / abs(baseline) * 100 >= .5), None)
        summary.update(baseline=baseline, peak_deviation_pct=equipment['max_abs_deviation_pct'],
                       onset_ns=onset, valid_updates=equipment['finite_updates'],
                       no_update_count=int(np.sum(~np.isfinite(arrays['health'][:, channels.index(equipment['channel'])]))),
                       suspicious=int(equipment['suspicious']),
                       quality_adequate=int(baseline not in (None, 0) and equipment['max_abs_deviation_pct'] is not None),
                       neighbor_columns=len(neighbors),
                       neighbor_unknown_baselines=sum(r['baseline_time_weighted_median'] is None for r in neighbors),
                       neighbor_suspicious=sum(r['suspicious'] for r in neighbors))
        assessment = ('insufficient_evidence' if not summary['quality_adequate'] else
                      'suspicious' if equipment['suspicious'] else 'normal')
        observation = ('RF amplitude crosses the exploratory deviation threshold.' if assessment == 'suspicious' else
                       'RF evidence is insufficient for the deviation check.' if assessment == 'insufficient_evidence' else
                       'The RF deviation check does not cross its exploratory threshold.')
        limitations += ['Sparse RF NaNs mean no new update; never backfill unknown leading data.',
                        'RF amplitude alone cannot corroborate beam disturbance or establish a unique cause.',
                        'Neighbor column presence does not establish station completeness.']
        checks = ('equipment', 'neighbors', 'quality')
    else:
        beam = beam_summary(meta, arrays)
        charge = beam_summary(meta, arrays, charge_only=True)
        compact = {}
        for row in beam['channels']:
            compact[row['channel']] = {key: int(value) if isinstance(value, bool) else value
                                       for key, value in row.items() if key != 'channel'}
            j = channels.index(row['channel'])
            candidate = ((arrays['bpm_time_ns'] >= meta['candidate_start_ns']) &
                         (arrays['bpm_time_ns'] <= meta['candidate_end_ns']))
            valid = np.isfinite(arrays['bpm'][:, j])
            if not row['channel'].endswith('TMIT'):
                valid &= np.isfinite(arrays['bpm'][:, j-1]) & (arrays['bpm'][:, j-1] >= 1e8) & (arrays['bpm'][:, j] != 100)
            compact[row['channel']]['valid_samples'] = int(np.sum(candidate & valid))
            compact[row['channel']]['masked_samples'] = int(np.sum(candidate & ~valid))
        onsets = [r['first_sustained_ns'] for r in beam['channels'] if r['first_sustained_ns'] is not None]
        summary.update(channels=compact, quality_adequate=int(beam['quality_adequate']),
                       disturbance_detected=int(beam['disturbance_detected']),
                       charge_disturbance_detected=int(charge['disturbance_detected']),
                       samples_in_candidate=beam['samples_in_candidate'], onset_ns=min(onsets) if onsets else None)
        assessment = ('insufficient_evidence' if not beam['quality_adequate'] else
                      'suspicious' if beam['disturbance_detected'] else 'normal')
        observation = ('Charge-valid beam checks detect a sustained disturbance.' if assessment == 'suspicious' else
                       'Beam quality is insufficient for a reliable heuristic assessment.' if assessment == 'insufficient_evidence' else
                       'Beam checks do not detect a sustained disturbance at the exploratory threshold.')
        limitations += ['Low-charge positions and sentinel values are masked.',
                        'A negative heuristic is limited evidence, not proof of normality.',
                        'Beam observations cannot establish a unique RF cause.']
        checks = ('beam', 'charge_validity', 'quality')
    refs = ['T-' + hashlib.sha256(json.dumps(dict(event_id=event_id, instrument=instrument,
             analysis=kind, summary=summary), sort_keys=True, allow_nan=False).encode()).hexdigest()[:12]
            for kind in checks]
    report = dict(kind='node_report', instrument=instrument, role_source=role_source,
                  event_id=event_id, assessment=assessment, observation=observation,
                  summary=summary, tool_refs=refs,
                  raw_bytes_held=sum(int(a.nbytes) for a in arrays.values()),
                  payload_bytes=0, limitations=limitations)
    serialize_node_report(report)
    return report
