# app.py
# Requirements suggestions (requirements.txt):
# streamlit
# pytesseract
# Pillow
# python-docx
# PyPDF2
# requests
# pandas

# System packages for Streamlit Cloud (packages.txt):
# tesseract-ocr

import streamlit as st
import random
import pandas as pd
import pytesseract
from PIL import Image
import docx
import PyPDF2
import requests
import hashlib
import io
import shutil

# ------------------- Baidu Translate API -------------------
APPID = ""  # 填入你的 APPID
KEY = ""    # 填入你的 KEY

def baidu_translate(q, from_lang="auto", to_lang="zh"):
    """Safe Baidu translate wrapper: uses timeout and returns fallback if API not configured."""
    if not q or not isinstance(q, str):
        return ""
    # If user didn't provide APPID/KEY, avoid making network call — return original word as fallback.
    if APPID == "" or KEY == "":
        # Return the original word (or you can return f"[No API] {q}")
        return q

    salt = str(random.randint(10000, 99999))
    sign_str = APPID + q + salt + KEY
    sign = hashlib.md5(sign_str.encode("utf-8")).hexdigest()
    url = "https://fanyi-api.baidu.com/api/trans/vip/translate"
    params = {"q": q, "from": from_lang, "to": to_lang,
              "appid": APPID, "salt": salt, "sign": sign}
    try:
        response = requests.get(url, params=params, timeout=3)
        data = response.json()
        if "error_code" in data:
            return q  # fallback to original word if API returns error
        return data["trans_result"][0]["dst"]
    except Exception:
        return q  # on any exception fallback to original word

# ------------------- Reading files -------------------
def read_file(uploaded_file):
    """Read uploaded file (txt/csv/docx/pdf) and return list of words (stripped)."""
    words = []
    name = uploaded_file.name.lower()
    content_bytes = uploaded_file.read()
    try:
        if name.endswith((".txt", ".csv")):
            try:
                content = content_bytes.decode("utf-8")
            except UnicodeDecodeError:
                content = content_bytes.decode("latin-1")
            words = content.split()
        elif name.endswith(".docx"):
            # docx.Document can accept a file-like object
            doc = docx.Document(io.BytesIO(content_bytes))
            for para in doc.paragraphs:
                words += para.text.split()
        elif name.endswith(".pdf"):
            reader = PyPDF2.PdfReader(io.BytesIO(content_bytes))
            for page in reader.pages:
                try:
                    text = page.extract_text()
                except Exception:
                    text = ""
                if text:
                    words += text.split()
    except Exception as e:
        st.error(f"Failed to read uploaded file: {e}")
    return [w.strip() for w in words if w.strip()]

# ------------------- reading from images (OCR) -------------------
def is_tesseract_available():
    """Check whether tesseract binary is available in PATH."""
    return shutil.which("tesseract") is not None

def read_image(image_file):
    """Perform OCR using pytesseract. If not available, show message and return []."""
    # image_file: streamlit uploaded file
    if not is_tesseract_available():
        st.warning("Tesseract OCR not found in the environment. OCR will be skipped. "
                   "To enable OCR, install system package 'tesseract-ocr' or configure Streamlit packages.txt.")
        return []
    try:
        img = Image.open(image_file)
        text = pytesseract.image_to_string(img)
        words = [w.strip() for w in text.split() if w.strip()]
        return words
    except Exception as e:
        st.error(f"OCR failed: {e}")
        return []

# ------------------- define Scramble Game -------------------
def scramble_word(w):
    letters = list(w)
    if len(letters) <= 1:
        return w
    random.shuffle(letters)
    scrambled = "".join(letters)
    # try a few times to avoid infinite loop on repeated letters
    attempts = 0
    while scrambled == w and attempts < 10:
        random.shuffle(letters)
        scrambled = "".join(letters)
        attempts += 1
    return scrambled

