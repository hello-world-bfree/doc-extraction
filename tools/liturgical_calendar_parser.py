#!/usr/bin/env python3
"""Parse USCCB Liturgical Calendar PDF into structured database records."""

import argparse
import json
import re
import sqlite3
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

import pdfplumber


COLORS = {
    "white", "red", "violet", "green", "rose", "gold", "black",
}

RANKS = {"Solemnity", "Feast", "Memorial"}

DAYS_OF_WEEK = {"Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"}
DAYS_UPPER = {"SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"}

MONTH_NAMES = {
    "JANUARY": 1, "FEBRUARY": 2, "MARCH": 3, "APRIL": 4,
    "MAY": 5, "JUNE": 6, "JULY": 7, "AUGUST": 8,
    "SEPTEMBER": 9, "OCTOBER": 10, "NOVEMBER": 11, "DECEMBER": 12,
}

DAY_LINE_RE = re.compile(
    r"^(\d{1,2})\s+(Sun|Mon|Tue|Wed|Thu|Fri|Sat|SUN|MON|TUE|WED|THU|FRI|SAT)\s+(.+)$"
)

COLOR_RE = re.compile(
    r"\s+((?:violet|white|red|green|rose|gold|black)(?:\s*(?:or|/)\s*(?:violet|white|red|green|rose|gold|black))*)$",
    re.IGNORECASE,
)

MONTH_HEADER_RE = re.compile(
    r"^(JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)\s+(\d{4})$"
)

COMBINED_MONTH_RE = re.compile(
    r"^(NOVEMBER|DECEMBER)\s*[–—-]\s*(JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)\s+(\d{4})$"
)

READING_RE = re.compile(
    r"^(?:(?:Vigil|Night|Dawn|Day|Morning|Evening):\s*)?[A-Z0-9]"
)

BOOK_ABBREVS = {
    "Gn", "Ex", "Lv", "Nm", "Dt", "Jos", "Jgs", "Ru", "1 Sm", "2 Sm",
    "1 Kgs", "2 Kgs", "1 Chr", "2 Chr", "Ezr", "Neh", "Tb", "Jdt", "Est",
    "1 Mc", "2 Mc", "Jb", "Ps", "Pss", "Prv", "Eccl", "Sg", "Wis", "Sir",
    "Is", "Jer", "Lam", "Bar", "Ez", "Dn", "Hos", "Jl", "Am", "Ob", "Jon",
    "Mi", "Na", "Hb", "Zep", "Hg", "Zec", "Mal",
    "Mt", "Mk", "Lk", "Jn", "Acts", "Rom", "1 Cor", "2 Cor", "Gal", "Eph",
    "Phil", "Col", "1 Thes", "2 Thes", "1 Tm", "2 Tm", "Ti", "Phlm", "Heb",
    "Jas", "1 Pt", "2 Pt", "1 Jn", "2 Jn", "3 Jn", "Jude", "Rv",
}

LECTIONARY_NUM_RE = re.compile(r"\((\d+[A-Za-z]?)\)")
PSALTER_RE = re.compile(r"Pss?\s+(I{1,4}V?|Prop)", re.IGNORECASE)

FOOTNOTE_RE = re.compile(r"^\d+\s+(?:Citations|Optional|When|In this|The Scripture)")
PAGE_NUM_RE = re.compile(r"^\d{1,3}$")

NOISE_PREFIXES = [
    "YEAR A", "YEAR B", "YEAR C",
    "WEEKDAYS I", "WEEKDAYS II",
    "PROPER CALENDAR",
    "ABBREVIATIONS",
    "OLD TESTAMENT", "NEW TESTAMENT",
    "APPENDIX", "APÉNDICE",
]


@dataclass
class LiturgicalDay:
    date: str
    day_of_week: str
    celebration: str
    rank: str
    color: str
    optional_memorials: list[str] = field(default_factory=list)
    readings: list[str] = field(default_factory=list)
    lectionary_numbers: list[str] = field(default_factory=list)
    psalter_week: str = ""
    season: str = ""
    notes: str = ""
    month: int = 0
    day: int = 0
    year: int = 0


