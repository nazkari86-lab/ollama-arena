"""Data and math tools."""
from __future__ import annotations

import ast
import math
import operator
from typing import Callable

import requests

_SAFE_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _eval_node(node):
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError("Only numeric constants allowed")
    if isinstance(node, ast.BinOp):
        op = _SAFE_OPS.get(type(node.op))
        if not op:
            raise ValueError("Unsupported operator")
        return op(_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp):
        op = _SAFE_OPS.get(type(node.op))
        if not op:
            raise ValueError("Unsupported unary operator")
        return op(_eval_node(node.operand))
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        funcs = {"sqrt": math.sqrt, "sin": math.sin, "cos": math.cos, "log": math.log}
        if node.func.id in funcs and len(node.args) == 1:
            return funcs[node.func.id](_eval_node(node.args[0]))
    raise ValueError("Unsupported expression")


def math_solver(args: dict) -> str:
    expr = args.get("expression") or args.get("expr") or ""
    if not expr:
        return "Error: expression required."
    try:
        tree = ast.parse(expr, mode="eval")
        result = _eval_node(tree.body)
        return f"{expr} = {result}"
    except Exception as exc:
        return f"Error: {exc}"


def crypto_price(args: dict) -> str:
    coin = (args.get("coin") or args.get("id") or "bitcoin").lower()
    try:
        resp = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": coin, "vs_currencies": "usd"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if coin not in data:
            return f"Error: Unknown coin '{coin}'."
        price = data[coin]["usd"]
        return f"{coin}: ${price:,.2f} USD"
    except Exception as exc:
        return f"Error: {exc}"


def tool_defs() -> list[tuple[str, Callable[[dict], str], dict, str]]:
    return [
        (
            "math_solver",
            math_solver,
            {
                "type": "function",
                "function": {
                    "name": "math_solver",
                    "description": "Safely evaluate a mathematical expression.",
                    "parameters": {
                        "type": "object",
                        "properties": {"expression": {"type": "string"}},
                        "required": ["expression"],
                    },
                },
            },
            "safe",
        ),
        (
            "crypto_price",
            crypto_price,
            {
                "type": "function",
                "function": {
                    "name": "crypto_price",
                    "description": "Get live cryptocurrency price from CoinGecko.",
                    "parameters": {
                        "type": "object",
                        "properties": {"coin": {"type": "string"}},
                    },
                },
            },
            "safe",
        ),
    ]
