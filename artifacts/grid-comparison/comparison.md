# Four-case demonstration comparison

Four label-selected demonstrations; not representative or held-out; no superiority claim is supported.

Model: `flwrlabs/endeavor-1.0`.

Failed attempts remain in this table even when a later retry succeeds.

| Event | Mode | Status | Agreement | Model calls | Input / output tokens | End-to-end s | Data shared %* | Grid |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| slac-001 | baseline | completed | N/A | 2 | N/A / N/A | 130.575 | 100.0 | centralized |
| slac-001 | baseline | failed | N/A | N/A | N/A / N/A | N/A | N/A | N/A |
| slac-001 | grid | completed | N/A | 5 | N/A / N/A | 160.798 | 1.396 | 3 nodes; Grid |
| slac-001 | grid | failed | N/A | N/A | N/A / N/A | N/A | N/A | N/A |
| slac-002 | baseline | completed | N/A | 2 | N/A / N/A | 242.905 | 100.0 | centralized |
| slac-002 | grid | completed | N/A | 5 | N/A / N/A | 168.542 | 1.238 | 3 nodes; Grid |
| slac-003 | baseline | failed | N/A | N/A | N/A / N/A | N/A | N/A | N/A |
| slac-003 | grid | completed | N/A | 5 | N/A / N/A | 312.206 | 1.187 | 3 nodes; Grid |
| slac-004 | baseline | completed | N/A | 2 | N/A / N/A | 126.867 | 100.0 | centralized |
| slac-004 | grid | completed | N/A | 5 | N/A / N/A | 236.889 | 1.256 | 3 nodes; Grid |

*Grid percentage is serialized summary payload bytes / raw instrument bytes held, not raw-sample disclosure. Baseline 100% denotes conceptual centralized access to all instrument data; it does not mean raw arrays were sent to the model. Local fallback is explicitly identified and does not demonstrate remote data locality.

N/A: source RF anomaly labels are not adjudicated beam-disturbance or unique-cause labels.
