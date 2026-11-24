"""Check the frozen CARE-VLA release and report per-kitchen VLM scores."""
from collections import Counter, defaultdict
import csv
from hashlib import sha256
import json
from pathlib import Path
import sys
from zipfile import ZipFile

archive_path, predictions_path, output = map(Path, sys.argv[1:])
observed = "observed_contact"
binary_labels = {observed: "yes", "no_contact_in_search": "no"}
link_fields = {"video", "log", "independent", "independent_log", "source_log", "witness_state"}

with ZipFile(archive_path) as archive:
    entries = archive.namelist()
    assert len(set(entries)) == len(entries)
    contents = {}
    for line in archive.read("SHA256SUMS.txt").decode().splitlines():
        digest, name = line.split("  ", 1)
        assert name not in contents
        contents[name] = sha256(archive.read(name)).hexdigest()
        assert contents[name] == digest, name
    assert set(contents) == set(entries) - {"SHA256SUMS.txt"}

    questions = [json.loads(line) for line in archive.read("questions.jsonl").splitlines()]
    labels = [json.loads(line) for line in archive.read("labels.jsonl").splitlines()]
    answers = {row["id"]: row for row in labels}
    assert len(questions) == len({q["id"] for q in questions}) == len(labels) == len(answers) == 280
    assert set(answers) == {q["id"] for q in questions}
    grouped_splits = defaultdict(set)
    image_splits = defaultdict(set)
    coverage = Counter()
    positives_with_video = 0
    evidence_refs = 0
    images = set()
    for question in questions:
        label = answers[question["id"]]
        assert question["cohort"] == label["cohort"]
        assert label["answer"] in binary_labels
        split = (question["cohort"], question["split"])
        grouped_splits[question["group"]].add(split)
        images.add(question["image"])
        image_splits[contents[question["image"]]].add(split)
        coverage["/".join((*split, label["answer"]))] += 1
        evidence = label["evidence"]
        assert evidence
        for field, name in evidence.items():
            if field in link_fields:
                assert name in contents, (question["id"], field, name)
                evidence_refs += 1
        if label["answer"] == observed:
            assert evidence["video"].endswith(".mp4")
            assert evidence.get("hand_contact", evidence.get("outcome") == "ACCESS_WITNESS") is True
            assert ("independent" in evidence) or ("independent_log" in evidence)
            positives_with_video += 1

assert sum(len(splits) > 1 for splits in grouped_splits.values()) == 0
assert sum(len(splits) > 1 for splits in image_splits.values()) == 0
assert len(images) == 144 and len(grouped_splits) == 72 and positives_with_video == 56
fresh = {row["id"]: row for row in questions if row["cohort"] == "fresh"}
assert len(fresh) == 126
buckets = defaultdict(list)
seen = set()
with predictions_path.open(encoding="utf-8-sig", newline="") as f:
    for row in csv.DictReader(f):
        qid = row["question_id"]
        question = fresh[qid]
        run = (row["model"], row["mode"], row["control"])
        assert (run, qid) not in seen
        seen.add((run, qid))
        assert row["gold"] == binary_labels[answers[qid]["answer"]]
        assert row["response"] in ("yes", "no")
        kitchen = int(question["group"].split("-")[1][1:])
        buckets[(*run, kitchen)].append(row)

assert len(buckets) == 36 and len(seen) == 1512
per_kitchen = []
for (model, mode, control, kitchen), bucket in sorted(buckets.items()):
    positive = sum(row["gold"] == "yes" for row in bucket)
    negative = len(bucket) - positive
    groups = len({fresh[row["question_id"]]["group"] for row in bucket})
    assert (groups, positive, negative) == (12, 9, 33)
    tp = sum(row["gold"] == row["response"] == "yes" for row in bucket)
    tn = sum(row["gold"] == row["response"] == "no" for row in bucket)
    per_kitchen.append(
        dict(model=model, mode=mode, control=control, layout=kitchen, groups=groups,
             questions=len(bucket), positive=positive, tp=tp, fp=negative-tn, tn=tn,
             balanced_accuracy=0.5 * (tp / positive + tn / negative))
    )

output.mkdir(parents=True, exist_ok=True)
with (output / "fresh_vlm_by_kitchen.csv").open("w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(per_kitchen[0]))
    writer.writeheader()
    writer.writerows(per_kitchen)
report = {
    "questions": len(questions),
    "groups": len(grouped_splits),
    "image_files": len(images),
    "distinct_image_byte_hashes": len(image_splits),
    "content_hashes_verified": len(contents),
    "resolved_evidence_references": evidence_refs,
    "contact_records_with_video_and_independent_check_path": positives_with_video,
    "groups_crossing_cohort_split": 0,
    "image_hashes_crossing_cohort_split": 0,
    "label_coverage": dict(sorted(coverage.items())),
    "fresh_scored_items_checked": len(seen),
}
(output / "dataset_integrity.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report))
