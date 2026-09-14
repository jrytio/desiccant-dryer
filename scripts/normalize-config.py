#!/usr/bin/env python3
"""Canonicalise `esphome config` output so two configs can be diffed
regardless of section order or list order.

Usage: normalize-config.py CONFIG_DUMP.txt > canonical.json
Run with ESPHome's own Python so PyYAML is available, e.g.
  "$(dirname "$(readlink -f "$(which esphome)")")/python" scripts/normalize-config.py dump.txt
"""
import json
import sys

import yaml


class AnyTag(yaml.SafeLoader):
    """SafeLoader that keeps unknown tags such as !lambda as data."""


def _any_ctor(loader, tag_suffix, node):
    if isinstance(node, yaml.ScalarNode):
        return {"__tag__": tag_suffix, "v": loader.construct_scalar(node)}
    if isinstance(node, yaml.SequenceNode):
        return {"__tag__": tag_suffix, "v": loader.construct_sequence(node)}
    return {"__tag__": tag_suffix, "v": loader.construct_mapping(node)}


AnyTag.add_multi_constructor("!", _any_ctor)


def canon(x, top=False):
    """Sort mapping keys everywhere. Sort a list only when it is the direct
    value of a top-level key (the component lists, whose order ESPHome does
    not care about). Nested lists such as `then:` actions and `filters:` are
    ordered semantics and are left in place."""
    if isinstance(x, dict):
        return {k: canon(v, top=False) for k, v in sorted(x.items())}
    if isinstance(x, list):
        items = [canon(v) for v in x]
        if top:
            items.sort(key=lambda v: json.dumps(v, sort_keys=True))
        return items
    return x


def main(path):
    with open(path) as f:
        text = "".join(l for l in f if not l.startswith(("INFO", "WARNING")))
    data = yaml.load(text, Loader=AnyTag)
    out = {k: canon(v, top=True) for k, v in sorted(data.items())}
    print(json.dumps(out, indent=1, sort_keys=True))


if __name__ == "__main__":
    main(sys.argv[1])
