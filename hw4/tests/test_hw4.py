import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT.parent/"hw3")); sys.path.insert(0,str(ROOT))
from semantic import analyze_text
from ir import Generator, Instruction, build_cfg, optimize, interference

SOURCE=(ROOT/"examples/control.funny").read_text(encoding="utf-8")

def run(code, params):
    labels={i.args[0]:n for n,i in enumerate(code) if i.op=="label"}; env=dict(params); pc=0
    def val(x): return env[x] if isinstance(x,str) else x
    while pc<len(code):
        i=code[pc]; op=i.op; a=i.args
        if op=="copy":env[i.dest]=val(a[0])
        elif op=="bin":
            x,y=val(a[0]),val(a[2]); env[i.dest]={"+":lambda:x+y,"-":lambda:x-y,"*":lambda:x*y,"/":lambda:x//y,"<":lambda:x<y,"<=":lambda:x<=y,">":lambda:x>y,">=":lambda:x>=y,"==":lambda:x==y,"!=":lambda:x!=y,"and":lambda:x and y,"or":lambda:x or y,"->":lambda:(not x) or y}[a[1]]()
        elif op=="un":env[i.dest]=(not val(a[1])) if a[0]=="not" else -val(a[1])
        elif op=="jump":pc=labels[a[0]];continue
        elif op=="branch":pc=labels[a[1] if val(a[0]) else a[2]];continue
        elif op=="return":return tuple(env[x] for x in a)
        pc+=1
    raise AssertionError("IR did not return")

class HW4Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        result=analyze_text(SOURCE); assert result.ok, result.errors
        g=Generator(); cls.before=g.function(result.ast.functions[0]); cls.after=optimize(cls.before)

    def test_ir_and_cfg_cover_control_flow(self):
        blocks=build_cfg(self.before)
        self.assertTrue(any(len(b.successors)==2 for b in blocks))
        self.assertTrue(any(any(i.op=="jump" for i in b.instructions) for b in blocks))

    def test_optimized_and_unoptimized_execution_match(self):
        for n in (-2,0,1,4,9):
            self.assertEqual(run(self.before,{"v2":n}),run(self.after,{"v2":n}))

    def test_optimizations_reduce_instruction_count(self):
        self.assertLess(len(self.after),len(self.before))

    def test_liveness_graph_is_symmetric_and_colored(self):
        graph,colors=interference(self.after)
        for node,neighbors in graph.items():
            for other in neighbors:
                self.assertIn(node,graph[other]); self.assertNotEqual(colors[node],colors[other])

    def test_function_call_is_lowered(self):
        source="function inc(x: int) returns r: int { r = x + 1; } function main() returns r: int { r = inc(4); }"
        result=analyze_text(source); self.assertTrue(result.ok,result.errors)
        g=Generator(); code=g.function(result.ast.functions[1])
        self.assertTrue(any(i.op=="call" and i.args[0]=="inc" for i in code))

    def test_multi_result_call_is_lowered(self):
        source="function pair(x: int) returns a: int, ok: bool { a = x; ok = true; } function main() returns r: int uses b: bool { r, b = pair(5); }"
        result=analyze_text(source); self.assertTrue(result.ok,result.errors)
        g=Generator(); code=g.function(result.ast.functions[1])
        call=next(i for i in code if i.op=="call_multi")
        self.assertEqual(call.args[0],"pair"); self.assertEqual(len(call.args[2]),2)

    def test_dce_keeps_values_used_by_array_store(self):
        code=[Instruction("copy",[3],"t1"),Instruction("store",["v1",0,"t1"]),Instruction("return",["v1"])]
        optimized=optimize(code,const=False,algebra=False,dce=True)
        self.assertTrue(any(i.dest=="t1" for i in optimized))

    def test_multi_result_definitions_are_in_liveness_graph(self):
        code=[Instruction("call_multi",["pair",["v1"],["v2","v3"]]),Instruction("return",["v2","v3"])]
        graph,colors=interference(code)
        self.assertIn("v2",graph); self.assertIn("v3",graph)
        self.assertIn("v3",graph["v2"]); self.assertNotEqual(colors["v2"],colors["v3"])

    def test_cse_invalidates_expression_after_operand_write(self):
        code=[Instruction("bin",["v1","+",2],"t1"),Instruction("copy",[9],"v1"),Instruction("bin",["v1","+",2],"t2"),Instruction("return",["t2"])]
        optimized=optimize(code,const=False,algebra=False,dce=False,cse=True)
        self.assertEqual(next(i for i in optimized if i.dest=="t2").op,"bin")

    def test_quantified_contract_is_preserved_as_high_level_ir(self):
        source="function f(x: int) requires forall(i: int | i >= x) returns r: int { r = x; }"
        result=analyze_text(source); self.assertTrue(result.ok,result.errors)
        g=Generator(); code=g.function(result.ast.functions[0])
        quant=next(i for i in code if i.op=="quantifier")
        self.assertEqual(quant.args[0],"forall")
        self.assertIn("v2",__import__("ir").uses_of(quant))

if __name__=="__main__": unittest.main()