def is_noise_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return True
    if PAGE_NUM_RE.match(stripped):
        return True
    if FOOTNOTE_RE.match(stripped):
        return True
    for prefix in NOISE_PREFIXES:
        if stripped.upper().startswith(prefix):
            return True
    if stripped.startswith("designated by Pss"):
        return True
    if stripped.startswith("or, for the Optional Memorial of"):
        return True
    return False


def looks_like_reading(line: str) -> bool:
    stripped = line.strip()
    if stripped.startswith(("Vigil:", "Night:", "Dawn:", "Day:", "Morning:", "Evening:")):
        return True
    if stripped.startswith("or any readings"):
        return True
    if stripped.startswith("or, for"):
        return True
    for abbrev in sorted(BOOK_ABBREVS, key=len, reverse=True):
        if stripped.startswith(abbrev + " "):
            return True
        if stripped.startswith(abbrev + ":"):
            return True
    if re.match(r"^\d\s+(Sm|Kgs|Chr|Mc|Cor|Thes|Tm|Jn|Pt)\s", stripped):
        return True
    return False


def extract_calendar_lines(pdf_path: str) -> list[str]:
    lines = []
    with pdfplumber.open(pdf_path) as pdf:
        in_calendar = False
        for page in pdf.pages:
            text = page.extract_text() or ""
            for line in text.split("\n"):
                stripped = line.strip()
                if not in_calendar:
                    if COMBINED_MONTH_RE.match(stripped) or MONTH_HEADER_RE.match(stripped):
                        in_calendar = True
                    elif DAY_LINE_RE.match(stripped) and not in_calendar:
                        if any(stripped.upper().startswith(f"{d} ") for d in range(1, 32)):
                            pass
                if in_calendar:
                    if stripped.startswith("APPENDIX") or stripped.startswith("APÉNDICE"):
                        break
                    lines.append(stripped)
            else:
                continue
            break
    return lines


def detect_season(celebration: str, month: int, day: int) -> str:
    c = celebration.upper()
    if "ADVENT" in c:
        return "Advent"
    if "CHRISTMAS" in c or "NATIVITY" in c or "OCTAVE OF THE NATIVITY" in c:
        return "Christmas"
    if "EPIPHANY" in c:
        return "Christmas"
    if "BAPTISM OF THE LORD" in c:
        return "Christmas"
    if "ASH WEDNESDAY" in c:
        return "Lent"
    if "LENT" in c:
        return "Lent"
    if "PALM SUNDAY" in c:
        return "Lent"
    if "HOLY THURSDAY" in c or "GOOD FRIDAY" in c or "HOLY SATURDAY" in c:
        return "Triduum"
    if "EASTER" in c or "PASCHAL" in c:
        return "Easter"
    if "PENTECOST" in c:
        return "Easter"
    if "ORDINARY TIME" in c or c == "WEEKDAY":
        return "Ordinary Time"
    return ""


