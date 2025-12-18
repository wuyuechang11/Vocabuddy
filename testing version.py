import streamlit as st
import random
import pandas as pd
import pytesseract
from PIL import Image, UnidentifiedImageError
import docx
import PyPDF2
import requests
import hashlib
import io
from gtts import gTTS
import os

# ------------------- TTS Audio Generation -------------------
AUDIO_DIR = "audio"

def ensure_audio_folder():
    os.makedirs(AUDIO_DIR, exist_ok=True)

def generate_tts_audio(word):
    ensure_audio_folder()
    audio_path = os.path.join(AUDIO_DIR, f"{word}.mp3")
    if not os.path.exists(audio_path):
        tts = gTTS(word, lang="en")
        tts.save(audio_path)
    return audio_path

# ------------------- Baidu Translate API -------------------
APPID = "20251130002509027"
KEY = "GtRhonqtdzGpchMRJuCq"

def baidu_translate(q, from_lang="auto", to_lang="zh"):
    if not q:
        return q
    if APPID == "" or KEY == "":
        return q
    salt = str(random.randint(10000, 99999))
    sign = hashlib.md5((APPID + q + salt + KEY).encode()).hexdigest()
    url = "https://fanyi-api.baidu.com/api/trans/vip/translate"
    params = {"q": q, "from": from_lang, "to": to_lang,
              "appid": APPID, "salt": salt, "sign": sign}
    try:
        r = requests.get(url, params=params, timeout=3)
        data = r.json()
        return data["trans_result"][0]["dst"]
    except Exception:
        return q

# ------------------- File Reading -------------------
def read_file(file):
    words = []
    name = file.name.lower()
    try:
        if name.endswith((".txt", ".csv")):
            words = file.read().decode("utf-8", errors="ignore").split()
        elif name.endswith(".docx"):
            doc = docx.Document(io.BytesIO(file.read()))
            for p in doc.paragraphs:
                words += p.text.split()
        elif name.endswith(".pdf"):
            reader = PyPDF2.PdfReader(io.BytesIO(file.read()))
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    words += text.split()
    except Exception:
        return []
    return [w.strip() for w in words if w.strip()]

def read_image(image_file):
    try:
        img = Image.open(io.BytesIO(image_file.read()))
        text = pytesseract.image_to_string(img)
        return [w.strip() for w in text.split() if w.strip()]
    except Exception:
        return []

# ------------------- Scramble Game -------------------
def scramble_word(w):
    letters = list(w)
    random.shuffle(letters)
    return "".join(letters)

# ------------------- Matching Game -------------------
def generate_matching_game_once(user_words):
    en, cn, mapping = [], [], {}
    for w in user_words:
        if w in st.session_state.translation_cache:
            trans = st.session_state.translation_cache[w]
        else:
            trans = baidu_translate(w)
            st.session_state.translation_cache[w] = trans
        en.append(w)
        cn.append(trans)
        mapping[w] = trans
    random.shuffle(en)
    random.shuffle(cn)
    return en, cn, mapping

def play_matching_game():
    if "matching_generated" not in st.session_state:
        en, cn, mapping = generate_matching_game_once(st.session_state.user_words)
        st.session_state.en = en
        st.session_state.cn = cn
        st.session_state.map = mapping
        st.session_state.answers = {}
        st.session_state.matching_generated = True

    st.subheader("Match English words with Chinese meaning")

    for w in st.session_state.en:
        sel = st.selectbox(w, ["Select"] + st.session_state.cn, key=f"m_{w}")
        st.session_state.answers[w] = sel

    if st.button("Submit Matching"):
        score = sum(
            st.session_state.answers[w] == st.session_state.map[w]
            for w in st.session_state.en
        )
        st.success(f"Score: {score}/10")
        st.session_state.game_started = False

# ------------------- Scenario-based Sentence Choice -------------------
def play_scenario_game():
    st.subheader("Word in Context")

    words = st.session_state.user_words

    if "scenario_idx" not in st.session_state:
        st.session_state.scenario_idx = 0
        st.session_state.scenario_score = 0
        st.session_state.scenario_order = random.sample(words, len(words))

    idx = st.session_state.scenario_idx

    if idx >= len(words):
        st.success(f"Game finished! Score: {st.session_state.scenario_score}/10")
        st.session_state.game_started = False
        return

    word = st.session_state.scenario_order[idx]

    st.markdown(f"**Target word:** {word}")
    st.info("You are writing an academic sentence.")

    sentences = [
        (f"The researcher used the word {word} appropriately in the study.", True),
        (f"I very {word} happy yesterday.", False),
        (f"The {word} was goodly nice.", False),
    ]

    random.shuffle(sentences)
    options = [s[0] for s in sentences]
    correct = [s[0] for s in sentences if s[1]][0]

    choice = st.radio("Choose the correct sentence:", options)

    if st.button("Submit"):
        if choice == correct:
            st.success("Correct usage!")
            st.session_state.scenario_score += 1
        else:
            st.error("Incorrect. Pay attention to grammar and context.")
        st.session_state.scenario_idx += 1
        st.rerun()

# ------------------- Streamlit UI -------------------
st.set_page_config(page_title="Vocabuddy", layout="centered")
st.title("Hi, Welcome to Vocabuddy")

if "user_words" not in st.session_state:
    st.session_state.user_words = []
if "translation_cache" not in st.session_state:
    st.session_state.translation_cache = {}
if "game_started" not in st.session_state:
    st.session_state.game_started = False

# ------------------- User Input -------------------
st.markdown("### 1. Provide 10 words")
words_input = st.text_area("Enter 10 words")
if words_input:
    st.session_state.user_words = [w for w in words_input.split() if w]

# ------------------- Choose Game -------------------
if len(st.session_state.user_words) == 10:
    st.markdown("### 2. Choose a game")
    mode = st.selectbox(
        "Game mode",
        ["Scrambled Letters Game", "Matching Game", "Listen & Choose", "Word in Context"]
    )

    if st.button("Start Game"):
        st.session_state.game_started = True
        st.session_state.game_mode = mode

# ------------------- Game Routing -------------------
if st.session_state.game_started:
    if st.session_state.game_mode == "Word in Context":
        play_scenario_game()
