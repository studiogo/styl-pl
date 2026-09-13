#!/usr/bin/env bash
# Hook UserPromptSubmit: wstrzykuje PEŁNĄ treść zasad pisania po przekroczeniu
# progu zapełnienia kontekstu. Im ciaśniej w kontekście, tym gęstsze progi —
# bo im dalej od startu sesji, tym słabiej działa jednorazowe wstrzyknięcie.
#
# Progi te same, co miał wcześniejszy hook zasad pisania (sprawdzone w praktyce).
# Fail-closed: przy problemie z odczytem wstrzykujemy. Cisza jest groźniejsza
# niż nadmiar.

PROGI="4,11,16,20,23,26,28,30.5,36,40,44,48,52,56,60,64,68,72,76,79.5,82.5,85.5,88.5,91,93,95,96.5,97.5,98.5,99.5"

KATALOG="$(dirname -- "$0")"
PLIK="$KATALOG/../zasady/styl-pisania.md"
[ -f "$PLIK" ] || exit 0

DANE="$(cat)"
DECYZJA="$(printf '%s' "$DANE" | RYTM_PROGI="$PROGI" \
  python3 "$KATALOG/rytm-progow.py" --decyzja --log 2>/dev/null)"

if [ "$DECYZJA" != "NIE" ]; then
  printf 'ZASADY PISANIA (styl-pl) — przypomnienie na progu zapełnienia kontekstu.\n\n'
  cat "$PLIK"
fi
exit 0
