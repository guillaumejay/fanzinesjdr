"""Restructure les fiches héritées de MediaWiki.

Chaque tableau « infobox » (grille à 3 ou 5 colonnes) devient :
- les images utiles (logo, couverture) ;
- une liste « - **Champ :** valeur » ;
- un sommaire en tableau « Titre | Auteur | Page | Type ».

Les titres de section passent de ### à ## et les badges d'état
(/images/partagees/) sont supprimés.

Usage : python scripts/restructure_fiches.py <fiche.md> [...]
Les auteurs extraits de façon douteuse sont listés sur la sortie standard.
"""
import re
import sys
from pathlib import Path

BADGE = re.compile(r"!\[[^\]]*\]\(/images/partagees/[^)]*\)")
IMAGE = re.compile(r"!\[[^\]]*\]\(([^)]*)\)")
LABEL = re.compile(r"^\*\*(.+?)\s*:\*\*\s*(.*)$")
TRAILING_PARENS = re.compile(r"^(.*[^\]\s])\s*\(([^()]*)\)$")
NOT_AUTHOR = re.compile(r"^([IVXLC]+|\d+|.*partie.*|bis|suite|fin)$", re.I)
TOC_HEADER = {"titre de l’article", "titre de l'article"}


def cells(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def split_author(title):
    m = TRAILING_PARENS.match(title)
    if not m or NOT_AUTHOR.match(m.group(2).strip()):
        return title, "", False
    author = m.group(2).strip()
    if re.search(r"https?:|www\.|/", author):
        return title, "", False
    if not re.match(r"[A-ZÀ-Ý]", author) or len(author.split()) > 8:
        return title, "", True
    return m.group(1).strip(), author, False


COLUMNS = {"jeu": "jeu", "auteur": "auteur", "auteurs": "auteur", "page": "page",
           "type d’article": "type", "type d'article": "type", "type": "type"}


def toc_columns(header):
    cols = {"titre": 0}
    for i, name in enumerate(header[1:], 1):
        key = COLUMNS.get(name.lower())
        if key:
            cols[key] = i
    return cols


def convert_table(rows, issue, fanzine, doubts):
    images, fields, toc, in_toc = [], [], [], False
    cols = {"titre": 0, "page": 1, "type": 2}
    for row in rows:
        row = [re.sub(r"\s{2,}", " ", c) for c in row]
        if all(re.fullmatch(r":?-{3,}:?", c) for c in row if c):
            continue
        if row[0].lower() in TOC_HEADER:
            in_toc, cols = True, toc_columns(row)
            continue
        if in_toc:
            get = lambda k: row[cols[k]] if k in cols and cols[k] < len(row) else ""
            title, page, kind, game = get("titre"), get("page"), get("type"), get("jeu")
            page = re.sub(r"^Pages?\s*", "", page, flags=re.I)
            if {title, page, kind, game} <= {"?", ""}:
                continue
            if not any(c for c in row[1:]):
                toc.append((title if "**" in title else f"**{title}**", "", "", "", ""))
                continue
            author = get("auteur")
            if "auteur" not in cols:
                title, author, doubtful = split_author(title)
                if doubtful:
                    doubts.append(f"{fanzine} · {issue} · {title}")
            toc.append((title, game, author, page, kind))
            continue
        for cell in row:
            if not cell:
                continue
            if cell == "Sommaire":
                in_toc = True
                break
            if cell.startswith("Titre :") or (not LABEL.match(cell) and IMAGE.search(cell)
                                               and re.search(r"détails? du", cell)):
                images += [img for img in IMAGE.findall(cell) if "/partagees/" not in img]
                continue
            m = LABEL.match(cell)
            if not m:
                fields.append(("", cell))
                continue
            label, value = m.groups()
            value = re.sub(r"(<br>\s*)?-{4,}(\s*<br>)?", "<br>", value)
            if label == "Couverture" and IMAGE.search(value):
                src = IMAGE.search(value).group(1)
                if "/partagees/" in src:
                    fields.append((label, "manquante"))
                else:
                    images.append(src)
            else:
                fields.append((label, value))
    out = []
    for src in images:
        if "logo" in src:
            alt = f"Logo de {fanzine}"
        elif issue.lower().startswith("numéro"):
            alt = f"Couverture du {issue.lower()} de {fanzine}"
        else:
            alt = f"Couverture de {fanzine}"
        out.append(f"![{alt}]({src})")
    if images:
        out.append("")
    out += [f"- **{l} :** {v}" if l else f"- {v}" for l, v in fields]
    if in_toc:
        out += ["", "**Sommaire**", ""]
        if toc and any(r[1] for r in toc):
            out += ["| Titre | Jeu | Auteur | Page | Type |", "| --- | --- | --- | --- | --- |"]
            out += [f"| {' | '.join(r)} |" for r in toc]
        elif toc:
            out += ["| Titre | Auteur | Page | Type |", "| --- | --- | --- | --- |"]
            out += [f"| {t} | {a} | {p} | {k} |" for t, _, a, p, k in toc]
        else:
            out.append("Sommaire à compléter.")
    return out


def restructure(path, doubts):
    text = Path(path).read_text(encoding="utf-8")
    if re.search(r"^\| Titre \|", text, re.M):
        return  # déjà restructurée
    head, body = text.split("\n---\n", 1) if text.startswith("---") else ("", text)
    fanzine = re.search(r'^title:\s*"?(.*?)"?\s*$', head, re.M).group(1)
    out, table, issue = [], [], "numéro"

    def flush():
        if table:
            out.extend(convert_table(table, issue, fanzine, doubts))
            table.clear()

    for line in body.splitlines():
        if line.lstrip().startswith("|"):
            table.append(cells(line))
            continue
        flush()
        if BADGE.fullmatch(line.strip()):
            continue
        line = BADGE.sub("", line)
        if line.startswith("### "):
            line = "## " + line[4:].strip()
            issue = line[3:]
            if out and out[-1] != "":
                out.append("")
        out.append(line)
    flush()
    body = re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip() + "\n"
    Path(path).write_text(f"{head}\n---\n{body}", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    doubts = []
    for p in sys.argv[1:]:
        restructure(p, doubts)
    print("\n".join(doubts) if doubts else "Aucun auteur douteux.")