def parse_calendar(pdf_path: str) -> list[LiturgicalDay]:
    lines = extract_calendar_lines(pdf_path)
    entries: list[LiturgicalDay] = []

    current_month = 0
    current_year = 0
    current_entry: LiturgicalDay | None = None
    prev_day_num = 0

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        if is_noise_line(line) and not DAY_LINE_RE.match(line) and not MONTH_HEADER_RE.match(line) and not COMBINED_MONTH_RE.match(line):
            i += 1
            continue

        m_combined = COMBINED_MONTH_RE.match(line)
        if m_combined:
            month1_name = m_combined.group(1)
            current_month = MONTH_NAMES[month1_name]
            current_year = int(m_combined.group(3))
            prev_day_num = 0
            i += 1
            continue

        m_month = MONTH_HEADER_RE.match(line)
        if m_month:
            current_month = MONTH_NAMES[m_month.group(1)]
            current_year = int(m_month.group(2))
            prev_day_num = 0
            i += 1
            continue

        m_day = DAY_LINE_RE.match(line)
        if m_day:
            if current_entry:
                entries.append(current_entry)

            day_num = int(m_day.group(1))
            dow = m_day.group(2).capitalize()[:3]
            rest = m_day.group(3).strip()

            if day_num < prev_day_num:
                current_month += 1
                if current_month > 12:
                    current_month = 1
                    current_year += 1

            prev_day_num = day_num

            color = ""
            color_match = COLOR_RE.search(rest)
            if color_match:
                color = color_match.group(1).strip().lower()
                rest = rest[:color_match.start()].strip()

            celebration = rest
            rank = ""

            current_entry = LiturgicalDay(
                date=f"{current_year}-{current_month:02d}-{day_num:02d}",
                day_of_week=dow,
                celebration=celebration,
                rank=rank,
                color=color,
                month=current_month,
                day=day_num,
                year=current_year,
            )

            season = detect_season(celebration, current_month, day_num)
            if season:
                current_entry.season = season

            i += 1
            continue

        if current_entry:
            if line in RANKS or line.startswith("Solemnity") or line.startswith("Feast") or line.startswith("Memorial"):
                rank_text = line.split("[")[0].strip()
                if current_entry.rank:
                    current_entry.rank += "; " + rank_text
                else:
                    current_entry.rank = rank_text
                if "[" in line:
                    bracket_text = line[line.index("["):]
                    current_entry.notes = (current_entry.notes + " " + bracket_text).strip()
                i += 1
                continue

            if line.startswith("[") and line.endswith("]"):
                memorial_name = line[1:-1].strip()
                memorial_name = re.sub(r"\d+$", "", memorial_name).strip()
                current_entry.optional_memorials.append(memorial_name)
                i += 1
                continue

            if line.startswith("[") and not line.endswith("]"):
                bracket_content = line
                j = i + 1
                while j < len(lines) and "]" not in bracket_content:
                    bracket_content += " " + lines[j].strip()
                    j += 1
                if bracket_content.startswith("[") and "]" in bracket_content:
                    end = bracket_content.index("]")
                    memorial_name = bracket_content[1:end].strip()
                    memorial_name = re.sub(r"\d+$", "", memorial_name).strip()
                    current_entry.optional_memorials.append(memorial_name)
                i = j
                continue

            if line.startswith("(") and not looks_like_reading(line):
                current_entry.notes = (current_entry.notes + " " + line).strip()
                i += 1
                continue

            if looks_like_reading(line):
                reading_block = line
                j = i + 1
                while j < len(lines):
                    next_line = lines[j].strip()
                    if DAY_LINE_RE.match(next_line):
                        break
                    if MONTH_HEADER_RE.match(next_line) or COMBINED_MONTH_RE.match(next_line):
                        break
                    if next_line in RANKS or next_line.startswith("Solemnity") or next_line.startswith("Memorial") or next_line.startswith("Feast"):
                        break
                    if next_line.startswith("["):
                        break
                    if is_noise_line(next_line):
                        break
                    if looks_like_reading(next_line):
                        break
                    reading_block += " " + next_line
                    j += 1

                reading_text = reading_block.strip()
                color_at_end = COLOR_RE.search(reading_text)
                if color_at_end and not current_entry.color:
                    current_entry.color = color_at_end.group(1).strip().lower()
                    reading_text = reading_text[:color_at_end.start()].strip()

                current_entry.readings.append(reading_text)

                for lect_match in LECTIONARY_NUM_RE.finditer(reading_text):
                    current_entry.lectionary_numbers.append(lect_match.group(1))

                pss_match = PSALTER_RE.search(reading_text)
                if pss_match and not current_entry.psalter_week:
                    current_entry.psalter_week = "Pss " + pss_match.group(1)

                i = j
                continue

            if line.upper() == line and len(line) > 3 and not DAY_LINE_RE.match(line):
                current_entry.celebration += " " + line
                i += 1
                continue

            current_entry.notes = (current_entry.notes + " " + line).strip()

        i += 1

    if current_entry:
        entries.append(current_entry)

    for entry in entries:
        c_upper = entry.celebration.upper()

        entry.celebration = re.sub(r"(?<=[a-zA-Z)\]])\d{1,2}$", "", entry.celebration).strip()

        if not entry.rank:
            if "OCTAVE" in c_upper:
                pass
            elif "SUNDAY" in c_upper:
                entry.rank = "Sunday"
            elif any(w in c_upper for w in ["SOLEMNITY", "NATIVITY", "EPIPHANY", "ASCENSION", "PENTECOST", "TRINITY", "MOST HOLY BODY", "SACRED HEART"]):
                entry.rank = "Solemnity"

        if "ASH WEDNESDAY" in c_upper:
            entry.season = "Lent"
        if "HOLY THURSDAY" in c_upper or "THURSDAY OF THE LORD" in c_upper:
            entry.season = "Triduum"
        if "GOOD FRIDAY" in c_upper or "FRIDAY OF THE PASSION" in c_upper:
            entry.season = "Triduum"
        if "HOLY SATURDAY" in c_upper or "EASTER VIGIL" in c_upper:
            entry.season = "Triduum"

        if not entry.season:
            entry.season = detect_season(entry.celebration, entry.month, entry.day)
            if not entry.season:
                entry.season = infer_season_from_context(entry, entries)

    return entries


