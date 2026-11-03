#!/usr/bin/env python3
"""Read-only smoke scorer for the opt-in local status bridge; never verifies co-op."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import time


class Blocked(ValueError):
    pass


def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result: raise Blocked("duplicate_json_key")
        result[key] = value
    return result


def counter(value):
    if type(value) is not str or not re.fullmatch(r"[1-9][0-9]{0,19}", value) or int(value) > 2**64-1:
        raise Blocked("invalid_counter")
    return int(value)


def vector(value):
    return type(value) is dict and set(value) == {"x", "y", "z"} and all(
        type(v) in (float, int) and math.isfinite(v) and abs(v) <= 1000000 for v in value.values())


def read_status(path):
    if path.is_symlink() or not stat.S_ISREG(path.stat().st_mode): raise Blocked("status_not_regular")
    flags=os.O_RDONLY | getattr(os,"O_NONBLOCK",0) | getattr(os,"O_NOFOLLOW",0) | getattr(os,"O_BINARY",0)
    fd=os.open(path,flags)
    with os.fdopen(fd,"rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode): raise Blocked("status_not_regular")
        return stream.read(32769)


class Scorer:
    def __init__(self, run_id, mission):
        if not re.fullmatch(r"[0-9a-f]{32}", run_id): raise Blocked("invalid_run_id")
        self.run_id, self.mission = run_id, mission
        self.previous = None
        self.advances = 0

    def accept(self, data):
        if len(data) > 32768: raise Blocked("status_too_large")
        try: value = json.loads(data, object_pairs_hook=unique, parse_constant=lambda _: (_ for _ in ()).throw(Blocked("nonfinite_json")))
        except (ValueError, RecursionError, UnicodeError): raise Blocked("invalid_json") from None
        if type(value) is not dict or value.get("schema") != 1 or type(value.get("schema")) is not int or value.get("kind") != "mgsv_observer_status": raise Blocked("wrong_status_schema")
        if value.get("observation_only") is not True or value.get("can_authorize") is not False: raise Blocked("readiness_overclaim")
        if value.get("run_id") != self.run_id: raise Blocked("wrong_run")
        if value.get("caller_affinity_checked") is not True: raise Blocked("missing_caller_affinity")
        generation, frame, tick = (counter(value.get(k)) for k in ("generation", "frame_id", "publisher_tick_ms"))
        observation = value.get("observation")
        if type(observation) is not dict or type(observation.get("schema")) is not int or observation["schema"] != 1 or observation.get("observation_only") is not True or observation.get("can_authorize") is not False or observation.get("coherent_snapshot_verified") is not False: raise Blocked("invalid_observation")
        proofs = observation.get("verification")
        keys = {"peer_liveness", "player_realization", "same_world", "center_agreement", "complete_initial_sync", "protocol_epoch", "playable_free_roam_contract", "save_isolation"}
        if type(proofs) is not dict or set(proofs) != keys or any(v is not False for v in proofs.values()): raise Blocked("verification_overclaim")
        native, context, slots = (observation.get(k) for k in ("native", "context", "player_slots"))
        if not all(type(v) is dict for v in (native, context, slots)): raise Blocked("missing_observation_sections")
        if native.get("status") != "observed" or native.get("native_available") is not True or native.get("sample_counter_exhausted") is not False: raise Blocked("native_unavailable")
        sample = counter(native.get("sample_id"))
        if type(context.get("mission")) is not int or context["mission"] != self.mission or type(context.get("location")) is not int or context["location"] != {30010:10,30020:20}[self.mission]: raise Blocked("wrong_world")
        if context.get("prepare_finished") is not True or context.get("not_playable") is not False: raise Blocked("not_in_prepared_playable_context")
        if type(context.get("sequence_name")) is not str or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{1,127}", context["sequence_name"]): raise Blocked("sequence_unavailable")
        if not vector(context.get("world_center")) or not vector(context.get("local_position")) or slots.get("slot0_present") is not True: raise Blocked("world_observation_incomplete")
        signature = hashlib.sha256(data).hexdigest()
        current = (generation, frame, tick, sample, signature)
        if self.previous:
            pg, pf, pt, ps, old_signature = self.previous
            if generation != pg: raise Blocked("generation_changed")
            if frame == pf:
                if signature != old_signature: raise Blocked("frame_rewritten")
                return False
            if frame < pf or tick <= pt or sample <= ps: raise Blocked("nonadvancing_observation")
            self.advances += 1
        self.previous = current
        return True


def run(status, run_id, mission, duration=5.0):
    scorer = Scorer(run_id, mission)
    deadline = time.monotonic() + duration
    started = time.monotonic()
    last_progress = None
    reason = "no_status"
    while time.monotonic() < deadline:
        try:
            data=read_status(status)
            if scorer.accept(data): last_progress = time.monotonic()
            reason = "insufficient_advancing_samples"
        except FileNotFoundError: reason = "no_status"
        except OSError: reason = "status_unreadable"
        except Blocked as error: return {"schema":1,"scope":"local_observer_smoke_only","result":"BLOCKED","reason":str(error),"co_op_verified":False}
        time.sleep(min(0.1, max(0, deadline-time.monotonic())))
    fresh = last_progress is not None and time.monotonic()-last_progress <= 1.0
    passed = scorer.advances >= 3 and fresh and time.monotonic()-started >= 2.0
    if not fresh and scorer.previous: reason = "stale_status"
    return {"schema":1,"scope":"local_observer_smoke_only","result":"PASS" if passed else "BLOCKED",
            "reason":"observations_advance" if passed else reason,"advances":scorer.advances,"co_op_verified":False}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--status",type=Path,required=True)
    parser.add_argument("--run-id",required=True)
    parser.add_argument("--mission",type=int,choices=(30010,30020),required=True)
    parser.add_argument("--duration",type=float,default=5)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    if not math.isfinite(args.duration) or not 2 <= args.duration <= 60: parser.error("duration must be 2–60 seconds")
    if args.output.resolve().is_relative_to(args.status.resolve().parent): parser.error("output must be outside the status directory")
    result=run(args.status,args.run_id,args.mission,args.duration)
    with args.output.open("x",encoding="utf-8") as out: json.dump(result,out,indent=2);out.write("\n")
    print(result["result"]+": "+result["reason"]+" (observer only; co-op remains unverified)")
    return 0 if result["result"]=="PASS" else 2


if __name__=="__main__": raise SystemExit(main())
