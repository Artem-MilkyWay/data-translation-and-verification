# HW2 — краткий отчёт

## 1. Цель

Реализовать LL(1) синтаксический анализатор языка Funny методом рекурсивного спуска, с интеграцией лексера HW1, выводом AST в JSON и диагностикой ошибок с позициями.

## 2. Выбор ветки

Выбран **LL(1) / рекурсивный спуск** (не LR/bison).

## 3. Лексер

- Переиспользован `automata.py` из HW1 без изменений.
- `lexer_spec.py` расширен токенами: `REQUIRES`, `ENSURES`, `FORALL`, `EXISTS`, `INT_TYPE`, `AND`, `OR`, `NOT`, `IMPLIES` (`->`), `COLON`, `BAR`.
- `lexer.py` — адаптер: вызывает `scan()`, восстанавливает `line`/`column`/`offset` для каждого токена.
- `int[]` — три токена: `INT_TYPE` `LBRACKET` `RBRACKET`.

## 4. Парсер

Класс `Parser` с методами по нетерминалам грамматики:

`parse_module`, `parse_function`, `parse_formula`, `parse_params`, `parse_type`,
`parse_local_vars`, `parse_statement`, `parse_block`, `parse_if`, `parse_while`,
`parse_assert`, `parse_assume`, `parse_assignment`, `parse_lvalue`,
`parse_expr` / `parse_term` / `parse_factor`,
`parse_condition` / `parse_impl` / `parse_or` / `parse_and` / `parse_not` / `parse_comparison`.

Приоритеты и ассоциативность зафиксированы слоями (как в `grammar.txt`).

Для `(condition)` vs `(expr)` используется ограниченный backtracking при `LPAREN`.

## 5. AST

Узлы — `@dataclass` в `ast_nodes.py`. Сериализация через `to_dict()` → JSON.
Корневой узел: `Module` с полями `functions` и `formulas`.

## 6. Ошибки

- `LexerError` — неожиданный символ, позиция `line:column`.
- `ParseError` — ожидаемый токен / конструкция, позиция из текущего токена.

## 7. Тесты

| Группа    | Файлы | Ожидание        |
|-----------|-------|-----------------|
| positive  | 8     | успешный AST    |
| negative  | 5     | ошибка + позиция|
| example   | sum.funny | структура Module |

Запуск: `python3 main.py --test`

