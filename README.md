# styl-pl

Zasady, dzięki którym AI odpowiada po polsku krótko, prostym językiem i bez waty. Dla każdego, kto pracuje z Claude Code, ChatGPT albo Claude w przeglądarce.

Repozytorium ma dwie warstwy. Pierwsza to sam plik zasad: wklejasz go do dowolnego AI i gotowe. Druga to wtyczka do Claude Code, która dodatkowo pilnuje zasad i mierzy, czy działają.

## Co jest w środku

| Plik | Do czego służy | Stan |
|---|---|---|
| `styl-pl.md` (katalog ze stylami) | Zasady pisania. Jedyne źródło prawdy. | działa |
| `zasady-dla-ciebie.md` | Te same zasady gotowe do wklejenia w dowolne AI, bez odwołań do autora. | działa |
| `hooks/kaganiec.py` | Sprawdza gotową odpowiedź. Gdy łamie progi, odsyła ją raz do poprawki. | działa |
| `hooks/licznik-mglistosci.py` | Po cichu mierzy każdą odpowiedź i zapisuje wynik na twoim dysku. | działa |
| `hooks/hooks.json` | Włącza kaganiec i licznik po instalacji wtyczki. | działa |
| `skills/raport-stylu/` | Pokazuje liczby zebrane przez licznik. | działa |
| `hooks/wstrzyknij-zasady.sh`, `hooks/wstrzyknij-na-progach.sh`, `hooks/rytm-progow.py` | Dawniej wklejały zasady do rozmowy. Wyłączone 06.09.2026, bo styl odpowiedzi robi to samo lepiej. | historia |
| `zasady/styl-pisania.md`, `zasady/styl-pisania-claude-app.md` | Starsze wersje zasad, nieużywane od 06.09.2026. | historia |

Pliki oznaczone „historia" zostają w repozytorium, żeby było widać, skąd przyszła obecna wersja. Nic ich nie uruchamia. Nie musisz ich instalować.

## Wariant A: sam plik zasad (bez instalowania czegokolwiek)

Otwórz plik `zasady-dla-ciebie.md`, skopiuj całą treść i wklej ją w jedno z miejsc poniżej. Niczego nie poprawiasz.

| Narzędzie | Miejsce |
|---|---|
| Claude Code | Wklej do pliku `~/.claude/CLAUDE.md` (wszystkie projekty) albo `CLAUDE.md` w katalogu projektu (jeden projekt). |
| Codex, Cursor i inne narzędzia czytające `AGENTS.md` | Wklej do pliku `AGENTS.md` w katalogu projektu. |
| ChatGPT w przeglądarce | Załóż projekt i wklej treść w pole z instrukcjami projektu. |
| Claude w przeglądarce | Załóż projekt i wklej treść w pole z instrukcjami projektu. |

W Claude Code możesz zamiast tego użyć zasad jako stylu odpowiedzi: to plik `styl-pl.md` z katalogu ze stylami. Styl działa najpewniej, bo siedzi w instrukcji systemowej, a Claude Code sam przypomina go w długiej rozmowie. Ten plik jest pisany pod autora: zamień w nim imię „Łukasz" na swoje i usuń zdanie o parkingu pomysłów, bo odwołuje się do skryptu, którego nie masz. Napisz w Claude Code: „zapisz plik styl-pl.md jako mój styl odpowiedzi", a potem w `/config` wybierz styl `styl-pl`.

## Wariant B: cała wtyczka w Claude Code

W Claude Code wpisz:

```
/plugin marketplace add studiogo/styl-pl
/plugin install styl-pl@styl-pl
```

Potem uruchom Claude Code od nowa i w `/config` wybierz styl `styl-pl:styl-pl`. Sama instalacja stylu nie włącza, trzeba go wybrać.

Raport z pomiarów: `/styl-pl:raport-stylu`.

## Wariant C: kaganiec i licznik ręcznie w `settings.json`

