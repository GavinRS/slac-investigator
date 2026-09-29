"""Deterministic, read-only evidence tools. No label access, writes, or alignment fitting."""
import hashlib, json
import numpy as np
from .data import load_event
from .instruments import load_slice
KINDS=('quality','equipment','beam','charge_validity','timing','neighbors')
INSTRUMENT_KINDS={'rf':('equipment','neighbors','quality'),'ltu':('beam','charge_validity','quality'),'dump':('beam','charge_validity','quality')}

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

def analyze(event_id,kind,instrument=None,data=None):
    """instrument restricts to that node's checks on its own slice; data=(meta,arrays) skips loading."""
    if kind not in (INSTRUMENT_KINDS[instrument] if instrument else KINDS):raise ValueError('Unknown analysis')
    m,a=data or (load_slice(event_id,instrument) if instrument else load_event(event_id)); limitations=list(m['limitations'])
    h=a.get('health_time_ns',a.get('bpm_time_ns'));b=a.get('bpm_time_ns',h)
    if kind=='quality':
        result={k:dict(**timing_quality(a[k+'_time_ns']),nonfinite_values=int(np.sum(~np.isfinite(a[k]))),channels=a[k].shape[1]) for k in ['health','bpm'] if k in a}
        if 'health' in a:result['rf_missing_semantics']='NaN means no new update; hold only a known previous value; no backfill. RF row cadence is NOT per-station sampling rate.'
    elif kind=='equipment':result=equipment_summary(m,a)
    elif kind in ('beam','charge_validity'):result=beam_summary(m,a,charge_only=kind=='charge_validity')
    elif kind=='neighbors':
        all_stations=[equipment_summary(m,a,c.removesuffix(':AMPL')) for c in m['channels']['health']]
        result=dict(available_columns=len(all_stations),unknown_baselines=sum(r['baseline_time_weighted_median'] is None for r in all_stations),suspicious=[r for r in all_stations if r['suspicious']],caution='Column presence does not establish continuous station operation or complete neighboring records.')
    else:
        eq=equipment_summary(m,a);beam=beam_summary(m,a)
        onsets=[r['first_sustained_ns'] for r in beam['channels'] if r['first_sustained_ns'] is not None]
        result=dict(recorded_rf_updates=eq['updates'],beam_onsets_ns=onsets,candidate_interval_ns=[m['candidate_start_ns'],m['candidate_end_ns']],documented_rf_reporting_delay_s=[0,5],delay_is_approximate=True,applied_shift_s=0,causal_attribution='Not established; asynchronous observations and candidate association alone cannot identify a unique cause.')
    body=dict(event_id=event_id,analysis=kind,source=m['source_url'],hdf5_group=m['hdf5_group'],interval_ns=[int(h[0]) if kind in ('equipment','neighbors','quality') else int(b[0]),int(h[-1]) if kind in ('equipment','neighbors','quality','timing') else int(b[-1])],result=result,limitations=limitations)
    body['ref']='T-'+hashlib.sha256(json.dumps(body,sort_keys=True).encode()).hexdigest()[:12]
    return body

def node_summary(event_id,instrument,arrays,role_source='assigned',meta=None):
    """Spec §3 node_report: summary numbers only, never raw samples. meta defaults to the bundled slice's."""
    m=meta or load_slice(event_id,instrument)[0]; runs=[analyze(event_id,k,instrument,(m,arrays)) for k in INSTRUMENT_KINDS[instrument]]
    r={x['analysis']:x['result'] for x in runs}; q=r['quality']['health' if instrument=='rf' else 'bpm']
    quality=dict(samples=q['samples'],nonfinite_values=q['nonfinite_values'],fraction_120hz=q['fraction_120hz'],max_gap_s=q['max_gap_s'])
    if instrument=='rf':
        e,n=r['equipment'],r['neighbors']; hits=sorted(x['channel'] for x in n['suspicious'])
        summary=dict(station=e['channel'],baseline=e['baseline_time_weighted_median'],peak_deviation_pct=e['max_abs_deviation_pct'],updates_in_window=len(e['updates']),finite_updates=e['finite_updates'],no_update_fraction=e['no_update_fraction'],neighbor_columns=n['available_columns'],neighbor_unknown_baselines=n['unknown_baselines'],neighbors_suspicious=len(hits),quality=quality)
        assessment='insufficient_evidence' if e['baseline_time_weighted_median'] is None else 'suspicious' if e['suspicious'] else 'normal'
        observation=f"{e['channel']} peak deviation {e['max_abs_deviation_pct'] or 0:.2f}% from baseline ({len(e['updates'])} updates in window); {len(hits)} of {n['available_columns']} stations deviate >=0.5%."
    else:
        bm=r['beam']; onsets=[c['first_sustained_ns'] for c in bm['channels'] if c['first_sustained_ns'] is not None]
        chans={c['channel']:dict(baseline=c['baseline_median'],peak_robust_z=c['peak_robust_z'],sustained=c['sustained'],longest_consecutive_samples=c['longest_consecutive_samples'],onset_ns=c['first_sustained_ns'],low_charge_samples=c['low_charge_samples'],invalid_position_samples=c['invalid_position_samples']) for c in bm['channels']}
        summary=dict(disturbance_detected=bm['disturbance_detected'],quality_adequate=bm['quality_adequate'],onset_ns=min(onsets) if onsets else None,samples_in_candidate=bm['samples_in_candidate'],channels=chans,quality=quality)
        assessment='suspicious' if bm['disturbance_detected'] else 'normal' if bm['quality_adequate'] else 'insufficient_evidence'
        observation=f"{sum(c['sustained'] for c in bm['channels'])} of {len(chans)} {instrument} channels show a sustained excursion in the candidate window; data quality {'adequate' if bm['quality_adequate'] else 'not adequate'}."
    report=dict(kind='node_report',instrument=instrument,role_source=role_source,event_id=event_id,assessment=assessment,observation=observation,summary=summary,tool_refs=[x['ref'] for x in runs],raw_bytes_held=int(sum(v.nbytes for v in arrays.values())),payload_bytes=0,limitations=list(m['limitations']))
    while report['payload_bytes']!=(n:=len(json.dumps(report).encode())):report['payload_bytes']=n
    return report
