#!/usr/bin/env python3
"""
Aktualizuje nadchazejici_zapasy.html a tabulka.html pro TJ Poniklá.

Nadcházející zápasy se stahují ze sportmap.cz (vždy aktuální sezóna),
tabulka z fotbalapi.denik.cz.

Soutěž se hledá automaticky: mezi mužskými soutěžemi okresu Semily se najde
ta, ve které je v tabulce Poniklá. Díky tomu skript přežije jak novou sezónu
(denik.cz každý rok zakládá nové ID), tak postup nebo pád do jiné ligy —
není potřeba nic ručně přepisovat.
"""

import json
import os
import re
import subprocess
import sys
import unicodedata
import requests
from datetime import datetime
from pathlib import Path

API_BASE = "https://fotbalapi.denik.cz/api/front/1/"
SPORTMAP_URL = "https://www.sportmap.cz/club/fotbal/tj-ponikla"
ORGANIZATION_UNIT_ID = 29  # okresní fotbalový svaz Semily
TEAM_NEEDLE = "ponikla"  # bez diakritiky, hledá se v názvu týmu
COMPETITION_ID_FALLBACK = 24148  # 9. liga Semily 2026/2027 — poslední záchrana
HERE = Path(__file__).parent

TABLE_PLACEHOLDER = "Sezóna ještě nezačala"
UPCOMING_PLACEHOLDER = "Žádné naplánované zápasy"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json",
}

FTP_HOST = os.environ.get("FTP_HOST", "tjponikla.cz")
FTP_USER = os.environ.get("FTP_USER", "admin.tjponikla.cz")
FTP_PASS = os.environ.get("FTP_PASS")
IN_CI = os.environ.get("GITHUB_ACTIONS") == "true"


