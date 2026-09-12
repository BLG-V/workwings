"""Safe expression subset evaluator for MAWP condition nodes.

Design goals
------------
* Never call ``eval`` / ``exec`` / ``compile``.
* Only whitelist: literals, dotted context paths, comparisons, and/or/not.
* No attribute access on arbitrary objects, no function calls, no indexing syntax.

Supported grammar (recursive-descent)::

    expr        := or_expr
    or_expr     := and_expr ( 'or' and_expr )*
    and_expr    := not_expr ( 'and' not_expr )*
    not_expr    := 'not' not_expr | comparison
    comparison  := primary ( comparator primary )?
    comparator  := '==' | '!=' | '>' | '<' | '>=' | '<='
    primary     := literal | path | '(' expr ')'
    literal     := STRING | NUMBER | true | false
    path        := IDENT ( '.' IDENT )*

Template sugar: ``{{ nodes.x.output.label }}`` is normalized to a path
before tokenization, matching YAML expr style used in workflows.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterator, Mapping, Sequence

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ExprError(Exception):
    """Base error for expression evaluation."""


class ExprSyntaxError(ExprError):
    """Expression cannot be parsed under the safe subset."""


class ExprNameError(ExprError):
    """A context path segment is missing (never silently None)."""


class ExprTypeError(ExprError):
    """Operand types are incompatible with an operator."""


class ExprSecurityError(ExprError):
    """Input attempts capabilities outside the whitelist."""


# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------


class TokenType(str, Enum):
    STRING = "STRING"
    NUMBER = "NUMBER"
    IDENT = "IDENT"
    TRUE = "TRUE"
    FALSE = "FALSE"
    EQ = "EQ"
    NE = "NE"
    GT = "GT"
    LT = "LT"
    GE = "GE"
    LE = "LE"
    AND = "AND"
    OR = "OR"
    NOT = "NOT"
    LPAREN = "LPAREN"
    RPAREN = "RPAREN"
    DOT = "DOT"
    EOF = "EOF"


@dataclass(frozen=True, slots=True)
class Token:
    type: TokenType
    value: Any
    pos: int


_COMPARATORS = {
    TokenType.EQ,
    TokenType.NE,
    TokenType.GT,
    TokenType.LT,
    TokenType.GE,
    TokenType.LE,
}

# Exact identifier names that are never allowed as path segments.
_BANNED_IDENTS: frozenset[str] = frozenset(
    {
        "eval",
        "exec",
        "compile",
        "open",
        "globals",
        "locals",
        "getattr",
        "setattr",
        "delattr",
        "builtins",
        "import",
        "__import__",
    }
)

# Characters that immediately indicate unsupported / dangerous syntax.
_BANNED_CHARS = set("[];{}`$\\")


# ---------------------------------------------------------------------------
# AST nodes
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class LiteralNode:
    value: Any


@dataclass(frozen=True, slots=True)
class PathNode:
    parts: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class UnaryOp:
    op: str  # "not"
    operand: Any


@dataclass(frozen=True, slots=True)
class BinaryOp:
    op: str
    left: Any
    right: Any


AstNode = LiteralNode | PathNode | UnaryOp | BinaryOp


# ---------------------------------------------------------------------------
# Preprocess / tokenize
# ---------------------------------------------------------------------------

# {{ nodes.a.b }}  ->  nodes.a.b
_TEMPLATE_PATH_RE = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)\s*\}\}")


def _normalize_templates(expr: str) -> str:
    """Rewrite ``{{ path }}`` sugar into bare dotted paths."""

    def repl(match: re.Match[str]) -> str:
        return match.group(1)

    return _TEMPLATE_PATH_RE.sub(repl, expr)


def _scan_string(src: str, start: int) -> tuple[str, int]:
    """Parse a single- or double-quoted string; no escapes beyond \\', \\\", \\\\."""
    quote = src[start]
    i = start + 1
    out: list[str] = []
    while i < len(src):
        ch = src[i]
        if ch == "\\" and i + 1 < len(src):
            nxt = src[i + 1]
            if nxt in ("\\", "'", '"'):
                out.append(nxt)
                i += 2
                continue
            raise ExprSyntaxError(f"unsupported escape at pos {i}")
        if ch == quote:
            return "".join(out), i + 1
        out.append(ch)
        i += 1
    raise ExprSyntaxError(f"unterminated string starting at pos {start}")


