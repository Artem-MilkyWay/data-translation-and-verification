"""Semantic rules, scope isolation, type annotations, and explicit fixture oracles."""
import json
import unittest
from dataclasses import fields, is_dataclass
from pathlib import Path

import ast_nodes as ast
from lexer import tokenize
from parser import parse_text
from semantic import analyze_text, unify, Type, INT, BOOL, ARRAY, ERROR

ROOT = Path(__file__).resolve().parent.parent
EXPRESSION_NODES = (ast.IntLit, ast.BoolLit, ast.Var, ast.ArrayAccess, ast.BinOp,
                    ast.UnOp, ast.FunctionCall, ast.FormulaRef, ast.Comparison,
                    ast.LogicalOp, ast.Not, ast.Quantifier)


def walk(node):
    if is_dataclass(node):
        yield node
        for field in fields(node):
            if field.name in {"position", "inferred_type", "symbol_id"}:
                continue
            value = getattr(node, field.name)
            if isinstance(value, list):
                for child in value:
                    yield from walk(child)
            elif is_dataclass(value):
                yield from walk(value)


class SemanticTests(unittest.TestCase):
    def check(self, source, codes=()):
        result = analyze_text(source)
        self.assertEqual([e.code for e in result.errors], list(codes),
                         [e.to_dict() for e in result.errors])
        self.assertEqual(result.ok, not codes)
        for node in walk(result.ast):
            if isinstance(node, EXPRESSION_NODES):
                self.assertIsNotNone(node.inferred_type, type(node).__name__)
                self.assertIsNotNone(node.position, type(node).__name__)
        return result

    def test_positive_fixtures(self):
        files = sorted((ROOT / "tests/positive").glob("*.funny"))
        self.assertEqual(len(files), 10)
        for path in files:
            with self.subTest(path=path.name):
                self.check(path.read_text(encoding="utf-8"))

    def test_negative_fixtures_exact_diagnostics(self):
        files = sorted((ROOT / "tests/negative").glob("*.funny"))
        self.assertEqual(len(files), 20)
        for path in files:
            with self.subTest(path=path.name):
                source = path.read_text(encoding="utf-8")
                expected = json.loads(path.with_suffix(".expected.json").read_text(encoding="utf-8"))
                result = self.check(source, [e["code"] for e in expected])
                self.assertEqual(len(result.errors), len(expected))
                for error, oracle in zip(result.errors, expected):
                    self.assertEqual(error.position.line, oracle["line"])
                    self.assertEqual(error.position.column, oracle["column"])
                    self.assertIn(oracle["message_contains"], error.message)
                    # Offset must independently identify the same line/column.
                    prefix = source[:error.position.offset]
                    self.assertEqual(prefix.count("\n") + 1, oracle["line"])
                    self.assertEqual(len(prefix.rsplit("\n", 1)[-1]) + 1, oracle["column"])

    def test_original_hw2_parser_cases(self):
        for path in sorted((ROOT / "tests/hw2/positive").glob("*.funny")):
            with self.subTest(path=path.name):
                source = path.read_text(encoding="utf-8")
                module, errors = parse_text(source)
                self.assertFalse(errors)
                self.assertEqual(module.to_dict()["kind"], "Module")
                self.check(source)
        for path in sorted((ROOT / "tests/hw2/negative").glob("*.funny")):
            with self.subTest(path=path.name):
                result = analyze_text(path.read_text(encoding="utf-8"))
                self.assertFalse(result.ok)
                self.assertTrue(result.errors)
                self.assertTrue(all(e.phase in {"lexer", "parser"} for e in result.errors))
                self.assertTrue(all(e.position.line >= 1 and e.position.column >= 1 for e in result.errors))

    def test_every_successful_expression_is_annotated_and_bound(self):
        result = self.check((ROOT / "examples/typed.funny").read_text())
        by_id = {s.id: s for s in result.symbols}
        for node in walk(result.ast):
            if isinstance(node, EXPRESSION_NODES):
                self.assertNotEqual(node.inferred_type, ERROR)
            if isinstance(node, (ast.Var, ast.FunctionCall, ast.VarDef, ast.Function, ast.Formula)):
                self.assertIn(node.symbol_id, by_id)
                self.assertEqual(by_id[node.symbol_id].name, node.name)
        data = json.loads(json.dumps(result.to_dict()))
        self.assertEqual(data["format_version"], 1)
        self.assertTrue(data["ok"])
        function = data["ast"]["functions"][0]
        self.assertEqual(function["inferred_type"], {"kind": "func", "params": ["int"], "returns": ["int"]})
        self.assertEqual(function["body"]["stmts"][0]["value"]["inferred_type"], "int")

    def test_error_nodes_also_have_types(self):
        result = self.check('function f() returns r: int { r = nope + 1; }', ['E_UNKNOWN_NAME'])
        value = result.ast.functions[0].body.stmts[0].value
        self.assertEqual(value.inferred_type, ERROR)
        self.assertEqual(value.left.inferred_type, ERROR)
        self.assertEqual(value.right.inferred_type, INT)

    def test_function_scope_does_not_leak(self):
        self.check('function f(x: int) returns r: int { r = x; } '
                   'function g() returns r: int { r = x; }', ['E_UNKNOWN_NAME'])

    def test_quantifier_shadow_restores_outer_binding(self):
        result = self.check('function f(x: int) returns r: int { '
                            'assert forall(x: bool | x); r = x; }')
        function = result.ast.functions[0]
        quantifier = function.body.stmts[0].predicate
        self.assertEqual(quantifier.body.symbol_id, quantifier.var.symbol_id)
        self.assertEqual(function.body.stmts[1].value.symbol_id, function.params[0].symbol_id)
        self.assertNotEqual(function.params[0].symbol_id, quantifier.var.symbol_id)

    def test_quantifier_sibling_does_not_see_binding(self):
        self.check('function f() returns r: int { assert forall(x: int | x > 0) and x > 1; r = 0; }',
                   ['E_UNKNOWN_NAME'])

    def test_duplicate_return_and_local(self):
        self.check('function f(a: int) returns a: int uses a: bool { a = 0; }',
                   ['E_DUPLICATE_NAME', 'E_DUPLICATE_NAME'])

    def test_duplicate_formula_and_function(self):
        self.check('f() -> true; function f() returns r: int { r = 0; }', ['E_DUPLICATE_NAME'])

    def test_forward_formula_and_source_order(self):
        self.check('function f() returns r: bool { r = p(); } p() -> true;', ['E_BEFORE_DECLARATION'])
        self.check('p() -> true; function f() returns r: bool { r = p(); }')
        self.check('function f() returns r: bool { r = true; } p() -> f();')

    def test_too_many_arguments_still_check_unknown_argument(self):
        self.check('function g(a: int) returns r: int {r = a;} '
                   'function f() returns r: int {r = g(1, missing);}',
                   ['E_UNKNOWN_NAME', 'E_ARGUMENT_COUNT'])

    def test_unknown_callee_still_checks_arguments(self):
        self.check('function f() returns r: int { r = missing(also_missing, true + false); }',
                   ['E_UNKNOWN_NAME', 'E_UNKNOWN_NAME', 'E_TYPE_MISMATCH', 'E_TYPE_MISMATCH'])

    def test_variable_can_shadow_function_but_cannot_be_called(self):
        self.check('function f() returns r: int {r = 0;} '
                   'function g() returns r: int uses f: int { r = f(); }', ['E_NOT_CALLABLE'])

    def test_function_as_value_rejected(self):
        self.check('function f() returns r: int { r = f; }', ['E_FUNCTION_VALUE'])

    def test_multiple_return_component_type(self):
        self.check('function pair() returns a: int, b: bool {a = 1; b = true;} '
                   'function f() returns r: int uses x: int { r, x = pair(); }', ['E_TYPE_MISMATCH'])

    def test_multiple_returns_in_scalar_expression_rejected(self):
        self.check('function pair() returns a: int, b: int {a = 1; b = 2;} '
                   'function f() returns r: int { r = pair() + 1; }', ['E_MULTI_VALUE'])

    def test_multiple_returns_to_one_target(self):
        self.check('function pair() returns a: int, b: int {a = 1; b = 2;} '
                   'function f() returns r: int { r = pair(); }', ['E_RESULT_COUNT'])

    def test_no_broadcast_assignment(self):
        self.check('function f() returns r: int uses x: int { r, x = 1; }', ['E_RESULT_COUNT'])

    def test_array_parameter_return_and_element_assignment(self):
        self.check('function id(a: int[]) returns r: int[] { r = a; } '
                   'function f(a: int[]) returns r: int uses x: int[] { x = id(a); x[0] = 3; r = x[0]; }')
        self.check('function f(a: int[]) returns r: int { a[0] = false; r = 0; }', ['E_TYPE_MISMATCH'])

    def test_no_bool_int_coercion_in_comparison(self):
        self.check('function f() returns r: bool { r = true < false; }', ['E_TYPE_MISMATCH', 'E_TYPE_MISMATCH'])
        self.check('function f(a: int[]) returns r: bool { r = a == 0; }', ['E_TYPE_MISMATCH'])

    def test_unary_and_logical_types(self):
        self.check('function f() returns r: int { r = -true; }', ['E_TYPE_MISMATCH'])
        self.check('function f() returns r: bool { r = not 1; }', ['E_TYPE_MISMATCH'])
        self.check('function f() returns r: bool { r = 1 and 2; }', ['E_TYPE_MISMATCH', 'E_TYPE_MISMATCH'])

    def test_all_boolean_contexts(self):
        self.check('function f() requires 1 returns r: int ensures 2 { '
                   'while (3) invariant 4 {r = 0;} assume 5; assert 6; }', ['E_TYPE_MISMATCH'] * 6)
        self.check('p() -> 1;', ['E_TYPE_MISMATCH'])
        self.check('function f() returns r: int { assert exists(x: int | 1); r = 0; }', ['E_TYPE_MISMATCH'])

    def test_annotations_mandatory_for_parameters_and_returns(self):
        for source in ['function f(a) returns r: int {r = 0;}',
                       'function f() returns r {r = 0;}', 'p(a) -> true;']:
            with self.subTest(source=source):
                result = analyze_text(source)
                self.assertFalse(result.ok)
                self.assertTrue(all(e.phase == 'parser' for e in result.errors))

    def test_no_local_inference_even_if_unused(self):
        self.check('function f() returns r: int uses x {r = 0;}', ['E_MISSING_TYPE'])

    def test_implication_associativity_and_arithmetic_precedence(self):
        result = self.check('function f() returns r: int, b: bool { r = 1 + 2 * 3 - 4; '
                            'b = true -> false -> true; }')
        arithmetic, logical = [s.value for s in result.ast.functions[0].body.stmts]
        self.assertEqual(arithmetic.op, '-')
        self.assertEqual(arithmetic.left.op, '+')
        self.assertEqual(arithmetic.left.right.op, '*')
        self.assertIsInstance(logical.right, ast.LogicalOp)
        self.assertIsInstance(logical.left, ast.BoolLit)

    def test_if_else_bodies_checked_after_bad_condition(self):
        self.check('function f() returns r: int { if (1) r = a; else r = b; }',
                   ['E_TYPE_MISMATCH', 'E_UNKNOWN_NAME', 'E_UNKNOWN_NAME'])

    def test_syntax_error_recovery_reports_multiple_positions(self):
        result = analyze_text('function f() returns r: int { r = ; r = ; r = 0; }')
        self.assertEqual(len(result.errors), 2)
        self.assertTrue(all(e.phase == 'parser' for e in result.errors))
        self.assertEqual(len(result.ast.functions[0].body.stmts), 1)
        self.assertEqual(result.symbols, [])

    def test_eof_and_lexical_error_positions(self):
        result = analyze_text('function f() returns r: int {\n r = 0;\n')
        self.assertEqual((result.errors[0].position.line, result.errors[0].position.column), (3, 1))
        result = analyze_text('function f() returns r: int {\n r = @;\n}')
        self.assertEqual(result.errors[0].phase, 'lexer')
        self.assertEqual((result.errors[0].position.line, result.errors[0].position.column), (2, 6))
        result = analyze_text('')
        self.assertEqual((result.errors[0].position.line, result.errors[0].position.column), (1, 1))

    def test_comment_lexeme_does_not_corrupt_positions(self):
        source = '// function f() returns r: int { r = nope; }\nfunction f() returns r: int { r = nope; }'
        tokens = tokenize(source)
        self.assertEqual((tokens[0].line, tokens[0].column, tokens[0].offset), (2, 1, source.index('\n') + 1))
        result = self.check(source, ['E_UNKNOWN_NAME'])
        self.assertEqual((result.errors[0].position.line, result.errors[0].position.column), (2, 35))

    def test_keyword_boundaries(self):
        tokens = tokenize('bool bool_value int integer true true_value')
        self.assertEqual([t.type for t in tokens], ['BOOL_TYPE', 'IDENT', 'INT_TYPE', 'IDENT', 'TRUE', 'IDENT'])

    def test_concrete_type_unification(self):
        for typ in [INT, BOOL, ARRAY]:
            self.assertEqual(unify(typ, typ), typ)
        self.assertEqual(unify(INT, BOOL), ERROR)
        self.assertEqual(unify(INT, ARRAY), ERROR)
        self.assertEqual(unify(ERROR, INT), ERROR)
        self.assertEqual(unify(ERROR, ERROR), ERROR)
        signature = Type('func', (INT, BOOL), (ARRAY,))
        self.assertEqual(unify(signature, Type('func', (INT, BOOL), (ARRAY,))), signature)
        self.assertEqual(unify(signature, Type('func', (INT,), (ARRAY,))), ERROR)
        self.assertEqual(unify(signature, Type('func', (INT, BOOL), (INT,))), ERROR)
        self.assertEqual(unify(Type('tuple', results=(INT, BOOL)), Type('tuple', results=(BOOL, INT))), ERROR)

    def test_repeat_analysis_is_deterministic(self):
        source = (ROOT / 'examples/typed.funny').read_text()
        self.assertEqual(analyze_text(source).to_dict(), analyze_text(source).to_dict())


if __name__ == '__main__':
    unittest.main()
