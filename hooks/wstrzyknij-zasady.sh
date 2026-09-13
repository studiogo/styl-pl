#!/usr/bin/env sh
# Hook SessionStart: wstrzykuje zasady pisania na początku każdej sesji.
# Nigdy nie blokuje startu — każda awaria kończy się kodem 0.
#
# Czysty POSIX sh, żeby działało wszędzie tam, gdzie Claude Code uruchamia
# hooki (sh na macOS i Linuksie, Git Bash na Windowsie).

katalog=$(dirname -- "$0")
plik="$katalog/../zasady/styl-pisania.md"
[ -f "$plik" ] || exit 0

printf 'ZASADY PISANIA (styl-pl). Obowiązują w każdej odpowiedzi do człowieka.\nWyłączenie na tę sesję: napisz "wyłącz styl-pl". Na stałe: odinstaluj wtyczkę.\n\n'
cat "$plik"
exit 0