def infer_season_from_context(entry: LiturgicalDay, all_entries: list[LiturgicalDay]) -> str:
    idx = all_entries.index(entry)
    for j in range(idx - 1, max(idx - 7, -1), -1):
        if all_entries[j].season:
            return all_entries[j].season
    return "Ordinary Time"


BIBLE_BOOKS = [
    ("Amos", "Am", "OT"), ("Baruch", "Bar", "OT"),
    ("1 Chronicles", "1 Chr", "OT"), ("2 Chronicles", "2 Chr", "OT"),
    ("Daniel", "Dn", "OT"), ("Deuteronomy", "Dt", "OT"),
    ("Ecclesiastes", "Eccl", "OT"), ("Esther", "Est", "OT"),
    ("Exodus", "Ex", "OT"), ("Ezekiel", "Ez", "OT"),
    ("Ezra", "Ezr", "OT"), ("Genesis", "Gn", "OT"),
    ("Habakkuk", "Hb", "OT"), ("Haggai", "Hg", "OT"),
    ("Hosea", "Hos", "OT"), ("Isaiah", "Is", "OT"),
    ("Jeremiah", "Jer", "OT"), ("Job", "Jb", "OT"),
    ("Joel", "Jl", "OT"), ("Jonah", "Jon", "OT"),
    ("Joshua", "Jos", "OT"), ("Judges", "Jgs", "OT"),
    ("Judith", "Jdt", "OT"), ("1 Kings", "1 Kgs", "OT"),
    ("2 Kings", "2 Kgs", "OT"), ("Lamentations", "Lam", "OT"),
    ("Leviticus", "Lv", "OT"), ("1 Maccabees", "1 Mc", "OT"),
    ("2 Maccabees", "2 Mc", "OT"), ("Malachi", "Mal", "OT"),
    ("Micah", "Mi", "OT"), ("Nahum", "Na", "OT"),
    ("Nehemiah", "Neh", "OT"), ("Numbers", "Nm", "OT"),
    ("Obadiah", "Ob", "OT"), ("Proverbs", "Prv", "OT"),
    ("Psalm(s)", "Ps(s)", "OT"), ("Ruth", "Ru", "OT"),
    ("1 Samuel", "1 Sm", "OT"), ("2 Samuel", "2 Sm", "OT"),
    ("Sirach", "Sir", "OT"), ("Song of Songs", "Sg", "OT"),
    ("Tobit", "Tb", "OT"), ("Wisdom", "Wis", "OT"),
    ("Zechariah", "Zec", "OT"), ("Zephaniah", "Zep", "OT"),
    ("Acts of the Apostles", "Acts", "NT"), ("Colossians", "Col", "NT"),
    ("1 Corinthians", "1 Cor", "NT"), ("2 Corinthians", "2 Cor", "NT"),
    ("Ephesians", "Eph", "NT"), ("Galatians", "Gal", "NT"),
    ("Hebrews", "Heb", "NT"), ("James", "Jas", "NT"),
    ("John (Gospel)", "Jn", "NT"), ("1 John", "1 Jn", "NT"),
    ("2 John", "2 Jn", "NT"), ("3 John", "3 Jn", "NT"),
    ("Jude", "Jude", "NT"), ("Luke", "Lk", "NT"),
    ("Mark", "Mk", "NT"), ("Matthew", "Mt", "NT"),
    ("1 Peter", "1 Pt", "NT"), ("2 Peter", "2 Pt", "NT"),
    ("Philemon", "Phlm", "NT"), ("Philippians", "Phil", "NT"),
    ("Revelation", "Rv", "NT"), ("Romans", "Rom", "NT"),
    ("1 Thessalonians", "1 Thes", "NT"), ("2 Thessalonians", "2 Thes", "NT"),
    ("1 Timothy", "1 Tm", "NT"), ("2 Timothy", "2 Tm", "NT"),
    ("Titus", "Ti", "NT"),
]


