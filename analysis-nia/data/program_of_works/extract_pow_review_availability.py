#!/usr/bin/env python3
"""Inventory the [POW FOR REVIEW] drop and match packages to Senate workbook rows.

Follow-up to extract_pow_availability.py (PBC "ONGOING UPLOADING" drop). This
drop is larger (900+ PDFs) and nests deeper:

    REGION [FOR REVIEW] / (IMO or province)? / category? / project folders|files

Layouts covered
  * REGION -> IMO -> loose PDFs                     (REGION 6)
  * REGION -> IMO -> category -> project dirs/files (CAR, REGION 1, 2, 5, 11)
  * REGION -> category -> project dirs              (REGION 7, 9, 10, 12, 13)
  * REGION -> category -> loose PDFs + PICTURES dir (REGION 8)
  * REGION -> province -> category -> project dirs  (REGION 3, 11)
  * REGION -> category -> DIVISION -> loose PDFs    (UPRIIS)
  * REGION -> category -> loose PDFs                (MARIIS)

Matching keeps the earlier method: region-scoped fuzzy scoring of parsed
system name + trailing amount + category hint, now with a province hint from
IMO/province folders. Weak/unmatched packages are re-checked against POW PDF
text (native layer; tesseract OCR when installed). Scores are triage labels,
not certified identity.

Output (this directory): pow_review_availability.json
"""
from __future__ import annotations

import json
import os
import re
import unicodedata
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path

HERE = Path(__file__).resolve().parent
ANALYSIS = HERE.parent.parent
ROOT = ANALYSIS.parent
SENATE_PATH = ANALYSIS / 'data' / 'senate_nia_dataset.json'
OUT_PATH = HERE / 'pow_review_availability.json'

# Local drop shipped with the repo (PBC "FOR REVIEW" upload; canonical upstream
# is the PEOPLE'S BUDGET COALITION REQUIREMENTS Drive folder). Override with
# NIA_POW_ROOT when the mirror moves.
PBC_DRIVE_URL = (
    'https://drive.google.com/drive/u/0/folders/1orH0hcmtfTuYRz4qdOBXwcYhIKk1Yt-m'
)
POW_ROOT = Path(os.environ.get(
    'NIA_POW_ROOT',
    str(ROOT / 'NIA_DATA' / '[POW FOR REVIEW] PROGRAM OF WORKS AND PICTURES'),
))
SOURCE_SUBFOLDER = '[POW FOR REVIEW] PROGRAM OF WORKS AND PICTURES'

REGION_MAP = {
    'CAR': ['Cordillera Administrative Region', 'CAR'],
    'REGION 1': ['Region 1'],
    'REGION 2': ['Region 2'],
    'REGION 3': ['Region 3', 'REGION 3'],
    'REGION 4A': ['Region 4A', 'Region IV-A'],
    'REGION 4B': ['Region 4B', 'Region IV-B'],
    'REGION 5': ['Region 5'],
    'REGION 6': ['Region 6'],
    'REGION 7': ['Region 7'],
    'REGION 8': ['Region 8'],
    'REGION 9': ['Region 9'],
    'REGION 10': ['Region 10'],
    'REGION 11': ['Region 11'],
    'REGION 12': ['Region 12'],
    'REGION 13': ['Region 13'],
    'MARIIS': ['MARIIS'],
    'UPRIIS': ['UPRIIS'],
}

# folder name -> work-type / Senate category hint (longest-prefix wins when
# scanning a name; order matters only via length sort at use site)
WORK_HINTS = [
    ('SERVICEROADSCIS', 'Improvement of Service Roads in Communal Irrigation Systems'),
    ('SERVICEROADNIS', 'Improvement of Service Roads in National Irrigation Systems'),
    ('SERVICEROADSNIS', 'Improvement of Service Roads in National Irrigation Systems'),
    ('SERVICEROADSNIA', 'Improvement of Service Roads in National Irrigation Systems'),
    ('SERVICEROADCIS', 'Improvement of Service Roads in Communal Irrigation Systems'),
    ('SERVICE ROAD CIS', 'Improvement of Service Roads in Communal Irrigation Systems'),
    ('SERVICE ROAD NIS', 'Improvement of Service Roads in National Irrigation Systems'),
    ('SERVICE ROADS NIS', 'Improvement of Service Roads in National Irrigation Systems'),
    ('SERVICE ROADS-CIS', 'Improvement of Service Roads in Communal Irrigation Systems'),
    ('SERVICE ROADS CIS', 'Improvement of Service Roads in Communal Irrigation Systems'),
    ('SERVICE ROADS', 'Improvement of Service Roads'),
    ('SERVICE ROAD', 'Improvement of Service Roads'),
    ('SERVICEROAD', 'Improvement of Service Roads'),
    ('SRCIS', 'Improvement of Service Roads in Communal Irrigation Systems'),
    ('ISR NIS', 'Improvement of Service Roads in National Irrigation Systems'),
    ('ISRNIS', 'Improvement of Service Roads in National Irrigation Systems'),
    ('ISR', 'Improvement of Service Roads'),
    ('REPAIR CIS', 'Repair of Communal Irrigation Systems'),
    ('REPAIR-CIS', 'Repair of Communal Irrigation Systems'),
    ('REPAIRCIS', 'Repair of Communal Irrigation Systems'),
    ('REPAIR NIS', 'Repair of National Irrigation Systems'),
    ('REPAIR-NIS', 'Repair of National Irrigation Systems'),
    ('REPAIRNIS', 'Repair of National Irrigation Systems'),
    ('REPAIR OF NIS', 'Repair of National Irrigation Systems'),
    ('REPAIR PIS', 'Repair of Pump Irrigation Systems'),
    ('REPAIR-PIS', 'Repair of Pump Irrigation Systems'),
    ('REPAIRPIS', 'Repair of Pump Irrigation Systems'),
    ('RESTO NIS', 'Restoration of National Irrigation Systems'),
    ('RESTO-NIS', 'Restoration of National Irrigation Systems'),
    ('RESTONIS', 'Restoration of National Irrigation Systems'),
    ('RESTO CIS', 'Restoration of Communal Irrigation Systems'),
    ('RESTO-CIS', 'Restoration of Communal Irrigation Systems'),
    ('RESTOCIS', 'Restoration of Communal Irrigation Systems'),
    ('CLIMATE CHANGE NIS', 'Climate Change Adaptation Works (National Systems)'),
    ('CLIMATE CHANGE CIS', 'Climate Change Adaptation Works (Communal Systems)'),
    ('CLIMATE CHANGE', 'Climate Change Adaptation Works'),
    ('CCAW', 'Climate Change Adaptation Works'),
    ('EPIP-SOLAR', 'Establishment of Pump Irrigation Projects'),
    ('EGPIP SOLAR', 'Establishment of Pump Irrigation Projects'),
    ('EPIPSOLAR', 'Establishment of Pump Irrigation Projects'),
    ('EGPIP', 'Establishment of Pump Irrigation Projects'),
    ('EPIP', 'Establishment of Pump Irrigation Projects'),
    ('SPIP', 'Establishment of Pump Irrigation Projects'),
    ('EXTENSION NIS', 'Extension/Expansion of Existing National Irrigation Systems'),
    ('EXTENSIONNIS', 'Extension/Expansion of Existing National Irrigation Systems'),
    ('EXTENSION-NIS', 'Extension/Expansion of Existing National Irrigation Systems'),
    ('EXT NIS', 'Extension/Expansion of Existing National Irrigation Systems'),
    ('EXTNIS', 'Extension/Expansion of Existing National Irrigation Systems'),
    ('SIP', 'Small Irrigation Projects'),
    ('SRIP', 'Small Irrigation Projects'),
    ('MDIP', 'Malinao Dam Improvement Project, Bohol'),
]