def _tokenize(expr: str) -> list[Token]:
    s = expr.strip()
    if not s:
        raise ExprSyntaxError("expression is empty")

    for ch in s:
        if ch in _BANNED_CHARS:
            raise ExprSecurityError(f"banned character {ch!r} in expression")

    tokens: list[Token] = []
    i = 0
    n = len(s)

    while i < n:
        ch = s[i]

        # whitespace
        if ch.isspace():
            i += 1
            continue

        # strings
        if ch in ("'", '"'):
            value, i = _scan_string(s, i)
            tokens.append(Token(TokenType.STRING, value, i))
            continue

        # multi-char operators
        if s.startswith("==", i):
            tokens.append(Token(TokenType.EQ, "==", i))
            i += 2
            continue
        if s.startswith("!=", i):
            tokens.append(Token(TokenType.NE, "!=", i))
            i += 2
            continue
        if s.startswith(">=", i):
            tokens.append(Token(TokenType.GE, ">=", i))
            i += 2
            continue
        if s.startswith("<=", i):
            tokens.append(Token(TokenType.LE, "<=", i))
            i += 2
            continue

        # single-char operators / punctuation
        if ch == ">":
            tokens.append(Token(TokenType.GT, ">", i))
            i += 1
            continue
        if ch == "<":
            tokens.append(Token(TokenType.LT, "<", i))
            i += 1
            continue
        if ch == "(":
            tokens.append(Token(TokenType.LPAREN, "(", i))
            i += 1
            continue
        if ch == ")":
            tokens.append(Token(TokenType.RPAREN, ")", i))
            i += 1
            continue
        if ch == ".":
            tokens.append(Token(TokenType.DOT, ".", i))
            i += 1
            continue

        # numbers (int / float); optional leading minus only if previous token
        # was an operator / start (handled by unary minus as part of number here
        # when at start or after comparator / lparen / and / or / not).
        if ch.isdigit() or (
            ch == "-"
            and i + 1 < n
            and s[i + 1].isdigit()
            and _unary_minus_allowed(tokens)
        ):
            j = i + 1 if ch == "-" else i
            dot_seen = False
            while j < n and (s[j].isdigit() or (s[j] == "." and not dot_seen)):
                if s[j] == ".":
                    dot_seen = True
                j += 1
            raw = s[i:j]
            # reject things like 1.2.3
            if raw.count(".") > 1:
                raise ExprSyntaxError(f"invalid number literal {raw!r}")
            number: int | float = float(raw) if "." in raw else int(raw)
            tokens.append(Token(TokenType.NUMBER, number, i))
            i = j
            continue

        # identifiers / keywords
        if ch.isalpha() or ch == "_":
            j = i + 1
            while j < n and (s[j].isalnum() or s[j] == "_"):
                j += 1
            word = s[i:j]
            lower = word.lower()
            if lower == "true":
                tokens.append(Token(TokenType.TRUE, True, i))
            elif lower == "false":
                tokens.append(Token(TokenType.FALSE, False, i))
            elif lower == "and":
                tokens.append(Token(TokenType.AND, "and", i))
            elif lower == "or":
                tokens.append(Token(TokenType.OR, "or", i))
            elif lower == "not":
                tokens.append(Token(TokenType.NOT, "not", i))
            else:
                _assert_safe_ident(word, pos=i)
                tokens.append(Token(TokenType.IDENT, word, i))
            i = j
            continue

        raise ExprSecurityError(f"unexpected / banned character {ch!r} at pos {i}")

    tokens.append(Token(TokenType.EOF, None, n))
    return tokens


def _unary_minus_allowed(tokens: Sequence[Token]) -> bool:
    if not tokens:
        return True
    prev = tokens[-1].type
    return prev in (
        TokenType.EQ,
        TokenType.NE,
        TokenType.GT,
        TokenType.LT,
        TokenType.GE,
        TokenType.LE,
        TokenType.AND,
        TokenType.OR,
        TokenType.NOT,
        TokenType.LPAREN,
    )


