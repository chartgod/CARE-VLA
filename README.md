# CARE-VLA

**A replay benchmark for post-task access in simulated homes**

Can someone reach an object after a household robot finishes its task? CARE-VLA pairs visual questions with labels and physics replay evidence from simulated kitchens. Paired cases hold the starting scene fixed while changing what the simulated actor can do or how a fixture can move.

[Download the dataset and replay bundle](https://github.com/chartgod/CARE-VLA/releases/download/v1.2.0/CARE-VLA_Reviewer_Core.zip) · [Browse the release](https://github.com/chartgod/CARE-VLA/releases/tag/v1.2.0) · [Run the checks](#reproduce-the-released-results)

| Visual questions | Initialized scene groups | Observed-contact labels |
| :---: | :---: | :---: |
| **280** | **72** | **56** |

![Three simulation frames from one drawer scene. The same starting image is used for both runs. The actor touches the marker when the drawer can slide. With the drawer locked ajar, the search finds no contact.](assets/drawer-replay.jpg)

*Example from the released test group `drawer-L01-S2670100`. The center and right panels show the last frames of the free and locked replays.*

## What the benchmark measures

CARE-VLA covers rotary trays, drawers, and corridors. The release contains 28 development questions and 252 test questions. The visual test includes a separate set from three held-out kitchen layouts.

| Task | Model input | Question |
| --- | --- | --- |
| **Endpoint forecasting** | Saved scene and a question specifying the actor's actions and fixture condition | Will the actor touch the target during the tested replay? |
| **Evidence verification** | Last replay frame and its question | Did the actor touch the target? |

Join `questions.jsonl` and `labels.jsonl` by `id` to find each reference label and its evidence paths. Positive labels include a replay clip and a separate surface-distance check. A no-witness label means the specified search found no contact. Labels describe a synthetic actor and an inert target in simulation.

## Downloads

| File | Contents |
| --- | --- |
| [Dataset and replay bundle](https://github.com/chartgod/CARE-VLA/releases/download/v1.2.0/CARE-VLA_Reviewer_Core.zip) · 446 MB | Questions, labels, images, evidence clips, raw model responses, scorers, and a portable MuJoCo replay for three boundary cases |
| [Evidence index and figure data](https://github.com/chartgod/CARE-VLA/releases/download/v1.2.0/CARE-VLA_Evidence_Index_and_Figure_Data.zip) · 22 kB | Links from question IDs to evidence and the data behind selected results figures |

Extract the core bundle and open `README_REVIEWER.md`. It lists the included archives, their checksums, and the dependencies for each replay.

## Reproduce the released results

### Score the archived model responses

Use Python 3.11 or newer. Run the following commands from the extracted core bundle with the dataset ZIP kept intact.

```sh
python -m zipfile -e CARE-VLA_VLM_Audit_20261124.zip vlm
python -I vlm/source/analyze_feedback.py vlm CARE-VLA_Dataset_v1.2.zip scored --experiment vision
python -I Validation/audit_release.py CARE-VLA_Dataset_v1.2.zip scored/vlm_rescored_items.csv audited
```

Compare `scored/` with `vlm/Results/` and `audited/` with `Validation/`. The checks score saved responses, audit dataset and split integrity, and report results by held-out kitchen.

### Replay three boundary cases on CPU

Extract `CARE-VLA_Table9_Reviewer.zip` and follow its `README_REVIEWER.md`. The verifier uses pinned MuJoCo dependencies to replay one additional contact and two unresolved cases at the original 4 mm decision threshold. It recalculates the summary from the archived ledger after checking those three cases. Full replay of all 36 fresh initializations requires the separate compiled-model companion described in the core bundle.

## Citation and attribution

> Seung Heon Lee. 2026. *CARE-VLA: A Replay Benchmark for Post-Task Access in Simulated Homes*. Dataset, version 1.2.0. [GitHub release](https://github.com/chartgod/CARE-VLA/releases/tag/v1.2.0).

See [source attribution](ATTRIBUTION.md) for RoboCasa scene and asset credits and upstream licensing.