# Generic words allowed in a category-only folder name (no system/amount).
CATEGORY_WORDS = {
    'resto', 'repair', 'service', 'roads', 'road', 'nis', 'cis', 'ris', 'pis',
    'epip', 'egpip', 'sip', 'srip', 'spip', 'spis', 'isr', 'srcis', 'line',
    'proj', 'project', 'climate', 'change', 'extension', 'expansion',
    'establishment', 'pump', 'ip', 'improvement', 'of', 'the', 'in', 'works',
    'solar', 'existing', 'national', 'communal', 'pis', 'ccaw', 'ext',
    'lineprojects', 'line',
}

# IMO / province folder acronyms that do not spell a province
IMO_ACRONYMS = {
    'lrimo': ['laguna', 'rizal'],
    'csimo': ['camarines', 'sur'],
    'omimo': ['occidental', 'mindoro'],
    'pmo': [],
    'cmo': [],
}

STOP = {
    'the', 'of', 'and', 'at', 'in', 'for', 'to', 'from', 'with', 'along', 'existing',
    'concrete', 'concreting', 'construction', 'improvement', 'rehabilitation', 'repair',
    'restoration', 'project', 'projects', 'irrigation', 'system', 'systems', 'canal',
    'service', 'road', 'roads', 'access', 'main', 'lateral', 'pump', 'solar', 'powered',
    'cy', 'pow', 'final', 'copy', 'pictures', 'picture', 'photos', 'nis', 'cis', 'ris',
    'pis', 'spip', 'spis', 'sip', 'egpip', 'epip', 'resto', 'isr', 'nia', 'sta', 'no',
    'p', 'm', 'pdf', 'pic', 'pertcpm', 'annex', 'b', 'photo', 'review', 'for', 'brgy',
    'barangay', 'imo', 'division', 'package', 'phase', 'site', 'area',
}

DOC_EXTS = {'.pdf', '.jpg', '.jpeg', '.png', '.webp', '.tif', '.tiff', '.jfif'}
IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.webp', '.tif', '.tiff', '.jfif'}

PICTURE_FILE = re.compile(
    r'(?i)(^|[-_ .])(picture|pictures|photos?|pic\d*|pix|geotagg?ed)([-_ .]|$)')
PICS_DIR = re.compile(
    r'(?i)^\s*(pictures?|photos?|geotagg?ed\s+photos?|photo\s+documentation|pix)\s*$')


