#!/usr/bin/env python3
"""HW4 driver; reuses the annotated AST and semantic front end from HW3."""
import argparse, json, sys
from pathlib import Path

HW3 = Path(__file__).resolve().parent.parent / "hw3"
sys.path.insert(0, str(HW3))
from semantic import analyze_text
from ir import Generator, build_cfg, optimize, interference

def main():
    p=argparse.ArgumentParser(description="Funny HW4: IR, CFG and local optimization")
    p.add_argument("file", help="Funny source file or - for stdin")
    p.add_argument("--no-const",action="store_true",help="disable constant folding/propagation")
    p.add_argument("--no-algebra",action="store_true",help="disable algebraic simplification")
    p.add_argument("--no-dce",action="store_true",help="disable local dead code elimination")
    p.add_argument("--cse",action="store_true",help="enable common subexpression elimination (reserved)")
    p.add_argument("--dot",action="store_true",help="also print CFG in DOT")
    p.add_argument("--pretty",action="store_true",help="emit structured JSON result")
    a=p.parse_args(); source=sys.stdin.read() if a.file=="-" else Path(a.file).read_text(encoding="utf-8")
    result=analyze_text(source)
    if not result.ok:
        for e in result.errors: print(f"{e.position.line}:{e.position.column}: {e.code}: {e.message}",file=sys.stderr)
        return 1
    module=result.ast; functions=[]
    for f in module.functions:
        g=Generator(); before=g.function(f); after=optimize(before,not a.no_const,not a.no_algebra,not a.no_dce,a.cse)
        cfg=build_cfg(after); graph,colors=interference(after)
        count_temps=lambda code:len({x.dest for x in code if x.dest and x.dest.startswith("t")})
        def decl(v):
            return {"name":v.name,"symbol_id":v.symbol_id,"ir_name":f"v{v.symbol_id}" if v.symbol_id is not None else v.name,"type":v.inferred_type.to_dict() if v.inferred_type else None}
        functions.append({"name":f.name,"symbol_id":f.symbol_id,"params":[decl(v) for v in f.params],"returns":[decl(v) for v in f.returns],"locals":[decl(v) for v in f.uses],"ir_before":[x.to_dict() for x in before],"ir_after":[x.to_dict() for x in after],"cfg":[{"name":b.name,"instructions":[x.to_dict() for x in b.instructions],"successors":b.successors} for b in cfg],"metrics":{"instructions_before":len(before),"instructions_after":len(after),"temporaries_before":count_temps(before),"temporaries_after":count_temps(after),"colors":len(set(colors.values()))},"interference":{k:sorted(v) for k,v in graph.items()},"coloring":colors})
    if a.pretty: print(json.dumps({"format":"funny-ir-v1","functions":functions},indent=2,ensure_ascii=False))
    else:
        for f in functions:
            print(f"function {f['name']} — IR before optimization")
            print("\n".join(f["ir_before"])); print("IR after optimization"); print("\n".join(f["ir_after"])); print("metrics:",json.dumps(f["metrics"],ensure_ascii=False))
            if a.dot:
                print("digraph CFG {")
                for b in f["cfg"]:
                    print(f'  "{b["name"]}";')
                    for dst in b["successors"]: print(f'  "{b["name"]}" -> "{dst}";')
                print("}")
    return 0
if __name__=="__main__": raise SystemExit(main())
