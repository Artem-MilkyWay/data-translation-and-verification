"""AST node definitions for Funny. Every node has to_dict() for JSON output."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional, Union


@dataclass(frozen=True)
class Position:
    line: int
    column: int
    offset: int

    def to_dict(self) -> dict:
        return {"line": self.line, "column": self.column, "offset": self.offset}


def _node(kind: str, source: "Node", **kwargs) -> dict:
    d = {"kind": kind}
    d.update(kwargs)
    # HW3 metadata; each class still serializes its own HW2 fields below.
    if source.position is not None:
        d["position"] = source.position.to_dict()
    inferred_type = getattr(source, "inferred_type", None)
    if inferred_type is not None:
        d["inferred_type"] = inferred_type.to_dict()
    symbol_id = getattr(source, "symbol_id", None)
    if symbol_id is not None:
        d["symbol_id"] = symbol_id
    return d


@dataclass
class TypeInt:
    position: Optional[Position] = None

    def to_dict(self) -> dict:
        return _node("TypeInt", self)


@dataclass
class TypeBool:
    position: Optional[Position] = None

    def to_dict(self) -> dict:
        return _node("TypeBool", self)


@dataclass
class TypeArray:
    """int[]"""
    position: Optional[Position] = None

    def to_dict(self) -> dict:
        return _node("TypeArray", self)


Type = Union[TypeInt, TypeBool, TypeArray]


@dataclass
class VarDef:
    name: str
    type: Optional[Type] = None  # None for local vars without annotation

    position: Optional[Position] = None
    inferred_type: Any = None
    symbol_id: Optional[int] = None

    def to_dict(self) -> dict:
        return _node(
            "VarDef", self,
            name=self.name,
            type=self.type.to_dict() if self.type else None,
        )


@dataclass
class IntLit:
    value: int

    position: Optional[Position] = None
    inferred_type: Any = None

    def to_dict(self) -> dict:
        return _node("IntLit", self, value=self.value)


@dataclass
class BoolLit:
    value: bool

    position: Optional[Position] = None
    inferred_type: Any = None

    def to_dict(self) -> dict:
        return _node("BoolLit", self, value=self.value)


@dataclass
class Var:
    name: str

    position: Optional[Position] = None
    inferred_type: Any = None
    symbol_id: Optional[int] = None

    def to_dict(self) -> dict:
        return _node("Var", self, name=self.name)


@dataclass
class ArrayAccess:
    array: "Expr"
    index: "Expr"

    position: Optional[Position] = None
    inferred_type: Any = None

    def to_dict(self) -> dict:
        return _node("ArrayAccess", self, array=self.array.to_dict(), index=self.index.to_dict())


@dataclass
class BinOp:
    op: str
    left: "Expr"
    right: "Expr"

    position: Optional[Position] = None
    inferred_type: Any = None

    def to_dict(self) -> dict:
        return _node("BinOp", self, op=self.op, left=self.left.to_dict(), right=self.right.to_dict())


@dataclass
class UnOp:
    op: str
    operand: "Expr"

    position: Optional[Position] = None
    inferred_type: Any = None

    def to_dict(self) -> dict:
        return _node("UnOp", self, op=self.op, operand=self.operand.to_dict())


@dataclass
class FunctionCall:
    name: str
    args: List["Expr"]

    position: Optional[Position] = None
    inferred_type: Any = None
    symbol_id: Optional[int] = None

    def to_dict(self) -> dict:
        return _node("FunctionCall", self, name=self.name, args=[a.to_dict() for a in self.args])


Expr = Union[IntLit, BoolLit, Var, ArrayAccess, BinOp, UnOp, FunctionCall,
             "Comparison", "LogicalOp", "Not", "Quantifier", "FormulaRef"]


@dataclass
class Comparison:
    op: str
    left: Expr
    right: Expr

    position: Optional[Position] = None
    inferred_type: Any = None

    def to_dict(self) -> dict:
        return _node("Comparison", self, op=self.op, left=self.left.to_dict(), right=self.right.to_dict())


@dataclass
class LogicalOp:
    op: str  # "and" | "or" | "->"
    left: "Condition"
    right: "Condition"

    position: Optional[Position] = None
    inferred_type: Any = None

    def to_dict(self) -> dict:
        return _node("LogicalOp", self, op=self.op, left=self.left.to_dict(), right=self.right.to_dict())


@dataclass
class Not:
    operand: "Condition"

    position: Optional[Position] = None
    inferred_type: Any = None

    def to_dict(self) -> dict:
        return _node("Not", self, operand=self.operand.to_dict())


Condition = Expr


@dataclass
class Quantifier:
    kind: str  # "forall" | "exists"
    var: VarDef
    body: Condition

    position: Optional[Position] = None
    inferred_type: Any = None

    def to_dict(self) -> dict:
        return _node("Quantifier", self, quant=self.kind, var=self.var.to_dict(), body=self.body.to_dict())


@dataclass
class FormulaRef:
    name: str
    args: List[Expr]

    position: Optional[Position] = None
    inferred_type: Any = None
    symbol_id: Optional[int] = None

    def to_dict(self) -> dict:
        return _node("FormulaRef", self, name=self.name, args=[a.to_dict() for a in self.args])


@dataclass
class Assign:
    targets: List[Union[Var, ArrayAccess]]
    value: Expr

    position: Optional[Position] = None

    def to_dict(self) -> dict:
        return _node(
            "Assign", self,
            targets=[t.to_dict() for t in self.targets],
            value=self.value.to_dict(),
        )


@dataclass
class If:
    condition: Condition
    then_branch: "Statement"
    else_branch: Optional["Statement"] = None

    position: Optional[Position] = None

    def to_dict(self) -> dict:
        return _node(
            "If", self,
            condition=self.condition.to_dict(),
            then=self.then_branch.to_dict(),
            else_=self.else_branch.to_dict() if self.else_branch else None,
        )


@dataclass
class While:
    condition: Condition
    invariant: Optional[Condition]
    body: "Statement"

    position: Optional[Position] = None

    def to_dict(self) -> dict:
        return _node(
            "While", self,
            condition=self.condition.to_dict(),
            invariant=self.invariant.to_dict() if self.invariant else None,
            body=self.body.to_dict(),
        )


@dataclass
class Block:
    stmts: List["Statement"]

    position: Optional[Position] = None

    def to_dict(self) -> dict:
        return _node("Block", self, stmts=[s.to_dict() for s in self.stmts])


@dataclass
class Assert:
    predicate: Condition

    position: Optional[Position] = None

    def to_dict(self) -> dict:
        return _node("Assert", self, predicate=self.predicate.to_dict())


@dataclass
class Assume:
    predicate: Condition

    position: Optional[Position] = None

    def to_dict(self) -> dict:
        return _node("Assume", self, predicate=self.predicate.to_dict())


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

    position: Optional[Position] = None
    inferred_type: Any = None
    symbol_id: Optional[int] = None

    def to_dict(self) -> dict:
        return _node(
            "Function", self,
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

    position: Optional[Position] = None
    inferred_type: Any = None
    symbol_id: Optional[int] = None

    def to_dict(self) -> dict:
        return _node(
            "Formula", self,
            name=self.name,
            params=[p.to_dict() for p in self.params],
            body=self.body.to_dict(),
        )


@dataclass
class Module:
    functions: List[Function] = field(default_factory=list)
    formulas: List[Formula] = field(default_factory=list)

    position: Optional[Position] = None

    def to_dict(self) -> dict:
        return _node(
            "Module", self,
            functions=[f.to_dict() for f in self.functions],
            formulas=[f.to_dict() for f in self.formulas],
        )

# Type alias for semantic-analysis annotations, not a base class.
Node = Union[TypeInt, TypeBool, TypeArray, VarDef, Expr, Statement, Function, Formula, Module]
