#!/usr/bin/env python3
"""
kaganiec.py — hook zdarzenia Stop. Sprawdza gotową odpowiedź względem
mechanicznych progów i ODRZUCA ją raz, gdy któryś łamie. Model dostaje listę
naruszeń i pisze odpowiedź jeszcze raz.

Różnica wobec licznika: licznik mierzy i zapisuje, kaganiec zatrzymuje.

BEZPIECZNIKI
  1. stop_hook_active = true  → nie odrzucamy (to już druga wersja; pętla zakazana).
  2. „wyłącz styl-pl" w dowolnej wiadomości Łukasza w tej sesji → cisza.
  3. plik ~/.claude/styl-pl/kaganiec.off → cisza (wyłącznik globalny).
  4. Ostatnie polecenie zawiera słowo z WYJATKI_DLUGOSCI („wyjaśnij", „rozpisz"…)
     → próg długości nie obowiązuje, reszta progów tak.
  5. Każda awaria skryptu → exit 0 bez wyjścia. Kaganiec nigdy nie psuje tury.

Progi w słowniku PROGI — jedno miejsce do strojenia. Każde odrzucenie loguje
się do ~/.claude/styl-pl/kaganiec.jsonl, żeby po tygodniu zobaczyć, co łapie.
"""

import datetime
import importlib.util
import json
import os
import re
import sys

KATALOG = os.path.dirname(os.path.abspath(__file__))
KATALOG_STANU = os.path.expanduser("~/.claude/styl-pl")
LOG = os.path.join(KATALOG_STANU, "kaganiec.jsonl")
WYLACZNIK = os.path.join(KATALOG_STANU, "kaganiec.off")

PROGI = {
    "slowa_prozy": 250,        # ~80. percentyl z 12 548 pomiarów (232)
    "zdanie_najdluzsze": 35,   # słów; 80. percentyl = 33
    "pytania_max": 1,          # znaków „?" w prozie poza linią KTO-CZEKA
}

# Ostatnie polecenie Łukasza z takim słowem = wolno pisać długo.
WYJATKI_DLUGOSCI = ("wyjaśnij", "wyjasnij", "rozpisz", "naucz", "wytłumacz",
                    "wytlumacz", "opisz dokładnie", "szczegółowo", "szczegolowo",
                    "po kolei", "krok po kroku", "raport", "plan")

# Zakazane otwarcia (styl-pl). Sprawdzane na pierwszych 60 znakach.
OTWARCIA = ("jasne", "rozumiem", "świetne pytanie", "przyjrzyjmy się",
            "zacznijmy od", "warto zaznaczyć", "pozwól", "oczywiście",
            "sure", "great question", "let me", "i'll ")

# Frazy odpływu od zadania i zakazane zamknięcia. Całe frazy, gdziekolwiek.
ODPLYW = ("czy chcesz", "chcesz, żebym", "chcesz żebym", "mogę też", "mogę również",
          "przy okazji", "warto też", "warto również", "jeśli chcesz", "daj znać",
          "mam nadzieję", "chętnie wyjaśnię", "podsumowując", "nie tylko",
          "warto zauważyć", "warto podkreślić", "warto dodać")

# Anglicyzmy z tabeli zamienników styl-pl + żelaznej zasady 1. Całe słowa.
ANGLICYZMY = ("content", "workflow", "case", "folder", "pipeline", "insights",
              "insight", "setup", "review", "output", "feature", "deploy",
              "dashboard", "template", "release", "meeting", "feedback")

KTO_CZEKA = re.compile(r"\[KTO-CZEKA: (GOTOWE|CZEKA) \| [^\]\n]{3,}\]")


def wczytaj_licznik():
    """Funkcje pomiaru bierzemy z licznika, żeby nie mieć dwóch definicji zdania."""
    sciezka = os.path.join(KATALOG, "licznik-mglistosci.py")
    spec = importlib.util.spec_from_file_location("licznik", sciezka)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def tekst_wiadomosci(msg):
    tresc = msg.get("content") if isinstance(msg, dict) else None
    if isinstance(tresc, str):
        return tresc
    if isinstance(tresc, list):
        return " ".join(b.get("text", "") for b in tresc
                        if isinstance(b, dict) and b.get("type") == "text")
    return ""


def wiadomosci_uzytkownika(transcript_path):
    """Lista tekstów wiadomości Łukasza (bez wyników narzędzi i bez komend)."""
    wynik = []
    try:
        with open(transcript_path, encoding="utf-8") as f:
            for linia in f:
                if '"type":"user"' not in linia and '"type": "user"' not in linia:
                    continue
                try:
                    w = json.loads(linia)
                except Exception:
                    continue
                if w.get("type") != "user":
                    continue
                t = tekst_wiadomosci(w.get("message", {})).strip()
                if t and not t.startswith("<"):
                    wynik.append(t)
    except OSError:
        pass
    return wynik


# Miejsca, w których angielskie słowo jest nazwą, nie stylem: adres strony,
# ścieżka pliku i pojedynczy wyraz w cudzysłowie (cytat z komunikatu albo
# przykład, o którym akurat rozmawiamy). Wycinamy je PRZED sprawdzeniem
# anglicyzmów — tam nie ma czego tłumaczyć, a odrzucenie blokuje odpowiedź
# bez wyjścia (10.09.2026: hook odrzucał zdanie cytujące własny komunikat).
ADRES = re.compile(
    r"(https?://\S+|www\.\S+|(?:~|\.)?/[\w./~-]+"
    r"|\b[\w-]+\.(?:py|sh|md|json|html|js|ts|txt|yml|yaml)\b)")
