#!/usr/bin/env python3
"""Découpe une fiche de fanzine en une page par numéro.

La fiche `fanzines/<slug>.md` conserve les généralités, les notes et une
galerie des numéros ; chaque section `### Numéro …` devient
`fanzines/<slug>/<id>.md`. Les pages de numéros sont masquées de la barre
latérale et reliées entre elles par les liens précédent / suivant.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

SECTION_RE = re.compile(r"^### (.+)$", re.M)
ISSUE_RE = re.compile(r"^Numéro\s+(?:(Hors Série|Spécial)\s+)?(\d+)$", re.I)
COVER_RE = re.compile(r"\*\*Couverture :\*\* !\[[^\]]*\]\(([^)]+)\)")
DATE_RE = re.compile(r"\*\*Date de parution :\*\*\s*([^|]*)\|")


def issue_id(kind: str | None, number: str) -> tuple[str, str]:
    """Retourne l'identifiant d'URL et le libellé court d'un numéro."""
    if not kind:
        return number, f"n°{number}"
    if kind.lower().startswith("hors"):
        return f"hs-{number}", f"hors-série n°{number}"
    return f"special-{number}", f"spécial n°{number}"


def yaml_str(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def split(page: Path) -> None:
    text = page.read_text(encoding="utf-8")
    front_end = text.index("\n---", 3) + 4
    front, body = text[:front_end], text[front_end:]
    title = re.search(r'^title: "(.*)"$', front, re.M).group(1)
    slug = page.stem

    matches = list(SECTION_RE.finditer(body))
    issues, kept = [], []
    cursor = 0
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        heading = ISSUE_RE.match(m.group(1).strip())
        if heading:
            kept.append(body[cursor:m.start()])
            ident, label = issue_id(heading.group(1), heading.group(2))
            content = body[m.end():end].strip("\n")
            cover = COVER_RE.search(content)
            date = DATE_RE.search(content)
            issues.append({
                "id": ident,
                "label": label,
                "content": content.replace("#### ", "## "),
                "cover": cover.group(1) if cover else None,
                "date": date.group(1).strip() if date else "?",
            })
            cursor = end
    kept.append(body[cursor:])
    overview = "".join(kept).rstrip("\n")

    out_dir = page.with_suffix("")
    out_dir.mkdir(exist_ok=True)
    for i, issue in enumerate(issues):
        nav = []
        for key, j in (("prev", i - 1), ("next", i + 1)):
            if 0 <= j < len(issues):
                other = issues[j]
                nav.append(f"{key}:\n  link: /fanzines/{slug}/{other['id']}/\n  label: {yaml_str(title + ' ' + other['label'])}")
            else:
                nav.append(f"{key}: false")
        full = f"{title} {issue['label']}"
        (out_dir / f"{issue['id']}.md").write_text(
            "---\n"
            f"title: {yaml_str(full)}\n"
            f"description: {yaml_str('Fiche de ' + full + '.')}\n"
            "sidebar:\n  hidden: true\n"
            + "\n".join(nav) + "\n---\n\n"
            f"[← Tous les numéros de {title}](/fanzines/{slug}/)\n\n"
            + issue["content"] + "\n",
            encoding="utf-8",
        )

    cards = []
    for issue in issues:
        img = (f'<img src="{issue["cover"]}" alt="Couverture du {issue["label"]} de {title}" loading="lazy">'
               if issue["cover"] else '<span class="issue-nocover">?</span>')
        date = "" if issue["date"] in ("?", "") else f'<small>{issue["date"]}</small>'
        cards.append(f'<a class="issue-card" href="/fanzines/{slug}/{issue["id"]}/">{img}<span>{issue["label"]}</span>{date}</a>')
    gallery = "\n### Numéros\n\n<div class=\"issue-grid\">\n" + "\n".join(cards) + "\n</div>\n"

    if "\n### Notes" in overview:
        head, notes = overview.split("\n### Notes", 1)
        overview = head.rstrip("\n") + "\n" + gallery + "\n### Notes" + notes
    else:
        overview += "\n" + gallery
    page.write_text(front + overview.rstrip("\n") + "\n", encoding="utf-8")
    print(f"{page.name}: {len(issues)} numéros -> {out_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pages", nargs="+", type=Path)
    for page in parser.parse_args().pages:
        split(page)


if __name__ == "__main__":
    main()
