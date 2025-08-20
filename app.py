import streamlit as st
import nltk
import easyocr
import tempfile
from PIL import Image
from collections import Counter
import re

# Download NLTK data
nltk.download("punkt")
nltk.download("wordnet")
nltk.download("omw-1.4")

# ------------------------------------------------------------
# Page Config
# ------------------------------------------------------------
st.set_page_config(
    page_title="TPT SEO Generator",
    page_icon="📚",
    layout="wide"
)

st.title("📚 TPT SEO Generator with Thumbnail Support & Keywords")
st.write("Generate SEO-optimized titles, descriptions, and keyword clusters for Teachers Pay Teachers resources.")

# ------------------------------------------------------------
# Description generator
# ------------------------------------------------------------
def generate_description(subject, grades, resource_type, focus, formats, standards, word_goal):
    grade_text = ", ".join(grades)
    format_text = " and ".join(formats)

    desc = (
        f"This {resource_type.lower()} is designed for {grade_text} students learning {subject.lower()}. "
        f"It provides engaging activities on {focus.lower()} with {format_text} options, making it easy to use "
        f"in the classroom or for homework. "
    )

    if standards:
        desc += f"This resource is fully aligned with {standards}, ensuring it meets curriculum expectations. "

    desc += (
        f"Inside, you'll find step-by-step materials that build student confidence, "
        f"support differentiation, and save you preparation time. "
        f"Perfect for guided practice, independent work, or review. "
    )

    # Pad description until target word count
    while len(desc.split()) < word_goal:
        desc += (
            " Teachers love how flexible and engaging this resource is, making it a must-have for "
            "any classroom looking to strengthen skills while keeping students motivated. "
        )

    return desc.strip()

# ------------------------------------------------------------
# Keyword extractor
# ------------------------------------------------------------
def extract_keywords(text, n=15):
    # Clean text
    text = text.lower()
    words = re.findall(r"[a-zA-Z]+", text)

    # Remove stopwords
    stopwords = set(nltk.corpus.stopwords.words("english"))
    words = [w for w in words if w not in stopwords and len(w) > 2]

    # Count frequency
    freq = Counter(words)
    return [w for w, _ in freq.most_common(n)]

# ------------------------------------------------------------
# Sidebar inputs
# ------------------------------------------------------------
with st.sidebar:
    st.header("Inputs")
    subject = st.text_input("Subject", value="Math")

    grades = st.multiselect(
        "Grade Level(s)",
        [
            "Preschool",
            "Kindergarten",
            "1st Grade",
            "2nd Grade",
            "3rd Grade",
            "4th Grade",
            "5th Grade",
            "6th Grade",
            "7th Grade",
            "8th Grade",
            "9th Grade",
            "10th Grade",
            "11th Grade",
            "12th Grade",
            "Homeschool",
            "Staff"
        ],
        default=["3rd Grade"]
    )

    resource_type = st.selectbox(
        "Resource Type",
        ["Worksheet", "Activities", "Lesson Plan", "Task Cards", "Quiz", "Project", "Assessment"],
        index=0
    )

    focus = st.text_input("Focus / Topic", value="Fractions")
    formats = st.multiselect("Formats", ["Printable", "Digital"], default=["Printable", "Digital"])
    standards = st.text_input("Standards (optional)", value="CCSS")
    word_goal = st.slider("Description target words", 120, 600, 280, step=20)
    n_variations = st.slider("How many variations?", 1, 5, 3)

    st.header("Thumbnail Upload (optional)")
    thumbnail_file = st.file_uploader("Upload a product thumbnail (PNG or JPEG)", type=["png", "jpeg"])

# ------------------------------------------------------------
# Process Thumbnail with EasyOCR
# ------------------------------------------------------------
thumbnail_text = ""
if thumbnail_file is not None:
    try:
        image = Image.open(thumbnail_file)
        st.image(image, caption="Uploaded Thumbnail", use_container_width=True)

        # Save to temp file for OCR
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_file:
            image.save(tmp_file.name)
            reader = easyocr.Reader(['en'], verbose=False)
            result = reader.readtext(tmp_file.name, detail=0)
            thumbnail_text = " ".join(result)

        if thumbnail_text:
            st.success("Extracted text from thumbnail to boost SEO keywords!")
            st.write(thumbnail_text)
    except Exception as e:
        st.error(f"Error reading thumbnail: {e}")

# ------------------------------------------------------------
# Generate output
# ------------------------------------------------------------
if st.button("Generate SEO Titles & Descriptions"):
    st.subheader("Generated Variations")

    base_text = f"{subject} {focus} {resource_type} {' '.join(grades)} {thumbnail_text}"

    for i in range(n_variations):
        title = f"{subject} {focus} {resource_type} for {', '.join(grades)}"
        if thumbnail_text:
            title += f" | {thumbnail_text[:40]}"

        description = generate_description(
            subject, grades, resource_type, focus, formats, standards, word_goal
        )

        # Extract SEO keywords
        keywords = extract_keywords(base_text + " " + description, n=12)

        st.markdown(f"### ✨ Variation {i+1}")
        st.markdown(f"**Title:** {title}")
        st.write(description)
        st.markdown("**SEO Keywords:** " + ", ".join(keywords))

