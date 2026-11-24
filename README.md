# CARE-VLA

CARE-VLA is an evidence-linked benchmark dataset for post-task access in simulated child–robot shared homes. It links questions about a synthetic actor's capabilities to stored scenes, simulator contact witnesses and bounded no-witness outcomes.

Version 1.2 contains 280 questions over 72 initialized groups. The original and fresh test sets include 252 questions and 51 physical contact witnesses. The dataset reports endpoint forecasting and evidence verification separately. Three held-out kitchens supply the fresh visual test. The compiled-model replay in the companion study reproduced its 198 branch outcomes and 27 contact witnesses in a separate Windows environment.

## Data and reproducibility

Download CARE-VLA_Reviewer_Core.zip from the [v1.2 release](https://github.com/chartgod/CARE-VLA/releases/tag/v1.2.0). It contains the unmodified dataset archive, the image and text input audit, and the standalone Table 9 verifier with three compiled replay cases. Extract the asset and start with README_REVIEWER.md. The full 36-case physical replays require a separate compiled-model companion.

Run both VLM checks with Python 3.11 or newer from this repository directory after extracting the core bundle into core/.

    python -m zipfile -e core/CARE-VLA_VLM_Audit_20261124.zip audit
    python -I tools/analyze_feedback.py audit core/CARE-VLA_Dataset_v1.2.zip scored --experiment vision
    python -I tools/audit_release.py core/CARE-VLA_Dataset_v1.2.zip scored/vlm_rescored_items.csv verified

Compare the generated scores to audit/Results and the integrity checks and per-kitchen scores to core/Validation. For the Table 9 replay, follow README_REVIEWER.md in core/CARE-VLA_Table9_Reviewer.zip. It uses CPU physics with pinned MuJoCo dependencies.

The task uses simulated contact with an inert marker, a synthetic actor, and explicit capability and motion bounds. A no-witness label describes the registered physical search. See ATTRIBUTION.md for upstream scene and simulator provenance.

## Citation

Seung Heon Lee. CARE-VLA: An Evidence-Linked Benchmark Dataset for Post-Task Access in Simulated Child–Robot Shared Homes. Manuscript.
