"""Summarize verified TAAS response cohorts from trace and response archives."""
from argparse import ArgumentParser
from collections import Counter, defaultdict
import csv
from hashlib import sha256
import json
from pathlib import Path
import re
from statistics import median, mean
from zipfile import ZipFile

ACCESS = "ACCESS_WITNESS"
CLEAR = "BLOCKED_IN_SEARCH"
METHODS = ("fixed", "geometry", "replay")
STABLE = ("C0", "C1", "C2")
FAMILIES = ("nominal", "higher_damping", "low_support_friction", "mechanical_stop")
MODELS = ("qwen25vl_72b", "internvl3_78b")


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def lines(value):
    return [json.loads(line) for line in value.decode("utf-8-sig").splitlines() if line.strip()]


def table(path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def save(root, name, value):
    (root / name).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def placement(root, out):
    directory = root / "placement_matched/test"
    source = csv.DictReader((root / "source/placement_assignments.csv").read_text().splitlines())
    pairs = {}
    for design in source:
        key = f'L{design["layout"]}-S{design["seed"]}'
        group = directory / key
        case = load(group / "case.json")
        verification = load(group / "independent_verification.json")
        assert case["status"] in {"complete", "no_held_start"}
        assert case["layout"] == int(design["layout"]) and case["style"] == int(design["style"])
        assert case["seed"] == int(design["seed"])
        assert verification["status"] == ("verified" if case["status"] == "complete" else "no_held_start")
        for phase in (*STABLE, "C1_to_C2"):
            trial = {}
            for method in METHODS:
                attempt = group / phase / method / "attempt.json"
                record = load(attempt) if case["status"] == "complete" else {}
                if record:
                    assert record["common_held_sha256"] == case["held_start_sha256"]
                    assert record["method"] == method and record["final_profile"] == ("C2" if phase == "C1_to_C2" else phase)
                    checked = next(r for r in verification["attempts"] if r["phase"] == f"{phase}/{method}")
                    assert len(checked["executions"]) == len(record["executions"])
                    if record["task_success"]:
                        assert checked["executions"][-1]["status"] == record["actor_access"]
                    if record["qualified"]:
                        assert 0 <= record["peak_unintended_n"] <= 2
                        assert 0 <= record["landing_speed_m_s"] <= .5
                trial[method] = {
                    "layout": case["layout"], "style": case["style"], "seed": case["seed"],
                    "case": key, "phase": phase, "method": method, "shared_held_start": bool(record),
                    "task_success": record.get("task_success", False),
                    "qualified": record.get("qualified", False),
                    "access_status": record.get("actor_access"),
                    "qualified_no_witness": record.get("qualified", False) and record.get("actor_access") == CLEAR,
                    "destination": record.get("selected_destination"),
                    "distance_m": record.get("path_m"),
                    "decision_s": record.get("decision_wall_s"),
                    "peak_contact_n": record.get("peak_unintended_n"),
                    "landing_speed_m_s": record.get("landing_speed_m_s"),
                    "actual_executions_independently_replayed": len(record.get("executions", [])),
                    "initial_choice": record.get("initial_choice"),
                }
            pairs[key, phase] = trial
    assert len(pairs) == 48 and len(list(directory.glob("L*"))) == 12
    summary = []
    for condition in ("stable", "C1_to_C2"):
        groups = [p for (_, phase), p in pairs.items() if (phase in STABLE) == (condition == "stable")]
        paired_path = [p for p in groups if all(x["qualified_no_witness"] for x in p.values())]
        for method in METHODS:
            s = [p[method] for p in groups]
            qualified = [v for v in s if v["qualified"]]
            measured = [v["decision_s"] for v in s if v["decision_s"] is not None]
            summary.append({
                "condition": condition, "method": method, "assigned": len(s),
                "common_held": sum(v["shared_held_start"] for v in s),
                "task_completed": sum(v["task_success"] for v in s), "qualified": len(qualified),
                "completed_contact_witness": sum(v["task_success"] and v["access_status"] == ACCESS for v in s),
                "contact_witness": sum(v["access_status"] == ACCESS for v in qualified),
                "uncertain": sum(v["access_status"] == "UNCERTAIN" for v in qualified),
                "qualified_no_witness": sum(v["qualified_no_witness"] for v in s),
                "rotary_qualified": sum(v["destination"] == "support_center" for v in qualified),
                "decision_median_s": median(measured) if measured else None,
                "paired_distance_n": len(paired_path),
                "paired_distance_mean_cm": 100 * mean(p[method]["distance_m"] for p in paired_path) if paired_path else None,
                "independent_executions": sum(v["actual_executions_independently_replayed"] for v in s),
            })
    table(out / "placement_trials.csv", [r for pair in pairs.values() for r in pair.values()])
    table(out / "placement_summary.csv", summary)
    return summary


def fixtures(root, out):
    import numpy as np

    source = csv.DictReader((root / "source/fixture_assignments.csv").read_text().splitlines())
    result = []
    for design in source:
        key = f'L{design["layout"]}-S{design["seed"]}'
        group = root / "fixtures/test" / key
        rerun = root / "fixtures_verified/test" / key
        case, audit = load(group / "result.json"), load(rerun / "result.json")
        assert (case["layout"], case["style"], case["seed"]) == tuple(int(design[k]) for k in ("layout", "style", "seed"))
        assert case["nominal_model_sha256"] == audit["nominal_model_sha256"]
        for name in ("initial", "stationary"):
            assert all(case["controls"][name][k] == audit["controls"][name][k] for k in ("status", "source_sha256"))
        assert len(case["branches"]) == len(audit["branches"]) == 8
        with np.load(group / "states.npz", allow_pickle=False) as original, np.load(
                rerun / "states.npz", allow_pickle=False) as reproduced:
            assert set(original.files) == set(reproduced.files)
            bitwise = {k: bool(np.array_equal(original[k], reproduced[k])) for k in original.files}
        for first, other in zip(case["branches"], audit["branches"]):
            keys = ("condition", "profile", "geometry", "new_witness", "source_sha256",
                    "target_supported_at_start", "stop_initial_clear")
            assert all(first[k] == other[k] for k in keys)
            assert first["physics"]["status"] == other["physics"]["status"]
            name, profile = first["condition"], first["profile"]
            witness = f"{name}_{profile}_witness"
            result.append({
                "case": key, "layout": case["layout"], "style": case["style"], "seed": case["seed"],
                "condition": name, "profile": profile, "geometry": first["geometry"],
                "physics": first["physics"]["status"], "new_witness": first["new_witness"],
                "start_eligible": first["stop_initial_clear"] and first["target_supported_at_start"],
                "bitwise_start": bitwise[name + "_source"], "bitwise_witness": bitwise.get(witness),
                "rotation_rad": first["physics"]["peak_sampled_rotation_rad"],
                "relative_slip_mm": first["physics"]["peak_sampled_relative_slip_m"] * 1000,
                "geometry_eval_s": first["geometry_wall_s"], "physics_eval_s": first["physics"]["wall_s"],
                "independent_surface_gap_m": first["physics"]["independent_surface_gap_m"],
            })
    assert len(result) == 96
    summary = []
    for profile in ("C0", "C2"):
        for kind in FAMILIES:
            s = [r for r in result if r["profile"] == profile and r["condition"] == kind]
            eligible = [r for r in s if r["start_eligible"]]
            summary.append({
                "profile": profile, "condition": kind, "assigned": len(s), "eligible": len(eligible),
                "geometry_positive": sum(v["geometry"] == ACCESS for v in eligible),
                "physics_witnesses": sum(v["physics"] == ACCESS for v in eligible),
                "new_witnesses": sum(v["new_witness"] for v in eligible),
                "geometry_only_positive": sum(v["geometry"] == ACCESS and v["physics"] == CLEAR for v in eligible),
                "physics_only_witness": sum(v["geometry"] == CLEAR and v["physics"] == ACCESS for v in eligible),
                "uncertain": sum(v["physics"] == "UNCERTAIN" for v in eligible),
                "max_slip_mm": max((v["relative_slip_mm"] for v in eligible), default=None),
                "bitwise_start": sum(v["bitwise_start"] for v in eligible),
                "bitwise_witness": sum(v["bitwise_witness"] is True for v in eligible),
            })
    table(out / "rotary_conditions.csv", result)
    table(out / "rotary_summary.csv", summary)
    return summary


def binary(raw):
    cleaned = raw.strip()
    matched = re.fullmatch(r"\x60{3}(?:json)?\s+([\s\S]*?)\s*\x60{3}", cleaned, re.I)
    try:
        value = json.loads(matched[1] if matched else cleaned)
    except ValueError:
        return "unparsed"
    return value["answer"] if isinstance(value, dict) and set(value) == {"answer"} and value["answer"] in {
        "yes", "no"} else "unparsed"


def predictions(records):
    result = {p["id"]: p for p in records}
    assert len(result) == len(records)
    return result


def vision(root, out, dataset):
    results = []
    answered = []
    audit_dir = root / "vlm_audited/predictions"
    with ZipFile(dataset) as archive:
        questions = predictions(lines(archive.read("Fresh/questions.jsonl")))
        gold = {r["id"]: ("yes" if r["answer"] == "observed_contact" else "no")
                for r in lines(archive.read("Fresh/labels.jsonl"))}
        assert len(gold) == len(questions) == 126
        matched_groups = defaultdict(list)
        for qid, question in questions.items():
            if question["contrast"] == "visual":
                matched_groups[question["group"]].append(qid)
        pairs = [p for p in matched_groups.values() if len(p) == 2 and {gold[i] for i in p} == {"yes", "no"}]
        npos = sum(g == "yes" for g in gold.values())
        assert npos == 27 and len(pairs) == 27
        for model in MODELS:
            donor = load(audit_dir / f"exchange_map_{model}.json")
            meta = load(audit_dir / f"{model}--audit.json")
            assert set(donor) == set(donor.values()) == set(questions)
            for mode in ("direct_forecast", "direct_full"):
                original = archive.read(f"Evaluation/raw_fresh/{model}--{mode}--test.jsonl")
                old = predictions(lines(original))
                spec = next(r for r in meta["conditions"] if r["mode"] == mode)
                assert sha256(original).hexdigest() == spec["archive_sha256"]
                baseline = {i: binary(r["raw"]) for i, r in old.items()}
                for control in ("matched", "text", "exchange"):
                    raw = old if control == "matched" else predictions(lines(
                        (audit_dir / f"{model}--{mode}--{control}.jsonl").read_bytes()))
                    assert raw.keys() == old.keys() == questions.keys()
                    n_rerun = 0
                    for i, r in raw.items():
                        assert r["prompt_sha256"] == old[i]["prompt_sha256"]
                        provided = r.get("donor_id")
                        if control == "text":
                            assert provided is None and r["input_sha256"] is None
                            representative = raw[r["generated_id"]]
                            assert representative["raw"] == r["raw"]
                            assert representative["prompt_sha256"] == r["prompt_sha256"]
                            n_rerun += int(i == r["generated_id"])
                        elif control == "exchange":
                            assert provided == donor[i] and old[provided]["input_sha256"] != old[i]["input_sha256"]
                            assert old[provided]["prompt_sha256"] == r["prompt_sha256"]
                            assert old[provided]["input_sha256"] == r["input_sha256"]
                            if r["execution_source"] == "gpu_exchange":
                                n_rerun += 1
                            else:
                                assert r["execution_source"] == "archived_exact_input"
                                assert r["raw"] == old[provided]["raw"]
                        answered.append({"model": model, "mode": mode, "control": control,
                                         "question_id": i, "gold": gold[i], "response": binary(r["raw"]),
                                         "comparison_image_id": provided})
                    if control == "text":
                        assert n_rerun == spec["text_unique"]
                    if control == "exchange":
                        assert n_rerun == spec["exchange_gpu_rows"]
                    measured = {i: binary(r["raw"]) for i, r in raw.items()}
                    tp = sum(gold[i] == measured[i] == "yes" for i in gold)
                    tn = sum(gold[i] == measured[i] == "no" for i in gold)
                    results.append({
                        "model": model, "mode": mode, "input": control, "n": len(gold), "positive": npos,
                        "tp": tp, "tn": tn, "balanced_accuracy": .5 * (tp/npos + tn/(len(gold)-npos)),
                        "prediction_changes": sum(measured[i] != baseline[i] for i in gold),
                        "both_correct_pairs": sum(all(measured[i] == gold[i] for i in p) for p in pairs),
                        "unparsed": sum(measured[i] == "unparsed" for i in gold),
                        "new_gpu_generations": n_rerun,
                    })
    table(out / "vlm_input_controls.csv", results)
    table(out / "vlm_rescored_items.csv", answered)
    return results


def main():
    p = ArgumentParser(description=__doc__)
    p.add_argument("reproduction", type=Path)
    p.add_argument("dataset_zip", type=Path)
    p.add_argument("output", type=Path)
    p.add_argument("--experiment", choices=("placement", "fixtures", "vision", "all"), default="all")
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=True)
    analyses = {"placement": placement, "fixtures": fixtures,
                "vision": lambda r, o: vision(r, o, a.dataset_zip)}
    for name, analyze in analyses.items():
        if a.experiment in ("all", name):
            report = analyze(a.reproduction, a.output)
            save(a.output, f"{name}_summary.json", report)
            print(name, json.dumps(report), flush=True)


if __name__ == "__main__":
    main()

