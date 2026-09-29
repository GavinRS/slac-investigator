# Data access and scope

Retrieved on 2026-09-29 from the [SLAC dataset index](https://www.slac.stanford.edu/grp/ad/ard/rfanom/rfanom.html). Web-tool retrieval returned 502; direct HTTPS through the system TLS client succeeded. Python's system certificate store initially failed verification; the downloader uses curl with normal certificate verification. No TLS bypass. Acquisition finished within the 15-minute access budget.

The workspace initially contained only `.git`. No existing implementation was replaced.

## Files actually inspected

- `data/raw/rfanom.html`: original public index.
- `data/raw/description.pdf` and extracted `description.txt`: dataset schema and transformations.
- `data/raw/candidates_AMPL.csv`, `labels_AMPL.csv`, `candidates_AMM.csv`, `labels_AMM.csv`: complete small metadata files.
- `data/raw/osti.html`: downloaded [DOE catalog entry](https://www.osti.gov/biblio/1869296).
- Source `klys_anom_dset_AMPL.h5`: 3,222,346,816 bytes according to HTTP HEAD. Four candidate groups were read by verified 206 byte-range requests, downloading 4,980,736 HDF5 bytes total. No complete HDF5 download.
- Source `klys_anom_dset_AMM.h5`: 383,264,536 bytes according to HEAD. Its data arrays were not downloaded.
- `data/events/slac-001` through `slac-004`: extracted arrays and metadata. NPZ preserves source values. JSON arrays encode missing values as null and timestamps as integer nanoseconds. Tests compare JSON decoding to NPZ exactly, including missing values.
- `data/manifest.json`: source-group mapping, extraction hashes and selection description. `data/evaluation_labels.json`: separate evaluation-only labels.

The retrieved CSV counts are AMM: 1,269 candidates / 1,237 labels / 385 positive labels; AMPL: 3,208 candidates / 2,845 labels / 553 positive labels. Candidate records span November 2 to December 9, 2020 UTC. Candidate and label counts differ; unlabelled candidates must not be treated as negatives.

## Exact observed channels

Every extracted health array has 82 AMPL columns. The exact column list is in each event metadata JSON. Presence of a column is not evidence of continuous coverage, active operation or completeness. The selected station is the candidate metadata association, not a proven cause.

Eight BPM columns, in actual order:

1. `BPMS:DMPH:502:TMIT`
2. `BPMS:DMPH:502:Y`
3. `BPMS:DMPH:693:TMIT`
4. `BPMS:DMPH:693:Y`
5. `BPMS:LTUH:250:TMIT`
6. `BPMS:LTUH:250:X`
7. `BPMS:LTUH:450:TMIT`
8. `BPMS:LTUH:450:X`

The four health shapes are (725,82), (813,82), (821,82), (769,82). BPM shapes are (2075,8), (2075,8), (2076,8), (2076,8). These are measured values, not synthetic demonstrations.

## Timestamps, missingness and transforms

HDF5 `index` attributes contain integer nanoseconds since Unix epoch. UI plots subtract the candidate end using integer arithmetic before converting to seconds. RF and BPM timestamps remain unchanged. The source health data is sparse: NaN indicates no new station update. We hold a previously observed value only for plotting and time-weighted baseline calculation; no leading backfill or assumption that missing means zero. The cadence of the union of 82 station timestamps is not a station's sampling rate.

The [dataset description](https://www.slac.stanford.edu/grp/ad/ard/rfanom/description.pdf) documents asynchronous RF updates and an approximate reporting delay up to five seconds. That is a bounded interpretation aid, not a measured delay for these events. The timing tool reports observed onsets separately and never fits a lag.

BPM positions have already been transformed in the published data. Low-charge positions may contain sentinel values rather than physical readings; tools mask positions when the associated TMIT is below 1e8. Source position scaling is retained, not reversed or reapplied. Units are labeled as source units/scaled positions because no additional physical calibration has been verified.

## Labels and supported tasks

CSV labels have `start`, `end`, `is_anom`, `anom_type`. `is_anom` is a human boolean anomaly label; `anom_type` is `f` (fault), `s` (sustained anomaly), or blank. This demo selects the first two positive and first two negative AMPL cases. The selection is deliberately illustrative and unsuitable for estimating population accuracy. Labels are excluded from AgentApp bundles and tool results. The first labeled plot is a development artifact, excluded from the app.

Supported prototype task: replay a supplied RF candidate and assess whether available beam measurements corroborate a disturbance, documenting uncertainty. Binary comparison is against anomaly labels, not a unique-cause ground truth. No fault-type classifier is implemented.

Unsupported: raw-stream anomaly detection validation; unique causal station diagnosis; protein/sample diagnosis; phase-based methods; synchronized protein measurements; known per-event fixed delays; live control. Random `samples` groups exist but are not extracted or assumed to be universally clean negatives.

## Licensing

No explicit dataset reuse license was located in the inspected SLAC index, description PDF, or DOE catalog HTML. Public download access is verified; redistribution rights are not established. The papers' licenses must not be treated as dataset licenses. No dataset license has been invented, and nothing has been published externally.

## Research context

The [2022 study](https://arxiv.org/abs/2206.04626) already presents automated RF fault detection; this prototype does not claim novelty for detection. The [2025 phase study](https://arxiv.org/html/2505.16052v1) uses a different, richer phase signal. Those phase measurements are not present in this extract. Our investigation/explanation workflow has not demonstrated improved human diagnosis, safety, or multiagent superiority.
