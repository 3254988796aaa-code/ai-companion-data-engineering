"""Deterministic local JSON -> redacted sessions and SFT-style JSONL."""

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import re

from companion.schema import normalize_session, system_prompt

RULES = [
    ("api_key", re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"), "[API_KEY]"),
    ("email", re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}"), "[EMAIL]"),
    ("phone", re.compile(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)"), "[PHONE]"),
]


def redact(text, counts):
    for name, pattern, replacement in RULES:
        text, n = pattern.subn(replacement, text)
        counts[name] += n
    return text


def canonical(payload):
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def write_jsonl(path, records):
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for row in records:
            stream.write(canonical(row) + "\n")


def run_pipeline(input_dir, output_dir, eval_percent=20):
    input_dir, output_dir = Path(input_dir).resolve(), Path(output_dir).resolve()
    if not input_dir.is_dir():
        raise ValueError("input_directory_missing")
    if input_dir == output_dir or input_dir in output_dir.parents or output_dir in input_dir.parents:
        raise ValueError("input_and_output_must_be_separate")
    if not 0 <= eval_percent <= 100:
        raise ValueError("invalid_eval_percent")
    output_dir.mkdir(parents=True, exist_ok=True)
    accepted, train, evaluation, rejected, lineage = [], [], [], [], []
    seen, masks, reasons = set(), Counter(), Counter()
    files = sorted(input_dir.glob("*.json"))
    for path in files:
        content = path.read_bytes()
        source = sha256(content).hexdigest()
        record_masks = Counter()
        try:
            try:
                raw = json.loads(content.decode("utf-8-sig"))
            except (UnicodeError, json.JSONDecodeError):
                raise ValueError("invalid_json") from None
            session = normalize_session(raw)
            if session["source_mode"] == "demo":
                raise ValueError("demo_session")
            if not session["messages"]:
                raise ValueError("empty_session")
            if len(session["messages"]) % 2:
                raise ValueError("incomplete_turn")
            session["nickname"] = redact(session["nickname"], record_masks)
            session["personality"] = redact(session["personality"], record_masks)
            for message in session["messages"]:
                message["content"] = redact(message["content"], record_masks)
            fingerprint = sha256(canonical({k: session[k] for k in
                ("nickname", "personality", "messages")}).encode("utf-8")).hexdigest()
            if fingerprint in seen:
                raise ValueError("duplicate_session")
            seen.add(fingerprint)
            masks.update(record_masks)
            session["session_id"] = fingerprint
            split = "eval" if int(fingerprint[:8], 16) % 100 < eval_percent else "train"
            accepted.append(session)
            target = evaluation if split == "eval" else train
            for index in range(1, len(session["messages"]), 2):
                target.append({"session_id": fingerprint, "turn_index": index // 2,
                    "messages": [{"role": "system", "content": system_prompt(session)},
                                 *session["messages"][:index + 1]]})
            lineage.append({"source_sha256": source, "session_id": fingerprint, "split": split})
        except ValueError as exc:
            reason = str(exc)
            reasons[reason] += 1
            rejected.append({"source_sha256": source, "reason": reason})
    outputs = {"sessions.jsonl": accepted, "sft_train.jsonl": train,
               "sft_eval.jsonl": evaluation, "rejected.jsonl": rejected, "lineage.jsonl": lineage}
    for name, rows in outputs.items():
        write_jsonl(output_dir / name, rows)
    report = {
        "pipeline_version": 1, "input_files": len(files), "accepted_sessions": len(accepted),
        "rejected_files": len(rejected), "rejection_reasons": dict(sorted(reasons.items())),
        "redactions_in_accepted_sessions": dict(sorted(masks.items())),
        "train_examples": len(train), "eval_examples": len(evaluation),
        "accepted_source_modes": dict(sorted(Counter(s["source_mode"] for s in accepted).items())),
        "config": {"eval_percent": eval_percent, "split_unit": "session",
                   "redaction_rules": [x[0] for x in RULES], "dedup": "normalized_redacted_session"},
        "output_sha256": {name: sha256((output_dir / name).read_bytes()).hexdigest() for name in outputs},
    }
    (output_dir / "quality_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--eval-percent", type=int, default=20)
    args = parser.parse_args()
    try:
        print(json.dumps(run_pipeline(args.input, args.output, args.eval_percent), ensure_ascii=False, indent=2))
    except (ValueError, OSError) as exc:
        parser.exit(2, f"Pipeline failed: {type(exc).__name__}. Check paths and arguments.\n")


if __name__ == "__main__":
    main()
