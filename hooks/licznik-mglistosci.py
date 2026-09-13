#!/usr/bin/env python3
"""
licznik-mglistosci.py — cichy pomiar tekstu. Hook zdarzenia Stop.

CO ROBI: czyta pole `last_assistant_message` z danych hooka, mierzy mglistość
i kilka miar pomocniczych, dopisuje wiersz do ~/.claude/styl-pl/pomiar.jsonl.

CZEGO NIE ROBI: niczego nie blokuje, nie odsyła do modelu, nie pisze na stdout.
Zawsze kończy kodem 0. Wg dokumentacji hooków tylko exit 2 blokuje zakończenie
tury — my go nigdy nie zwracamy, więc licznik nie może zepsuć rozmowy.

PO CO: żeby po tygodniu pracy zobaczyć na liczbach, czy zasady pisania
realnie zmieniają tekst — zamiast zgadywać z wrażenia.
"""

import json
import os
import re
import sys
import datetime

KATALOG_STANU = os.path.expanduser("~/.claude/styl-pl")
LOG_STYLU = os.path.join(KATALOG_STANU, "pomiar.jsonl")


# Puste ozdobniki — zasada „Zakazane maniery" z pliku zasad.
ZAKAZANE_MANIERY = [
    "nośne", "nośna", "nośny",
    "szew", "szwie", "szwy",
    "trafiłeś w coś istotnego",
    "warto zaznaczyć", "warto podkreślić", "warto zauważyć",
    "chropowatości", "chropowatość",
    "ortogonaln", "nietrywialn", "kanoniczn",
    "nie tylko", "kluczowe jest", "istotne jest",
]

# Anglicyzmy z żelaznej zasady 1. Szukamy jako całych słów.
ANGLICYZMY = [
    "content", "workflow", "feature", "deploy", "deployment", "dashboard",
    "review", "output", "input", "template", "folder", "release", "meeting",
    "feedback", "insight", "insights", "case", "scope", "update", "setup",
    "framework", "pipeline", "commit", "target", "quick win",
]

# Preambuły — otwarcia zakazane przez zasady ADHD.
PREAMBULY = [
    "świetne pytanie", "oczywiście", "rozumiem", "jasne", "pozwól",
    "let me", "i'll ", "sure", "great question",
    "zaraz to", "już to", "chętnie",
]

SKROTY = ("np.", "itd.", "itp.", "tzn.", "tj.", "m.in.", "ok.", "ur.", "godz.",
          "mln.", "tys.", "por.", "zob.", "ss.", "str.", "ul.", "nr.", "dr.")

SAMOGLOSKI = "aeiouyąęó"

# Wyraz: zaczyna się literą, może mieć w środku łącznik lub apostrof.
SLOWO = re.compile(r"[A-Za-ząćęłńóśźżĄĆĘŁŃÓŚŹŻ][\w'-]*")


def sylaby(slowo):
    """
    Liczba sylab w polskim słowie: tyle, ile grup samogłosek. Wyjątek: „i"
    przed samogłoską nie tworzy własnej sylaby (cia-sto to dwie, nie trzy).
    """
    s = re.sub(r"[^a-ząćęłńóśźż]", "", slowo.lower())
    if not s:
        return 0
    n = 0
    poprzednia = False
    for i, z in enumerate(s):
        jest = z in SAMOGLOSKI
        if jest:
            if z == "i" and i + 1 < len(s) and s[i + 1] in SAMOGLOSKI:
                poprzednia = False
                continue
            if not poprzednia:
                n += 1
        poprzednia = jest
    return max(n, 1)