def parse_bible_abbreviations(_pdf_path: str) -> list[tuple[str, str, str]]:
    return [(name, abbrev, testament) for name, abbrev, testament in BIBLE_BOOKS]


def detect_liturgical_year(pdf_path: str) -> str:
    with pdfplumber.open(pdf_path) as pdf:
        text = pdf.pages[6].extract_text() or ""
    m = re.search(r"LITURGICAL YEAR (\d{4})", text)
    if m:
        return m.group(1)
    return ""


def parse_principal_celebrations(pdf_path: str) -> list[tuple[str, str]]:
    rows = []
    with pdfplumber.open(pdf_path) as pdf:
        tables = pdf.pages[6].extract_tables()
        if tables:
            for row in tables[0]:
                if row[0] and row[1]:
                    rows.append((row[0].strip(), row[1].strip()))
    return rows


def parse_lectionary_cycles(pdf_path: str) -> list[tuple[str, str, str]]:
    rows = []
    with pdfplumber.open(pdf_path) as pdf:
        tables = pdf.pages[6].extract_tables()
        if len(tables) > 1:
            for row in tables[1]:
                if row[0] and row[1]:
                    cycle_type = row[0].strip()
                    cycle_name = row[1].strip()
                    date_range = (row[2] or "").strip().replace("\n", "; ")
                    rows.append((cycle_type, cycle_name, date_range))
    return rows


def parse_liturgy_of_hours(pdf_path: str) -> list[tuple[str, str, str]]:
    rows = []
    with pdfplumber.open(pdf_path) as pdf:
        tables = pdf.pages[7].extract_tables()
        if tables:
            for row in tables[0]:
                if row[0] and row[2]:
                    date_range = row[0].strip()
                    season = (row[1] or "").strip().replace("\n", " ")
                    volume = row[2].strip()
                    rows.append((date_range, season, volume))
    return rows


PROPER_CALENDAR_RE = re.compile(
    r"^(January|February|March|April|May|June|July|August|September|October|November|December|Fourth Thursday)\b"
)

PROPER_RANK_SUFFIXES = {"Memorial", "Feast", "Solemnity"}