Dla osób, które nie chcą wtyczki. Pobierz repozytorium do dowolnego katalogu i dopisz do `~/.claude/settings.json` (zamień `/SCIEZKA/styl-pl` na swój katalog):

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          { "type": "command", "command": "python3 \"/SCIEZKA/styl-pl/hooks/licznik-mglistosci.py\"", "timeout": 5 },
          { "type": "command", "command": "python3 \"/SCIEZKA/styl-pl/hooks/kaganiec.py\"", "timeout": 10 }
        ]
      }
    ]
  }
}
```

Masz już sekcję `hooks` w tym pliku? Dopisz tylko wpis `Stop`, nie wklejaj drugiej sekcji. Wymagany Python 3.

## Jak działa kaganiec

Po każdej odpowiedzi sprawdza sześć rzeczy: długość (250 słów prozy), najdłuższe zdanie (35 słów), zakazane otwarcia, frazy odpływające od tematu, anglicyzmy z listy i liczbę pytań (najwyżej jedno). Na końcu wymaga dokładnie jednej linii `[KTO-CZEKA: ...]`.

Gdy coś łamie, odsyła odpowiedź z listą poprawek. Robi to tylko raz: druga wersja przechodzi zawsze, więc rozmowa nie utknie w pętli.

Na polecenie z „wyjaśnij", „rozpisz", „naucz", „raport" albo „plan" limit długości nie obowiązuje. Reszta progów tak.

Dwie rzeczy, o których trzeba wiedzieć:

1. Poprawka kosztuje. Odrzucona odpowiedź powstaje dwa razy.
2. Kaganiec wymaga linii `[KTO-CZEKA]`. Plik zasad każe ją pisać. Jeśli używasz kagańca z innymi zasadami, odrzuci każdą pierwszą wersję.

Wyłączenie na jedną rozmowę: napisz „wyłącz styl-pl". Na stałe: załóż pusty plik `~/.claude/styl-pl/kaganiec.off`.

## Co pokazały pomiary

Liczby z jednego komputera autora, 17.08 do 13.09.2026.

- Licznik zmierzył ponad 17 tysięcy odpowiedzi.
- Kaganiec sprawdził 4185 odpowiedzi od 05.09 i odrzucił 18 procent.
- Mediana długości: 194 słowa w pierwszych 200 odpowiedziach, 119 słów w całym okresie. Mediany z pojedynczych dni skaczą od 49 do 198 słów, bo zależą od rodzaju pracy. Pojedynczy dzień niczego nie dowodzi.
- Zasada sprawdzalna słowem działa: zakaz wstępów w rodzaju „Jasne" trzymał się w 99,7 procent odpowiedzi (2565 odpowiedzi, sierpień).
- Zasada wymagająca liczenia w trakcie pisania nie działa: zdanie do 15 słów trzymało się w 15 procent. Dlatego próg podniesiono do 35 słów i sprawdza go kaganiec, a nie sam model.

Wniosek: opis w rodzaju „pisz jaśniej" niczego nie zmienia. Zmienia zakaz konkretnego słowa i sprawdzenie po fakcie.

## Co znaczy mglistość

Mniej więcej: ile lat nauki trzeba, żeby zrozumieć tekst za pierwszym razem. Wzór: 0,4 × (słowa na zdanie + procent słów o czterech i więcej sylabach). To polska wersja indeksu FOG Roberta Gunninga. Próg czterech sylab przyjmują Pisarek, Seretny oraz Miodek, Maziarz, Piekot, Poprawa i Zarzeczny.

| Wynik | Poziom | Punkt odniesienia |
|---|---|---|
| 1-6 | bardzo prosty, szkoła podstawowa | |
| 7-9 | prosty | dziennik „Fakt" ok. 7 |
| 10-12 | dość prosty, liceum | „Newsweek" ok. 12 |
| 13-15 | dość trudny, studia licencjackie | |
| 16-17 | trudny, studia magisterskie | |
| 18+ | bardzo trudny | teksty prawne ok. 20 |

Znana wada: wzór karze każde długie słowo, także takie, które znasz dobrze („automatyzacja", „użytkownika"). Zespół Tomasza Piekota zbudował poprawioną miarę MGŁA (narzędzie Logios), która pomija słowa długie, ale częste. Ta wtyczka liczy klasyczny FOG, bo nie potrzebuje słownika częstości.

Mglistość nie ocenia trafności. Krótka i bezużyteczna odpowiedź wypadnie lepiej niż długa i potrzebna.

## Twoje dane

Licznik zapisuje wyniki w `~/.claude/styl-pl/pomiar.jsonl`, kaganiec w `~/.claude/styl-pl/kaganiec.jsonl`. Zapisuje liczby i kody naruszeń, nie treść rozmów. Nic nie wychodzi poza twój komputer.

## Skąd to się wzięło

Zasady o kształcie odpowiedzi pochodzą z [i-have-adhd](https://github.com/ayghri/i-have-adhd) (licencja MIT, Ayoub Ghriss), przetłumaczone i dopasowane do polszczyzny. Zasady doboru słów opierają się na standardzie prostego języka Jasnopisu, Fundacji Języka Polskiego, Uniwersytetu Szczecińskiego, UAM i UW.

## Licencja

MIT. Szczegóły w pliku `LICENSE`.
