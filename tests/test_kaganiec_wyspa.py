"""Test: blok wyspy i znacznik sztafety nie liczą się do pytań w prozie kagańca."""
import importlib.util
import os

KATALOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hooks")


def _moduł(nazwa, plik):
    spec = importlib.util.spec_from_file_location(nazwa, os.path.join(KATALOG, plik))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


kaganiec = _moduł("kaganiec", "kaganiec.py")
licznik = kaganiec.wczytaj_licznik()

WYSPA = ("<!-- wyspa\n? decyzja | Wybierz wariant A albo B.\n"
         "? odpowiedz | Podaj numer zamówienia.\n? test | Otwórz stronę i sprawdź.\n"
         "teraz: Czekam na decyzję.\ntemat: Wybór wariantu\n-->")


def kody(odpowiedz):
    naruszenia, _ = kaganiec.zbadaj(odpowiedz, licznik, False)
    return [n[0] for n in naruszenia]


def test_jedno_pytanie_w_prozie_i_wyspa_bez_naruszenia():
    assert "pytania" not in kody("Wynik jest gotowy. Który wariant wybierasz?\n\n" + WYSPA)


def test_dwa_pytania_w_prozie_to_naruszenie():
    assert "pytania" in kody("Który wariant wybierasz? A który termin?\n\n" + WYSPA)


def test_znacznik_sztafety_i_wyspa_bez_naruszenia():
    odp = "Praca trwa. [SZTAFETA? 71%]\n\n<!-- wyspa\n? decyzja | Wybierz wariant.\n-->"
    assert "pytania" not in kody(odp)