# ------------------- Matching Game -------------------
def generate_matching_game(user_words):
    """Generate two shuffled lists and mapping; returns en_shuffled, cn_shuffled, mapping."""
    word_en, word_cn, mapping = [], [], {}
    for w in user_words:
        cn = baidu_translate(w)
        word_en.append(w)
        word_cn.append(cn)
        mapping[w] = cn
    en_shuffled = word_en[:]
    cn_shuffled = word_cn[:]
    random.shuffle(en_shuffled)
    random.shuffle(cn_shuffled)
    return en_shuffled, cn_shuffled, mapping

def prepare_matching_game():
    """Create and store matching lists/mapping in session_state only once per game start."""
    if not st.session_state.get("matching_words_generated", False):
        en_list, cn_list, mapping = generate_matching_game(st.session_state.user_words)
        # store canonical lists
        st.session_state.en_list = en_list
        st.session_state.cn_list = cn_list
        st.session_state.mapping = mapping
        st.session_state.matching_words_generated = True
        # ensure answers cleared
        st.session_state.matching_answers = {w: "Select" for w in en_list}

def play_matching_game():
    prepare_matching_game()

    en_list = st.session_state.en_list
    cn_list = st.session_state.cn_list
    mapping = st.session_state.mapping

    st.subheader("Match English words with their Chinese meaning")

    # We present each English word with a selectbox. Use stable keys.
    for en_word in en_list:
        # Use an explicit key per selectbox so Streamlit persistence works
        key_name = f"matching_{en_word}"
        # Pre-fill with previous selection if exists
        default = st.session_state.matching_answers.get(en_word, "Select")
        choice = st.selectbox(
            label=f"{en_word} →",
            options=["Select"] + cn_list,
            index=(0 if default not in cn_list else (cn_list.index(default)+1)),
            key=key_name,
            help="Select the correct Chinese meaning"
        )
        # Save selection in session_state mapping
        st.session_state.matching_answers[en_word] = choice

    if st.button("Submit Matching Game"):
        score = 0
        results_rows = []
        for w in en_list:
            user_choice = st.session_state.matching_answers.get(w, "Select")
            correct = (user_choice == mapping[w])
            if correct:
                score += 1
            results_rows.append({
                "Word": w,
                "Correct Meaning": mapping[w],
                "Your Answer": user_choice,
                "Correct?": correct
            })
        st.session_state.matching_score = score
        st.success(f"You scored: {score}/{len(en_list)}")
        df = pd.DataFrame(results_rows)
        st.subheader("Your results")
        st.table(df)
        # after finishing, mark game as finished so it doesn't keep the same UI as active game
        st.session_state.game_started = False

# ------------------- Streamlit Design -------------------
st.set_page_config(page_title="Vocabuddy", layout="centered")
st.title("Hi — Welcome to Vocabuddy")

# ------------------- session_state defaults -------------------
if "user_words" not in st.session_state:
    st.session_state.user_words = []
if "game_started" not in st.session_state:
    st.session_state.game_started = False
if "game_mode" not in st.session_state:
    st.session_state.game_mode = None

# Scrambled Game state
if "scramble_index" not in st.session_state:
    st.session_state.scramble_index = 0
if "scramble_score" not in st.session_state:
    st.session_state.scramble_score = 0
if "scramble_answers" not in st.session_state:
    st.session_state.scramble_answers = []
if "scramble_scrambled" not in st.session_state:
    st.session_state.scramble_scrambled = []

# Matching generation flag and storage
if "matching_words_generated" not in st.session_state:
    st.session_state.matching_words_generated = False
if "matching_answers" not in st.session_state:
    st.session_state.matching_answers = {}
if "matching_score" not in st.session_state:
    st.session_state.matching_score = 0

# ------------------- Users Input -------------------
st.markdown("### 1) Provide 10 words")
words_input = st.text_area("Please enter 10 words (use space or press Enter for each)", height=120)
if words_input:
    st.session_state.user_words = [w.strip() for w in words_input.split() if w.strip()]

