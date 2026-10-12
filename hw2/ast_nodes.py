"""AST node definitions for Funny. Every node has to_dict() for JSON output."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional, Union


def _node(kind: str, **kwargs) -> dict:
    d = {"kind": kind}
    d.update(kwargs)
    return d


@dataclass
class TypeInt:
    def to_dict(self) -> dict:
        return _node("TypeInt")


@dataclass
class TypeArray:
    """int[]"""
    def to_dict(self) -> dict:
        return _node("TypeArray")


Type = Union[TypeInt, TypeArray]


@dataclass
class VarDef:
    name: str
    type: Optional[Type] = None  # None for local vars without annotation

    def to_dict(self) -> dict:
        return _node(
            "VarDef",
            name=self.name,
            type=self.type.to_dict() if self.type else None,
        )


@dataclass
class IntLit:
    value: int

    def to_dict(self) -> dict:
        return _node("IntLit", value=self.value)


@dataclass
class BoolLit:
    value: bool

    def to_dict(self) -> dict:
        return _node("BoolLit", value=self.value)


@dataclass
class Var:
    name: str

    def to_dict(self) -> dict:
        return _node("Var", name=self.name)


@dataclass
class ArrayAccess:
    array: "Expr"
    index: "Expr"

    def to_dict(self) -> dict:
        return _node("ArrayAccess", array=self.array.to_dict(), index=self.index.to_dict())


@dataclass
class BinOp:
    op: str
    left: "Expr"
    right: "Expr"

    def to_dict(self) -> dict:
        return _node("BinOp", op=self.op, left=self.left.to_dict(), right=self.right.to_dict())


@dataclass
class UnOp:
    op: str
    operand: "Expr"

    def to_dict(self) -> dict:
        return _node("UnOp", op=self.op, operand=self.operand.to_dict())


@dataclass
class FunctionCall:
    name: str
    args: List["Expr"]

    def to_dict(self) -> dict:
        return _node("FunctionCall", name=self.name, args=[a.to_dict() for a in self.args])


Expr = Union[IntLit, BoolLit, Var, ArrayAccess, BinOp, UnOp, FunctionCall]


@dataclass
class Comparison:
    op: str
    left: Expr
    right: Expr

    def to_dict(self) -> dict:
        return _node("Comparison", op=self.op, left=self.left.to_dict(), right=self.right.to_dict())


@dataclass
class LogicalOp:
    op: str  # "and" | "or" | "->"
    left: "Condition"
    right: "Condition"

    def to_dict(self) -> dict:
        return _node("LogicalOp", op=self.op, left=self.left.to_dict(), right=self.right.to_dict())


@dataclass
class Not:
    operand: "Condition"

    def to_dict(self) -> dict:
        return _node("Not", operand=self.operand.to_dict())


Condition = Union[BoolLit, Comparison, LogicalOp, Not, "Quantifier", "FormulaRef"]


@dataclass
class Quantifier:
    kind: str  # "forall" | "exists"
    var: VarDef
    body: Condition

    def to_dict(self) -> dict:
        return _node("Quantifier", quant=self.kind, var=self.var.to_dict(), body=self.body.to_dict())


@dataclass
class FormulaRef:
    name: str
    args: List[Expr]

    def to_dict(self) -> dict:
        return _node("FormulaRef", name=self.name, args=[a.to_dict() for a in self.args])


@dataclass
class Assign:
    targets: List[Union[Var, ArrayAccess]]
    value: Expr

    def to_dict(self) -> dict:
        return _node(
            "Assign",
            targets=[t.to_dict() for t in self.targets],
            value=self.value.to_dict(),
        )


@dataclass
class If:
    condition: Condition
    then_branch: "Statement"
    else_branch: Optional["Statement"] = None

    def to_dict(self) -> dict:
        return _node(
            "If",
            condition=self.condition.to_dict(),
            then=self.then_branch.to_dict(),
            else_=self.else_branch.to_dict() if self.else_branch else None,
        )


@dataclass
class While:
    condition: Condition
    invariant: Optional[Condition]
    body: "Statement"

    def to_dict(self) -> dict:
        return _node(
            "While",
            condition=self.condition.to_dict(),
            invariant=self.invariant.to_dict() if self.invariant else None,
            body=self.body.to_dict(),
        )


@dataclass
class Block:
    stmts: List["Statement"]

    def to_dict(self) -> dict:
        return _node("Block", stmts=[s.to_dict() for s in self.stmts])


@dataclass
class Assert:
    predicate: Condition

    def to_dict(self) -> dict:
        return _node("Assert", predicate=self.predicate.to_dict())


@dataclass
class Assume:
    predicate: Condition

    def to_dict(self) -> dict:
        return _node("Assume", predicate=self.predicate.to_dict())


Statement = Union[Assign, If, While, Block, Assert, Assume]


@dataclass
class Function:
    name: str
    params: List[VarDef]
    returns: List[VarDef]
    requires: Optional[Condition] = None
    ensures: Optional[Condition] = None
    uses: List[VarDef] = field(default_factory=list)
    body: Statement = field(default_factory=lambda: Block([]))

    def to_dict(self) -> dict:
        return _node(
            "Function",
            name=self.name,
            params=[p.to_dict() for p in self.params],
            returns=[r.to_dict() for r in self.returns],
            requires=self.requires.to_dict() if self.requires else None,
            ensures=self.ensures.to_dict() if self.ensures else None,
            uses=[u.to_dict() for u in self.uses],
            body=self.body.to_dict(),
        )


@dataclass
class Formula:
    name: str
    params: List[VarDef]
    body: Condition

    def to_dict(self) -> dict:
        return _node(
            "Formula",
            name=self.name,
            params=[p.to_dict() for p in self.params],
            body=self.body.to_dict(),
        )


@dataclass
class Module:
    functions: List[Function] = field(default_factory=list)
    formulas: List[Formula] = field(default_factory=list)

    def to_dict(self) -> dict:
        return _node(
            "Module",
            functions=[f.to_dict() for f in self.functions],
            formulas=[f.to_dict() for f in self.formulas],
        )
