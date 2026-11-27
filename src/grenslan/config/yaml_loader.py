"""Strict, data-only YAML loading for operator configuration (PC-059).

Configuration is plain data, so only the JSON-compatible subset of YAML is
accepted: one document whose root is a mapping with string keys, containing
mappings, sequences, strings, integers, finite floats, booleans and nulls.

Rejected, each with the offending line number:

- duplicate keys, which PyYAML otherwise resolves silently to the last value;
- every explicit tag, including executable ``!!python/*`` tags, custom tags and
  standard ones such as ``!!binary`` or ``!!set``;
- anchors, aliases and ``<<`` merge keys, which let one value appear under
  several keys and hide duplicates;
- unquoted timestamps, which YAML would turn into date objects;
- ``.inf`` and ``.nan``;
- multiple documents, oversized text and nesting beyond a fixed depth.

Structure is checked on the parser's event stream before any node graph is
composed. That pass never recurses, so hostile nesting cannot exhaust the
stack. Error reasons never quote configuration content, because a value may be
a secret that was pasted into the wrong place.
"""

from __future__ import annotations

import math
from typing import Any

import yaml
from yaml.events import (
    AliasEvent,
    CollectionEndEvent,
    CollectionStartEvent,
    DocumentStartEvent,
    NodeEvent,
)
from yaml.nodes import MappingNode, Node, ScalarNode, SequenceNode

DEFAULT_MAX_DEPTH = 32

_TAG = "tag:yaml.org,2002:"
_PLAIN_SCALARS = {_TAG + name for name in ("str", "int", "float", "bool", "null")}


class ConfigSyntaxError(ValueError):
    """The configuration text is not acceptable plain-data YAML."""

    def __init__(self, reason: str, line: int) -> None:
        super().__init__(f"line {line}: {reason}")
        self.reason = reason
        self.line = line


def _line(node_or_event: Any) -> int:
    mark = getattr(node_or_event, "start_mark", None)
    return mark.line + 1 if mark is not None else 1


def _check_events(text: str, max_depth: int) -> None:
    depth = 0
    documents = 0
    try:
        for event in yaml.parse(text, Loader=yaml.SafeLoader):
            if isinstance(event, DocumentStartEvent):
                documents += 1
                if documents > 1:
                    raise ConfigSyntaxError("configuration must be a single document", _line(event))
            elif isinstance(event, AliasEvent):
                raise ConfigSyntaxError("aliases are not permitted", _line(event))
            elif isinstance(event, NodeEvent):
                if event.anchor is not None:
                    raise ConfigSyntaxError("anchors are not permitted", _line(event))
                if getattr(event, "tag", None) is not None:
                    raise ConfigSyntaxError("explicit tags are not permitted", _line(event))
                if isinstance(event, CollectionStartEvent):
                    depth += 1
                    if depth > max_depth:
                        raise ConfigSyntaxError("configuration exceeds the maximum nesting depth", _line(event))
            elif isinstance(event, CollectionEndEvent):
                depth -= 1
    except yaml.MarkedYAMLError as exc:
        mark = exc.problem_mark or exc.context_mark
        raise ConfigSyntaxError("invalid yaml syntax", mark.line + 1 if mark else 1) from None
    except yaml.YAMLError:
        raise ConfigSyntaxError("invalid yaml syntax", 1) from None


class _Builder:
    def __init__(self, loader: yaml.SafeLoader) -> None:
        self._loader = loader

    def build(self, node: Node) -> Any:
        if isinstance(node, MappingNode):
            return self._mapping(node)
        if isinstance(node, SequenceNode):
            return [self.build(item) for item in node.value]
        if isinstance(node, ScalarNode):
            return self._scalar(node)
        raise ConfigSyntaxError("unsupported yaml node", _line(node))

    def _mapping(self, node: MappingNode) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key_node, value_node in node.value:
            if key_node.tag == _TAG + "merge":
                raise ConfigSyntaxError("merge keys are not permitted", _line(key_node))
            if not isinstance(key_node, ScalarNode) or key_node.tag != _TAG + "str":
                raise ConfigSyntaxError("mapping keys must be plain strings", _line(key_node))
            key = key_node.value
            if key in result:
                raise ConfigSyntaxError("duplicate key", _line(key_node))
            result[key] = self.build(value_node)
        return result

    def _scalar(self, node: ScalarNode) -> Any:
        if node.tag == _TAG + "timestamp":
            raise ConfigSyntaxError("quote date and time values as strings", _line(node))
        if node.tag not in _PLAIN_SCALARS:
            raise ConfigSyntaxError("unsupported scalar type; quote the value as a string", _line(node))
        value = self._loader.construct_object(node)
        if isinstance(value, float) and not math.isfinite(value):
            raise ConfigSyntaxError("non-finite numbers are not permitted", _line(node))
        return value


def load_config_text(text: str, *, max_bytes: int, max_depth: int = DEFAULT_MAX_DEPTH) -> dict[str, Any]:
    """Parse configuration text into plain data or raise :class:`ConfigSyntaxError`."""
    if len(text.encode("utf-8")) > max_bytes:
        raise ConfigSyntaxError("configuration exceeds the size limit", 1)
    _check_events(text, max_depth)
    loader = yaml.SafeLoader(text)
    try:
        root = loader.get_single_node()
        if not isinstance(root, MappingNode):
            raise ConfigSyntaxError("configuration root must be a mapping", _line(root))
        result: dict[str, Any] = _Builder(loader).build(root)
        return result
    except yaml.MarkedYAMLError as exc:
        mark = exc.problem_mark or exc.context_mark
        raise ConfigSyntaxError("invalid yaml syntax", mark.line + 1 if mark else 1) from None
    finally:
        loader.dispose()
