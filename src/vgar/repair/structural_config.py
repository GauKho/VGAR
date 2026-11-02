"""Host-owned structural policy: literal dotted prefixes, safe YAML, no target code."""
from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml


def _name(value: Any) -> bool:
    return isinstance(value, str) and bool(value) and value.strip() == value


def _prefix(value: Any) -> bool:
    return _name(value) and all(part.isidentifier() for part in value.split('.'))


def validate_structural_config(value: Mapping[str, Any], *, repo_key: str | None = None) -> dict[str, Any]:
    """Validate and detach a policy. Absence is represented by None, not {}.

    Layer prefixes may overlap; the longest namespace match wins. An identical
    prefix in two layers is invalid. There are no implicit layer permissions.
    """
    allowed = {'repo_key', 'forbidden_imports', 'layers', 'allowed_layer_imports'}
    if not isinstance(value, Mapping) or set(value) - allowed or not _name(value.get('repo_key')):
        raise ValueError('Structural config requires repo_key and only documented fields')
    if repo_key is not None and value['repo_key'] != repo_key:
        raise ValueError('Structural config repo_key differs from graph repository')
    result: dict[str, Any] = {'repo_key': value['repo_key']}
    if 'forbidden_imports' in value:
        rules = value['forbidden_imports']
        if not isinstance(rules, list):
            raise ValueError('forbidden_imports must be a list')
        pairs = set()
        for rule in rules:
            if (not isinstance(rule, Mapping) or set(rule) != {'source', 'target'}
                    or not _prefix(rule['source']) or not _prefix(rule['target'])):
                raise ValueError('Forbidden rule requires source/target dotted module prefixes')
            pair = (rule['source'], rule['target'])
            if pair in pairs:
                raise ValueError('Duplicate forbidden-import rule')
            pairs.add(pair)
        result['forbidden_imports'] = [{'source': a, 'target': b} for a, b in sorted(pairs)]
    if ('layers' in value) != ('allowed_layer_imports' in value):
        raise ValueError('layers and allowed_layer_imports must be supplied together')
    if 'layers' in value:
        layers, permissions = value['layers'], value['allowed_layer_imports']
        if (not isinstance(layers, Mapping) or not layers or not all(_name(k) for k in layers)
                or not isinstance(permissions, Mapping) or set(permissions) != set(layers)):
            raise ValueError('Layer definitions and permissions must have the same nonempty label set')
        used = set()
        normalized_layers, normalized_permissions = {}, {}
        for label in sorted(layers):
            prefixes, targets = layers[label], permissions[label]
            if (not isinstance(prefixes, list) or not prefixes or not all(_prefix(p) for p in prefixes)
                    or len(set(prefixes)) != len(prefixes) or used.intersection(prefixes)):
                raise ValueError('Each module prefix must belong to exactly one configured layer')
            if (not isinstance(targets, list) or not all(_name(t) for t in targets)
                    or len(set(targets)) != len(targets) or set(targets) - set(layers)):
                raise ValueError('Layer permissions require unique known target layers')
            used.update(prefixes)
            normalized_layers[label], normalized_permissions[label] = sorted(prefixes), sorted(targets)
        result.update(layers=normalized_layers, allowed_layer_imports=normalized_permissions)
    return result


def load_structural_config(path: Path | str | None) -> dict[str, Any] | None:
    """Missing policy -> None. Malformed/unsafe/duplicate-key/aliased YAML -> ValueError.

    Compose is used only to reject ambiguous keys/aliases; construction still
    goes through yaml.safe_load. No custom object tags, templates or evaluation.
    """
    if path is None:
        return None
    try:
        text = Path(path).read_text(encoding='utf-8-sig')
    except FileNotFoundError:
        return None
    except (OSError, TypeError, UnicodeError) as error:
        raise ValueError('Cannot read structural policy') from error
    try:
        tree = yaml.compose(text, Loader=yaml.SafeLoader)
        pending, seen = [tree], set()
        while pending:
            node = pending.pop()
            if node is None:
                continue
            if id(node) in seen:
                raise ValueError('YAML aliases are not supported in structural policies')
            seen.add(id(node))
            if isinstance(node, yaml.MappingNode):
                keys = set()
                for key, child in node.value:
                    if not isinstance(key, yaml.ScalarNode) or key.tag != 'tag:yaml.org,2002:str':
                        raise ValueError('Structural policy keys must be strings')
                    if key.value in keys:
                        raise ValueError('Duplicate YAML mapping key: ' + key.value)
                    keys.add(key.value)
                    pending.extend((key, child))
            elif isinstance(node, yaml.SequenceNode):
                pending.extend(node.value)
        data = yaml.safe_load(text)
    except yaml.YAMLError as error:
        raise ValueError('Invalid or unsafe structural YAML') from error
    return validate_structural_config(data)
