# app.py
import re
import csv
import io
import math
import random
import itertools
from datetime import date
from typing import List, Dict

import streamlit as st
import nltk
from nltk.stem import WordNetLemmatizer

from PIL import Image
import pytesseract

# -----------------------------
# NLTK Setup
# -----------------------------
nltk.download("wordnet")
nltk.download("omw-1.4")

lemmatizer = WordNetLemmatizer()

# -----------------------------
# Utility Functions
# -----------------------------
def slugify(s: str) -> str:
    s = re.sub(r"[^\w\s-]", "", s, flags=re.U).strip().lower()
    return re.sub(r"[-\s]+", "-", s, flags=re.U)

def uniq(seq):
    seen = set()
    out = []
    for x in seq:
        if x not in seen:
            out.append(x)
            seen.add(x)
    return out

def title_case(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().title()

def join_with_and(items: List[str]) -> str:
    items = [i for i in items if i]
    if not items: return ""
    if len(items) == 1: return items[0]
    return ", ".join(items[:-1]) + " and " + items[-1]

def soft_cap(text: str, limit: int) -> str:
    if len(text) <= limit: return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return cut + "…"

# -----------------------------
# SEO Helpers
# -----------------------------
def keyword_candidates(subject: str, grades: List[str], resource_type: str, focus: str, extras: Dict) -> List[str]:
    g = [re.sub(r"grade\s*", "", gr, flags=re.I).strip() for gr in grades] or [""]
    gnorm = [f"grade {x}".strip() for x in g if x]
    base = [
        subject, resource_type, focus,
        f"{focus} {resource_type}",
        f"{subject} {focus}",
        f"{join_with_and(gnorm)} {resource_type}",
        f"{focus} activities",
        f"{focus} worksheets",
        f"{focus} lesson plans",
    ]
    raw = [k.strip().lower() for k in base]
    cleaned = uniq([re.sub(r"\s+", " ", k).strip() for k in raw if k])
    return cleaned

def score_title(title: str, focus_terms: List[str]) -> Dict:
    length = len(title)
    length_score = 1.0 if 40 <= length <= 100 else 0.7
    presence = sum(1 for t in focus_terms if t.lower() in title.lower())
    presence_score = min(1.0, presence / max(1, len(focus_terms)))
    score = round((0.6 * length_score + 0.4 * presence_score), 2)
    return {"length": length, "score": min(score, 1.0)}

def score_description(desc: str, focus_terms: List[str]) -> Dict:
    length = len(desc)
    presence = sum(1 for t in focus_terms if t.lower() in desc.lower())
    length_score = 1.0 if 300 <= length <= 900 else 0.7
    presence_score = min(1.0, presence / max(1, len(focus_terms)))
    score = round((0.6 * length_score + 0.4 * presence_score), 2)
    return {"length": length, "score": min(score, 1.0)}

# -----------------------------
# Generators
# -----------------------------
TITLE_TEMPLATES = [
    "{Focus} {Resource} for {Grades} | {Subject}",
    "{Grades} {Subject}: {Focus} {Resource}",
    "Engaging {Focus} {Resource} for {Grades} | Printable & Digital",
]

def format_short(formats: List[str]) -> str:
    if not formats: return "Printable & Digital"
    fm = [f.title() for f in formats]
    return join_with_and(fm)

def generate_title(subject: str, grades: List[str], resource_type: str, focus: str, formats: List[str]) -> str:
    gtxt = join_with_and(grades) if grades else ""
    template = random.choice(TITLE_TEMPLATES)
    title = template.format(
        Focus=title_case(focus),
        Resource=title_case(resource_type),
        Grades=gtxt,
        Subject=title_case(subject),
    )
    return soft_cap(re.sub(r"\s+", " ", title).strip(), 110)

def generate_description(subject: str, grades: List[str], resource_type: str, focus: str, formats: List[str],
                         standards: str, tone: str, word_goal: int = 300) -> str:
    subject_lower = subject.lower()
    focus_lower = focus.lower()
    grades_txt = join_with_and(grades) if grades else ""
    resource_lower = resource_type.lower()
    fmt = format_short(formats)

    desc = (
        f"Help your {grades_txt.lower()} {subject_lower} students master **{focus_lower}** "
        f"with this {resource_lower}. It’s low-prep and comes in {fmt.lower()} for flexible teaching. "
        f"Perfect for centers, homework, or review."
    )
    return desc.strip()

# -----------------------------
# Streamlit UI
# -----------------------------
st.set_page_config(page_title="TPT SEO Generator", page_icon="🧑‍🏫", layout="wide")
st.title("🧑‍🏫 TPT SEO Generator with Thumbnail Support")

# Sidebar inputs
with st.sidebar:
    st.header("Inputs")
    subject = st.text_input("Subject", value="Math")
    grades = st.multiselect("Grade Level(s)", ["Preschool", "Kindergarten", "Grade 1", "Grade 2", "Grade 3", "Grade 4", "Grade 5", "Grade 6"], default=["Preschool"])
    resource_type = st.selectbox("Resource Type", ["Worksheet", "Activities", "Lesson Plan"], index=0)
    focus = st.text_input("Focus / Topic", value="Fractions")
    formats = st.multiselect("Formats", ["Printable", "Digital"], default=["Printable", "Digital"])
    standards = st.text_input("Standards (optional)", value="CCSS")
    word_goal = st.slider("Description target words", 120, 600, 280, step=20)
    n_variations = st.slider("How many variations?", 1, 5, 3)

    # 🔹 Thumbnail upload
    st.header("Thumbnail Upload (optional)")
    thumbnail = st.file_uploader("Upload product thumbnail", type=["png", "jpg", "jpeg"])

    thumbnail_text = ""
    if thumbnail is not None:
        image = Image.open(thumbnail)
        st.image(image, caption="Uploaded Thumbnail", use_column_width=True)
        thumbnail_text = pytesseract.image_to_string(image)
        if thumbnail_text.strip():
            st.markdown("**Extracted text from thumbnail:**")
            st.code(thumbnail_text.strip())

    gen_btn = st.button("🚀 Generate")

# -----------------------------
# Generation
# -----------------------------
if gen_btn:
    st.subheader("Generated Variations")
    all_rows = []
    for _ in range(n_variations):
        title = generate_title(subject, grades, resource_type, focus, formats)
        desc = generate_description(subject, grades, resource_type, focus, formats, standards, tone, word_goal)

        # 🔹 Use thumbnail text in description
        if thumbnail_text.strip():
            desc += f" Thumbnail highlights: {thumbnail_text.strip()}"

        keywords = ", ".join(keyword_candidates(subject, grades, resource_type, focus, {}))
        tscore = score_title(title, [focus.lower(), subject.lower(), resource_type.lower()])
        dscore = score_description(desc, [focus.lower(), subject.lower(), resource_type.lower()])

        with st.container(border=True):
            st.markdown(f"**Title:** {title}")
            st.markdown(f"**Description:** {desc}")
            st.markdown(f"**Keywords:** {keywords}")
            st.caption(f"Title score: {tscore['score']} • Description score: {dscore['score']}")

        all_rows.append({"title": title, "description": desc, "keywords": keywords})

    # CSV Export
    csv_buf = io.StringIO()
    writer = csv.DictWriter(csv_buf, fieldnames=list(all_rows[0].keys()))
    writer.writeheader()
    for r in all_rows:
        writer.writerow(r)
    st.download_button("⬇️ Download CSV", data=csv_buf.getvalue().encode("utf-8"),
                       file_name=f"tpt_seo_{date.today().isoformat()}.csv", mime="text/csv")