def strip_diacritics(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn")


# ── Nadcházející zápasy ze sportmap.cz ─────────────────────────────────────────

def fetch_upcoming() -> list[dict]:
    """Stáhne nadcházející zápasy TJ Poniklá ze sportmap.cz (vždy aktuální sezóna)."""
    r = requests.get(SPORTMAP_URL, headers={"User-Agent": HEADERS["User-Agent"]}, timeout=15)
    r.raise_for_status()

    m = re.search(r'id="mapSourceMatches">(\[.*?\])</div>', r.text, re.DOTALL)
    if not m:
        raise RuntimeError("Na sportmap.cz nebyl nalezen seznam zápasů (mapSourceMatches).")

    raw_matches = json.loads(m.group(1))
    events = []
    for match in raw_matches:
        detail = match.get("match_detail", "")
        m_detail = re.search(
            r"Zápas:\s*(.+?)\s*:\s*(.+?)\s*\((\d{1,2})\.(\d{1,2})\.(\d{4})\s+(\d{2}):(\d{2})\)",
            detail,
        )
        if not m_detail:
            continue
        home, guest, day, month, year, hh, mm = m_detail.groups()
        dt = datetime(int(year), int(month), int(day), int(hh), int(mm))
        location = match.get("match_field", "").removeprefix("Hřiště: ").strip()
        events.append({"dt": dt, "home": home.strip(), "guest": guest.strip(), "location": location})

    return sorted(events, key=lambda x: x["dt"])


# ── Načtení tabulky z API ─────────────────────────────────────────────────────

def season_year(now: datetime | None = None) -> int:
    """Ročník sezóny: 2026/2027 má v API year=2026. Nová sezóna začíná v červenci."""
    now = now or datetime.now()
    return now.year if now.month >= 7 else now.year - 1


def fetch_standings(competition_id: int) -> list[dict]:
    r = requests.get(
        f"{API_BASE}standing",
        params={"competitionId": competition_id},
        headers=HEADERS,
        timeout=15,
    )
    r.raise_for_status()
    data = r.json()
    return data.get("rounds", []) if isinstance(data, dict) else []


def find_competition(year: int) -> tuple[int, str, list[dict]] | None:
    """Najde mužskou soutěž okresu Semily, ve které Poniklá figuruje v tabulce.

    Když je Poniklá ve víc soutěžích (základní část + nadstavbová skupina),
    vybere tu s nejvíc týmy, tedy hlavní tabulku.
    """
    r = requests.get(
        f"{API_BASE}competitions",
        params={"organizationUnitIds": ORGANIZATION_UNIT_ID, "year": year, "limit": 100},
        headers=HEADERS,
        timeout=15,
    )
    r.raise_for_status()

    candidates = []
    for comp in r.json().get("results", []):
        if comp.get("category") != "Muži":
            continue
        try:
            standings = fetch_standings(comp["id"])
        except Exception as e:
            print(f"   ⚠️  soutěž {comp.get('id')} nešla načíst: {e!r}", file=sys.stderr)
            continue
        if any(TEAM_NEEDLE in strip_diacritics(t.get("teamName", "")) for t in standings):
            candidates.append((len(standings), comp["id"], comp.get("name", "?"), standings))

    if not candidates:
        return None
    candidates.sort(key=lambda c: c[0], reverse=True)
    _, comp_id, name, standings = candidates[0]
    return comp_id, name, standings


def resolve_standings() -> tuple[list[dict], str]:
    """Vrátí tabulku aktuální soutěže Poniklé a její popis.

    Zkusí letošní ročník, pak loňský (v červenci–srpnu nemusí být nová soutěž
    ještě vypsaná), a teprve nakonec zadrátované ID.
    """
    this_year = season_year()
    for year in (this_year, this_year - 1):
        found = find_competition(year)
        if found:
            comp_id, name, standings = found
            return standings, f"{name} {year}/{year + 1} (id={comp_id})"
        print(f"   ⚠️  pro ročník {year}/{year + 1} se soutěž s Poniklou nenašla", file=sys.stderr)

    print(f"   ⚠️  používám záložní COMPETITION_ID={COMPETITION_ID_FALLBACK}", file=sys.stderr)
    return fetch_standings(COMPETITION_ID_FALLBACK), f"záložní id={COMPETITION_ID_FALLBACK}"


# ── Generování HTML fragmentů ─────────────────────────────────────────────────

def build_upcoming_html(events: list[dict]) -> str:
    rows = []
    for ev in events:
        datum = ev["dt"].strftime("%d.%m.%Y")
        cas = ev["dt"].strftime("%H:%M")
        rows.append(
            f"    <tr>\n"
            f"      <td>{datum}</td>\n"
            f"      <td>{cas}</td>\n"
            f"      <td>{ev['home']}</td>\n"
            f"      <td>{ev['guest']}</td>\n"
            f"      <td>{ev['location']}</td>\n"
            f"    </tr>"
        )
    body = "\n".join(rows) if rows else f'    <tr><td colspan="5">{UPCOMING_PLACEHOLDER}</td></tr>'
    return (
        '<table border="1" class="dataframe">\n'
        "  <thead>\n"
        '    <tr style="text-align: right;">\n'
        "      <th>Datum</th>\n"
        "      <th>Čas</th>\n"
        "      <th>Domácí</th>\n"
        "      <th>Hosté</th>\n"
        "      <th>Místo</th>\n"
        "    </tr>\n"
        "  </thead>\n"
        "  <tbody>\n"
        f"{body}\n"
        "  </tbody>\n"
        "</table>"
    )


def build_table_html(standings: list[dict]) -> str:
    rows = []
    for t in standings:
        scored = t.get("goalScored", 0)
        conceded = t.get("goalConceded", 0)
        rows.append(
            f"    <tr>\n"
            f"      <td>{t.get('rank', '')}</td>\n"
            f"      <td>{t.get('teamName', '')}</td>\n"
            f"      <td>{t.get('totalMatchesPlayed', 0)}</td>\n"
            f"      <td>{t.get('win', 0)}</td>\n"
            f"      <td>{t.get('draw', 0)}</td>\n"
            f"      <td>{t.get('loss', 0)}</td>\n"
            f"      <td>{scored}:{conceded}</td>\n"
            f"      <td>{t.get('points', 0)}</td>\n"
            f"    </tr>"
        )
    body = (
        "\n".join(rows)
        if rows
        else f'    <tr><td colspan="8">{TABLE_PLACEHOLDER}, tabulka bude brzy k dispozici.</td></tr>'
    )
    return (
        '<table border="1" class="dataframe">\n'
        "  <thead>\n"
        '    <tr style="text-align: right;">\n'
        "      <th>Pořadí</th>\n"
        "      <th>Tým</th>\n"
        "      <th>Z</th>\n"
        "      <th>V</th>\n"
        "      <th>R</th>\n"
        "      <th>P</th>\n"
        "      <th>Skóre</th>\n"
        "      <th>B</th>\n"
        "    </tr>\n"
        "  </thead>\n"
        "  <tbody>\n"
        f"{body}\n"
        "  </tbody>\n"
        "</table>"
    )


def has_real_rows(path: Path, placeholder: str) -> bool:
    """Obsahuje soubor skutečná data (ne jen zástupný řádek)?"""
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8")
    return "<td>" in text and placeholder not in text


# ── Nahrání na web (Websupport FTP) ───────────────────────────────────────────

UPLOAD_TARGETS = [
    ("nadchazejici_zapasy.html", "nadhazenici.html"),
    ("tabulka.html", "tabulka.html"),
]
REMOTE_DIRS = ["", "public_html/"]


def _connect_ftps():
    """FTPS (explicitní AUTH TLS) — heslo nejde po drátě v plaintextu."""
    import ftplib
    f = ftplib.FTP_TLS()
    f.connect(FTP_HOST, 21, timeout=30)
    f.auth()
    f.login(FTP_USER, FTP_PASS)
    f.prot_p()
    f.set_pasv(True)
    return f


def _connect_plain(passive: bool):
    import ftplib
    f = ftplib.FTP()
    f.connect(FTP_HOST, 21, timeout=30)
    f.login(FTP_USER, FTP_PASS)
    f.set_pasv(passive)
    return f


CONNECT_STRATEGIES = [
    ("FTPS / AUTH TLS, pasivní", _connect_ftps),
    ("FTP pasivní", lambda: _connect_plain(True)),
    ("FTP aktivní", lambda: _connect_plain(False)),
]


def upload_to_web() -> list[str]:
    """Nahraje vygenerované tabulky na web. Vrací seznam problémů (prázdný = OK).

    Websupport se z různých sítí chová jinak, proto se zkouší víc způsobů
    připojení. Každý upload se navíc ověří porovnáním velikosti na serveru —
    zelený běh tak znamená, že se web skutečně změnil.
    """
    for label, connect in CONNECT_STRATEGIES:
        print(f"   zkouším {label}...")
        try:
            ftp = connect()
        except Exception as e:
            print(f"   ✗ {label}: {type(e).__name__}: {e}", file=sys.stderr)
            continue

        try:
            uploaded, failures = [], []
            for local_name, remote_name in UPLOAD_TARGETS:
                local_path = HERE / local_name
                local_size = local_path.stat().st_size
                landed = False
                for prefix in REMOTE_DIRS:
                    remote = f"{prefix}{remote_name}"
                    try:
                        with open(local_path, "rb") as fh:
                            ftp.storbinary(f"STOR {remote}", fh)
                        remote_size = ftp.size(remote)
                        if remote_size != local_size:
                            failures.append(
                                f"{remote}: na serveru {remote_size} B, lokálně {local_size} B"
                            )
                            continue
                        uploaded.append(remote)
                        landed = True
                    except Exception as e:
                        # Ne každá cesta na serveru existuje, to je v pořádku.
                        print(f"     • {remote}: {type(e).__name__}: {e}", file=sys.stderr)
                if not landed:
                    failures.append(f"{local_name} se nepodařilo nahrát nikam")

            if uploaded and not failures:
                print(f"   ✅ nahráno přes {label}: {', '.join(uploaded)}")
                return []
            if uploaded:
                print(f"   ⚠️  částečně nahráno přes {label}: {', '.join(uploaded)}", file=sys.stderr)
                return failures
            print(f"   ✗ {label}: nenahrál se ani jeden soubor", file=sys.stderr)
        finally:
            try:
                ftp.quit()
            except Exception:
                ftp.close()

    return [
        "FTP upload selhal všemi způsoby (FTPS, pasivní i aktivní FTP) — "
        "web zůstal nezměněný. Zkontroluj přihlašovací údaje a jestli hosting "
        "nepustí jen určité IP adresy."
    ]


# ── Hlavní funkce ─────────────────────────────────────────────────────────────

def main():
    problems: list[str] = []

    print("📅 Stahuju nadcházející zápasy ze sportmap.cz...")
    upcoming = fetch_upcoming()
    print(f"   {len(upcoming)} nadcházejících zápasů")

    print("📊 Hledám aktuální soutěž a stahuju tabulku...")
    standings, comp_label = resolve_standings()
    print(f"   {comp_label} — {len(standings)} týmů")

    table_path = HERE / "tabulka.html"
    upcoming_path = HERE / "nadchazejici_zapasy.html"

    # Prázdnou tabulkou nikdy nepřepisuj dobrá data — to by na webu smazalo ligu.
    if not standings and has_real_rows(table_path, TABLE_PLACEHOLDER):
        problems.append(
            "API vrátilo prázdnou tabulku, ale tabulka.html obsahuje platná data — "
            "nechávám poslední dobrou verzi. Zkontroluj, jestli se nezměnila soutěž."
        )
        print(f"⚠️  {problems[-1]}", file=sys.stderr)
    else:
        table_path.write_text(build_table_html(standings), encoding="utf-8")
        print("✅ tabulka.html aktualizován")

    upcoming_path.write_text(build_upcoming_html(upcoming), encoding="utf-8")
    print("✅ nadchazejici_zapasy.html aktualizován")
    if not upcoming:
        print("   (žádné naplánované zápasy — mezi sezónami je to normální)")

    # Nahrání na web
    if not FTP_PASS:
        msg = "FTP_PASS není nastavené, přeskakuji upload na web."
        print(f"⚠️  {msg}", file=sys.stderr)
        if IN_CI:
            problems.append(msg + " V Actions to znamená chybějící secret.")
    else:
        print("📤 Nahrávám na web...")
        problems.extend(upload_to_web())

    # Push na GitHub
    print("🚀 Pushuji na GitHub...")
    date_str = datetime.now().strftime("%d.%m.%Y")
    subprocess.run(
        ["git", "-C", str(HERE), "add", "nadchazejici_zapasy.html", "tabulka.html"], check=True
    )
    result = subprocess.run(
        ["git", "-C", str(HERE), "commit", "-m", f"Auto-update: {date_str}"],
        capture_output=True, text=True
    )
    if "nothing to commit" in result.stdout + result.stderr:
        print("   Žádné změny k pushnutí.")
    else:
        push = subprocess.run(
            ["git", "-C", str(HERE), "push"], capture_output=True, text=True
        )
        if push.returncode == 0:
            print("✅ GitHub aktualizován")
        else:
            msg = f"git push selhal: {push.stderr.strip().splitlines()[-1] if push.stderr.strip() else 'neznámá chyba'}"
            print(f"⚠️  {msg}", file=sys.stderr)
            problems.append(msg)

    if problems:
        print("\n❌ Update dokončen s problémy:", file=sys.stderr)
        for p in problems:
            print(f"   • {p}", file=sys.stderr)
        sys.exit(1)

    print("\n🎉 Vše v pořádku.")


if __name__ == "__main__":
    main()
