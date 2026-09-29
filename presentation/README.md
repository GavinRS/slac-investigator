# Beamline Investigator — scrolling presentation

A seven-chapter visual explanation of the beamline followed by an investigation grounded in `slac-001`. The existing operator console and Python/Flower backend remain separate and unchanged.

## Run

```sh
cd presentation
npm ci
npm run dev
```

Open http://127.0.0.1:3000. For a complete production bundle, run:

```sh
npm run build
cd ../frontend
npm run build
```

`frontend/dist/index.html` is the operator console; `frontend/dist/story/index.html` is the new presentation. The presentation also bundles a copy of the existing console at `./console/`, so `frontend/story` can be hosted independently. Relative asset paths and self-hosted fonts keep it portable.

## Evidence and scientific boundaries

- `prepare-evidence.mjs` copies exact points and original saved reports from `frontend/data/slac-001.json` before each build. Generated `src/evidence.json` is ignored by Git.
- Equipment: `KLYS:LI29:11:AMPL`, 20 finite updates. A step line holds only previously known values; dots identify recorded updates. A held segment is not a continuous measurement.
- Beam: charge-qualified `BPMS:LTUH:250:X`, with negative excursions preserved. The y-axis uses source-scaled units, not millimeters.
- Charge comparison: `BPMS:DMPH:502:TMIT` and `BPMS:LTUH:250:TMIT`. The source criterion is TMIT < 1e8; invalid position samples remain masked.
- Both primary plots use the same native time axis and the candidate interval from -5.3 to 0 seconds. No timing offset is introduced. There are no post-candidate BPM samples in the extract.
- The protein, equipment arrangement, and visible disturbance are illustrations, not reconstructions. Electrons travel through the accelerator; X-rays are produced at the illustrative undulator.
- Investigation and challenge controls are explicitly recorded playback, using saved Flower runs. They do not issue new model calls or control accelerator hardware.
- Presentation captions summarize archived reports but do not convert their older assessment enum into current schema v2. Original reports are available in the evidence dialog.
- The supported conclusion is an RF anomaly and a corroborated beam disturbance. Asynchronous reporting, 28 unknown neighboring baselines, and missing phase/power/interlock evidence prevent a unique-cause conclusion.

## Demo sequence

Scroll from the protein to the accelerator, then into the aligned signal plots. Click **Investigate**, let the four recorded findings play, then move to the low-charge challenge and click **Review the low-charge challenge**. End with the two separate conclusions: beam disturbance supported; unique cause not established.

Keyboard-focusable controls, reduced-motion support, mobile layouts, and a readable non-WebGL fallback are included. No requests are made to Lovable by this presentation.