def mglistosc(zdania, slowa_zdaniowe, slowa_slownictwa):
    """
    Indeks mglistości FOG w polskiej adaptacji:
        0,4 × (średnia liczba słów w zdaniu + procent słów trudnych)

    Słowo trudne = 4 sylaby i więcej. Próg czterech sylab dla polszczyzny
    przyjmują Pisarek, Seretny oraz Miodek, Maziarz, Piekot, Poprawa
    i Zarzeczny (w angielskim oryginale są to 3 sylaby).

    Dwa źródła danych, bo dwie części wzoru mierzą co innego:
      - średnią długość zdania liczymy z prozy i punktów list,
      - procent słów trudnych z całości, łącznie z komórkami tabel.

    Wynik ≈ liczba lat nauki potrzebna, żeby zrozumieć tekst za pierwszym razem.
    Łapie jednocześnie długie zdania i ciężkie słowa, więc nie da się jej
    poprawić samym skracaniem — „Implementacja wymaga rekonfiguracji
    parametryzowanego interfejsu" ma 5 słów na zdanie i mglistość 34.

    Znana wada wzoru: karze każde długie słowo, także dobrze znane
    („automatyzacja", „użytkownika"). Poprawioną wersję bez tej wady — MGŁA —
    ma narzędzie Logios; wymaga słownika częstości, którego tu nie mamy.
    """
    if not zdania or not slowa_zdaniowe or not slowa_slownictwa:
        return None, None
    srednia = len(slowa_zdaniowe) / len(zdania)
    trudne = sum(1 for w in slowa_slownictwa if sylaby(w) >= 4)
    procent = 100 * trudne / len(slowa_slownictwa)
    return round(0.4 * (srednia + procent), 1), round(procent, 1)


def dane_wejsciowe():
    """Dane hooka ze standardowego wejścia. Brak albo śmieci = pusty słownik."""
    try:
        if sys.stdin.isatty():
            return {}
        surowe = sys.stdin.read()
        if not surowe.strip():
            return {}
        odczyt = json.loads(surowe)
        return odczyt if isinstance(odczyt, dict) else {}
    except Exception:
        return {}


def wytnij_kod(tekst):
    """
    Usuwa bloki kodu ogrodzone ``` oraz kod w linii. Zwraca (proza, znaki_kodu).
    Kod nie jest prozą — jego długość nie mówi nic o czytelności odpowiedzi.
    """
    bloki = re.findall(r"```.*?```", tekst, flags=re.S)
    znaki_kodu = sum(len(b) for b in bloki)
    proza = re.sub(r"```.*?```", " ", tekst, flags=re.S)
    # Kod w środku zdania liczymy jako jeden element, nie jako jego treść.
    proza = re.sub(r"`[^`]+`", "KOD", proza)
    return proza, znaki_kodu


def czy_separator_tabeli(linia):
    """Wiersz w rodzaju |---|:---:|---| — sam myślniki, dwukropki i kreski."""
    return bool(re.fullmatch(r"\|[\s:|-]+\|?", linia.strip()))


def rozdziel_tekst(proza):
    """
    Dzieli odpowiedź na dwie porcje, bo dwie części wzoru potrzebują różnych
    danych:

    1. `tekst_zdaniowy` — akapity i punkty list. Z tego liczymy ŚREDNIĄ DŁUGOŚĆ
       ZDANIA. Komórki tabel tu nie wchodzą: są z natury krótkie (2-8 słów),
       więc rozcieńczałyby średnią i zaniżały wynik tym mocniej, im więcej tabel.

    2. `slowa_slownictwa` — wszystkie słowa łącznie z komórkami tabel. Z tego
       liczymy PROCENT SŁÓW TRUDNYCH. Ciężkie słowo w komórce jest tak samo
       ciężkie jak w zdaniu, więc musi się liczyć.

    Odpadają wszędzie: nagłówki sekcji, wiersz nagłówkowy tabeli i separator —
    to etykiety, nie treść.

    Uwaga: taki rozdział to decyzja tego licznika, nie część oryginalnego wzoru.
    FOG powstał w 1952 roku dla tekstu ciągłego i o tabelach nie mówi nic.
    """
    surowe = proza.splitlines()
    zdaniowe, slowa_tabel = [], []
    for i, linia in enumerate(surowe):
        s = linia.strip()
        if not s or s.startswith("#"):
            continue

        if s.startswith("|"):
            if czy_separator_tabeli(s):
                continue
            nastepna = surowe[i + 1].strip() if i + 1 < len(surowe) else ""
            if czy_separator_tabeli(nastepna):
                continue
            for komorka in s.strip("|").split("|"):
                k = re.sub(r"\*\*|__|\*|`", "", komorka).strip()
                slowa_tabel.extend(SLOWO.findall(k))
            continue

        s = re.sub(r"^>\s*", "", s)
        s = re.sub(r"^[-*+]\s+", "", s)
        s = re.sub(r"^\d+[.)]\s+", "", s)
        s = re.sub(r"\*\*|__|\*", "", s)
        if not s:
            continue
        if not s.endswith((".", "!", "?", ":", "…")):
            s += "."
        zdaniowe.append(s)

    tekst_zdaniowy = " ".join(zdaniowe)
    return tekst_zdaniowy, SLOWO.findall(tekst_zdaniowy) + slowa_tabel


