"""Three-address IR, CFG construction, optimizations and register allocation."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Instruction:
    op: str
    args: list[Any] = field(default_factory=list)
    dest: str | None = None

    def __str__(self):
        if self.op == "label": return f"{self.args[0]}:"
        if self.op == "jump": return f"goto {self.args[0]}"
        if self.op == "branch": return f"if {self.args[0]} goto {self.args[1]} else {self.args[2]}"
        if self.op == "return": return "return " + ", ".join(map(str, self.args))
        if self.op == "store": return f"{self.args[0]}[{self.args[1]}] = {self.args[2]}"
        if self.op == "call": return f"{self.dest} = call {self.args[0]}({', '.join(map(str,self.args[1]))})"
        if self.op == "call_void": return f"call {self.args[0]}({', '.join(map(str,self.args[1]))})"
        if self.op == "call_multi": return f"{', '.join(self.args[2])} = call {self.args[0]}({', '.join(map(str,self.args[1]))})"
        if self.op == "quantifier": return f"{self.dest} = {self.args[0]} {self.args[1]} . <predicate AST>"
        if self.op == "copy": return f"{self.dest} = {self.args[0]}"
        if self.op == "un": return f"{self.dest} = {self.args[0]} {self.args[1]}"
        if self.op == "bin": return f"{self.dest} = {self.args[0]} {self.args[1]} {self.args[2]}"
        if self.op == "load": return f"{self.dest} = {self.args[0]}[{self.args[1]}]"
        if self.op in ("assert", "assume"): return f"{self.op} {self.args[0]}"
        return f"{self.op} " + ", ".join(map(str,self.args))

    def to_dict(self): return {"op":self.op,"dest":self.dest,"args":self.args}


def var_name(v): return f"v{v.symbol_id}" if getattr(v, "symbol_id", None) is not None else v.name


class Generator:
    def __init__(self): self.code=[]; self.temp=0; self.label=0
    def t(self): self.temp+=1; return f"t{self.temp}"
    def l(self): self.label+=1; return f"L{self.label}"
    def emit(self,op,*args,dest=None): self.code.append(Instruction(op,list(args),dest))
    def expr(self,e):
        from ast_nodes import IntLit,BoolLit,Var,ArrayAccess,BinOp,UnOp,Comparison,LogicalOp,Not,FunctionCall,FormulaRef,Quantifier
        if isinstance(e,(IntLit,BoolLit)): return e.value
        if isinstance(e,Var): return var_name(e)
        if isinstance(e,ArrayAccess):
            a=self.expr(e.array); i=self.expr(e.index); d=self.t(); self.emit("load",a,i,dest=d); return d
        if isinstance(e,(BinOp,Comparison,LogicalOp)):
            a=self.expr(e.left); b=self.expr(e.right); d=self.t(); self.emit("bin",a,e.op,b,dest=d); return d
        if isinstance(e,(UnOp,Not)):
            x=self.expr(e.operand); d=self.t(); self.emit("un", "not" if isinstance(e,Not) else e.op,x,dest=d); return d
        if isinstance(e,(FunctionCall,FormulaRef)):
            args=[self.expr(x) for x in e.args]; d=self.t(); self.emit("call",e.name,args,dest=d); return d
        if isinstance(e,Quantifier):
            # Keep a quantified predicate opaque: evaluating its body once
            # would change the binding semantics of forall/exists.
            d=self.t(); self.emit("quantifier",e.kind,var_name(e.var),e.body.to_dict(),dest=d); return d
        raise ValueError(f"Unsupported expression: {type(e).__name__}")
    def stmt(self,s):
        from ast_nodes import Assign,Block,If,While,Assert,Assume,Var,ArrayAccess
        if isinstance(s,Block):
            for x in s.stmts:self.stmt(x)
        elif isinstance(s,Assign):
            from ast_nodes import FunctionCall
            if isinstance(s.value,FunctionCall) and len(s.targets)>1:
                args=[self.expr(x) for x in s.value.args]
                targets=[var_name(t) if isinstance(t,Var) else f"{self.expr(t.array)}[{self.expr(t.index)}]" for t in s.targets]
                self.emit("call_multi",s.value.name,args,targets)
                return
            value=self.expr(s.value)
            for target in s.targets:
                if isinstance(target,Var): self.emit("copy",value,dest=var_name(target))
                else: self.emit("store",self.expr(target.array),self.expr(target.index),value)
        elif isinstance(s,If):
            c=self.expr(s.condition); yes=self.l(); no=self.l(); end=self.l(); self.emit("branch",c,yes,no)
            self.emit("label",yes); self.stmt(s.then_branch); self.emit("jump",end)
            self.emit("label",no)
            if s.else_branch:self.stmt(s.else_branch)
            self.emit("label",end)
        elif isinstance(s,While):
            head=self.l(); body=self.l(); end=self.l(); self.emit("label",head); c=self.expr(s.condition); self.emit("branch",c,body,end); self.emit("label",body); self.stmt(s.body); self.emit("jump",head); self.emit("label",end)
        elif isinstance(s,(Assert,Assume)): self.emit("assert" if isinstance(s,Assert) else "assume",self.expr(s.predicate))
        else: raise ValueError(f"Unsupported statement: {type(s).__name__}")
    def function(self,f):
        self.code=[]; self.emit("label",f.name)
        if f.requires:self.emit("assert",self.expr(f.requires))
        self.stmt(f.body)
        if f.ensures:self.emit("assert",self.expr(f.ensures))
        self.emit("return",*[var_name(v) for v in f.returns])
        return self.code


@dataclass
class BasicBlock:
    name: str
    instructions: list[Instruction]
    successors: list[str]=field(default_factory=list)

def build_cfg(code):
    leaders={0}; labels={}
    for i,x in enumerate(code):
        if x.op=="label": leaders.add(i); labels[x.args[0]]=i
        if x.op in ("jump","branch") and i+1<len(code): leaders.add(i+1)
    starts=sorted(leaders); blocks=[]; index_to_block={}
    for n,start in enumerate(starts):
        end=starts[n+1] if n+1<len(starts) else len(code); name=code[start].args[0] if code[start].op=="label" else f"B{n}"
        block=BasicBlock(name,code[start:end]); blocks.append(block)
        for i in range(start,end):index_to_block[i]=name
    byname={b.name:b for b in blocks}
    for n,b in enumerate(blocks):
        tail=b.instructions[-1] if b.instructions else None
        if tail and tail.op=="jump": b.successors=[str(tail.args[0])]
        elif tail and tail.op=="branch": b.successors=[str(tail.args[1]),str(tail.args[2])]
        elif tail and tail.op=="return": pass
        elif n+1<len(blocks):b.successors=[blocks[n+1].name]
    return blocks

def optimize(code, const=True, algebra=True, dce=True, cse=False):
    # Safe block-local forward propagation, clearing facts at control flow edges.
    out=[]; env={}
    for ins in code:
        if ins.op in ("label","jump","branch","return"): env={}
        a=ins.args[:]
        if ins.op in ("copy","bin","un","load"):
            a=[env.get(x,x) if isinstance(x,str) else x for x in a]
        if ins.op=="bin" and algebra:
            x,op,y=a
            if ((op=="+" and (y==0 or x==0)) or (op=="-" and y==0)
                    or (op=="*" and (y==1 or x==1)) or (op=="/" and y==1)):
                passthrough=x if y in (0,1) else y
                if op=="+" and x==0: passthrough=y
                ins=Instruction("copy",[x],ins.dest); a=ins.args
                ins=Instruction("copy",[passthrough],ins.dest); a=ins.args
            elif op=="*" and (x==0 or y==0): ins=Instruction("copy",[0],ins.dest); a=ins.args
        if const and ins.op=="un" and isinstance(a[1],(int,bool)):
            try: value=not a[1] if a[0]=="not" else -a[1]
            except TypeError: value=None
            if value is not None: ins=Instruction("copy",[value],ins.dest); a=ins.args
        if const and ins.op=="bin" and all(isinstance(x,(int,bool)) for x in (a[0],a[2])):
            x,op,y=a[0],a[1],a[2]
            try: value={"+":lambda:x+y,"-":lambda:x-y,"*":lambda:x*y,"/":lambda:x//y if y else None,"<":lambda:x<y,"<=":lambda:x<=y,">":lambda:x>y,">=":lambda:x>=y,"==":lambda:x==y,"!=":lambda:x!=y,"and":lambda:x and y,"or":lambda:x or y,"->":lambda:(not x) or y}[op]()
            except (KeyError,ZeroDivisionError): value=None
            if value is not None: ins=Instruction("copy",[value],ins.dest); a=ins.args
        ins=Instruction(ins.op,a,ins.dest); out.append(ins)
        if ins.dest:
            if ins.op=="copy" and isinstance(a[0],(int,bool)):env[ins.dest]=a[0]
            else:env.pop(ins.dest,None)
    if cse:
        # Common subexpressions are reused only within a straight-line block.
        reused=[]; expressions={}
        for i in out:
            if i.op=="label": expressions={}
            if i.dest:
                expressions={key:value for key,value in expressions.items()
                             if i.dest not in (key[0],key[2])}
            if i.op=="bin":
                key=(i.args[0],i.args[1],i.args[2])
                if key in expressions:
                    i=Instruction("copy",[expressions[key]],i.dest)
                else: expressions[key]=i.dest
            if i.op in ("jump","branch","return"): expressions={}
            reused.append(i)
        out=reused
    if dce:
        blocks=build_cfg(out); byname={b.name:b for b in blocks}; live_in={b.name:set() for b in blocks}; live_out={b.name:set() for b in blocks}
        changed=True
        while changed:
            changed=False
            for block in reversed(blocks):
                after=set().union(*(live_in.get(s,set()) for s in block.successors)) if block.successors else set()
                before=set(after)
                for i in reversed(block.instructions):
                    before.difference_update(defs_of(i))
                    before.update(uses_of(i))
                if after!=live_out[block.name] or before!=live_in[block.name]:
                    live_out[block.name]=after; live_in[block.name]=before; changed=True
        cleaned=[]
        for block in blocks:
            live=set(live_out[block.name]); kept=[]
            for i in reversed(block.instructions):
                needed=i.dest is None or i.dest in live or i.op in ("call","call_multi")
                if needed:
                    live.difference_update(defs_of(i))
                    live.update(uses_of(i)); kept.append(i)
            cleaned.extend(reversed(kept))
        out=cleaned
    return out

def uses_of(i):
    if i.op in ("copy","un","assert","assume","branch","return"): return {x for x in i.args if isinstance(x,str) and x.startswith(("v","t"))}
    if i.op=="bin":return {x for x in (i.args[0],i.args[2]) if isinstance(x,str) and x.startswith(("v","t"))}
    if i.op=="call":return {x for x in i.args[1] if isinstance(x,str) and x.startswith(("v","t"))}
    if i.op=="call_multi":
        values={x for x in i.args[1] if isinstance(x,str) and x.startswith(("v","t"))}
        for target in i.args[2]:
            if isinstance(target,str) and "[" in target:
                values.update(part for part in target.replace("]","").split("[") if part.startswith(("v","t")))
        return values
    if i.op=="load":return {x for x in i.args if isinstance(x,str) and x.startswith(("v","t"))}
    if i.op=="store":return {x for x in i.args if isinstance(x,str) and x.startswith(("v","t"))}
    if i.op=="quantifier":
        found=set()
        def visit(value):
            if isinstance(value,dict):
                if value.get("kind")=="Var" and value.get("symbol_id") is not None: found.add(f"v{value['symbol_id']}")
                for child in value.values():visit(child)
            elif isinstance(value,list):
                for child in value:visit(child)
        visit(i.args[2]); found.discard(i.args[1]); return found
    return set()

def defs_of(i):
    if i.op=="call_multi":return {x for x in i.args[2] if isinstance(x,str) and "[" not in x and x.startswith(("v","t"))}
    return {i.dest} if i.dest else set()

def interference(code):
    blocks=build_cfg(code); graph={}; live_in={b.name:set() for b in blocks}; live_out={b.name:set() for b in blocks}
    for ins in code:
        for name in defs_of(ins): graph.setdefault(name,set())
        for name in uses_of(ins): graph.setdefault(name,set())
    changed=True
    while changed:
        changed=False
        for b in reversed(blocks):
            after=set().union(*(live_in.get(s,set()) for s in b.successors)) if b.successors else set(); before=set(after)
            for i in reversed(b.instructions):
                before.difference_update(defs_of(i))
                before.update(uses_of(i))
            if after!=live_out[b.name] or before!=live_in[b.name]: live_out[b.name]=after; live_in[b.name]=before; changed=True
    for b in blocks:
        live=set(live_out[b.name])
        for i in reversed(b.instructions):
            use=uses_of(i); defined=defs_of(i)
            for d in defined:
                graph.setdefault(d,set())
                for x in live | (defined-{d}):
                    if x!=d:graph.setdefault(x,set()).add(d); graph[d].add(x)
            live.difference_update(defined)
            live.update(use)
    colors={}
    for node in sorted(graph,key=lambda n:(-len(graph[n]),n)):
        used={colors[x] for x in graph[node] if x in colors}; color=0
        while color in used:color+=1
        colors[node]=color
    return graph,colors
