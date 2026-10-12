# HW2 — Funny parser (LL(1) recursive descent)

Синтаксический анализатор учебного языка **Funny**. Метод — LL(1), рекурсивный спуск.
Переиспользует лексер из HW1 (`automata.py`), строит AST в JSON, сообщает об ошибках с позициями.

---

## Требования

- Python 3.10+
- Внешние зависимости не нужны

---

## Архитектура

```
текст программы (.funny)
    │
    │  lexer.py: tokenize()
    │  вызывает scan() из automata.py (HW1)
    ▼
список Token(type, value, line, column, offset)
    │
    │  parser.py: parse_text()
    │  LL(1) рекурсивный спуск
    ▼
Module (AST)
    │
    │  ast_nodes.py: to_dict()
    ▼
JSON
```

---

## Структура проекта

```
hw2_funny/
├── automata.py       # HW1: NFA/DFA/scan (без изменений)
├── lexer_spec.py     # правила токенов HW1 + HW2
├── lexer.py          # адаптер: Token с позициями
├── ast_nodes.py      # dataclass-узлы AST
├── parser.py         # LL(1) рекурсивный спуск
├── main.py           # CLI
├── grammar.txt       # грамматика Funny (LL(1)-форма)
├── README.md
├── REPORT.md
├── examples/
│   └── sum.funny
└── tests/
    ├── positive/     # 8 файлов
    ├── negative/     # 5 файлов
    └── run_tests.py
```

---

## Запуск

### AST в JSON

```bash
python3 main.py examples/sum.funny --ast
```

### Поток токенов с позициями

```bash
python3 main.py examples/sum.funny --tokens
```

### Компактный JSON

```bash
python3 main.py examples/sum.funny --ast --compact
```

### Все тесты

```bash
python3 main.py --test
```

или напрямую:

```bash
python3 tests/run_tests.py
```

---

## Пример

Вход `examples/sum.funny`:

```
function sum(a: int) returns r: int {
    r = a + 5;
}
```

Вывод `--ast`:

```json
{
  "kind": "Module",
  "functions": [
    {
      "kind": "Function",
      "name": "sum",
      "params": [
        {"kind": "VarDef", "name": "a", "type": {"kind": "TypeInt"}}
      ],
      "returns": [
        {"kind": "VarDef", "name": "r", "type": {"kind": "TypeInt"}}
      ],
      "requires": null,
      "ensures": null,
      "uses": [],
      "body": {
        "kind": "Block",
        "stmts": [
          {
            "kind": "Assign",
            "targets": [{"kind": "Var", "name": "r"}],
            "value": {
              "kind": "BinOp",
              "op": "+",
              "left": {"kind": "Var", "name": "a"},
              "right": {"kind": "IntLit", "value": 5}
            }
          }
        ]
      }
    }
  ],
  "formulas": []
}
```

---

## Формат AST

Все узлы — JSON-объекты с полем `kind`. Корневой узел — `Module`.

### Узлы

| `kind` | Поля | Что означает |
|---|---|---|
| `Module` | `functions`, `formulas` | корень программы |
| `Function` | `name`, `params`, `returns`, `requires`, `ensures`, `uses`, `body` | объявление функции |
| `Formula` | `name`, `params`, `body` | объявление формулы |
| `VarDef` | `name`, `type` | объявление переменной (`a: int`) |
| `TypeInt` | — | тип `int` |
| `TypeArray` | — | тип `int[]` |
| `Block` | `stmts` | блок `{ ... }` |
| `Assign` | `targets`, `value` | присваивание |
| `If` | `condition`, `then`, `else_` | условный оператор |
| `While` | `condition`, `invariant`, `body` | цикл |
| `Assert` | `predicate` | `assert p;` |
| `Assume` | `predicate` | `assume p;` |
| `IntLit` | `value` | целое число |
| `BoolLit` | `value` | `true` / `false` |
| `Var` | `name` | имя переменной |
| `ArrayAccess` | `array`, `index` | `a[i]` |
| `BinOp` | `op`, `left`, `right` | бинарная операция |
| `UnOp` | `op`, `operand` | унарная операция (`-a`) |
| `FunctionCall` | `name`, `args` | вызов функции |
| `Comparison` | `op`, `left`, `right` | сравнение |
| `LogicalOp` | `op`, `left`, `right` | `and` / `or` / `->` |
| `Not` | `operand` | `not p` |
| `Quantifier` | `quant`, `var`, `body` | `forall` / `exists` |
| `FormulaRef` | `name`, `args` | ссылка на формулу |

---

## Что поддерживается

### Синтаксис

- Функции: `function name(params) returns ... { body }`
- Опциональные `requires` / `ensures` / `uses`
- Операторы: присваивание, `if`/`else`, `while` + `invariant`, блоки, `assert`, `assume`
- Массивы: `a[i]` в выражениях и в lvalue
- Арифметика `+ - * /`, унарный `-`, скобки
- Условия: `not`, `and`, `or`, `->` (правоасс.), сравнения `== != <= >= < >`
- Формулы: `name(params) => predicate;`
- Кванторы `forall` / `exists` (синтаксически)

### Приоритеты операторов (высший → низший)

1. `not`
2. `and`
3. `or`
4. `->` (правоассоциативный)
5. `== != <= >= < >`
6. `+ -`
7. `* /`
8. унарный `-`

Полная грамматика — в `grammar.txt`.

---

## Обработка ошибок

Ошибки содержат **позицию** в виде `line:column` (обе с 1).

### Пример: пропущена точка с запятой

Вход `tests/negative/03_missing_semicolon.funny`:

```
function f() returns r: int {
    r = 0
}
```

Вывод:

```
Parse error: expected one of ('SEMICOLON',), got RBRACE at 3:1 (got RBRACE '}')
```

Формат: `<что ожидалось>, <что нашли> at <line>:<column>`.

### Пример: неизвестный символ

Вход `tests/negative/04_bad_char.funny`:

```
function f() returns r: int {
    r = @;
}
```

Вывод:

```
Lexer error: unexpected character '@' at 2:9
```

---

## Тесты

### Позитивные (`tests/positive/`)

Все файлы должны **успешно** парситься, корень AST = `Module`.

| Файл | Что проверяет |
|---|---|
| `01_minimal.funny` | минимальная функция без параметров |
| `02_arith.funny` | арифметика `+ - * /`, приоритеты |
| `03_if.funny` | `if` / `else` |
| `04_while.funny` | `while` + `invariant` |
| `05_requires_ensures.funny` | `requires` / `ensures` |
| `06_array.funny` | обращение `a[0]` |
| `07_assert_assume.funny` | `assert` / `assume` |
| `08_call.funny` | вызов функции с аргументами |

### Негативные (`tests/negative/`)

Все файлы должны **упасть** с `LexerError` или `ParseError`.

| Файл | Что проверяет | Ожидаемая ошибка |
|---|---|---|
| `01_empty.funny` | пустой ввод | `empty input` |
| `02_unclosed_brace.funny` | незакрытая `{` | `expected RBRACE` |
| `03_missing_semicolon.funny` | пропущена `;` | `expected SEMICOLON at 3:1` |
| `04_bad_char.funny` | недопустимый символ `@` | `unexpected character at 2:9` |
| `05_missing_returns.funny` | нет `returns` | `expected RETURNS at 1:14` |

### Запуск

```bash
python3 main.py --test
```

Ожидаемый вывод:

```
=== Positive tests ===
  PASS  01_minimal.funny
  ...
=== Negative tests ===
  PASS  01_empty.funny: empty input
  ...
=== Example check ===
  PASS  examples/sum.funny structure

All tests PASS
```

---