def parse_proper_calendar(pdf_path: str) -> list[tuple[str, str, str]]:
    rows = []
    with pdfplumber.open(pdf_path) as pdf:
        text = pdf.pages[10].extract_text() or ""

    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not PROPER_CALENDAR_RE.match(line):
            i += 1
            continue

        parts = line.split(maxsplit=2) if not line.startswith("Fourth") else line.split(maxsplit=3)

        if line.startswith("Fourth Thursday"):
            date_str = "Fourth Thursday in November"
            rest = ""
            j = i + 1
            while j < len(lines):
                next_l = lines[j].strip()
                if next_l == "in November":
                    j += 1
                    continue
                if PROPER_CALENDAR_RE.match(next_l) or next_l.startswith("Sunday") or next_l.startswith("*") or next_l.isdigit():
                    break
                rest += " " + next_l
                j += 1
            celebration = rest.strip() if rest.strip() else "Thanksgiving Day"
            rank = ""
            for r in PROPER_RANK_SUFFIXES:
                if celebration.endswith(r):
                    rank = r
                    celebration = celebration[:-len(r)].strip()
                    break
            rows.append((date_str, celebration, rank or "Optional Memorial"))
            i = j
            continue

        if len(parts) >= 3:
            month = parts[0]
            day_num = parts[1]
            date_str = f"{month} {day_num}"
            rest = parts[2] if len(parts) > 2 else ""
        else:
            i += 1
            continue

        j = i + 1
        while j < len(lines):
            next_l = lines[j].strip()
            if PROPER_CALENDAR_RE.match(next_l) or next_l.startswith("Sunday") or next_l.startswith("*") or next_l.isdigit():
                break
            if next_l.startswith("(Patronal") or next_l.startswith("(Corpus"):
                rest += " " + next_l
                j += 1
                continue
            rest += " " + next_l
            j += 1

        celebration = rest.strip()
        rank = "Optional Memorial"
        for r in sorted(PROPER_RANK_SUFFIXES, key=len, reverse=True):
            if celebration.endswith(r):
                rank = r
                celebration = celebration[:-len(r)].strip()
                break
            idx = celebration.find(f" {r} ")
            if idx > 0:
                rank = r
                celebration = (celebration[:idx] + celebration[idx+len(r)+1:]).strip()
                break

        celebration = celebration.rstrip("*").strip()
        celebration = re.sub(r"\s{2,}", " ", celebration)
        rows.append((date_str, celebration, rank))
        i = j

    with pdfplumber.open(pdf_path) as pdf:
        text2 = pdf.pages[10].extract_text() or ""
    for line in text2.split("\n"):
        stripped = line.strip()
        if stripped.startswith("Sunday between"):
            celebration_lines = []
            idx = text2.split("\n").index(line)
            for ll in text2.split("\n")[idx:idx+3]:
                celebration_lines.append(ll.strip())
            full = " ".join(celebration_lines)
            if "EPIPHANY" in full:
                rank = "Solemnity"
                rows.append(("Sunday between January 2 and January 8", "THE EPIPHANY OF THE LORD", rank))
        if stripped.startswith("Sunday after"):
            rows.append(("Sunday after the Most Holy Trinity", "THE MOST HOLY BODY AND BLOOD OF CHRIST (Corpus Christi)", "Solemnity"))

    return rows


