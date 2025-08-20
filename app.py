# app.py
import re
import csv
import io
import math
import random
import itertools
from datetime import date
from typing import List, Tuple, Dict

import streamlit as st
import nltk
from nltk.stem import WordNetLemmatizer

# -----------------------------
# Utilities
# -----------------------------
lemmatizer = WordNetLemmatizer()

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

def lemmatize_words(words: List[str]) -> List[str]:
    return [lemmatizer.lemmatize(w) for w in words]

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
        f"{focus} centers",
        f"{focus} assessments",
    ]
    # Long-tail
    long_tail = [
        f"{focus} differentiated",
        f"{focus} small group",
        f"{focus} printable",
        f"{focus} no prep",
        f"{focus} google slides",
        f"{focus} self-checking",
        f"{focus} formative assessment",
    ]
    # Seasonal / classroom contexts
    contexts = []
    if extras.get("seasonal"):
        contexts += [f"{focus} back to school", f"{focus} end of year", f"{focus} test prep"]
    # Standards
    if extras.get("standards"):
        contexts += [f"{focus} {extras['standards']} aligned"]
    # Formats
    fmts = []
    if extras.get("formats"):
        for fmt in extras["formats"]:
            fmts.append(f"{focus} {fmt.lower()}")
            fmts.append(f"{resource_type} {fmt.lower()}")
    # Grades variants
    gv = []
    for gr in g:
        if not gr: continue
        gv += [f"{focus} grade {gr}", f"{resource_type} grade {gr}", f"{subject} grade {gr}"]

    raw = [k.strip().lower() for k in base + long_tail + contexts + fmts + gv]
    # Dedup + clean
    cleaned = uniq([re.sub(r"\s+", " ", k).strip() for k in raw if k])
    return cleaned

def cluster_keywords(keywords: List[str], max_per_cluster: int = 6) -> List[List[str]]:
    # simple heuristic: group by headword (first lemmatized token)
    buckets: Dict[str, List[str]] = {}
    for kw in keywords:
        head = lemmatizer.lemmatize(kw.split()[0])
        buckets.setdefault(head, []).append(kw)
    clusters = [kws[:max_per_cluster] for kws in buckets.values()]
    # sort clusters by length (desc)
    clusters.sort(key=lambda c: -len(c))
    return clusters

def score_title(title: str, focus_terms: List[str]) -> Dict:
    # naive SEO score: length band + keyword presence
    length = len(title)
    length_score = 1.0 if 40 <= length <= 100 else (0.7 if 25 <= length <= 120 else 0.4)
    presence = sum(1 for t in focus_terms if t.lower() in title.lower())
    presence_score = min(1.0, presence / max(1, len(focus_terms)))
    # structure bonus if includes grade and resource
    structure = 0.2 if re.search(r"\bgrade\b|\bk-\d\b|\bgrades?\b", title, re.I) else 0.0
    structure += 0.2 if re.search(r"worksheet|activity|activities|lesson|bundle|unit|game|centers?|assessment", title, re.I) else 0.0
    score = round((0.6 * length_score + 0.4 * presence_score + structure), 2)
    return {"length": length, "score": min(score, 1.0)}

def score_description(desc: str, focus_terms: List[str]) -> Dict:
    length = len(desc)
    presence = sum(1 for t in focus_terms if t.lower() in desc.lower())
    structure = 0.2 if any(x in desc.lower() for x in ["perfect for", "includes", "what's inside", "how to use"]) else 0.0
    length_score = 1.0 if 300 <= length <= 900 else (0.8 if 180 <= length <= 1200 else 0.5)
    presence_score = min(1.0, presence / max(1, len(focus_terms)))
    score = round((0.6 * length_score + 0.4 * presence_score + structure), 2)
    return {"length": length, "score": min(score, 1.0)}

# -----------------------------
# Generators
# -----------------------------
TITLE_TEMPLATES = [
    "{Focus} {Resource} for {Grades} | {Subject} ({FormatShort})",
    "{Grades} {Subject}: {Focus} {Resource} – Differentiated & No-Prep",
    "Engaging {Focus} {Resource} for {Grades} | Printable & Digital",
    "{Focus} {Resource} ({FormatShort}) – {Grades} {Subject} Centers & Practice",
    "{Focus} {Resource} | {Grades} {Subject} | Aligned & Classroom-Tested",
    "No-Prep {Focus} {Resource} for {Grades} – Small Groups & Intervention",
    "{Focus} {Resource} Bundle for {Grades} | {Subject} | Review & Assessment",
]

