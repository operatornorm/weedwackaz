#!/usr/bin/env python3
"""Cross-check a metadata-only report against the explicit native binding pins."""
import json
from pathlib import Path
import re

PINS=Path(__file__).resolve().parents[1]/'qa/steam-invite-bindings.json'


def check(report, pins=None):
    pins=pins or json.loads(PINS.read_bytes())
    if type(report) is not dict or type(report.get('schema')) is not int or report['schema']!=1 or report.get('kind')!='mgsv_steam_capabilities':raise ValueError('report_schema')
    for key,expected in (('read_only',True),('can_install',False),('runtime_interfaces_verified',False),('invite_callbacks_verified',False)):
        if report.get(key) is not expected:raise ValueError('report_scope')
    if report.get('executable_sha256')!=pins['executable_sha256']:raise ValueError('executable_identity')
    dll=report.get('steam_api64')
    if type(dll) is not dict or dll.get('sha256')!=pins['steam_dll_sha256'] or type(dll.get('size')) is not int or dll['size']!=pins['steam_dll_size'] or dll.get('machine')!=pins['machine']:raise ValueError('module_identity')
    names=dll.get('steam_exports')
    if type(names) is not list or len(names)!=pins['reported_steam_exports'] or any(type(n) is not str or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_@]{0,127}',n) for n in names):raise ValueError('export_inventory')
    if len(set(names))!=len(names) or type(dll.get('named_export_count')) is not int or dll['named_export_count']!=pins['reported_named_exports']:raise ValueError('export_counts')
    if not set(pins['required_exports']).issubset(names):raise ValueError('required_export_missing')
    versions=dll.get('interface_string_candidates')
    if type(versions) is not list or any(type(v) is not str for v in versions) or not set(pins['factory_versions']).issubset(versions):raise ValueError('interface_candidate_missing')
    return {'schema':1,'status':'metadata_matches_native_binding_pins','required_exports':len(pins['required_exports']),
            'can_enable_gameplay':False,'runtime_interfaces_verified':False,'mgo_coexistence_verified':False}
