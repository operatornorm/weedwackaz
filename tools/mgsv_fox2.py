"""Bounded FOX2 structure reader for allocation preflight; never executes game data.

Format source: pinned datfpk v0.3.0 fox2/{header,entity,property,
stringlookupliteral}.go. Supports scalar integer/hash fields and their containers.
Unsupported types fail closed. Parsed literals stay internal; exports are selected.
"""

import re
import posixpath
import struct

from mgsv_pack_report import K2, city64, get32, get64, hash16, require

MAX_FOX = 1 << 20
MAX_ENTITIES = 64
MAX_PROPERTIES = 512
MAX_VALUES = 4096
FORMATS = {0: "b", 1: "B", 2: "h", 3: "H", 4: "i", 5: "I", 6: "q", 7: "Q",
           10: "B", 11: "Q", 12: "Q", 13: "Q", 20: "Q", 21: "Q"}
IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,126}\Z")
CONTROLLER = "TppPlayer2BlockControllerData"
DATASET = "DataSet"
TEXTURE = "TexturePackLoadConditioner"
BLOCK_PROPERTIES = (
    "name", "dataSet", "configuration_commonMotionBlockSize", "configuration_commonMotionBlockSizePs3",
    "configuration_additiveMotionBlockCount", "configuration_additiveMotionBlockSize",
    "configuration_partsBlockCount", "configuration_partsBlockSize", "instanceSettings_instancePackagePath",
    "instanceSettings_instanceBlockSize", "instanceSettings_commonMotionTypeName",
    "instanceSettings_partsTypeNames", "instanceSettings_partsTypeInitial")


def align16(value):
    return (value + 15) & ~15


def strcode64(value):
    data = value.encode("utf-8") if isinstance(value, str) else value
    data = data if data and data.endswith(b"\0") else data + b"\0"
    require(len(data) <= 128, "fox_literal_hash_limit")
    seed = (data[0] << 16) + len(data) - 1 if len(data) > 1 else 0
    return hash16(city64(data) - K2, seed) & 0xffffffffffff