def create_database(entries: list[LiturgicalDay], db_path: str, pdf_paths: list[str] | None = None, append: bool = False):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS liturgical_calendar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            day_of_week TEXT NOT NULL,
            celebration TEXT NOT NULL,
            rank TEXT,
            color TEXT,
            season TEXT,
            optional_memorials TEXT,
            readings TEXT,
            lectionary_numbers TEXT,
            psalter_week TEXT,
            notes TEXT
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_date ON liturgical_calendar(date)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_season ON liturgical_calendar(season)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_rank ON liturgical_calendar(rank)")
    if append:
        dates = {e.date for e in entries}
        for d in dates:
            c.execute("DELETE FROM liturgical_calendar WHERE date = ?", (d,))
    else:
        c.execute("DELETE FROM liturgical_calendar")

    for entry in entries:
        c.execute("""
            INSERT INTO liturgical_calendar
            (date, day_of_week, celebration, rank, color, season,
             optional_memorials, readings, lectionary_numbers, psalter_week, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            entry.date,
            entry.day_of_week,
            entry.celebration,
            entry.rank,
            entry.color,
            entry.season,
            json.dumps(entry.optional_memorials) if entry.optional_memorials else None,
            json.dumps(entry.readings) if entry.readings else None,
            json.dumps(entry.lectionary_numbers) if entry.lectionary_numbers else None,
            entry.psalter_week or None,
            entry.notes.strip() or None,
        ))

    if pdf_paths:
        if not append:
            c.execute("DROP TABLE IF EXISTS bible_abbreviations")
            c.execute("DROP TABLE IF EXISTS principal_celebrations")
            c.execute("DROP TABLE IF EXISTS lectionary_cycles")
            c.execute("DROP TABLE IF EXISTS liturgy_of_hours")
            c.execute("DROP TABLE IF EXISTS proper_calendar_usa")
            c.execute("""
                CREATE TABLE bible_abbreviations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    book_name TEXT NOT NULL,
                    abbreviation TEXT NOT NULL,
                    testament TEXT NOT NULL
                )
            """)
            c.execute("""
                CREATE TABLE principal_celebrations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    liturgical_year TEXT NOT NULL,
                    celebration TEXT NOT NULL,
                    date TEXT NOT NULL
                )
            """)
            c.execute("""
                CREATE TABLE lectionary_cycles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    liturgical_year TEXT NOT NULL,
                    cycle_type TEXT NOT NULL,
                    cycle_name TEXT NOT NULL,
                    date_range TEXT NOT NULL
                )
            """)
            c.execute("""
                CREATE TABLE liturgy_of_hours (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    liturgical_year TEXT NOT NULL,
                    date_range TEXT NOT NULL,
                    season TEXT NOT NULL,
                    volume TEXT NOT NULL
                )
            """)
            c.execute("""
                CREATE TABLE proper_calendar_usa (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date_designation TEXT NOT NULL,
                    celebration TEXT NOT NULL,
                    rank TEXT NOT NULL
                )
            """)

            abbrevs = parse_bible_abbreviations(pdf_paths[0])
            for book_name, abbrev, testament in abbrevs:
                c.execute("INSERT INTO bible_abbreviations (book_name, abbreviation, testament) VALUES (?, ?, ?)",
                           (book_name, abbrev, testament))
            print(f"  bible_abbreviations: {len(abbrevs)} rows")

            proper = parse_proper_calendar(pdf_paths[0])
            for date_designation, celebration, rank in proper:
                c.execute("INSERT INTO proper_calendar_usa (date_designation, celebration, rank) VALUES (?, ?, ?)",
                           (date_designation, celebration, rank))
            print(f"  proper_calendar_usa: {len(proper)} rows")

        if append:
            c.execute("""CREATE TABLE IF NOT EXISTS principal_celebrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT, liturgical_year TEXT NOT NULL,
                celebration TEXT NOT NULL, date TEXT NOT NULL)""")
            c.execute("""CREATE TABLE IF NOT EXISTS lectionary_cycles (
                id INTEGER PRIMARY KEY AUTOINCREMENT, liturgical_year TEXT NOT NULL,
                cycle_type TEXT NOT NULL, cycle_name TEXT NOT NULL, date_range TEXT NOT NULL)""")
            c.execute("""CREATE TABLE IF NOT EXISTS liturgy_of_hours (
                id INTEGER PRIMARY KEY AUTOINCREMENT, liturgical_year TEXT NOT NULL,
                date_range TEXT NOT NULL, season TEXT NOT NULL, volume TEXT NOT NULL)""")

        total_celebrations = 0
        total_cycles = 0
        total_hours = 0
        for pdf_path in pdf_paths:
            lit_year = detect_liturgical_year(pdf_path)
            if not lit_year:
                continue

            c.execute("DELETE FROM principal_celebrations WHERE liturgical_year = ?", (lit_year,))
            c.execute("DELETE FROM lectionary_cycles WHERE liturgical_year = ?", (lit_year,))
            c.execute("DELETE FROM liturgy_of_hours WHERE liturgical_year = ?", (lit_year,))

            celebrations = parse_principal_celebrations(pdf_path)
            for celebration, date_str in celebrations:
                c.execute("INSERT INTO principal_celebrations (liturgical_year, celebration, date) VALUES (?, ?, ?)",
                           (lit_year, celebration, date_str))
            total_celebrations += len(celebrations)

            cycles = parse_lectionary_cycles(pdf_path)
            for cycle_type, cycle_name, date_range in cycles:
                c.execute("INSERT INTO lectionary_cycles (liturgical_year, cycle_type, cycle_name, date_range) VALUES (?, ?, ?, ?)",
                           (lit_year, cycle_type, cycle_name, date_range))
            total_cycles += len(cycles)

            hours = parse_liturgy_of_hours(pdf_path)
            for date_range, season, volume in hours:
                c.execute("INSERT INTO liturgy_of_hours (liturgical_year, date_range, season, volume) VALUES (?, ?, ?, ?)",
                           (lit_year, date_range, season, volume))
            total_hours += len(hours)

        print(f"  principal_celebrations: {total_celebrations} rows")
        print(f"  lectionary_cycles: {total_cycles} rows")
        print(f"  liturgy_of_hours: {total_hours} rows")

    conn.commit()
    conn.close()


def main():
    parser = argparse.ArgumentParser(description="Parse USCCB Liturgical Calendar PDF")
    parser.add_argument("pdf_paths", nargs="+", help="Path(s) to liturgical calendar PDF(s)")
    parser.add_argument("--output-db", "-d", help="SQLite database output path")
    parser.add_argument("--output-json", "-j", help="JSON output path")
    parser.add_argument("--preview", "-p", type=int, default=0, help="Preview N entries")
    parser.add_argument("--append", "-a", action="store_true", help="Append to existing DB (only updates liturgical_calendar table)")
    args = parser.parse_args()

    all_entries: list[LiturgicalDay] = []
    for pdf_path in args.pdf_paths:
        entries = parse_calendar(pdf_path)
        print(f"Parsed {len(entries)} liturgical days from {Path(pdf_path).name}")
        all_entries.extend(entries)

    seen_dates: dict[str, int] = {}
    deduped: list[LiturgicalDay] = []
    for entry in all_entries:
        key = f"{entry.date}|{entry.celebration}"
        if key not in seen_dates:
            seen_dates[key] = 1
            deduped.append(entry)

    if len(all_entries) != len(deduped):
        print(f"Deduplicated: {len(all_entries)} -> {len(deduped)} entries (removed {len(all_entries) - len(deduped)} overlapping)")
    all_entries = deduped

    if args.preview:
        for entry in all_entries[:args.preview]:
            d = asdict(entry)
            del d["month"], d["day"], d["year"]
            print(json.dumps(d, indent=2))

    if args.output_json:
        output = [asdict(e) for e in all_entries]
        for d in output:
            del d["month"], d["day"], d["year"]
        Path(args.output_json).write_text(json.dumps(output, indent=2))
        print(f"Wrote {args.output_json}")

    if args.output_db:
        create_database(all_entries, args.output_db, pdf_paths=args.pdf_paths, append=args.append)
        print(f"{'Appended to' if args.append else 'Wrote'} {args.output_db}")

    if not args.output_json and not args.output_db and not args.preview:
        seasons: dict[str, int] = {}
        ranks: dict[str, int] = {}
        for e in all_entries:
            seasons[e.season] = seasons.get(e.season, 0) + 1
            if e.rank:
                ranks[e.rank] = ranks.get(e.rank, 0) + 1
        print(f"\nSeasons: {json.dumps(seasons, indent=2)}")
        print(f"Ranks: {json.dumps(ranks, indent=2)}")
        print(f"\nFirst: {all_entries[0].date} {all_entries[0].celebration}")
        print(f"Last:  {all_entries[-1].date} {all_entries[-1].celebration}")


if __name__ == "__main__":
    main()