CTA_TEMPLATES = [
    "Perfect for whole group, small groups, centers, homework, or test prep.",
    "Use for stations, early finishers, intervention, sub plans, and assessments.",
    "Differentiated options support diverse learners and save you planning time.",
    "Low-prep and ready-to-print; includes digital versions for flexible teaching.",
]

INCLUDES_TEMPLATES = [
    "Includes {count} {resource_lower}(s), answer keys, and editable versions.",
    "What’s inside: step-by-step teacher guide, printable pages, and digital slides.",
    "You’ll get: scaffolded practice, challenge tasks, and self-checking forms.",
]

USAGE_TEMPLATES = [
    "Ideal for {grades} {subject_lower} units on {focus_lower}.",
    "Aligns to {standards} with clear objectives and formative checks." ,
    "Use during warm-ups, stations, exit tickets, assessments, and homework.",
]

TONE_PHRASES = {
    "neutral": ["clear", "classroom-tested", "standards-aligned", "ready-to-use"],
    "enthusiastic": ["engaging", "fun", "high-impact", "student-approved"],
    "professional": ["data-informed", "research-based", "scaffolded", "differentiated"],
}

def format_short(formats: List[str]) -> str:
    if not formats: return "Printable & Digital"
    fm = [f.title() for f in formats]
    if "Google Slides" in fm and "Digital" not in fm:
        # avoid redundancy
        fm = [x for x in fm if x != "Digital"]
    return join_with_and(fm)

def generate_title(subject: str, grades: List[str], resource_type: str, focus: str, formats: List[str]) -> str:
    gtxt = join_with_and(grades) if grades else ""
    fmt = format_short(formats)
    template = random.choice(TITLE_TEMPLATES)
    title = template.format(
        Focus=title_case(focus),
        Resource=title_case(resource_type),
        Grades=gtxt,
        Subject=title_case(subject),
        FormatShort=fmt
    )
    # clean double spaces and soft cap around ~110 chars (good for TPT + search)
    return soft_cap(re.sub(r"\s+", " ", title).strip(), 110)

def generate_description(subject: str, grades: List[str], resource_type: str, focus: str, formats: List[str],
                         standards: str, tone: str, word_goal: int = 300) -> str:
    subject_lower = subject.lower()
    focus_lower = focus.lower()
    grades_txt = join_with_and(grades) if grades else ""
    resource_lower = resource_type.lower()
    fmt = format_short(formats)

    tone_words = ", ".join(TONE_PHRASES.get(tone, TONE_PHRASES["neutral"]))

    parts = []
    # Hook
    parts.append(
        f"Help your {grades_txt.lower()} {subject_lower} students master **{focus_lower}** with this {tone_words} {resource_lower}. "
        f"It’s truly low-prep and comes in {fmt.lower()} for flexible teaching."
    )
    # What it is
    parts.append(
        random.choice(INCLUDES_TEMPLATES).format(count=random.randint(10, 40), resource_lower=resource_lower)
    )
    # How to use
    use = random.choice(USAGE_TEMPLATES).format(
        grades=grades_txt, subject_lower=subject_lower, focus_lower=focus_lower, standards=standards or "key standards"
    )
    parts.append(use)
    # CTA
    parts.append(random.choice(CTA_TEMPLATES))

    desc = " ".join(parts)
    # expand to approximate word count
    if word_goal and len(desc.split()) < word_goal:
        extra = (" Tips for differentiation and extension are included so every learner is challenged at the right level. "
                 "Clear directions and answer keys make implementation quick for you and supportive for students. ")
        while len((desc + extra).split()) <= word_goal:
            desc += extra

    return desc.strip()

# -----------------------------
# Streamlit UI
# -----------------------------
st.set_page_config(page_title="TPT SEO Generator", page_icon="🧑‍🏫", layout="wide")

st.title("🧑‍🏫 TPT Title & Description Generator")
st.caption("Generate SEO-optimized titles, descriptions, and keyword clusters for Teachers Pay Teachers resources.")

with st.sidebar:
    st.header("Inputs")
    subject = st.text_input("Subject", value="Math")
    grades = st.multiselect(
        "Grade Level(s)",
        ["Kindergarten", "Grade 1", "Grade 2", "Grade 3", "Grade 4", "Grade 5",
         "Grade 6", "Grade 7", "Grade 8", "High School"],
        default=["Grade 3"]
    )
    resource_type = st.selectbox(
        "Resource Type",
        ["Worksheet", "Activities", "Lesson Plan", "Unit", "Game", "Centers", "Assessment", "Task Cards", "Escape Room"],
        index=0
    )
    focus = st.text_input("Focus / Topic", value="Fractions")
    formats = st.multiselect("Formats", ["Printable", "Digital", "Google Slides", "Self-Checking (Forms)"], default=["Printable", "Digital"])
    standards = st.text_input("Standards (optional)", value="CCSS")
    tone = st.select_slider("Tone", options=["neutral", "professional", "enthusiastic"], value="enthusiastic")
    seasonal = st.checkbox("Seasonal/Context Keywords (Back to School, EOY, Test Prep)", value=True)
    n_variations = st.slider("How many variations?", 1, 12, 5)
    word_goal = st.slider("Description target words", 120, 600, 280, step=20)

    st.header("Batch (optional)")
    batch_focuses = st.text_area("Multiple Focus Topics (one per line)", placeholder="Fractions\nMultiplication Facts\nArea and Perimeter")

    gen_btn = st.button("🚀 Generate")