def _assert_safe_ident(name: str, *, pos: int) -> None:
    # Dunder / private attribute smuggling via path segments.
    if "__" in name:
        raise ExprSecurityError(
            f"banned dunder identifier {name!r} at pos {pos}"
        )
    if name.lower() in _BANNED_IDENTS:
        raise ExprSecurityError(f"banned identifier {name!r} at pos {pos}")


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


class _Parser:
    """Recursive-descent parser producing a tiny AST (no code objects)."""

    def __init__(self, tokens: Sequence[Token]) -> None:
        self._tokens = tokens
        self._i = 0

    def parse(self) -> AstNode:
        node = self._parse_or()
        if self._peek().type != TokenType.EOF:
            tok = self._peek()
            raise ExprSyntaxError(f"unexpected token {tok.type} at pos {tok.pos}")
        return node

    def _peek(self) -> Token:
        return self._tokens[self._i]

    def _advance(self) -> Token:
        tok = self._tokens[self._i]
        self._i += 1
        return tok

    def _match(self, *types: TokenType) -> Token | None:
        if self._peek().type in types:
            return self._advance()
        return None

    def _parse_or(self) -> AstNode:
        left = self._parse_and()
        while self._match(TokenType.OR):
            right = self._parse_and()
            left = BinaryOp("or", left, right)
        return left

    def _parse_and(self) -> AstNode:
        left = self._parse_not()
        while self._match(TokenType.AND):
            right = self._parse_not()
            left = BinaryOp("and", left, right)
        return left

    def _parse_not(self) -> AstNode:
        if self._match(TokenType.NOT):
            return UnaryOp("not", self._parse_not())
        return self._parse_comparison()

    def _parse_comparison(self) -> AstNode:
        left = self._parse_primary()
        op_tok = self._match(
            TokenType.EQ,
            TokenType.NE,
            TokenType.GT,
            TokenType.LT,
            TokenType.GE,
            TokenType.LE,
        )
        if op_tok is None:
            return left
        # Only a single comparison (no chained a < b < c) — keeps subset simple.
        right = self._parse_primary()
        if self._peek().type in _COMPARATORS:
            raise ExprSyntaxError(
                "chained comparisons are not supported; use and/or explicitly"
            )
        return BinaryOp(str(op_tok.value), left, right)

    def _parse_primary(self) -> AstNode:
        tok = self._peek()

        if tok.type == TokenType.STRING:
            self._advance()
            return LiteralNode(tok.value)
        if tok.type == TokenType.NUMBER:
            self._advance()
            return LiteralNode(tok.value)
        if tok.type == TokenType.TRUE:
            self._advance()
            return LiteralNode(True)
        if tok.type == TokenType.FALSE:
            self._advance()
            return LiteralNode(False)

        if tok.type == TokenType.IDENT:
            return self._parse_path()

        if self._match(TokenType.LPAREN):
            node = self._parse_or()
            if not self._match(TokenType.RPAREN):
                raise ExprSyntaxError("missing closing ')'")
            return node

        raise ExprSyntaxError(f"expected value at pos {tok.pos}, got {tok.type}")

    def _parse_path(self) -> PathNode:
        first = self._advance()
        assert first.type == TokenType.IDENT
        parts: list[str] = [str(first.value)]

        while self._match(TokenType.DOT):
            nxt = self._peek()
            if nxt.type != TokenType.IDENT:
                raise ExprSyntaxError(f"expected identifier after '.' at pos {nxt.pos}")
            ident = self._advance()
            name = str(ident.value)
            _assert_safe_ident(name, pos=ident.pos)
            parts.append(name)

        # Function-call shape: ident(  — hard reject (no calls allowed).
        if self._peek().type == TokenType.LPAREN and len(parts) == 1:
            # Could be grouping after a bare word — still treat word( as call attempt
            # unless we already consumed a path. Bare `foo(` is a call.
            raise ExprSecurityError(
                f"function calls are forbidden near {parts[0]!r}"
            )

        return PathNode(tuple(parts))


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------