def parse_fox2(data):
    require(isinstance(data, bytes) and 32 <= len(data) <= MAX_FOX, "fox_size")
    magic, version, count, strings_at, cursor = struct.unpack_from("<5I", data)
    require((magic, version) == (0x786f62f2, 0x35), "fox_magic")
    require(0 < count <= MAX_ENTITIES and 32 <= cursor <= strings_at <= len(data) and
            cursor % 16 == strings_at % 16 == 0, "fox_sections")
    entities, property_total, value_total = [], 0, 0
    for _ in range(count):
        start = cursor
        require(start + 64 <= strings_at, "fox_entity_bounds")
        size, class_id, marker, address, entity_id, class_version, class_hash, static, dynamic, offset, static_size, total = \
            struct.unpack_from("<hIIQQhQHHiii", data, start)
        require(size == offset == 64 and marker == 0x746e65 and
                64 <= static_size <= total <= strings_at - start and
                static_size % 16 == total % 16 == 0, "fox_entity_layout")
        require(not any(e["address"] == address for e in entities), "fox_duplicate_address")
        property_total += static + dynamic
        require(property_total <= MAX_PROPERTIES, "fox_property_limit")
        entity = {"class_hash": class_hash, "class_id": class_id, "version": class_version,
                  "address": address, "id": entity_id, "offset": start, "properties": []}
        cursor = start + 64
        for group, entries, end in (("static", static, start + static_size),
                                     ("dynamic", dynamic, start + total)):
            for _ in range(entries):
                require(cursor + 32 <= end, "fox_property_bounds")
                name, datatype, container, values, data_offset, length = struct.unpack_from("<QBBhhH", data, cursor)
                require(datatype in FORMATS and container in (0, 1, 2, 3), "fox_unsupported_type_or_container")
                require(data_offset == 32 and length >= 32 and length % 16 == 0 and
                        length <= end - cursor and 0 <= values <= 256, "fox_property_layout")
                value_total += values
                require(value_total <= MAX_VALUES, "fox_value_limit")
                width = struct.calcsize("<" + FORMATS[datatype])
                stride = align16(8 + width) if container == 2 else width
                require(align16(32 + values * stride) == length, "fox_property_size")
                payload = cursor + 32
                numbers = [struct.unpack_from("<" + FORMATS[datatype], data,
                                               payload + i * stride + (8 if container == 2 else 0))[0]
                           for i in range(values)]
                require(datatype != 10 or all(n in (0, 1) for n in numbers), "fox_boolean")
                keys = [get64(data, payload + i * stride) for i in range(values)] if container == 2 else []
                require(len(keys) == len(set(keys)), "fox_duplicate_map_key")
                require(not any(p["name_hash"] == name for p in entity["properties"]), "fox_duplicate_property")
                entity["properties"].append({"name_hash": name, "datatype": datatype, "container": container,
                                             "values": numbers, "keys": keys, "group": group,
                                             "offset": cursor, "size": length,
                                             "unknown": data[cursor + 16:cursor + 32]})
                cursor += length
            require(cursor == end, "fox_property_section_end")
        entities.append(entity)
    require(cursor == strings_at, "fox_entity_section_end")
    literals = {}
    for literal_records in range(4096):
        require(cursor + 8 <= len(data), "fox_literal_termination")
        key = get64(data, cursor)
        cursor += 8
        if key == 0:
            break
        require(cursor + 4 <= len(data), "fox_literal_bounds")
        length = struct.unpack_from("<i", data, cursor)[0]
        cursor += 4
        require(0 <= length <= 127 and length <= len(data) - cursor, "fox_literal_length")
        raw = data[cursor:cursor + length]
        cursor += length
        require(strcode64(raw) == key, "fox_literal_fingerprint")
        text = raw.decode("utf-8")
        require(key not in literals or literals[key] == text, "fox_conflicting_literal")
        literals[key] = text
    else:
        require(False, "fox_literal_limit")
    footer = align16(cursor)
    require(footer + 5 <= len(data) and not any(data[cursor:footer]) and
            data[footer:footer + 5] == b"\0\0end" and
            len(data) == align16(footer + 5) and not any(data[footer + 5:]), "fox_footer")
    return {"entities": entities, "literals": literals, "strings_at": strings_at,
            "literal_end": cursor - 8, "literal_records": literal_records}


def prop(entity, name, datatype, container, count=None):
    matches = [p for p in entity["properties"] if p["name_hash"] == strcode64(name)]
    require(len(matches) == 1, "fox_required_property")
    p = matches[0]
    require(p["datatype"] == datatype and p["container"] == container and p["group"] == "static" and
            not any(p["unknown"]) and (count is None or len(p["values"]) == count), "fox_required_property_type")
    return p


def literal(tree, key):
    if key == strcode64(""):
        return ""
    require(key in tree["literals"], "fox_required_literal")
    return tree["literals"][key]


