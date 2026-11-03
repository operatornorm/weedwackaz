"""Validate startup observations without inferring licensing or gameplay success."""
import argparse
import json
import re
from pathlib import Path

REQUEST_KEYS = {"schema", "stage", "run", "session", "challenge", "source_tag", "manifest_sha256", "result_sha256"}
REPORT_KEYS = {"schema", "stage", "run", "session", "challenge", "source_tag", "result", "process_started",
               "observed_seconds", "exit_code_hex", "native_error", "close_method", "gameplay_verified",
               "offline_license_verified", "save_isolation_verified", "co_op_verified"}
PROOFS = ("gameplay_verified", "offline_license_verified", "save_isolation_verified", "co_op_verified")


def decode(raw):
    if not isinstance(raw, bytes) or len(raw) > 2048:
        raise ValueError("oversized input")
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("duplicate JSON key")
            value[key] = item
        return value
    return json.loads(raw.decode("utf-8-sig"), object_pairs_hook=unique)


def check(request_raw, report_raw, copy_receipt, source_tag, manifest_tag, result_tag):
    request, report = decode(request_raw), decode(report_raw)
    if not isinstance(request, dict) or set(request) != REQUEST_KEYS or not isinstance(report, dict) or set(report) != REPORT_KEYS:
        raise ValueError("wrong schema")
    for value in (request, report):
        if type(value["schema"]) is not int or value["schema"] != 1 or value["stage"] != "startup-v1":
            raise ValueError("wrong stage")
        for key, size in (("run", 32), ("session", 32), ("challenge", 32), ("source_tag", 64)):
            if not isinstance(value[key], str) or not re.fullmatch("[0-9a-f]{" + str(size) + "}", value[key]) or value[key] == "0" * size:
                raise ValueError("invalid identifier")
    if copy_receipt.get("result") != "copy_observations_accepted" or request["run"] != copy_receipt.get("run_id") or request["session"] != copy_receipt.get("guest_session_id"):
        raise ValueError("wrong copied guest session")
    if request["source_tag"] != source_tag or request["manifest_sha256"] != manifest_tag or request["result_sha256"] != result_tag:
        raise ValueError("wrong published source or copied baseline")
    if any(request[key] != report[key] for key in ("schema", "stage", "run", "session", "challenge", "source_tag")):
        raise ValueError("mismatched startup request")
    if any(report[key] is not False for key in PROOFS):
        raise ValueError("unsupported proof claim")
    if type(report["process_started"]) is not bool or type(report["observed_seconds"]) is not int or not 0 <= report["observed_seconds"] <= 130:
        raise ValueError("invalid observation")
    if report["exit_code_hex"] is not None and (not isinstance(report["exit_code_hex"], str) or not re.fullmatch("[0-9A-F]{8}", report["exit_code_hex"])):
        raise ValueError("invalid exit code")
    if report["native_error"] is not None and (type(report["native_error"]) is not int or not -(2**31) <= report["native_error"] < 2**32):
        raise ValueError("invalid native error")
    if report["close_method"] not in ("not_needed", "graceful", "forced", "failed"):
        raise ValueError("invalid close method")
    outcome = report["result"]
    if outcome not in ("owner_aborted", "exited_before_deadline", "process_survived_deadline", "probe_error", "cleanup_failed"):
        raise ValueError("unknown result")
    if outcome == "owner_aborted" and (report["process_started"] or report["observed_seconds"] != 0 or report["exit_code_hex"] is not None or report["native_error"] is not None or report["close_method"] != "not_needed"):
        raise ValueError("inconsistent abort")
    if outcome in ("exited_before_deadline", "process_survived_deadline") and (not report["process_started"] or report["exit_code_hex"] is None or report["native_error"] is not None):
        raise ValueError("inconsistent process outcome")
    if outcome == "exited_before_deadline" and report["close_method"] != "not_needed":
        raise ValueError("inconsistent early exit")
    if outcome == "process_survived_deadline" and (report["observed_seconds"] < 119 or report["close_method"] not in ("graceful", "forced")):
        raise ValueError("inconsistent bounded observation")
    if outcome == "probe_error" and report["native_error"] is None:
        raise ValueError("missing error")
    if outcome == "cleanup_failed" and (not report["process_started"] or report["close_method"] != "failed"):
        raise ValueError("inconsistent cleanup failure")
    return {"schema": 1, "result": "startup_observations_accepted", "outcome": outcome,
            "process_started": report["process_started"], "observed_seconds": report["observed_seconds"],
            "exit_code_hex": report["exit_code_hex"], "native_error": report["native_error"],
            "run_id": request["run"], "guest_session_id": request["session"],
            "executed_source_attested": False, **{key: False for key in PROOFS}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("request", "report", "copy-receipt"):
        parser.add_argument("--" + name, required=True, type=Path)
    for name in ("source-tag", "manifest-tag", "result-tag"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    print(json.dumps(check(args.request.read_bytes(), args.report.read_bytes(), json.loads(args.copy_receipt.read_text()), args.source_tag, args.manifest_tag, args.result_tag), indent=2))


if __name__ == "__main__": main()