def norm(s: str) -> str:
    s = unicodedata.normalize('NFKD', s or '')
    s = ''.join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    s = re.sub(r'[^a-z0-9]+', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()


def tokens(s: str) -> set[str]:
    return {t for t in norm(s).split() if t and t not in STOP and len(t) > 1}


def parse_amount(name: str):
    # trailing "…-10M", "(21.250M)", "- 2.45M", "5Mrev", "-30M-1-43"
    for pat in (
        r'[-_( ]P?(\d{1,3}(?:\.\d+)?)\s*M\b\.?\)?',
        r'^P?(\d{1,3}(?:\.\d+)?)\s*M\b',
    ):
        m = re.search(pat, name, flags=re.I)
        if m and not re.match(r'20\d\d', m.group(1)):
            return int(round(float(m.group(1)) * 1_000_000))
    return None


def work_hint(name: str):
    """Best (prefix, category) for a folder/file name, longest prefix first."""
    u = re.sub(r'[-_]', ' ', name).upper()
    u = re.sub(r'^\d+\.\s*', '', u)
    for prefix, cat in sorted(WORK_HINTS, key=lambda w: -len(w[0])):
        if prefix in u:
            return prefix, cat
    return None, None


NOISE = re.compile(
    r'(?i)\b(pow|program of works?|annex|plans?|general layout|pictures?|photos?|'
    r'photographs?|pic\d*|pix|geotagg?ed|signed|esigned|rev(ised)?|final|copy|closed|'
    r'approved|supporting documents?|procurementinstallation|as of \d+|open source|'
    r'yung|with|documentation|layout|esigned|toc|t o |to #|ae ?a)\b')
DIVISION_CODE = re.compile(r'(?i)\bD[IVX1-6]{1,4}\b')
REGION_PREFIX = re.compile(r'(?i)\b(r\d{1,2}|rio)_')


def extract_system(name: str) -> str:
    s = name
    s = re.sub(r'(?i)^\s*\d+\.\s*', ' ', s)
    s = REGION_PREFIX.sub(' ', s)
    s = re.sub(r'(?i)\bcy\s*202\d\b|\b202[0-9]\b|\b11232026\b', ' ', s)
    for prefix, _ in sorted(WORK_HINTS, key=lambda w: -len(w[0])):
        if prefix in s.upper():
            s = re.sub(re.escape(prefix), ' ', s, count=1, flags=re.I)
    s = NOISE.sub(' ', s)
    s = DIVISION_CODE.sub(' ', s)
    # strip trailing/inline amount tokens ("…-10M", "(21.250M)", "- 2.45M")
    s = re.sub(r'[-_(\s]*P?\d+(?:\.\d+)?\s*M\)?\.?(?=\s|$|[-_]|$)', ' ', s)
    s = re.sub(r'\(1\)$', ' ', s)
    s = re.sub(r'[-_]+', ' ', s)
    s = re.sub(r'#\d+', ' ', s)
    out = ' '.join(s.split()).strip(' -_.')
    return out


def package_key_from_stem(stem: str) -> str:
    key = re.sub(r'(?i)^(picture[-_ ]?|pic\d*[-_ ]?|photos?[-_ ]?)', '', stem)
    key = re.sub(r'(?i)[-_ ]?(pow|pictures?|photos?|pertcpm|pic\d*|annex\s*b)$', '', key)
    return key.strip(' -_')


# ---------------------------------------------------------------- discovery

def doc_files_in(path: Path) -> list[Path]:
    out = []
    for p in path.rglob('*'):
        if not p.is_file():
            continue
        if p.name.startswith('.') or p.name.startswith('~$'):
            continue
        out.append(p)
    return out


def classify_file(f: Path) -> str:
    """bucket: pdf | image | other  (picture-named PDFs remain pdf bucket here)"""
    ext = f.suffix.lower()
    if ext == '.pdf':
        return 'pdf'
    if ext in IMAGE_EXTS:
        return 'image'
    # docx/doc inside pictures folders are photo sheets; handled by caller
    return 'other'


def make_counts(files: list[Path]) -> dict:
    pdfs, images, other = [], [], []
    for f in files:
        ext = f.suffix.lower()
        if PICTURE_FILE.search(f.stem) or PICS_DIR.match(f.parent.name):
            if ext == '.pdf':
                pdfs.append(f)          # picture-sheet PDF
            else:
                images.append(f)        # jpg/docx photo sheets alike
            continue
        if ext == '.pdf':
            pdfs.append(f)
        elif ext in IMAGE_EXTS:
            images.append(f)
        else:
            other.append(f)
    picture_pdfs = [f for f in pdfs if PICTURE_FILE.search(f.stem)]
    pow_pdf_count = len(pdfs) - len(picture_pdfs)
    photo_count = len(images) + len(picture_pdfs)
    return {
        'pdf_count': len(pdfs),
        'image_count': len(images),
        'other_count': len(other),
        'doc_count': len(pdfs) + len(images),
        'pow_pdf_count': pow_pdf_count,
        'photo_count': photo_count,
        'pdfs': [str(f.relative_to(POW_ROOT)) for f in pdfs][:8],
        'images': [str(f.relative_to(POW_ROOT)) for f in images][:8],
    }


def parse_folder_region(name: str) -> str | None:
    base = re.sub(r'\[FOR REVIEW\]', '', name).strip()
    base = re.sub(r'\s+', ' ', base).upper()
    return base if base in REGION_MAP else None


def is_province_folder(name: str, province_vocab: set[str]) -> bool:
    n = re.sub(r'\[FOR REVIEW\]', '', name).strip()
    low = norm(re.sub(r'(?i)\bimo\b', '', n))
    if re.match(r'(?i)^division\b', n):
        return True
    if not low:
        return True  # bare "IMO" folder
    if low in IMO_ACRONYMS:
        return True
    if n.upper().rstrip().endswith('IMO') or re.search(r'(?i)\bIMO\b', n):
        return True
    toks = low.split()
    if not toks or any(re.search(r'\d', t) for t in toks):
        return False
    # every token is a province word from the Senate vocabulary
    return bool(toks) and all(t in province_vocab for t in toks)


def is_category_folder(name: str) -> bool:
    n = re.sub(r'\[FOR REVIEW\]', '', name).strip()
    # Allocation-group folders (e.g. "120M - SPIP", "454M - RESTO_REPAIR
    # NIS_CIS") group per-project children; the amount itself does not make
    # a folder a project. Judge what remains after amounts and work prefixes.
    s = n
    s = re.sub(r'(?i)[-_(\s]*P?\d+(?:\.\d+)?\s*[Mm]\)?\.?', ' ', s)
    toks = norm(s).split()
    if not toks:
        return True
    if all(t in CATEGORY_WORDS for t in toks):
        return True
    work, _ = work_hint(n)
    if work:
        rest = norm(re.sub(re.escape(work), ' ', n, flags=re.I)).split()
        rest = [t for t in rest
                if not re.fullmatch(r'\d+(\.\d+)?', t)
                and t not in {'m', 'p'}]
        if not rest or all(t in CATEGORY_WORDS for t in rest):
            return True
    return False


class Collector:
    def __init__(self, senate_projects: list[dict]):
        self.pkgs: list[dict] = []
        self.region_dirs: dict[str, Path] = {}
        province_vocab: set[str] = set()
        for p in senate_projects:
            for t in norm(p.get('province') or '').split():
                province_vocab.add(t)
        self.province_vocab = province_vocab

    def add(self, region: str, name: str, path: Path, kind: str,
            parent_ctx: dict, files: list[Path]):
        if not files:
            return
        counts = make_counts(files)
        if counts['doc_count'] == 0 and counts['other_count'] == 0:
            return
        work, cat = work_hint(name)
        if not work and parent_ctx.get('work'):
            work = parent_ctx['work']
        if not cat:
            cat = parent_ctx.get('cat')
        amount = parse_amount(name)
        if not amount:
            for f in files:
                if f.suffix.lower() == '.pdf' and not PICTURE_FILE.search(f.stem):
                    amount = parse_amount(f.stem) or amount
                    if amount:
                        break
        system = extract_system(name)
        if not system and kind == 'loose_pdf':
            system = extract_system(package_key_from_stem(Path(name).stem))
        # Prefer the region's actual directory name (e.g. "REGION 9 [FOR
        # REVIEW]") so id/path bases match on disk.
        actual_region_dir = self.region_dirs.get(region, POW_ROOT / region)
        try:
            rel = path.relative_to(actual_region_dir).as_posix()
        except ValueError:
            try:
                rel = path.relative_to(POW_ROOT).as_posix()
            except ValueError:
                rel = name
        prov = parent_ctx.get('province') or ''
        # Loose-file groups share their folder path; suffix the group key to
        # keep package ids unique (folder path alone collides).
        suffix = ''
        if kind == 'loose_pdf':
            suffix = ' :: ' + (norm(name) or 'files')
        self.pkgs.append({
            'id': f'{region}/{rel}{suffix}',
            'region_folder': region,
            'province_folder': prov or None,
            'kind': kind,
            'name': name,
            'path': str(path.relative_to(POW_ROOT)),
            'work_prefix': work,
            'category_hint': cat,
            'system_guess': system or None,
            'amount_php': amount,
            **counts,
        })

    def walk(self, region: str, region_dir: Path):
        self.region_dirs[region] = region_dir
        for entry in sorted(region_dir.iterdir()):
            if not entry.is_dir():
                continue
            self._walk_dir(region, entry, {'work': None, 'cat': None, 'province': ''})

    def _walk_dir(self, region: str, d: Path, ctx: dict):
        name = d.name.strip()
        entries = sorted(d.iterdir())
        files = [e for e in entries if e.is_file()
                 and not e.name.startswith('.') and not e.name.startswith('~$')]
        subdirs = [e for e in entries if e.is_dir()]
        pics = [s for s in subdirs if PICS_DIR.match(s.name)]
        nav = [s for s in subdirs if s not in pics]
        nav = [s for s in nav if not s.name.startswith('.')]

        if is_pics := PICS_DIR.match(name):
            return  # photo container: attributed by parent

        if is_province_folder(name, self.province_vocab):
            ctx2 = dict(ctx)
            low = norm(re.sub(r'(?i)\bimo\b', '', name))
            hint = IMO_ACRONYMS.get(low, low.split())
            if hint:
                ctx2['province'] = ' '.join(hint)
            if files:
                self._group_loose(region, d, files, ctx2, pics)
            for s in nav:
                self._walk_dir(region, s, ctx2)
            return

        if is_category_folder(name):
            work, cat = work_hint(name)
            ctx2 = dict(ctx)
            if work:
                ctx2['work'] = work
                ctx2['cat'] = cat
            made = self._group_loose(region, d, files, ctx2, pics) if files else []
            for s in nav:
                self._walk_dir(region, s, ctx2)
            if not files and not nav and not pics:
                return  # empty category folder
            return

        # project directory — one package, absorbing nested photo folders
        self.add(region, name, d, 'project_dir', ctx, doc_files_in(d))

    def _group_loose(self, region: str, d: Path, files: list[Path],
                     ctx: dict, pics_dirs: list[Path]) -> list[dict]:
        """Group loose document files (and sibling PICTURES-dir files) into
        packages by parsed system name. Each group is added exactly once."""
        groups: dict[str, dict] = {}
        order: list[str] = []
        pics_pool: list[Path] = []

        def group_key_for(stem: str) -> str:
            system = extract_system(stem)
            key = norm(system or stem)
            return key or norm(stem)

        def add_file(f: Path, from_pics: bool):
            stem = package_key_from_stem(f.stem)
            key = group_key_for(stem if not from_pics else stem)
            if not key:
                key = norm(f.stem)
            if key not in groups:
                groups[key] = {
                    'name': stem or f.stem,
                    'path': f.parent,
                    'files': [],
                }
                order.append(key)
            groups[key]['files'].append(f)

        def add_file_group(pfs: list[Path]):
            if not pfs:
                return
            stem = package_key_from_stem(pfs[0].stem) or pfs[0].parent.name
            key = group_key_for(stem) or norm(pfs[0].parent.name)
            groups[key] = {
                'name': stem,
                'path': pfs[0].parent,
                'files': list(pfs),
            }
            order.append(key)

        for f in files:
            # Picture-named files (GEOTAGGED PICTURES.pdf, photo sheets) join
            # the existing groups of this folder rather than forming their own
            # packages — attributed as photo docs to the folder's projects.
            if PICTURE_FILE.search(f.stem):
                pics_pool.append(f)
                continue
            add_file(f, from_pics=False)
        for pd in pics_dirs:
            for pf in doc_files_in(pd):
                key = group_key_for(package_key_from_stem(pf.stem))
                if key in groups:
                    groups[key]['files'].append(pf)
                else:
                    pics_pool.append(pf)
        # attach leftover picture files to the largest group (or their own
        # photo-only package when the folder has no other documents)
        if groups:
            for pf in pics_pool:
                target = max(groups.values(), key=lambda g: len(g['files']))
                target['files'].append(pf)
        elif pics_pool:
            add_file_group(pics_pool)

        made = []
        for key in order:
            g = groups[key]
            self.add(region, g['name'], g['path'], 'loose_pdf', ctx, g['files'])
            made.append({'name': g['name'], 'files': g['files']})
        return made


# ---------------------------------------------------------------- matching

def load_senate():
    data = json.loads(SENATE_PATH.read_text())
    by_region = defaultdict(list)
    projects = []
    for p in data['projects']:
        title = p.get('submission_label') or p.get('label') or ''
        amount = p.get('hgab_amount') if p.get('hgab_amount') else p.get('nep_amount')
        row = {
            'id': p['id'],
            'status': p.get('status'),
            'category': p.get('category'),
            'region': p.get('region'),
            'province': p.get('province'),
            'province_n': norm(p.get('province') or ''),
            'title': title,
            'title_n': norm(title),
            'toks': tokens(title),
            'amount': amount,
            'nep_amount': p.get('nep_amount'),
            'hgab_amount': p.get('hgab_amount'),
        }
        projects.append(row)
        by_region[p.get('region') or ''].append(row)
    return projects, by_region


GENERIC_HEAD_WORDS = {
    'river', 'mountain', 'creek', 'ground', 'irrigation', 'system', 'systems',
    'project', 'the', 'of', 'new', 'upper', 'lower', 'north', 'south', 'east',
    'west', 'main', 'dam', 'pump', 'san', 'santa', 'brgy', 'barangay',
}


def build_acronym_index(projects: list[dict]) -> dict[str, dict]:
    """Map acronym (e.g. VIS) → full head text of the Senate row that coined it.

    Only unambiguous, non-generic-word acronyms are retained. Single letters or
    generic-only heads are skipped. Used to expand one-token system guesses
    (folder names like `BCIS`, `ZRIS`) before title similarity scoring.
    """
    per_region: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for p in projects:
        head = re.split(r'[:]', p['title'] or '', maxsplit=1)[0].strip()
        if not head or len(head) < 4:
            continue
        words = re.findall(r'[A-Za-z]+', head)
        if len(words) < 2:
            continue
        if all(w.lower() in GENERIC_HEAD_WORDS for w in words):
            continue
        acr = ''.join(w[0] for w in words).upper()
        if len(acr) < 2 or len(set(acr)) < 2:
            continue
        per_region[p['region']][acr].append(head)
    idx: dict[str, dict] = {}
    for region, acrs in per_region.items():
        for acr, heads in acrs.items():
            if len(set(heads)) == 1:
                idx.setdefault(region, {})[acr] = heads[0]
    return idx


def compact_title(senate_row: dict) -> str:
    return ' '.join(t for t in senate_row['title_n'].split() if t not in STOP)


def score_package(pkg: dict, senate_row: dict, acr_idx: dict | None = None) -> dict:
    sys_raw = pkg.get('system_guess') or ''
    sys_n = norm(sys_raw)
    sys_toks = tokens(sys_raw)
    # Acronym expansion: single-token system guess that matches an unambiguous
    # acronym coined by this Senate row's region (e.g. VIS → Visitacion
    # Irrigation System) expands for similarity scoring only.
    expanded = None
    if (acr_idx and sys_toks and len(sys_toks) == 1
            and re.fullmatch(r'[A-Za-z]{2,6}\d*', sys_raw.replace(' ', ''))):
        acr = re.sub(r'\d+', '', sys_raw).upper().replace(' ', '')
        cand = acr_idx.get(senate_row['region'], {}).get(acr)
        if cand and norm(cand) != sys_n:
            expanded = cand
    cat_boost = 0.0
    if pkg.get('category_hint') and senate_row['category']:
        if pkg['category_hint'][:20].lower() in (senate_row['category'] or '').lower():
            cat_boost = 0.08
        elif set(norm(pkg['category_hint']).split()) & set(norm(senate_row['category']).split()) - {'of', 'in', 'the'}:
            cat_boost = 0.05
    prov_boost = 0.0
    if pkg.get('province_folder'):
        pv = set(norm(pkg['province_folder']).split())
        sv = set(senate_row['province_n'].split())
        if pv & sv:
            prov_boost = 0.06
    amt_score = 0.0
    if pkg.get('amount_php') and senate_row['amount']:
        if senate_row['amount'] == pkg['amount_php']:
            amt_score = 0.25
        elif abs(senate_row['amount'] - pkg['amount_php']) / max(pkg['amount_php'], 1) <= 0.02:
            amt_score = 0.15
        elif abs(senate_row['amount'] - pkg['amount_php']) / max(pkg['amount_php'], 1) <= 0.10:
            amt_score = 0.05
    substr = 0.0
    if sys_n and sys_n.replace(' ', '') in senate_row['title_n'].replace(' ', ''):
        substr = 0.15
    elif sys_toks and any(len(t) >= 4 and t in senate_row['title_n'] for t in sys_toks):
        substr = 0.10
    if expanded:
        exp_n = norm(expanded)
        ratio = max(
            SequenceMatcher(None, sys_n, senate_row['title_n']).ratio(),
            SequenceMatcher(None, sys_n, compact_title(senate_row)).ratio(),
        )
        exp_ratio = SequenceMatcher(None, exp_n, senate_row['title_n']).ratio()
        ratio = max(ratio, exp_ratio)
        overlap = len(sys_toks & senate_row['toks']) / max(len(sys_toks), 1)
        # Full expansion credit requires the amount to agree too — otherwise
        # every same-system row absorbs the package regardless of amount.
        if norm(expanded).replace(' ', '') in senate_row['title_n'].replace(' ', ''):
            overlap = max(overlap, 1.0 if amt_score > 0 else 0.5)
    else:
        ratio = SequenceMatcher(None, sys_n, senate_row['title_n']).ratio() if sys_n else 0.0
        compact = ' '.join(t for t in senate_row['title_n'].split() if t not in STOP)
        ratio = max(ratio, SequenceMatcher(None, sys_n, compact).ratio()) if sys_n else 0.0
        overlap = len(sys_toks & senate_row['toks']) / max(len(sys_toks), 1) if sys_toks else 0.0
    score = (0.45 * ratio + 0.25 * overlap + amt_score
             + cat_boost + prov_boost + substr)
    return {
        'score': round(score, 3),
        'title_ratio': round(ratio, 3),
        'token_overlap': round(overlap, 3),
        'amount_hit': amt_score > 0,
        'cat_boost': cat_boost > 0,
        'province_boost': prov_boost > 0,
        'senate_id': senate_row['id'],
        'status': senate_row['status'],
        'category': senate_row['category'],
        'region': senate_row['region'],
        'amount': senate_row['amount'],
        'title': senate_row['title'],
    }


def match_strength(top: dict | None, pkg: dict) -> str:
    if not top:
        return 'unmatched'
    if not pkg.get('system_guess') and not pkg.get('amount_php'):
        return 'review'
    if top.get('pdf_confirmed'):
        return 'strong'
    # Filename amount contradicting the row (>=2x or <=0.5x) vetoes strong
    amt = pkg.get('amount_php')
    row_amt = top.get('amount')
    amount_veto = bool(amt and row_amt and (amt / row_amt >= 2.0 or amt / row_amt <= 0.5))
    # Title evidence = the parsed system actually appears in the row title
    # (overlap) or the full system string ratios well against it. A ratio
    # against a different same-category row must not count.
    title_evidence = ((top.get('token_overlap') or 0) >= 0.5
                      or (top.get('title_ratio') or 0) >= 0.25)
    sys_toks = tokens(pkg.get('system_guess') or '')
    if title_evidence and sys_toks and not (
            tokens(pkg.get('system_guess') or '') & set(top.get('title', '').lower().split())):
        # token overlap already demands shared words; guard ratio-only paths
        title_evidence = (top.get('title_ratio') or 0) >= 0.4 or bool(
            sys_toks & {t for t in norm(top.get('title') or '').split()})
    if amount_veto:
        return 'weak' if top['score'] >= 0.25 else 'unmatched'
    if top['score'] >= 0.55 and title_evidence:
        return 'strong'
    if top['amount_hit'] and top['score'] >= 0.40 and title_evidence:
        return 'strong'
    if top['score'] >= 0.25:
        return 'weak'
    return 'unmatched'


def package_pdf_paths(pkg: dict) -> list[Path]:
    root = POW_ROOT / pkg['path']
    paths: list[Path] = []
    if root.is_file() and root.suffix.lower() == '.pdf':
        paths = [root]
    elif root.is_dir():
        paths = sorted({*root.rglob('*.pdf'), *root.rglob('*.PDF')})
    else:
        for rel in pkg.get('pdfs') or []:
            p = POW_ROOT / rel
            if p.is_file():
                paths.append(p)
    paths = sorted(set(paths), key=lambda p: (
        1 if PICTURE_FILE.search(p.stem) else 0, p.name))
    return paths


def extract_pdf_text(pdf: Path, max_pages: int = 4) -> tuple[str, str]:
    try:
        import pymupdf
    except ImportError:
        return '', 'empty'
    doc = pymupdf.open(pdf)
    try:
        parts = []
        for i, page in enumerate(doc):
            if i >= max_pages:
                break
            parts.append(page.get_text('text') or '')
        text = '\n'.join(parts).strip()
        if len(re.sub(r'\s+', '', text)) >= 40:
            return text, 'native'
        try:
            import subprocess
            import tempfile
            ocr_parts = []
            for i, page in enumerate(doc):
                if i >= min(2, max_pages):
                    break
                pix = page.get_pixmap(dpi=150)
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                    pix.save(tmp.name)
                    tmp_path = tmp.name
                try:
                    r = subprocess.run(
                        ['tesseract', tmp_path, 'stdout', '-l', 'eng'],
                        capture_output=True, text=True, timeout=90)
                    if r.returncode == 0 and r.stdout.strip():
                        ocr_parts.append(r.stdout)
                finally:
                    Path(tmp_path).unlink(missing_ok=True)
            ocr = '\n'.join(ocr_parts).strip()
            if len(re.sub(r'\s+', '', ocr)) >= 40:
                return ocr, 'ocr'
        except Exception:
            pass
        return text, 'empty' if not text else 'native'
    finally:
        doc.close()


def package_document_text(pkg: dict) -> tuple[str, str, list[str]]:
    paths = package_pdf_paths(pkg)
    if not paths:
        return '', 'empty', []
    chunks, methods, used = [], [], []
    for pdf in paths[:3]:
        text, method = extract_pdf_text(pdf)
        if text:
            chunks.append(text)
            methods.append(method)
            used.append(str(pdf.relative_to(POW_ROOT)))
    if not chunks:
        return '', 'empty', [str(p.relative_to(POW_ROOT)) for p in paths[:3]]
    method = 'ocr' if methods == ['ocr'] else ('native' if 'native' in methods else methods[0])
    return '\n'.join(chunks), method, used


def amounts_in_text(text: str) -> set[int]:
    found: set[int] = set()
    for m in re.finditer(r'(?:php|₱)\s*\.?\s*([\d,]+(?:\.\d+)?)', text, re.I):
        try:
            v = float(m.group(1).replace(',', ''))
            found.add(int(round(v * 1_000_000)) if v < 10_000 else int(round(v)))
        except ValueError:
            pass
    for m in re.finditer(r'([\d,]+(?:\.\d+)?)\s*(?:million|\bM\b)', text, re.I):
        try:
            found.add(int(round(float(m.group(1).replace(',', '')) * 1_000_000)))
        except ValueError:
            pass
    for m in re.finditer(r'\b(\d{1,3}(?:,\d{3}){2,}(?:\.\d+)?)\b', text):
        try:
            found.add(int(round(float(m.group(1).replace(',', '')))))
        except ValueError:
            pass
    return found


def score_package_with_pdf(pkg: dict, senate_row: dict, pdf_text: str, pdf_n: str,
                           pdf_amounts: set[int], acr_idx: dict | None = None) -> dict:
    base = score_package(pkg, senate_row, acr_idx)
    title = senate_row['title']
    title_n = senate_row['title_n']
    toks = [t for t in title_n.split() if len(t) >= 4 and t not in STOP]
    hits = sum(1 for t in toks if t in pdf_n)
    hit_ratio = hits / max(len(toks), 1) if toks else 0.0
    head = re.split(r'[:\-–]', title, maxsplit=1)[0].strip()
    head_n = norm(head)
    head_core = re.sub(r'\b(cis|ris|pis|is|spip|nis)\b', ' ', head_n)
    head_core = re.sub(r'\s+', ' ', head_core).strip()
    compact_pdf = pdf_n.replace(' ', '')
    phrase_hit = bool(head_n) and len(head_n) >= 6 and head_n.replace(' ', '') in compact_pdf
    if not phrase_hit and head_core and len(head_core) >= 6:
        phrase_hit = head_core.replace(' ', '') in compact_pdf
    if not phrase_hit and head_n:
        head_toks = [t for t in head_n.split() if len(t) >= 4 and t not in STOP]
        phrase_hit = len(head_toks) >= 2 and all(t in pdf_n for t in head_toks)
    distinctive = [t for t in toks if len(t) >= 5]
    distinctive_hits = [t for t in distinctive if t in pdf_n]
    amt = senate_row['amount']
    # Generic site words must not confirm an identity on their own (water,
    # ground, project, system … appear in every POW form).
    GENERIC_SITE_WORDS = {
        'water', 'ground', 'project', 'system', 'systems', 'works', 'canal',
        'road', 'roads', 'dam', 'dams', 'river', 'sheetpile', 'sheet', 'pile',
        'rehabilitation', 'scoured', 'slope', 'protection', 'structures',
        'impounding', 'irrigation', 'improvement', 'installation', 'lining',
        'concreting', 'construction', 'pump', 'solar', 'drainage', 'elevated',
        'diversion', 'embankment', 'formation', 'upstream', 'downstream',
        'appurtenant', 'appurtenances', 'interlocking', 'blocks', 'intake',
        'concrete', 'masonry', 'spillway', 'gabion', 'existing', 'chb',
        'sitio', 'barangay', 'brgy', 'purok', 'zone', 'phase', 'units', 'unit',
        'pumping', 'station', 'reservoir', 'pipeline', 'steel', 'type',
        'shaped', 'main', 'lateral', 'canalization', 'small', 'powered',
    }
    site_distinctive_hits = [t for t in distinctive_hits
                             if t not in GENERIC_SITE_WORDS]
    site_hit = bool(site_distinctive_hits) and any(
        len(t) >= 6 for t in site_distinctive_hits)
    # Amount veto: a package whose filename amount clearly contradicts the
    # Senate row (>=2x or <=0.5x) cannot confirm via the PDF — cost-breakdown
    # lines can mimic nearby amounts (P20M row vs P200M POW total). Only an
    # exact row-amount print in the PDF overrides the veto.
    pkg_amt = pkg.get('amount_php')
    amount_veto = bool(pkg_amt and amt and (pkg_amt / amt >= 2.0 or pkg_amt / amt <= 0.5))
    amt_in_pdf = False
    if amt and pdf_amounts:
        if amt in pdf_amounts:
            amt_in_pdf = True
        elif not amount_veto and any(abs(a - amt) / max(amt, 1) <= 0.02 for a in pdf_amounts):
            amt_in_pdf = True
    if amount_veto and not (amt and amt in pdf_amounts):
        phrase_hit = False
        site_hit = False
        amt_in_pdf = False
    pdf_score = (
        0.45 * hit_ratio
        + (0.2 if phrase_hit else 0.0)
        + (0.15 if site_hit else 0.0)
        + (0.2 if amt_in_pdf else 0.0)
        + (0.05 if base['cat_boost'] else 0.0)
    )
    combined = max(base['score'], 0.35 * base['score'] + 0.65 * pdf_score)
    confirmed = (
        (phrase_hit and (amt_in_pdf or base['amount_hit'] or hit_ratio >= 0.35 or site_hit))
        or (hit_ratio >= 0.55 and (amt_in_pdf or base['amount_hit']))
        or (hit_ratio >= 0.7)
        or (phrase_hit and hit_ratio >= 0.4)
        or (site_hit and (amt_in_pdf or base['amount_hit'] or phrase_hit))
    )
    out = {
        **base,
        'score': round(combined, 3),
        'pdf_hit_ratio': round(hit_ratio, 3),
        'pdf_hits': hits,
        'pdf_tokens': len(toks),
        'pdf_phrase_hit': phrase_hit,
        'pdf_site_hit': site_hit,
        'pdf_amount_hit': amt_in_pdf,
        'pdf_confirmed': confirmed,
        'amount_hit': base['amount_hit'] or amt_in_pdf,
    }
    return out


def confirm_weak_with_pdf(pkg: dict, pool: list[dict], top: dict | None,
                          scored: list[dict], acr_idx: dict | None = None):
    text, method, used = package_document_text(pkg)
    evidence = {
        'method': method,
        'pdfs': used,
        'chars': len(text),
        'snippet': re.sub(r'\s+', ' ', text)[:280] if text else '',
    }
    if method == 'empty' or len(text) < 40:
        return top, scored, evidence
    pdf_n = norm(text)
    pdf_amounts = amounts_in_text(text)
    rescored = [score_package_with_pdf(pkg, s, text, pdf_n, pdf_amounts, acr_idx)
                for s in pool]
    rescored.sort(key=lambda x: (
        -int(x.get('pdf_confirmed') or False),
        -x['score'],
        -(x.get('pdf_hit_ratio') or 0),
        x['title'] or '',
    ))
    new_top = rescored[0] if rescored else top
    if new_top and new_top.get('pdf_confirmed'):
        evidence['confirmed'] = True
        evidence['senate_id'] = new_top['senate_id']
        evidence['pdf_hit_ratio'] = new_top.get('pdf_hit_ratio')
        evidence['pdf_phrase_hit'] = new_top.get('pdf_phrase_hit')
        evidence['pdf_amount_hit'] = new_top.get('pdf_amount_hit')
    else:
        evidence['confirmed'] = False
    return new_top, rescored[:5], evidence


# ---------------------------------------------------------------- build

def build():
    senate, by_region = load_senate()
    acr_idx = build_acronym_index(senate)
    collector = Collector(senate)
    if POW_ROOT.is_dir():
        for region_dir in sorted(p for p in POW_ROOT.iterdir() if p.is_dir()):
            region = parse_folder_region(region_dir.name)
            if not region:
                continue
            collector.walk(region, region_dir)
    pkgs = collector.pkgs

    matched_packages = []
    for pkg in pkgs:
        regions = REGION_MAP.get(pkg['region_folder'], [])
        pool = []
        for r in regions:
            pool.extend(by_region.get(r, []))
        scored = [score_package(pkg, s, acr_idx) for s in pool]
        scored.sort(key=lambda x: (-x['score'], x['title'] or ''))
        top = scored[0] if scored else None
        strength = match_strength(top, pkg)
        pdf_evidence = None
        if strength in ('weak', 'unmatched', 'review') and pool:
            top, scored, pdf_evidence = confirm_weak_with_pdf(
                pkg, pool, top, scored, acr_idx)
            strength = match_strength(top, pkg)
        entry = {
            **{k: pkg[k] for k in (
                'id', 'region_folder', 'province_folder', 'kind', 'name', 'path',
                'work_prefix', 'category_hint', 'system_guess', 'amount_php',
                'pdf_count', 'image_count', 'other_count', 'doc_count',
                'pow_pdf_count', 'photo_count', 'pdfs', 'images',
            )},
            'match_strength': strength,
            'best_match': top,
            'candidates': scored[:3],
            'pdf_evidence': pdf_evidence,
        }
        matched_packages.append(entry)

    # Aggregate doc counts onto Senate projects. Only strong matches attribute
    # coverage; weak/unmatched stay visible in the packages table.
    by_project: dict[str, dict] = {}
    for pkg in matched_packages:
        top = pkg.get('best_match')
        if not top or pkg['match_strength'] != 'strong':
            continue
        soft = pkg['match_strength'] == 'weak' and not top.get('pdf_confirmed')
        sid = top['senate_id']
        attribution = {
            'package_id': pkg['id'],
            'package_name': pkg['name'],
            'package_path': pkg['path'],
            'match_strength': pkg['match_strength'],
            'score': top['score'],
            'soft': soft,
            'pdf_confirmed': bool(top.get('pdf_confirmed')),
            'pdf_count': pkg['pdf_count'],
            'image_count': pkg['image_count'],
            'doc_count': pkg['doc_count'],
            'pow_pdf_count': pkg.get('pow_pdf_count', 0),
            'photo_count': pkg.get('photo_count', 0),
        }
        cur = by_project.get(sid)
        if not cur:
            by_project[sid] = {
                'senate_id': sid,
                'title': top['title'],
                'region': top['region'],
                'category': top['category'],
                'status': top['status'],
                'amount': top['amount'],
                'match_strength': pkg['match_strength'],
                'pdf_confirmed': bool(top.get('pdf_confirmed')),
                'package_count': 1,
                'pdf_count': pkg['pdf_count'],
                'image_count': pkg['image_count'],
                'doc_count': pkg['doc_count'],
                'pow_pdf_count': pkg.get('pow_pdf_count', 0),
                'photo_count': pkg.get('photo_count', 0),
                'packages': [attribution],
            }
            continue
        cur['package_count'] += 1
        cur['pdf_count'] += pkg['pdf_count']
        cur['image_count'] += pkg['image_count']
        cur['doc_count'] += pkg['doc_count']
        cur['pow_pdf_count'] = cur.get('pow_pdf_count', 0) + pkg.get('pow_pdf_count', 0)
        cur['photo_count'] = cur.get('photo_count', 0) + pkg.get('photo_count', 0)
        cur['packages'].append(attribution)
        if top['score'] > cur.get('best_score', -1):
            cur['best_score'] = top['score']
            cur['match_strength'] = pkg['match_strength']
        if top.get('pdf_confirmed') or pkg['match_strength'] == 'strong':
            if cur['match_strength'] != 'strong':
                cur['match_strength'] = pkg['match_strength']
            cur['pdf_confirmed'] = cur.get('pdf_confirmed') or bool(top.get('pdf_confirmed'))
    for proj in by_project.values():
        proj.pop('best_score', None)

    # Conflict resolution: a Senate row that collected strong packages with
    # mutually inconsistent parsed amounts keeps only amount-consistent or
    # PDF-confirmed packages; the rest are demoted to review (still listed).
    for proj in by_project.values():
        amts = {pk.get('amount_php') for pk in (
            next((q for q in matched_packages if q['id'] == pk['package_id']), {})
            for pk in proj['packages'])}
        amts.discard(None)
        if len(amts) > 1:
            keep = []
            for pk in proj['packages']:
                pkgq = next((q for q in matched_packages
                             if q['id'] == pk['package_id']), {})
                pa = pkgq.get('amount_php')
                consistent = (pa is None or pa == proj.get('amount')
                              or (proj.get('amount') and abs(pa - proj['amount'])
                                  / max(proj['amount'], 1) <= 0.02))
                if consistent or pk.get('pdf_confirmed'):
                    keep.append(pk)
                else:
                    pk['conflict_demoted'] = True
                    for q in matched_packages:
                        if q['id'] == pk['package_id']:
                            q['match_strength'] = 'review'
                            q['best_match'] = q.get('best_match')
            if keep:
                proj['packages'] = keep
                proj['package_count'] = len(keep)
                proj['pdf_count'] = sum(pk['pdf_count'] for pk in keep)
                proj['image_count'] = sum(pk['image_count'] for pk in keep)
                proj['doc_count'] = sum(pk['doc_count'] for pk in keep)
                proj['pow_pdf_count'] = sum(pk.get('pow_pdf_count', 0) for pk in keep)
                proj['photo_count'] = sum(pk.get('photo_count', 0) for pk in keep)
            else:
                proj['match_strength'] = 'review'

    # rows reduced to zero packages by conflict resolution lose coverage
    for sid in [sid for sid, p in by_project.items() if not p['packages']]:
        del by_project[sid]

    # demoted (review) packages must disappear from attribution lists
    for proj in by_project.values():
        if any(pk.get('conflict_demoted') for pk in proj.get('packages', [])):
            proj['packages'] = [pk for pk in proj['packages']
                                if not pk.get('conflict_demoted')]
            proj['package_count'] = len(proj['packages'])
            proj['pdf_count'] = sum(pk['pdf_count'] for pk in proj['packages'])
            proj['image_count'] = sum(pk['image_count'] for pk in proj['packages'])
            proj['doc_count'] = sum(pk['doc_count'] for pk in proj['packages'])
            proj['pow_pdf_count'] = sum(pk.get('pow_pdf_count', 0) for pk in proj['packages'])
            proj['photo_count'] = sum(pk.get('photo_count', 0) for pk in proj['packages'])
            if not proj['packages']:
                proj['match_strength'] = 'review'

    # full coverage of all Senate rows
    coverage = []
    for srow in senate:
        hit = by_project.get(srow['id'])
        if hit:
            has_pow = (hit.get('pow_pdf_count') or 0) > 0
            has_photos = (hit.get('photo_count') or 0) > 0
            coverage.append({
                **hit,
                'supported': True,
                'support': 'supported',
                'has_pow': has_pow,
                'has_photos': has_photos,
            })
        else:
            coverage.append({
                'senate_id': srow['id'],
                'title': srow['title'],
                'region': srow['region'],
                'category': srow['category'],
                'status': srow['status'],
                'amount': srow['amount'],
                'supported': False,
                'support': 'unsupported',
                'has_pow': False,
                'has_photos': False,
                'match_strength': None,
                'package_count': 0,
                'pdf_count': 0,
                'image_count': 0,
                'doc_count': 0,
                'pow_pdf_count': 0,
                'photo_count': 0,
                'packages': [],
            })
    coverage.sort(key=lambda r: (
        0 if r['supported'] else 1,
        -(r['doc_count'] or 0),
        r['region'] or '',
        r['title'] or '',
    ))

    by_reg = defaultdict(lambda: {
        'packages': 0, 'strong': 0, 'weak': 0, 'review': 0, 'unmatched': 0,
        'docs': 0, 'pdfs': 0, 'images': 0,
        'projects_with_docs': 0, 'senate_projects': 0, 'unsupported': 0,
    })
    for pkg in matched_packages:
        b = by_reg[pkg['region_folder']]
        b['packages'] += 1
        b[pkg['match_strength']] += 1
        b['docs'] += pkg['doc_count']
        b['pdfs'] += pkg['pdf_count']
        b['images'] += pkg['image_count']
    folder_for_region = {}
    for folder, labels in REGION_MAP.items():
        for label in labels:
            folder_for_region[label] = folder
    for row in coverage:
        folder = folder_for_region.get(row['region'] or '')
        if not folder:
            continue
        b = by_reg[folder]
        b['senate_projects'] += 1
        if row['supported']:
            b['projects_with_docs'] += 1
        else:
            b['unsupported'] += 1

    strength_counts = defaultdict(int)
    for pkg in matched_packages:
        strength_counts[pkg['match_strength']] += 1
    supported_n = sum(1 for r in coverage if r['supported'])
    unsupported_n = len(coverage) - supported_n
    with_pow_n = sum(1 for r in coverage if r.get('has_pow'))
    with_photos_n = sum(1 for r in coverage if r.get('has_photos'))
    support_scale = [
        {'id': 'pow', 'label': 'With POW', 'count': with_pow_n,
         'detail': 'Program of Works PDF in the [POW FOR REVIEW] drop'},
        {'id': 'photos', 'label': 'With geotagged photos', 'count': with_photos_n,
         'detail': 'Site pictures / picture sheets in the [POW FOR REVIEW] drop'},
        {'id': 'none', 'label': 'No supporting docs', 'count': unsupported_n,
         'detail': 'No package in this drop mapped to the Senate row'},
    ]

    payload = {
        'schema_version': 1,
        'source': str(POW_ROOT),
        'source_drive_url': PBC_DRIVE_URL,
        'source_drive_folder': "PEOPLE'S BUDGET COALITION REQUIREMENTS",
        'source_subfolder': SOURCE_SUBFOLDER,
        'note': (
            'Supporting-document availability from the [POW FOR REVIEW] Program of '
            'Works drop. Packages are parsed as work-type / system / amount from '
            'folder and file names (region -> IMO/province -> category -> project '
            'nesting), then fuzzy-matched to Senate workbook submission titles within '
            'the same region, with province and category boosts. Matches are triage '
            'candidates, not certified identity. Unsupported means no package in this '
            'drop mapped to the Senate row. Weak filename matches are re-checked '
            'against POW PDF text (native layer; OCR only where tesseract exists). '
            'Local path is configured in extract_pow_review_availability.py '
            '(or NIA_POW_ROOT); canonical upstream is the PBC Google Drive folder.'
        ),
        'summary': {
            'region_folders': len({p['region_folder'] for p in matched_packages}),
            'packages': len(matched_packages),
            'total_docs': sum(p['doc_count'] for p in matched_packages),
            'total_pdfs': sum(p['pdf_count'] for p in matched_packages),
            'total_images': sum(p['image_count'] for p in matched_packages),
            'match_strength': dict(strength_counts),
            'senate_projects': len(senate),
            'senate_projects_with_docs': supported_n,
            'senate_projects_unsupported': unsupported_n,
            'senate_projects_with_pow': with_pow_n,
            'senate_projects_with_photos': with_photos_n,
            'senate_docs_attributed': sum(p['doc_count'] for p in by_project.values()),
            'support_scale': support_scale,
        },
        'by_region': [
            {'region_folder': k, **v}
            for k, v in sorted(by_reg.items())
        ],
        'packages': matched_packages,
        'projects': sorted(
            by_project.values(),
            key=lambda r: (-r['doc_count'], r['region'] or '', r['title'] or ''),
        ),
        'coverage': coverage,
    }
    OUT_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n')
    return payload


if __name__ == '__main__':
    out = build()
    s = out['summary']
    print(f"packages={s['packages']} docs={s['total_docs']} "
          f"(pdfs={s['total_pdfs']} images={s['total_images']})")
    print(f"match_strength={s['match_strength']}")
    print(f"senate_with_docs={s['senate_projects_with_docs']}/{s['senate_projects']}")
    print(f"scale: pow={s['senate_projects_with_pow']} photos={s['senate_projects_with_photos']} "
          f"none={s['senate_projects_unsupported']}")
    print(f'wrote {OUT_PATH}')