def validate_controller_slots(tree, slots):
    """Supported controller structure; slot count is not a claim about realized players."""
    require(slots in (1, 2), "fox_slot_policy")
    by_class = {}
    for e in tree["entities"]:
        name = literal(tree, e["class_hash"])
        by_class.setdefault(name, []).append(e)
    require(set(by_class) == {DATASET, CONTROLLER, TEXTURE} and
            all(len(v) == 1 for v in by_class.values()), "fox_controller_entity_set")
    dataset, controller, texture = (by_class[name][0] for name in (DATASET, CONTROLLER, TEXTURE))
    require((controller["class_id"], controller["version"]) == (0x88, 3) and
            (dataset["class_id"], dataset["version"]) == (0xe8, 0) and
            (texture["class_id"], texture["version"]) == (0x48, 0), "fox_controller_schema")
    for entity, expected in ((controller, BLOCK_PROPERTIES), (dataset, ("name", "dataSet", "dataList")),
                             (texture, ("name", "dataSet", "texturePackPath"))):
        require({p["name_hash"] for p in entity["properties"]} == {strcode64(n) for n in expected} and
                all(p["group"] == "static" for p in entity["properties"]), "fox_controller_property_set")
    require(all(entity["address"] != 0 for entity in (dataset, controller, texture)) and
            prop(dataset, "dataSet", 21, 0, 1)["values"] == [0], "fox_dataset_root")
    prop(dataset, "name", 11, 0, 1)
    links = prop(dataset, "dataList", 13, 2, 2)
    require(set(links["values"]) == {controller["address"], texture["address"]}, "fox_dataset_links")
    for child in (controller, texture):
        name_key = prop(child, "name", 11, 0, 1)["values"][0]
        require(name_key in links["keys"] and links["values"][links["keys"].index(name_key)] == child["address"] and
                prop(child, "dataSet", 21, 0, 1)["values"] == [dataset["address"]], "fox_controller_graph")
    for name in BLOCK_PROPERTIES:
        if name.startswith("configuration_") or name == "instanceSettings_instanceBlockSize":
            prop(controller, name, 5, 0, 1)
    require(prop(controller, "configuration_partsBlockCount", 5, 0, 1)["values"] == [slots], "fox_single_parts_slot")
    for name in ("instanceSettings_partsTypeNames", "instanceSettings_partsTypeInitial"):
        values = prop(controller, name, 11, 1, slots)["values"]
        require(all(IDENTIFIER.fullmatch(literal(tree, value)) for value in values), "fox_parts_type_literal")
    instance = literal(tree, prop(controller, "instanceSettings_instancePackagePath", 11, 0, 1)["values"][0])
    require(re.fullmatch(r"/Assets/tpp/pack/player/game_object/[A-Za-z0-9_-]+\.fpk", instance) and
            ((instance == "/Assets/tpp/pack/player/game_object/two_players_game_obj.fpk") == (slots == 2)),
            "fox_instance_package")
    require(IDENTIFIER.fullmatch(literal(tree, prop(controller, "instanceSettings_commonMotionTypeName", 11, 0, 1)["values"][0])),
            "fox_motion_type_literal")
    prop(texture, "texturePackPath", 12, 0, 1)
    return True


def validate_single_slot(tree):
    """A supported stock structure, not a claim about realized player count or co-op."""
    return validate_controller_slots(tree, 1)


def controller_summary(tree):
    """Selected structure only. Never exports literal tables, arbitrary strings or asset bodies."""
    names = [tree["literals"].get(e["class_hash"], "<unresolved>") for e in tree["entities"]]
    names = [n if n in (DATASET, CONTROLLER, TEXTURE) else "<unrecognized>" for n in names]
    result = {"entity_classes": names, "entity_count": len(names), "controller_count": names.count(CONTROLLER)}
    if result["controller_count"] == 1:
        controller = tree["entities"][names.index(CONTROLLER)]
        result["controller_class_version"] = controller["version"]
        fields = {}
        for name in BLOCK_PROPERTIES:
            matches = [p for p in controller["properties"] if p["name_hash"] == strcode64(name)]
            if len(matches) == 1:
                p = matches[0]
                fields[name] = {"datatype": p["datatype"], "container": p["container"], "count": len(p["values"])}
                if p["datatype"] == 5 and (name.startswith("configuration_") or
                                            name == "instanceSettings_instanceBlockSize"):
                    fields[name]["values"] = p["values"]
                if p["datatype"] == 11 and name.startswith("instanceSettings_"):
                    fields[name]["value_hashes"] = ["%016x" % value for value in p["values"]]
                    if name == "instanceSettings_instancePackagePath":
                        paths = [tree["literals"].get(value, "") for value in p["values"]]
                        fields[name]["asset_paths"] = [value if re.fullmatch(r"/Assets/[A-Za-z0-9_./-]+", value) and
                                                        posixpath.normpath(value) == value else "<value omitted>"
                                                        for value in paths]
        result["selected_fields"] = fields
        expected = {strcode64(name) for name in BLOCK_PROPERTIES}
        result["unexpected_property_hashes"] = ["%016x" % p["name_hash"] for p in controller["properties"]
                                                if p["name_hash"] not in expected]
    return result
