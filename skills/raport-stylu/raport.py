#!/usr/bin/env python3
"""
raport.py — pokazuje, jak mglisty jest tekst, który dostajesz od Claude Code.

Dane zbiera hook `licznik-mglistosci.py` (zdarzenie Stop) do pliku
~/.claude/styl-pl/pomiar.jsonl. Pomiar nie kosztuje tokenów.
"""

import argparse
import collections
import datetime
import json
import os
import sys

LOG = os.path.expanduser("~/.claude/styl-pl/pomiar.jsonl")

# Skala wg polskiej adaptacji indeksu FOG (Pisarek, Seretny; Miodek, Maziarz,
# Piekot, Poprawa, Zarzeczny). Wynik = liczba lat nauki potrzebna do zrozumienia.
# Punkty odniesienia: „Fakt" ok. 7, „Newsweek" ok. 12, teksty prawne ok. 20.
SKALA = [
    (7, "bardzo prosty — szkoła podstawowa"),
    (10, "prosty — poziom dziennika „Fakt”"),
    (13, "dość prosty — poziom „Newsweeka”"),
    (16, "dość trudny — studia licencjackie"),
    (18, "trudny — studia magisterskie"),
    (999, "bardzo trudny — poziom tekstów prawnych"),
]


def opis(fog):
    for prog, tekst in SKALA:
        if fog < prog:
            return tekst
    return SKALA[-1][1]


def wczytaj(sciezka, od_dni=None):
    wpisy, granica = [], None
    if od_dni:
        granica = datetime.datetime.now() - datetime.timedelta(days=od_dni)
    with open(sciezka, encoding="utf-8") as f:
        for linia in f:
            linia = linia.strip()
            if not linia.startswith("{"):
                continue
            try:
                w = json.loads(linia)
            except Exception:
                continue
            if granica:
                try:
                    if datetime.datetime.fromisoformat(w["czas"]) < granica:
                        continue
                except Exception:
                    pass
            wpisy.append(w)
    return wpisy


def mediana(lista):
    if not lista:
        return 0
    s = sorted(lista)
    n = len(s)
    return s[n // 2] if n % 2 else round((s[n // 2 - 1] + s[n // 2]) / 2, 1)


def slupek(wartosc, maks, szer=28):
    return "█" * max(1, round(szer * wartosc / maks)) if wartosc else ""


def main():
    p = argparse.ArgumentParser(description="Raport mglistości odpowiedzi.")
    p.add_argument("--dni", type=int, default=None, help="Tylko ostatnie N dni.")
    p.add_argument("--najgorsze", type=int, default=5,
                   help="Ile najmglistszych odpowiedzi pokazać (domyślnie 5).")
    p.add_argument("--plik", default=LOG)
    a = p.parse_args()

    if not os.path.exists(a.plik):
        print(f"Brak danych: {a.plik}")
        print("Licznik jeszcze nic nie zapisał. Zakończ przynajmniej jedną turę.")
        sys.exit(0)

    wszystkie = [w for w in wczytaj(a.plik, a.dni) if w.get("mglistosc") is not None]
    if not wszystkie:
        print("Dziennik jest pusty dla podanych warunków.")
        sys.exit(0)

    # Wersja 1 nie liczyła tabel, wersja 2 liczy komórki jak zdania. Wyniki obu
    # są nieporównywalne, więc raportujemy tylko najnowszą i mówimy, ile odpadło.
    najnowsza = max(w.get("wersja_miary", 1) for w in wszystkie)
    wpisy = [w for w in wszystkie if w.get("wersja_miary", 1) == najnowsza]
    pominiete = len(wszystkie) - len(wpisy)

    fog = [w["mglistosc"] for w in wpisy]
    med = mediana(fog)
    zakres = f"ostatnie {a.dni} dni" if a.dni else "cały pomiar"

    print(f"MGLISTOŚĆ TEKSTU — {zakres} · {len(wpisy)} odpowiedzi\n")
    if pominiete:
        print(f"  (pominięto {pominiete} odpowiedzi zmierzonych starszą wersją")
        print(f"   miary — wyników nie da się porównywać)\n")
    print(f"  mediana      {med:>5}   ({opis(med)})")
    print(f"  najniższa    {min(fog):>5}")
    print(f"  najwyższa    {max(fog):>5}")
    trudne = [w["slow_trudnych_proc"] for w in wpisy
              if w.get("slow_trudnych_proc") is not None]
    if trudne:
        print(f"  słów 4+ sylabowych   {sum(trudne)/len(trudne):>5.1f}%")

    print("\nROZKŁAD")
    kubelki = collections.Counter()
    for f in fog:
        kubelki[min(int(f // 2) * 2, 20)] += 1
    maks = max(kubelki.values())
    for dol in sorted(kubelki):
        etykieta = f"{dol}-{dol+2}" if dol < 20 else "20+"
        print(f"  {etykieta:>6}  {slupek(kubelki[dol], maks):<28} {kubelki[dol]}")

    print("\nCO ZNACZY LICZBA")
    print("  Mglistość ≈ ile lat nauki trzeba, żeby zrozumieć tekst za pierwszym")
    print("  razem. Liczona jako 0,4 × (słowa na zdanie + procent słów 4 i więcej")
    print("  sylabowych). Punkty list liczą się jak zdania, tabele i nagłówki nie.")
    poprzedni = 0
    for prog, tekst in SKALA:
        etykieta = f"{poprzedni}-{prog - 1}" if prog < 999 else f"{poprzedni}+"
        print(f"  {etykieta:<8} {tekst}")
        poprzedni = prog
    print("\n  Uwaga: FOG mierzy trudność powierzchniową, nie zrozumiałość.")
    print("  Karze słowa długie, także te dobrze znane („automatyzacja”,")
    print("  „użytkownika”). Poprawioną wersję bez tej wady — MGŁA — ma Logios.")

    print("\n  Uwaga: dwie odpowiedzi na to samo pytanie potrafią różnić się")
    print("  o 3-4 punkty. Pojedynczy wynik nic nie znaczy — patrz na medianę.")

    najg = sorted(wpisy, key=lambda w: -w["mglistosc"])[:a.najgorsze]
    if najg:
        print(f"\nNAJMGLISTSZE ODPOWIEDZI ({len(najg)})")
        for w in najg:
            czas = w.get("czas", "")[:16].replace("T", " ")
            print(f"  {w['mglistosc']:>5}  {czas}  "
                  f"({w.get('slowa_prozy', 0)} słów, "
                  f"{w.get('slow_trudnych_proc', 0)}% trudnych)")

    maniery = collections.Counter()
    for w in wpisy:
        for k, v in (w.get("maniery") or {}).items():
            maniery[k] += v
        for k, v in (w.get("anglicyzmy") or {}).items():
            maniery[k] += v
    if maniery:
        print("\nNAJCZĘSTSZE PUSTE FRAZY I ANGLICYZMY")
        for fraza, ile in maniery.most_common(8):
            print(f"  {ile:>4}x  {fraza}")


if __name__ == "__main__":
    main()