col1, col2 = st.columns(2)
with col1:
    uploaded_file = st.file_uploader("Upload a file (txt/csv/docx/pdf)", type=["txt","csv","docx","pdf"])
    if uploaded_file:
        st.session_state.user_words = read_file(uploaded_file)
with col2:
    uploaded_image = st.file_uploader("Upload an image (OCR)", type=["png","jpg","jpeg","bmp","tiff","tif"])
    if uploaded_image:
        ocr_words = read_image(uploaded_image)
        if ocr_words:
            st.session_state.user_words = ocr_words

# ------------------- show words and validate count -------------------
if st.session_state.user_words:
    st.write("Current words:", st.session_state.user_words)
    if len(st.session_state.user_words) != 10:
        st.warning("Please provide exactly 10 words (current count: {})".format(len(st.session_state.user_words)))

# ------------------- choose game mode -------------------
if st.session_state.user_words and len(st.session_state.user_words) == 10:
    st.markdown("### 2) Choose a game mode")
    st.session_state.game_mode = st.selectbox(
        "Choose game mode",
        ["Scrambled Letters Game", "Matching Game"],
        index=0
    )

    if st.button("Start Game"):
        # initialize everything needed for both games
        st.session_state.game_started = True

        # Scramble initialization
        st.session_state.scramble_index = 0
        st.session_state.scramble_score = 0
        st.session_state.scramble_answers = [""] * len(st.session_state.user_words)
        st.session_state.scramble_scrambled = [""] * len(st.session_state.user_words)

        # Matching initialization
        st.session_state.matching_words_generated = False
        st.session_state.matching_answers = {}
        st.session_state.matching_score = 0

        # shuffle order for games where appropriate
        random.shuffle(st.session_state.user_words)
        st.experimental_rerun()  # restart to ensure UI updates with new session_state

# ------------------- Scrambled Game -------------------
if st.session_state.game_started and st.session_state.game_mode == "Scrambled Letters Game":
    st.markdown("### Scrambled Letters Game — Spell the word in correct order")
    idx = st.session_state.scramble_index

    if idx < len(st.session_state.user_words):
        current_word = st.session_state.user_words[idx]

        if not st.session_state.scramble_scrambled[idx]:
            scrambled = scramble_word(current_word)
            st.session_state.scramble_scrambled[idx] = scrambled
        else:
            scrambled = st.session_state.scramble_scrambled[idx]

        def submit_answer():
            answer = st.session_state.get("scramble_input", "")
            st.session_state.scramble_answers[idx] = answer.strip()
            if answer.strip().lower() == current_word.lower():
                st.session_state.scramble_score += 1
            st.session_state.scramble_index += 1
            st.session_state.scramble_input = ""
            st.experimental_rerun()

        st.text_input(
            f"Word {idx + 1}: {scrambled}",
            key="scramble_input",
            on_change=submit_answer,
            placeholder="Type the correct word and press Enter"
        )
    else:
        st.success(f"Game finished! Your score: {st.session_state.scramble_score}/{len(st.session_state.user_words)}")
        data = {
            "Word": st.session_state.user_words,
            "Scrambled": st.session_state.scramble_scrambled,
            "Your Answer": st.session_state.scramble_answers,
            "Correct?": [
                ua.strip().lower() == w.lower()
                for ua, w in zip(st.session_state.scramble_answers, st.session_state.user_words)
            ]
        }
        df = pd.DataFrame(data)
        st.subheader("Your accuracy")
        st.table(df)
        st.session_state.game_started = False

# ------------------- Matching Game -------------------
if st.session_state.game_started and st.session_state.game_mode == "Matching Game":
    play_matching_game()

# ------------------- Footer / tips -------------------
st.markdown("---")
st.markdown("**Tips:**")
st.markdown("- If you want to use OCR (pytesseract) on Streamlit Cloud, add `tesseract-ocr` to `packages.txt` and include `pytesseract` in `requirements.txt`.")
st.markdown("- Fill `APPID` and `KEY` for Baidu Translate to enable Chinese translations. If left empty the app will fall back to showing the original English words (no external requests).")
