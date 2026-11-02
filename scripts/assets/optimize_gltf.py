"""Losslessly weld identical vertices, order triangles for a 16-entry cache,
and order vertex streams by first use. No quantization or decoder is required.
Only the simple, opaque, unskinned triangle meshes generated here are accepted.
"""

import base64
from collections import defaultdict
import copy
import json
from pathlib import Path
import struct
import sys


def misses(triangles, capacity=16):
    cache = []
    count = 0
    for triangle in triangles:
        for vertex in triangle:
            if vertex in cache:
                cache.remove(vertex)
            else:
                count += 1
            cache.insert(0, vertex)
            del cache[capacity:]
    return count


def cache_order(triangles, records):
    adjacent = defaultdict(set)
    for index, triangle in enumerate(triangles):
        for vertex in triangle:
            adjacent[vertex].add(index)
    pending = set(range(len(triangles)))
    remaining = {vertex: len(indices) for vertex, indices in adjacent.items()}
    cache = []
    output = []
    # Attribute bytes make ties deterministic regardless of previous vertex IDs.
    keys = [tuple(records[v] for v in tri) for tri in triangles]
    while pending:
        candidates = set().union(*(adjacent[v] for v in cache)) & pending
        if not candidates:
            candidates = pending
        chosen = min(
            candidates,
            key=lambda i: (
                -sum(v in cache for v in triangles[i]),
                sum(remaining[v] for v in triangles[i]),
                keys[i],
            ),
        )
        tri = triangles[chosen]
        output.append(tri)
        pending.remove(chosen)
        for vertex in tri:
            remaining[vertex] -= 1
            if vertex in cache:
                cache.remove(vertex)
            cache.insert(0, vertex)
            del cache[16:]
    return output if misses(output) < misses(triangles) else triangles


def optimize(document, data):
    assert len(document["buffers"]) == 1
    assert not document.get("skins") and not document.get("animations")
    result = copy.deepcopy(document)
    result["accessors"] = []
    result["bufferViews"] = []
    output = bytearray()

    def read(index):
        a = document["accessors"][index]
        assert "sparse" not in a
        v = document["bufferViews"][a["bufferView"]]
        assert v["buffer"] == 0
        width = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}[a["type"]]
        fmt = "<" + {5126: "f", 5123: "H", 5125: "I"}[a["componentType"]] * width
        size = struct.calcsize(fmt)
        offset = v.get("byteOffset", 0) + a.get("byteOffset", 0)
        return [
            bytes(
                data[
                    offset
                    + i * v.get("byteStride", size) : offset
                    + i * v.get("byteStride", size)
                    + size
                ]
            )
            for i in range(a["count"])
        ], fmt

    def append(records, original, target, fmt):
        while len(output) % 4:
            output.append(0)
        start = len(output)
        output.extend(b"".join(records))
        view = len(result["bufferViews"])
        result["bufferViews"].append(
            dict(
                buffer=0,
                byteOffset=start,
                byteLength=len(output) - start,
                target=target,
            )
        )
        accessor = copy.deepcopy(original)
        accessor.pop("byteOffset", None)
        accessor.update(bufferView=view, count=len(records))
        if "min" in accessor or "max" in accessor:
            values = list(zip(*(struct.unpack(fmt, r) for r in records)))
            accessor.update(min=[min(v) for v in values], max=[max(v) for v in values])
        result["accessors"].append(accessor)
        return len(result["accessors"]) - 1

    for mesh in result["meshes"]:
        for primitive in mesh["primitives"]:
            assert primitive.get("mode", 4) == 4
            assert not primitive.get("targets") and not primitive.get("extensions")
            material = (
                result.get("materials", [])[primitive["material"]]
                if "material" in primitive
                else {}
            )
            assert material.get("alphaMode", "OPAQUE") != "BLEND"
            names = list(primitive["attributes"])
            streams = [read(primitive["attributes"][n]) for n in names]
            records = list(zip(*(stream[0] for stream in streams)))
            index_records, index_fmt = read(primitive["indices"])
            indices = [struct.unpack(index_fmt, r)[0] for r in index_records]
            unique = []
            lookup = {}
            remap = {}
            for index in indices:
                key = records[index]
                if key not in lookup:
                    lookup[key] = len(unique)
                    unique.append(key)
                remap[index] = lookup[key]
            triangles = [
                tuple(remap[v] for v in indices[i : i + 3])
                for i in range(0, len(indices), 3)
            ]
            triangles = cache_order(triangles, unique)
            fetched = {}
            ordered = []
            new_indices = []
            for triangle in triangles:
                for vertex in triangle:
                    if vertex not in fetched:
                        fetched[vertex] = len(ordered)
                        ordered.append(unique[vertex])
                    new_indices.append(fetched[vertex])
            for column, name in enumerate(names):
                old = document["accessors"][primitive["attributes"][name]]
                primitive["attributes"][name] = append(
                    [r[column] for r in ordered], old, 34962, streams[column][1]
                )
            component = 5123 if len(ordered) <= 65536 else 5125
            fmt = "<H" if component == 5123 else "<I"
            primitive["indices"] = append(
                [struct.pack(fmt, v) for v in new_indices],
                dict(componentType=component, type="SCALAR"),
                34963,
                fmt,
            )
    result["buffers"][0]["byteLength"] = len(output)
    return result, bytes(output)


def optimize_file(path):
    path = Path(path)
    doc = json.loads(path.read_text())
    uri = doc["buffers"][0]["uri"]
    embedded = uri.startswith("data:")
    if not embedded:
        assert Path(uri).name == uri, "Do not rewrite shared/external mesh buffers"
    data = (
        base64.b64decode(uri.split(",")[1])
        if embedded
        else (path.parent / uri).read_bytes()
    )
    result, output = optimize(doc, data)
    if embedded:
        result["buffers"][0]["uri"] = (
            "data:application/octet-stream;base64," + base64.b64encode(output).decode()
        )
    else:
        (path.parent / uri).write_bytes(output)
    path.write_text(
        json.dumps(
            result,
            indent=None if embedded else 2,
            separators=(",", ":") if embedded else None,
        )
        + "\n"
    )
    return len(data), len(output)


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        before, after = optimize_file(arg)
        print(f"{arg}: {before} -> {after} bytes")