CYTOWANY_WYRAZ = re.compile(r"[\u201e\"\'\u2018\u201a]([\w-]{2,20})[\u201d\"\'\u2019]")


def bez_nazw_wlasnych(tekst):
    """Usuwa adresy, ścieżki i cytowane pojedyncze wyrazy (patrz komentarz wyżej)."""
    tekst = ADRES.sub(" ", tekst)
    return CYTOWANY_WYRAZ.sub(" ", tekst)


def zbadaj(odpowiedz, lic, wolno_dlugo):
    """Zwraca listę naruszeń: (kod, opis, naprawa)."""
    naruszenia = []
    proza, _ = lic.wytnij_kod(odpowiedz)
    slowa = proza.split()
    tekst_zdan, _ = lic.rozdziel_tekst(proza)
    zdania = lic.podziel_na_zdania(tekst_zdan)
    dlugosci = [len(z.split()) for z in zdania]
    maly = proza.lower()

    if not wolno_dlugo and len(slowa) > PROGI["slowa_prozy"]:
        naruszenia.append(("dlugosc",
            f"{len(slowa)} słów prozy, próg {PROGI['slowa_prozy']}",
            "wytnij zdania, które nie zmieniają decyzji czytelnika; punkt listy = max 2 zdania"))

    if dlugosci and max(dlugosci) > PROGI["zdanie_najdluzsze"]:
        najdluzsze = zdania[dlugosci.index(max(dlugosci))]
        naruszenia.append(("zdanie",
            f"zdanie na {max(dlugosci)} słów, próg {PROGI['zdanie_najdluzsze']}: „{najdluzsze[:90]}…”",
            "potnij na dwa albo trzy zdania"))

    poczatek = maly.strip()[:60]
    trafione = next((o for o in OTWARCIA if poczatek.startswith(o)), None)
    if trafione:
        naruszenia.append(("otwarcie", f"zakazane otwarcie „{trafione}”",
                           "skreśl pierwsze zdanie, zacznij od wyniku"))

    odplyw = {f: maly.count(f) for f in ODPLYW if f in maly}
    if odplyw:
        naruszenia.append(("odplyw",
            "frazy odpływu/zamknięcia: " + ", ".join(f"„{k}”" for k in odplyw),
            "usuń zdania z tymi frazami; pomysł poza zadaniem → park.py, nie do odpowiedzi"))

    angl = {a: len(re.findall(r"\b" + a + r"\b", bez_nazw_wlasnych(maly)))
            for a in ANGLICYZMY}
    angl = {k: v for k, v in angl.items() if v}
    if angl:
        naruszenia.append(("anglicyzm",
            "anglicyzmy: " + ", ".join(f"„{k}”" for k in angl),
            "zamień wg tabeli zamienników (treść, proces, przypadek, katalog, potok, wnioski, konfiguracja, przegląd, wynik, funkcja, wdrożenie, tablica, szablon, wydanie, spotkanie, uwagi)"))

    bez_znacznika = KTO_CZEKA.sub("", proza)
    pytania = bez_znacznika.count("?")
    if pytania > PROGI["pytania_max"]:
        naruszenia.append(("pytania",
            f"{pytania} pytania w odpowiedzi, dozwolone {PROGI['pytania_max']}",
            "zostaw jedno pytanie, na które sam nie znasz odpowiedzi; resztę rozstrzygnij"))

    # Linia KTO-CZEKA wycofana 11.10.2026 (nadzor-sesji); stare odpowiedzi z nią tylko ją pomijają.

    return naruszenia, len(slowa)


def zapisz_log(wpis):
    try:
        os.makedirs(KATALOG_STANU, exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(wpis, ensure_ascii=False) + "\n")
    except OSError:
        pass


def main():
    if os.path.exists(WYLACZNIK):
        return
    try:
        dane = json.loads(sys.stdin.read() or "{}")
    except Exception:
        return
    if not isinstance(dane, dict):
        return
    if dane.get("stop_hook_active"):
        return  # druga wersja odpowiedzi przechodzi zawsze
    odpowiedz = dane.get("last_assistant_message") or ""
    if not odpowiedz.strip():
        return

    uzytkownik = wiadomosci_uzytkownika(dane.get("transcript_path") or "")
    if any("wyłącz styl-pl" in u.lower() for u in uzytkownik):
        return
    ostatnie = uzytkownik[-1].lower() if uzytkownik else ""
    wolno_dlugo = any(w in ostatnie for w in WYJATKI_DLUGOSCI)

    lic = wczytaj_licznik()
    naruszenia, slowa = zbadaj(odpowiedz, lic, wolno_dlugo)

    zapisz_log({
        "czas": datetime.datetime.now().isoformat(timespec="seconds"),
        "sesja": (dane.get("session_id") or "?")[:8],
        "slowa_prozy": slowa,
        "wolno_dlugo": wolno_dlugo,
        "odrzucono": bool(naruszenia),
        "kody": [n[0] for n in naruszenia],
    })

    if not naruszenia:
        return

    linie = ["KAGANIEC styl-pl: odpowiedź odrzucona. Napisz ją jeszcze raz, poprawiając WSZYSTKIE punkty:"]
    for i, (kod, opis, naprawa) in enumerate(naruszenia, 1):
        linie.append(f"{i}. [{kod}] {opis} → {naprawa}.")
    linie.append("Nie komentuj odrzucenia, nie tłumacz się, nie dodawaj nic nowego. Sama poprawiona odpowiedź.")
    print(json.dumps({"decision": "block", "reason": "\n".join(linie)}, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
