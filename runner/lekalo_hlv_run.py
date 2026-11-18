"""Produce HLV v1 evidence from a complete, explicitly selected set of runners."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

import yaml


def hlv(program, root, *argv):
    result = subprocess.run([program, *argv, "--root", str(root)], cwd=root,
                            stdout=subprocess.PIPE, check=False)
    document = json.loads(result.stdout)
    return result.returncode, document


def snapshots(program, root):
    code, doc = hlv(program, root, "evidence", "snapshot")
    if code or doc.get("schema_version") != 1:
        raise ValueError("HLV snapshot failed")
    result = {}
    for record in doc["snapshots"]:
        key = record["binding"]
        if key in result or not record.get("inputs"):
            raise ValueError("duplicate binding or empty input snapshot")
        result[key] = record
    if not result:
        raise ValueError("HLV has no execution bindings")
    return result


def relative_file(root, relative):
    path = Path(relative)
    if not path.parts or path.is_absolute() or ".." in path.parts:
        raise ValueError("expected a relative project path")
    target = root / path
    if target.resolve() != target:
        raise ValueError("symlink in evidence path")
    return target


def check(program, root, structural):
    argv = ["check", "--strict", "--json"]
    if structural:
        argv.append("--structural-only")
    code, report = hlv(program, root, *argv)
    if report.get("structural_only") is not structural or report.get("exit_code") != code:
        raise ValueError("incompatible HLV check result")
    return code, report


def run(args):
    root = args.root.resolve(strict=True)
    config_root = root if (root / "project.yaml").is_file() else relative_file(root, ".hlv")
    config = yaml.safe_load(relative_file(config_root, "project.yaml").read_bytes())
    output = relative_file(config_root, config["execution_evidence"]["path"])
    plan = json.loads(args.plan.read_bytes())
    if not isinstance(plan, dict) or any(
        cmd is not None and (not isinstance(cmd, list) or not cmd or
                             any(not isinstance(s, str) or not s or "\0" in s for s in cmd))
        for cmd in plan.values()
    ):
        raise ValueError("each binding needs a direct command array or null for skipped")
    code, preflight = check(args.hlv, root, True)
    if code or preflight.get("structural_status") != "passed":
        raise ValueError("strict HLV structural check failed")
    first = snapshots(args.hlv, root)
    if set(first) != set(plan):
        raise ValueError("runner plan must cover the configured HLV binding IDs exactly")
    reports = relative_file(root, ".lekalo/hlv-runs")
    reports.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(dir=reports))
    runs = []
    for index, (binding, command) in enumerate(sorted(plan.items())):
        before = snapshots(args.hlv, root)[binding]
        log = directory / f"{index}.log"
        with log.open("xb") as stream:
            if command is None:
                stream.write(b"Binding explicitly skipped by the runner plan.\n")
                outcome = "skipped"
            else:
                try:
                    result = subprocess.run(command, cwd=root, stdin=subprocess.DEVNULL,
                                            stdout=stream, stderr=subprocess.STDOUT, check=False)
                    outcome = "passed" if result.returncode == 0 else "failed"
                except OSError as exc:
                    stream.write(f"Runner unavailable: {exc}\n".encode())
                    outcome = "incomplete"
        if first[binding] != before or before != snapshots(args.hlv, root).get(binding):
            outcome = "incomplete"
        runs.append({"snapshot":before, "code_revision":args.revision, "run_id":args.run_id,
                     "outcome":outcome, "finished_at":datetime.now(timezone.utc).isoformat(),
                     "artifact_ref":log.relative_to(root).as_posix()})
    final = snapshots(args.hlv, root)
    if set(final) != set(first):
        raise ValueError("the configured HLV binding set changed during execution")
    for record in runs:
        if final[record["snapshot"]["binding"]] != record["snapshot"]:
            record["outcome"] = "incomplete"
    encoded = (json.dumps({"schema_version":1,"runs":runs}, indent=2)+"\n").encode()
    # The configured path names the HLV run manifest. Preserve unrelated files.
    if output.exists():
        previous = yaml.safe_load(output.read_bytes())
        if not isinstance(previous, dict) or previous.get("schema_version") != 1 or not isinstance(previous.get("runs"), list):
            raise ValueError("existing evidence file is not an HLV v1 run manifest")
    with tempfile.NamedTemporaryFile(dir=output.parent, delete=False) as stream:
        staged = Path(stream.name)
        try:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        except BaseException:
            staged.unlink(missing_ok=True)
            raise
    try:
        os.replace(staged, output)
    finally:
        staged.unlink(missing_ok=True)
    code, report = check(args.hlv, root, False)
    print(json.dumps(report))
    accepted = report.get("execution_evidence", {})
    rows = accepted.get("bindings", [])
    verified = (code == 0 and accepted.get("status") == "passed" and
                len(rows) == len(plan) and {r["binding"] for r in rows} == set(plan) and
                all(r.get("run_id") == args.run_id and r.get("code_revision") == args.revision
                    and r.get("status") == "passed" for r in rows) and
                output.read_bytes() == encoded and all(r["outcome"] == "passed" for r in runs))
    return 0 if verified else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--hlv", default="hlv")
    args = parser.parse_args()
    if not args.run_id.strip() or not args.revision.strip():
        parser.error("run identity and revision must be non-empty")
    try:
        return run(args)
    except (OSError, ValueError, KeyError, TypeError, yaml.YAMLError) as exc:
        print(f"HLV evidence unavailable: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
