#!/usr/bin/env python3
"""
KQL -> Elasticsearch Query DSL translator
-----------------------------------------
Kibana never exposes its KQL parser over HTTP: the browser parses KQL client
side and ships plain Query DSL to /internal/bsearch. This module reimplements
the subset of KQL that log searching actually uses, so the MCP server can take
the same string a human types into the Kibana search bar.

Supported
    field:value              field:"quoted phrase"      field:*        (exists)
    field:val*               field:(a or b or c)        free text
    field >= 500             field < 2                  (numeric/date ranges)
    AND OR NOT               and or not (case insensitive)
    ( grouping )             implicit AND between adjacent clauses
    \\-escaped specials      "quotes with \\" inside"

Not supported (raises KqlError, use kibana_raw_bsearch instead)
    nested:{ ... } syntax, scripted/runtime field functions

Public API
    to_dsl(kql: str) -> dict     translate; returns {"match_all": {}} when blank
    KqlError                     raised on malformed input, message is user facing

Run `python3 kql.py "some : kql"` to print the generated DSL.
"""

from __future__ import annotations

import json
import sys
from typing import Any, Dict, List, Optional, Tuple


class KqlError(ValueError):
    """Malformed KQL. The message is meant to be shown to the caller."""


# --------------------------------------------------------------------------
# Tokenizer
# --------------------------------------------------------------------------

_KEYWORDS = {"and": "and", "or": "or", "not": "not"}
_BREAK_CHARS = set('():<>="')
_WHITESPACE = set(" \t\r\n")

# token = (kind, value)
#   kind in: lparen rparen colon op and or not word phrase
Token = Tuple[str, str]


def _tokenize(text: str) -> List[Token]:
    tokens: List[Token] = []
    i, n = 0, len(text)

    while i < n:
        ch = text[i]

        if ch in _WHITESPACE:
            i += 1
            continue

        if ch == "(":
            tokens.append(("lparen", "("))
            i += 1
            continue

        if ch == ")":
            tokens.append(("rparen", ")"))
            i += 1
            continue

        if ch == ":":
            tokens.append(("colon", ":"))
            i += 1
            continue

        if ch in "<>":
            if i + 1 < n and text[i + 1] == "=":
                tokens.append(("op", ch + "="))
                i += 2
            else:
                tokens.append(("op", ch))
                i += 1
            continue

        if ch == "=":
            # KQL has no bare '=', but people type it. Treat as ':'.
            tokens.append(("colon", ":"))
            i += 1
            continue

        if ch == '"':
            i += 1
            buf: List[str] = []
            closed = False
            while i < n:
                c = text[i]
                if c == "\\" and i + 1 < n:
                    buf.append(text[i + 1])
                    i += 2
                    continue
                if c == '"':
                    closed = True
                    i += 1
                    break
                buf.append(c)
                i += 1
            if not closed:
                raise KqlError("Unterminated quoted string in KQL.")
            tokens.append(("phrase", "".join(buf)))
            continue

        # bare word
        buf = []
        while i < n:
            c = text[i]
            if c in _WHITESPACE or c in _BREAK_CHARS:
                break
            if c == "\\" and i + 1 < n:
                buf.append(text[i + 1])
                i += 2
                continue
            buf.append(c)
            i += 1
        word = "".join(buf)
        if not word:
            raise KqlError(f"Unexpected character {text[i]!r} at position {i}.")
        lowered = word.lower()
        if lowered in _KEYWORDS:
            tokens.append((_KEYWORDS[lowered], word))
        else:
            tokens.append(("word", word))

    return tokens


# --------------------------------------------------------------------------
# Clause builders
# --------------------------------------------------------------------------

def _has_wildcard(value: str) -> bool:
    return "*" in value or "?" in value


def _coerce(value: str) -> Any:
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value


def _field_clause(field: str, kind: str, value: str) -> Dict[str, Any]:
    if kind == "phrase":
        return {"match_phrase": {field: value}}
    if value == "*":
        return {"exists": {"field": field}}
    if _has_wildcard(value):
        return {
            "query_string": {
                "fields": [field],
                "query": value,
                "analyze_wildcard": True,
            }
        }
    return {"match": {field: value}}


def _bare_clause(kind: str, value: str) -> Dict[str, Any]:
    if kind == "phrase":
        return {"multi_match": {"query": value, "type": "phrase", "lenient": True}}
    if _has_wildcard(value):
        return {"query_string": {"query": value, "analyze_wildcard": True, "lenient": True}}
    return {"multi_match": {"query": value, "lenient": True}}


_RANGE_KEYS = {">": "gt", ">=": "gte", "<": "lt", "<=": "lte"}


def _range_clause(field: str, op: str, value: str) -> Dict[str, Any]:
    return {"range": {field: {_RANGE_KEYS[op]: _coerce(value)}}}


def _and(clauses: List[Dict[str, Any]]) -> Dict[str, Any]:
    if len(clauses) == 1:
        return clauses[0]
    return {"bool": {"filter": clauses}}


def _or(clauses: List[Dict[str, Any]]) -> Dict[str, Any]:
    if len(clauses) == 1:
        return clauses[0]
    return {"bool": {"should": clauses, "minimum_should_match": 1}}


def _not(clause: Dict[str, Any]) -> Dict[str, Any]:
    return {"bool": {"must_not": [clause]}}