def _resolve_path(parts: Sequence[str], context: Mapping[str, Any]) -> Any:
    """Walk a dotted path through mappings only (no attribute access)."""
    if not parts:
        raise ExprNameError("empty path")

    cur: Any = context
    walked: list[str] = []
    for key in parts:
        walked.append(key)
        path_str = ".".join(walked)
        if not isinstance(cur, Mapping):
            raise ExprNameError(
                f"cannot resolve '{path_str}': parent is {type(cur).__name__}, "
                "not a mapping"
            )
        if key not in cur:
            raise ExprNameError(f"context path not found: '{path_str}'")
        cur = cur[key]
    return cur


def _compare(op: str, left: Any, right: Any) -> bool:
    try:
        if op == "==":
            return left == right
        if op == "!=":
            return left != right
        if op == ">":
            return left > right
        if op == "<":
            return left < right
        if op == ">=":
            return left >= right
        if op == "<=":
            return left <= right
    except TypeError as exc:
        raise ExprTypeError(
            f"cannot apply {op!r} between {type(left).__name__} and {type(right).__name__}"
        ) from exc
    raise ExprSyntaxError(f"unknown comparator {op!r}")


def _eval_ast(node: AstNode, context: Mapping[str, Any]) -> Any:
    if isinstance(node, LiteralNode):
        return node.value
    if isinstance(node, PathNode):
        return _resolve_path(node.parts, context)
    if isinstance(node, UnaryOp):
        if node.op == "not":
            return not bool(_eval_ast(node.operand, context))
        raise ExprSyntaxError(f"unknown unary op {node.op!r}")
    if isinstance(node, BinaryOp):
        if node.op == "and":
            # short-circuit
            left = _eval_ast(node.left, context)
            return bool(left) and bool(_eval_ast(node.right, context))
        if node.op == "or":
            left = _eval_ast(node.left, context)
            return bool(left) or bool(_eval_ast(node.right, context))
        if node.op in {"==", "!=", ">", "<", ">=", "<="}:
            left = _eval_ast(node.left, context)
            right = _eval_ast(node.right, context)
            return _compare(node.op, left, right)
        raise ExprSyntaxError(f"unknown binary op {node.op!r}")
    raise ExprSyntaxError(f"unknown AST node {type(node).__name__}")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class ExprEvaluator:
    """Whitelist expression evaluator for condition nodes.

    Example::

        ev = ExprEvaluator()
        ev.evaluate(
            "{{ nodes.n_classify.output.label }} == 'urgent'",
            {"nodes": {"n_classify": {"output": {"label": "urgent"}}}},
        )
    """

    def evaluate(self, expr: str, context: dict[str, Any]) -> Any:
        """Evaluate ``expr`` against ``context`` and return the result.

        Parameters
        ----------
        expr:
            Safe-subset expression string. May include ``{{ path }}`` sugar.
        context:
            Mapping root that typically contains ``nodes`` / ``params`` / ``vars``.

        Returns
        -------
        Any
            Usually ``bool`` for comparisons; literals/paths may return other types
            if the whole expression is a bare primary (useful for debugging).

        Raises
        ------
        ExprSyntaxError
            Parse / grammar errors.
        ExprNameError
            Missing context path (never returns None silently).
        ExprTypeError
            Illegal operand types for an operator.
        ExprSecurityError
            Attempts to use banned syntax or identifiers.
        """
        if not isinstance(expr, str):
            raise ExprSyntaxError("expr must be a str")
        if not isinstance(context, Mapping):
            raise ExprSyntaxError("context must be a mapping")

        # Defense: reject if raw source still contains eval/exec keywords as idents
        # even before tokenization (belt and suspenders with tokenizer bans).
        lowered = expr.lower()
        for banned in ("eval(", "exec(", "compile(", "__"):
            if banned in lowered:
                raise ExprSecurityError(f"banned pattern {banned!r} in expression")

        normalized = _normalize_templates(expr)
        tokens = _tokenize(normalized)
        # Extra pass: IDENT followed immediately by LPAREN anywhere => call.
        self._reject_calls(tokens)
        ast = _Parser(tokens).parse()
        return _eval_ast(ast, context)

    @staticmethod
    def _reject_calls(tokens: Sequence[Token]) -> None:
        for idx in range(len(tokens) - 1):
            if (
                tokens[idx].type == TokenType.IDENT
                and tokens[idx + 1].type == TokenType.LPAREN
            ):
                raise ExprSecurityError(
                    f"function calls are forbidden: {tokens[idx].value}("
                )