# Prepare extras
extras = {"seasonal": seasonal, "formats": formats, "standards": standards}

def produce_rows(subject, grades, resource_type, focus, formats, standards, tone, word_goal, n_variations):
    rows = []
    cand = keyword_candidates(subject, grades, resource_type, focus, extras)
    clusters = cluster_keywords(cand)
    focus_terms = uniq([focus.lower(), subject.lower(), resource_type.lower()])
    for _ in range(n_variations):
        title = generate_title(subject, grades, resource_type, focus, formats)
        desc = generate_description(subject, grades, resource_type, focus, formats, standards, tone, word_goal)
        tscore = score_title(title, focus_terms)
        dscore = score_description(desc, focus_terms)
        primary_keywords = ", ".join(uniq(list(itertools.islice(itertools.chain.from_iterable(clusters), 15))))
        tags = ", ".join(uniq(list(itertools.islice(cand, 12))))
        rows.append({
            "title": title,
            "description": desc,
            "keywords": primary_keywords,
            "tags": tags,
            "title_score": tscore["score"],
            "description_score": dscore["score"],
            "title_length": tscore["length"],
            "description_length": dscore["length"],
            "slug": slugify(f"{focus}-{resource_type}-{join_with_and(grades)}-{subject}")
        })
    return rows, clusters

if gen_btn:
    cols = st.columns([1.3, 1, 1])
    with cols[0]:
        st.subheader("Generated Variations")

        focus_list = [focus.strip() for focus in (batch_focuses.splitlines() if batch_focuses.strip() else [focus])]
        all_rows = []
        for f in focus_list:
            rows, clusters = produce_rows(subject, grades, resource_type, f, formats, standards, tone, word_goal, n_variations)
            for i, r in enumerate(rows, start=1):
                with st.container(border=True):
                    st.markdown(f"**Title:** {r['title']}")
                    st.markdown(f"**Description:**\n\n{r['description']}")
                    st.markdown(f"**Keywords:** {r['keywords']}")
                    st.markdown(f"**Tags (short list):** {r['tags']}")
                    st.caption(f"Title score: {r['title_score']} (len {r['title_length']} chars) • "
                               f"Description score: {r['description_score']} (len {r['description_length']} chars) • "
                               f"Slug: `{r['slug']}`")
                all_rows.append({"focus": f, **r})

        # CSV export
        csv_buf = io.StringIO()
        writer = csv.DictWriter(csv_buf, fieldnames=list(all_rows[0].keys()) if all_rows else [])
        writer.writeheader()
        for r in all_rows:
            writer.writerow(r)
        st.download_button("⬇️ Download CSV", data=csv_buf.getvalue().encode("utf-8"),
                           file_name=f"tpt_seo_{date.today().isoformat()}.csv", mime="text/csv")

    with cols[1]:
        st.subheader("Keyword Clusters")
        cand = keyword_candidates(subject, grades, resource_type, focus, extras)
        clusters = cluster_keywords(cand)
        for idx, cluster in enumerate(clusters[:8], start=1):
            with st.container(border=True):
                st.caption(f"Cluster {idx}")
                st.write(", ".join(cluster))

    with cols[2]:
        st.subheader("Guidelines & Checks")
        st.markdown(
            "- Aim for titles **40–100** characters.\n"
            "- Include **grade + resource type + focus** in the title.\n"
            "- Keep descriptions **180–900** chars; front-load benefits.\n"
            "- Sprinkle **long-tail** phrases (e.g., *no-prep*, *centers*, *test prep*).\n"
            "- Use **formats** (Printable, Digital, Google Slides) sparingly to avoid redundancy.\n"
            "- Add **clear CTAs** (how/where to use)."
        )
        st.divider()
        st.write("Quick Checks")
        title_example = generate_title(subject, grades, resource_type, focus, formats)
        desc_example = generate_description(subject, grades, resource_type, focus, formats, standards, tone, word_goal)
        st.code(title_example, language="text")
        st.code(soft_cap(desc_example, 320), language="text")