def podziel_na_zdania(tekst):
    """Podział po . ! ? z ochroną popularnych polskich skrótów."""
    if not tekst.strip():
        return []
    zabezpieczony = tekst
    for i, s in enumerate(SKROTY):
        zabezpieczony = zabezpieczony.replace(s, f"@@{i}@@")
    czesci = re.split(r"(?<=[.!?…])\s+", zabezpieczony)
    zdania = []
    for c in czesci:
        for i, s in enumerate(SKROTY):
            c = c.replace(f"@@{i}@@", s)
        c = c.strip()
        if len(c.split()) >= 2:
            zdania.append(c)
    return zdania


def policz_trafienia(tekst_maly, wzorce, cale_slowa=False):
    """Zwraca słownik {wzorzec: ile razy} dla wzorców, które wystąpiły."""
    trafienia = {}
    for w in wzorce:
        if cale_slowa:
            ile = len(re.findall(r"\b" + re.escape(w) + r"\b", tekst_maly))
        else:
            ile = tekst_maly.count(w)
        if ile:
            trafienia[w] = ile
    return trafienia


def main():
    dane = dane_wejsciowe()
    odpowiedz = dane.get("last_assistant_message") or ""
    if not odpowiedz.strip():
        return

    sesja8 = (dane.get("session_id") or "?")[:8]
    proza, znaki_kodu = wytnij_kod(odpowiedz)
    slowa = proza.split()
    tekst_zdan, slowa_slownictwa = rozdziel_tekst(proza)
    zdania = podziel_na_zdania(tekst_zdan)
    dlugosci = [len(z.split()) for z in zdania]
    maly = proza.lower()

    # Preambuła liczy się tylko na samym początku odpowiedzi.
    poczatek = maly.strip()[:60]
    preambula = next((p for p in PREAMBULY if poczatek.startswith(p)), None)

    slowa_zdan = SLOWO.findall(tekst_zdan)
    fog, proc_trudnych = mglistosc(zdania, slowa_zdan, slowa_slownictwa)

    wpis = {
        "czas": datetime.datetime.now().isoformat(timespec="seconds"),
        "sesja": sesja8,
        # 1: tabele wypadały z liczenia (mierzona połowa odpowiedzi).
        # 2: komórki tabel liczone jak zdania (zaniżało — komórki są krótkie).
        # 3: komórki wchodzą do słownictwa, ale nie do długości zdań.
        # Wyników różnych wersji nie wolno mieszać.
        "wersja_miary": 3,
        "mglistosc": fog,
        "slow_trudnych_proc": proc_trudnych,
        "slowa_prozy": len(slowa),
        "znaki_prozy": len(proza),
        "znaki_kodu": znaki_kodu,
        "zdania": len(zdania),
        "zdanie_najdluzsze": max(dlugosci) if dlugosci else 0,
        "zdanie_srednie": round(sum(dlugosci) / len(dlugosci), 1) if dlugosci else 0,
        "zdania_ponad_25_slow": sum(1 for d in dlugosci if d > 25),
        "preambula": preambula,
        "maniery": policz_trafienia(maly, ZAKAZANE_MANIERY),
        "anglicyzmy": policz_trafienia(maly, ANGLICYZMY, cale_slowa=True),
        "permission_mode": dane.get("permission_mode"),
    }

    os.makedirs(KATALOG_STANU, exist_ok=True)
    with open(LOG_STYLU, "a", encoding="utf-8") as f:
        f.write(json.dumps(wpis, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Siatka bezpieczeństwa: licznik nigdy nie psuje tury.
        pass
    sys.exit(0)
