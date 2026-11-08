"""Group 8: name-collision noise.

Codec defines get/dumps/join/append, so name matching will propose internal
targets for builtin and stdlib calls with the same names.
"""
import json
import os.path


class Codec:
    def dumps(self, value):
        return str(value)

    def get(self, key):
        return key

    def join(self, parts):
        return "".join(parts)

    def append(self, item):
        return item


def main():
    data = {"k": 1}
    data.get("k")  # expect: external
    parts = ["a", "b"]
    parts.append("c")  # expect: external
    ", ".join(parts)  # expect: external
    os.path.join("x", "y")  # expect: external
    json.dumps(data)  # expect: external
    codec = Codec()
    # Control case: the same name, genuinely internal.
    return codec.get("k")  # expect: cg_cases.g08_noise.Codec.get
