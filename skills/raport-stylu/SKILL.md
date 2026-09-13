---
name: raport-stylu
description: Pokazuje, jak mglisty jest tekst, który dostajesz od Claude Code — mediana, rozkład i najgorsze odpowiedzi. Use when użytkownik mówi "raport stylu", "mglistość", "czy zasady pisania działają", "jak piszesz", "/raport-stylu".
---

# Raport stylu

Uruchom:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/raport-stylu/raport.py"
python3 "${CLAUDE_PLUGIN_ROOT}/skills/raport-stylu/raport.py" --dni 7
python3 "${CLAUDE_PLUGIN_ROOT}/skills/raport-stylu/raport.py" --najgorsze 10
```

Pokaż użytkownikowi wynik w całości. Nie streszczaj tabeli własnymi słowami.

## Skąd dane

Hook `licznik-mglistosci.py` (zdarzenie Stop) po każdej turze mierzy odpowiedź
i dopisuje wiersz do `~/.claude/styl-pl/pomiar.jsonl`. Czyta pole
`last_assistant_message`, które Claude Code i tak podaje hookom — pomiar nie
kosztuje ani jednego tokenu i niczego nie blokuje.

## Jak czytać wynik

- **Mediana, nie średnia.** Jedna długa odpowiedź zawyża średnią.
- **Pojedynczy wynik nic nie znaczy.** Dwie odpowiedzi na to samo pytanie
  potrafią różnić się o 3-4 punkty. Wnioski wyciągaj z co najmniej
  kilkudziesięciu odpowiedzi.
- **Mglistość jest alarmem, nie linijką.** Wychwyci osunięcie się w urzędowy
  język (powyżej 16). Nie rozstrzygnie, czy tekst o wyniku 9,9 jest lepszy od
  tekstu o wyniku 10,4.

## Czego nie mierzy

Trafności, kompletności ani przydatności. Krótka i bezużyteczna odpowiedź wypadnie
tu lepiej niż długa i potrzebna. To miara formy, nie wartości.
