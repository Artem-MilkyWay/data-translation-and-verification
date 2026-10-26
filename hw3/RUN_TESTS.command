#!/bin/zsh
cd -- "$(dirname -- "$0")" || exit 2
python3.13 tests/run_tests.py
result=$?
printf '\nКод завершения: %s (0 — все тесты прошли).\n' "$result"
printf 'Нажмите Enter, чтобы закрыть окно.'
read -r answer
exit "$result"