# --------------------------------------------------------------------------
# Parser (recursive descent)
# --------------------------------------------------------------------------

_PRIMARY_STARTERS = {"word", "phrase", "lparen", "not"}


class _Parser:
    def __init__(self, tokens: List[Token]) -> None:
        self.tokens = tokens
        self.pos = 0

    # -- helpers ----------------------------------------------------------
    def peek(self, offset: int = 0) -> Optional[Token]:
        idx = self.pos + offset
        return self.tokens[idx] if idx < len(self.tokens) else None

    def next(self) -> Token:
        tok = self.peek()
        if tok is None:
            raise KqlError("Unexpected end of KQL expression.")
        self.pos += 1
        return tok

    def expect(self, kind: str) -> Token:
        tok = self.next()
        if tok[0] != kind:
            raise KqlError(f"Expected {kind} but found {tok[1]!r}.")
        return tok

    # -- grammar ----------------------------------------------------------
    def parse(self) -> Dict[str, Any]:
        if not self.tokens:
            return {"match_all": {}}
        node = self.parse_or()
        if self.pos != len(self.tokens):
            raise KqlError(f"Unexpected trailing token {self.tokens[self.pos][1]!r}.")
        return node

    def parse_or(self) -> Dict[str, Any]:
        clauses = [self.parse_and()]
        while self.peek() and self.peek()[0] == "or":
            self.next()
            clauses.append(self.parse_and())
        return _or(clauses)

    def parse_and(self) -> Dict[str, Any]:
        clauses = [self.parse_not()]
        while True:
            tok = self.peek()
            if tok is None:
                break
            if tok[0] == "and":
                self.next()
                clauses.append(self.parse_not())
                continue
            # implicit AND between adjacent clauses, as Kibana does
            if tok[0] in _PRIMARY_STARTERS:
                clauses.append(self.parse_not())
                continue
            break
        return _and(clauses)

    def parse_not(self) -> Dict[str, Any]:
        if self.peek() and self.peek()[0] == "not":
            self.next()
            return _not(self.parse_not())
        return self.parse_primary()

    def parse_primary(self) -> Dict[str, Any]:
        tok = self.next()

        if tok[0] == "lparen":
            node = self.parse_or()
            self.expect("rparen")
            return node

        if tok[0] not in ("word", "phrase"):
            raise KqlError(f"Unexpected token {tok[1]!r} in KQL expression.")

        nxt = self.peek()

        # field : value
        if nxt and nxt[0] == "colon":
            if tok[0] == "phrase":
                raise KqlError("A quoted string cannot be used as a field name.")
            self.next()
            return self.parse_field_value(tok[1])

        # field >= value
        if nxt and nxt[0] == "op":
            if tok[0] == "phrase":
                raise KqlError("A quoted string cannot be used as a field name.")
            op = self.next()[1]
            val = self.next()
            if val[0] not in ("word", "phrase"):
                raise KqlError(f"Expected a value after {op!r}.")
            return _range_clause(tok[1], op, val[1])

        # bare term / phrase
        return _bare_clause(tok[0], tok[1])

    def parse_field_value(self, field: str) -> Dict[str, Any]:
        tok = self.peek()
        if tok is None:
            raise KqlError(f"Field {field!r} has no value after ':'.")

        if tok[0] == "lparen":
            self.next()
            node = self.parse_value_or(field)
            self.expect("rparen")
            return node

        if tok[0] == "not":
            self.next()
            return _not(self.parse_field_value(field))

        if tok[0] not in ("word", "phrase"):
            raise KqlError(f"Field {field!r} has no value after ':'.")

        self.next()
        return _field_clause(field, tok[0], tok[1])

    # value lists inside  field:( a or b )
    def parse_value_or(self, field: str) -> Dict[str, Any]:
        clauses = [self.parse_value_and(field)]
        while self.peek() and self.peek()[0] == "or":
            self.next()
            clauses.append(self.parse_value_and(field))
        return _or(clauses)

    def parse_value_and(self, field: str) -> Dict[str, Any]:
        clauses = [self.parse_value_not(field)]
        while True:
            tok = self.peek()
            if tok is None:
                break
            if tok[0] == "and":
                self.next()
                clauses.append(self.parse_value_not(field))
                continue
            if tok[0] in ("word", "phrase", "lparen", "not"):
                clauses.append(self.parse_value_not(field))
                continue
            break
        return _and(clauses)

    def parse_value_not(self, field: str) -> Dict[str, Any]:
        if self.peek() and self.peek()[0] == "not":
            self.next()
            return _not(self.parse_value_not(field))
        tok = self.peek()
        if tok and tok[0] == "lparen":
            self.next()
            node = self.parse_value_or(field)
            self.expect("rparen")
            return node
        tok = self.next()
        if tok[0] not in ("word", "phrase"):
            raise KqlError(f"Expected a value for field {field!r}, found {tok[1]!r}.")
        return _field_clause(field, tok[0], tok[1])


def to_dsl(kql: Optional[str]) -> Dict[str, Any]:
    """Translate a KQL string into an Elasticsearch Query DSL clause."""
    if kql is None or not kql.strip():
        return {"match_all": {}}
    return _Parser(_tokenize(kql)).parse()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.stderr.write('usage: python3 kql.py "log.level:ERROR and message:*timeout*"\n')
        sys.exit(2)
    print(json.dumps(to_dsl(" ".join(sys.argv[1:])), indent=2))
