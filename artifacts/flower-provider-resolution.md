# Flower provider recovery and live investigation review

Provider access is resolved. The existing Pacterra credential is loaded into the environment that launches SuperLink; no key value was copied into this project, printed, committed, or intentionally logged. The optional Nebius adapter was not used or changed during this work.

## Verified configuration

- Installed Flower: 1.39.0. The model worker forwards the Responses request and model ID unchanged.
- Pacterra’s `training/pacterra-mini/agent/agent_app.py` uses the injected Flower runtime client and `gpt-5.6-sol`; `backend/pf02/README.md` documents `https://api.openai.com/v1/responses` with `FLWR_MODEL_API_KEY`.
- The existing ignored, mode-0600 `../Pacterra/.env.local` contains the credential. This project’s ignored mode-0600 `.env.local` sources that file and configures the documented OpenAI Responses endpoint. It contains no copied key.
- `scripts/start.sh` now loads `.env.local` before executing SuperLink. The model remains gpt-5.6-sol; its direct-provider identifier replaces the Flower-hosted routing name `openai/gpt-5.6-sol`. The UI obtains its default from `pyproject.toml`.
- Exact live integration: AgentApp → OpenAI SDK using Flower-injected runtime URL/token → Flower model worker → OpenAI `/v1/responses`. These are real Flower-executed runs, not direct SDK bypasses.

## Completed requested checks

| Check | Run ID | Model / tool calls | Wall time | Final model enum | Evidence review |
|---|---|---|---|---|---|
| slac-001 investigation | [4210859065409350628](runs/4210859065409350628.json) | 8 / 14 | 75.635 s | corroborated | Main conclusion supported, with a numerical onset caveat |
| slac-001 human follow-up | [16085169257987671247](runs/16085169257987671247.json) | 9 / 11 | 85.168 s | corroborated | Main answer supported, with the same numerical onset caveat |
| slac-003 dashboard investigation | [1795740798858395915](runs/1795740798858395915.json) | 5 / 7 | 50.928 s | corroborated | Explanation broadly supported; headline assessment is not supported for the intended beam-corroboration question |

The human follow-up continued series `10907516783703553172`. It asked: “Could low charge explain the position readings, and does the timing evidence establish that this RF station caused the beam disturbance?” Its lead requested additional evidence and delegated a focused equipment follow-up. The slac-003 check was submitted through the existing Streamlit dashboard; the completed page showed specialist findings, tool requests, the evidence ledger, the final assessment and human follow-up input.

Every linked trace preserves the operator-visible specialist/coordinator exchanges, deterministic tool results, original final model assessment and usage. Private chain-of-thought was not collected. The review is added separately; original model findings were not rewritten.

## Claim-level review

### slac-001 investigation

A large RF amplitude excursion co-occurs with beam disturbance evidence; unique RF causation is not established.

- The supporting statement equates first_sustained_ns with exact low-charge onset for three TMIT channels. DMPH:502 and LTUH:450 first cross TMIT < 1e8 one sample (8.388611 ms) later. The tool onset is the combined robust-deviation OR low-charge criterion, not exclusively low charge.

### slac-001 human follow-up

Low charge invalidates DMPH:502:Y, DMPH:693:Y and LTUH:450:X samples; LTUH:250:X has a separate 42-sample sustained excursion with valid charge. Native timing does not prove station causation.

- The supporting low-charge-onset statement repeats the one-sample precision error identified in the initial investigation.

### slac-003 dashboard investigation

The RF amplitude excursion is about 2.913%, but all four TMIT channels have zero low-charge samples and the beam tool detects no sustained disturbance. The explanation correctly states no beam corroboration.

- The final assessment enum is corroborated, while the narrative explicitly says the beam disturbance is not corroborated. It labels RF-only evidence rather than answering the intended RF-versus-beam investigation question. Treat this headline as a semantic validation failure, not a confirmed beam-disturbing fault.
- The exploratory negative beam result does not prove normality; sparse RF updates do not establish exact excursion duration.

The onset audit is saved separately in [slac-001-charge-onset-audit.json](slac-001-charge-onset-audit.json). It uses original local arrays after the run, not ground-truth labels or shifted timestamps. For DMPH:502 and LTUH:450 the exact first low-charge timestamp is 1604277200706075091 ns; the combined detector onset is 1604277200697686480 ns. DMPH:693 crosses the low-charge threshold at the latter timestamp.

## Fixes and unsuccessful attempts

- A genuine first live attempt [9495441432884253524](runs/9495441432884253524.json) failed channel validation. The workflow now provides the exact valid channel catalog, records rejected findings, and permits one correction-only turn within the unchanged 12-call shared budget. Regression tests confirm invalid channels remain rejected and the budget cannot be exceeded.
- [4781198549003856549](runs/4781198549003856549.json) was the first successful live slac-001 run. A subsequent SuperLink process interruption stopped [2001975716377699945](runs/2001975716377699945.json) and an in-progress dashboard check. No final assessment was accepted from the interrupted follow-up.
- A restored project runtime served the final requested sequence. A separate background launch attempt encountered an already occupied Fleet port and was not used. The startup script now selects `.flower/slac.sqlite` for future launches; restart durability of the active serving instance was not verified. Saved JSON traces do not depend on keeping that process alive.
- The original missing-key attempts remain in [flower-collaborative-pair.md](flower-collaborative-pair.md). They are historical failures, not current provider status.
- 28 tests passed, including two new bounded-correction tests. No mocked protocol fixture was substituted for a live run.

## Remaining limitations

The slac-003 headline exposes an assessment-definition problem: schema/reference checks cannot establish semantic support. Its explanation is useful, but “corroborated” must not be interpreted as evidence of beam impact. The slac-001 findings also contain the documented onset overprecision. Both need operator review; no fully automatic diagnostic validity is claimed.

The selected public extracts are small and incomplete; phase and interlock records requested by the agents are not available through current tools. No causal proof, validated fault-detector performance, cost estimate, safety improvement, or multiagent superiority is claimed. Pricing was not returned, so cost remains null. Baseline comparison was not part of this provider-recovery run.

Restart locally with `./scripts/start.sh` after stopping the existing project server. The key stays in Pacterra’s ignored local file; update that file locally if it expires. Keep the endpoint paired with the credential’s provider.
