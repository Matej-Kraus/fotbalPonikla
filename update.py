#!/usr/bin/env python3
"""
Aktualizuje nadchazejici_zapasy.html a tabulka.html pro TJ Poniklá.
Nadcházející zápasy se stahují ze sportmap.cz (vždy aktuální sezóna),
tabulka z fotbalapi.denik.cz.

POZOR: COMPETITION_ID se každou sezónu mění (denik.cz vytvoří novou soutěž
pro 9. ligu Semily). Když se na podzim/v srpnu tabulka přestane plnit,
je potřeba najít nové ID a upravit konstantu níže.
"""

import json
import os
import re
import subprocess
import sys
import requests
from datetime import datetime
from pathlib import Path

COMPETITION_ID = 24148  # 9. liga Semily 2026/2027
API_BASE = "https://fotbalapi.denik.cz/api/front/1/"
SPORTMAP_URL = "https://www.sportmap.cz/club/fotbal/tj-ponikla"
HERE = Path(__file__).parent

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json",
}

FTP_HOST = os.environ.get("FTP_HOST", "tjponikla.cz")
FTP_USER = os.environ.get("FTP_USER", "admin.tjponikla.cz")
FTP_PASS = os.environ.get("FTP_PASS")


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

def fetch_standings() -> list[dict]:
    r = requests.get(
        f"{API_BASE}standing?competitionId={COMPETITION_ID}",
        headers=HEADERS,
        timeout=10,
    )
    r.raise_for_status()
    data = r.json()
    return data.get("rounds", []) if isinstance(data, dict) else []


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
    body = "\n".join(rows) if rows else '    <tr><td colspan="5">Žádné naplánované zápasy</td></tr>'
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
    body = "\n".join(rows) if rows else '    <tr><td colspan="8">Sezóna ještě nezačala, tabulka bude brzy k dispozici.</td></tr>'
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


# ── Hlavní funkce ─────────────────────────────────────────────────────────────

def main():
    print("📅 Stahuju nadcházející zápasy ze sportmap.cz...")
    upcoming = fetch_upcoming()
    print(f"   {len(upcoming)} nadcházejících zápasů")

    print("📊 Stahuju tabulku z API...")
    standings = fetch_standings()
    print(f"   {len(standings)} týmů")

    (HERE / "nadchazejici_zapasy.html").write_text(
        build_upcoming_html(upcoming), encoding="utf-8"
    )
    (HERE / "tabulka.html").write_text(
        build_table_html(standings), encoding="utf-8"
    )

    print(f"✅ nadchazejici_zapasy.html aktualizován")
    print(f"✅ tabulka.html aktualizován")

    # Upload na FTP server
    if not FTP_PASS:
        print("⚠️  FTP_PASS není nastavené, přeskakuji FTP upload.", file=sys.stderr)
    else:
        print("📤 Nahrávám na FTP server...")
        try:
            import ftplib

            with ftplib.FTP() as ftp:
                ftp.connect(FTP_HOST, 21)
                ftp.login(FTP_USER, FTP_PASS)
                ftp.set_pasv(True)
                uploads = [
                    ("nadchazejici_zapasy.html", "nadhazenici.html"),
                    ("tabulka.html", "tabulka.html"),
                ]
                for local_name, remote_name in uploads:
                    for prefix in ("", "public_html/"):
                        with open(HERE / local_name, "rb") as f:
                            ftp.storbinary(f"STOR {prefix}{remote_name}", f)
            print("✅ FTP upload hotov")
        except Exception as e:
            print(f"⚠️  FTP chyba: {type(e).__name__}: {e!r}", file=sys.stderr)

    # Push na GitHub
    print("🚀 Pushuji na GitHub...")
    date_str = datetime.now().strftime("%d.%m.%Y")
    subprocess.run(["git", "-C", str(HERE), "add", "nadchazejici_zapasy.html", "tabulka.html"], check=True)
    result = subprocess.run(
        ["git", "-C", str(HERE), "commit", "-m", f"Auto-update: {date_str}"],
        capture_output=True, text=True
    )
    if "nothing to commit" in result.stdout + result.stderr:
        print("   Žádné změny k pushnutí.")
    else:
        subprocess.run(["git", "-C", str(HERE), "push"], check=True)
        print("✅ GitHub aktualizován")


if __name__ == "__main__":
    main()
