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
import re

# ------------------- 1. 网页背景与主题配置 -------------------
# 使用你提供的图片作为背景
BACKGROUND_IMAGE_URL = "https://raw.githubusercontent.com/your-username/your-repo/main/background.jpg" 
# 注意：如果是本地运行，建议将图片放在与代码同级的目录，或者使用有效的网络链接。
# 这里我使用了 CSS 滤镜确保文字在深蓝背景上依然清晰。

THEME_CSS = f"""
<style>
.stApp {{
    background-image: linear-gradient(rgba(10, 25, 47, 0.8), rgba(10, 25, 47, 0.8)), url("https://img.freepik.com/free-vector/outer-space-educational-background_23-2149156643.jpg");
    background-size: cover;
    background-position: center;
    background-attachment: fixed;
    color: #E6F1FF;
}}

/* 卡片容器样式 */
div.block-container {{
    background-color: rgba(23, 42, 69, 0.7);
    padding: 2rem;
    border-radius: 15px;
    border: 1px solid #64FFDA;
}}

/* 标题样式 */
h1, h2, h3 {{
    color: #64FFDA !important;
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
}}

/* 按钮样式 */
.stButton>button {{
    background-color: #64FFDA;
    color: #0A192F;
    border-radius: 5px;
    font-weight: bold;
    border: none;
    width: 100%;
}}
.stButton>button:hover {{
    background-color: #45D1B2;
    color: #0A192F;
}}
</style>
"""

# ------------------- 2. 基础核心函数 -------------------
AUDIO_DIR = "audio"

def ensure_audio_folder():
    os.makedirs(AUDIO_DIR, exist_ok=True)

def generate_tts_audio(word):
    ensure_audio_folder()
    audio_path = os.path.join(AUDIO_DIR, f"{word}.mp3")
    if not os.path.exists(audio_path):
        try:
            tts = gTTS(word, lang='en')
            tts.save(audio_path)
        except: return None
    return audio_path

# 百度翻译
APPID = "20251130002509027" 
KEY = "GtRhonqtdzGpchMRJuCq"

def baidu_translate(q, from_lang="auto", to_lang="zh"):
    if not q or not isinstance(q, str): return q
    if APPID == "" or KEY == "": return q
    salt = str(random.randint(10000, 99999))
    sign = hashlib.md5((APPID + q + salt + KEY).encode("utf-8")).hexdigest()
    url = "https://fanyi-api.baidu.com/api/trans/vip/translate"
    params = {"q": q, "from": from_lang, "to": to_lang, "appid": APPID, "salt": salt, "sign": sign}
    try:
        response = requests.get(url, params=params, timeout=3)
        return response.json()["trans_result"][0]["dst"]
    except: return q

# 文件读取
def read_file(file):
    words = []
    name = file.name.lower()
    try:
        if name.endswith((".txt", ".csv")):
            content = file.read().decode("utf-8", errors="ignore")
            words = content.split()
        elif name.endswith(".docx"):
            doc = docx.Document(io.BytesIO(file.read()))
            for para in doc.paragraphs: words += para.text.split()
        elif name.endswith(".pdf"):
            reader = PyPDF2.PdfReader(io.BytesIO(file.read()))
            for page in reader.pages:
                text = page.extract_text()
                if text: words += text.split()
    except: return []
    return [w.strip() for w in words if w.strip()]

def read_image(image_file):
    try:
        img = Image.open(io.BytesIO(image_file.read()))
        text = pytesseract.image_to_string(img)
        return [w.strip() for w in text.split() if w.strip()]
    except: return []

# ------------------- 3. 游戏模块 -------------------

# 游戏 1: Scrambled Letters
def scramble_word(w):
    letters = list(w)
    if len(letters) <= 1: return w
    scrambled = "".join(random.sample(letters, len(letters)))
    return scrambled if scrambled != w else scramble_word(w)

# 游戏 2: Matching Game
def play_matching_game():
    if "matching_words_generated" not in st.session_state or not st.session_state.matching_words_generated:
        word_en = st.session_state.user_words[:]
        mapping = {w: baidu_translate(w) for w in word_en}
        cn_list = list(mapping.values())
        random.shuffle(word_en)
        random.shuffle(cn_list)
        st.session_state.en_list = word_en
        st.session_state.cn_list = cn_list
        st.session_state.mapping = mapping
        st.session_state.matching_answers = {w: "Select" for w in word_en}
        st.session_state.matching_words_generated = True

    st.subheader("Match English words with Chinese meanings")
    for en_word in st.session_state.en_list:
        st.session_state.matching_answers[en_word] = st.selectbox(
            f"{en_word} ->", ["Select"] + st.session_state.cn_list, key=f"match_{en_word}"
        )

    if st.button("Submit Matching"):
        score = sum(1 for w in st.session_state.en_list if st.session_state.matching_answers[w] == st.session_state.mapping[w])
        st.success(f"Score: {score}/{len(st.session_state.user_words)}")
        st.session_state.game_started = False

# 游戏 3: Listen & Choose
def play_listen_game():
    st.header("🎧 Listen & Choose")
    idx = st.session_state.listen_index
    words = st.session_state.user_words

    if idx < len(words):
        current_word = words[idx]
        if st.button("Play Next Audio"): st.session_state.audio_ready = True
        
        if st.session_state.get("audio_ready"):
            audio_file = generate_tts_audio(current_word)
            if audio_file: st.audio(audio_file)
            user_choice = st.radio("What did you hear?", words, key=f"lc_{idx}")
            if st.button("Submit Answer"):
                if user_choice == current_word:
                    st.session_state.listen_score += 1
                    st.success("Correct!")
                else: st.error(f"Wrong! It was {current_word}")
                st.session_state.listen_index += 1
                st.session_state.audio_ready = False
                st.experimental_rerun()
    else:
        st.success(f"Finished! Score: {st.session_state.listen_score}/10")
        st.session_state.game_started = False

# 游戏 4: Fill-in-the-Blank
def play_fib_game():
    st.subheader("Fill-in-the-Blank")
    idx = st.session_state.fib_idx
    words = st.session_state.user_words
    if "fib_sentences" not in st.session_state:
        st.session_state.fib_sentences = [f"I really like to use the {w} in my daily life." for w in words]

    if idx < len(words):
        sentence = st.session_state.fib_sentences[idx].replace(words[idx], "_____")
        st.write(f"Sentence {idx+1}: {sentence}")
        choice = st.radio("Choose the word:", words, key=f"fib_{idx}")
        if st.button("Submit"):
            if choice == words[idx]:
                st.session_state.fib_score += 1
                st.success("Correct!")
            else: st.error(f"Wrong! Answer: {words[idx]}")
            st.session_state.fib_idx += 1
            st.experimental_rerun()
    else:
        st.success(f"Finished! Score: {st.session_state.fib_score}/10")
        st.session_state.game_started = False

# --- 新增游戏 5: 情境故事大作战 (Story Challenge) ---
def play_story_game():
    st.subheader("📖 Contextual Story Challenge")
    st.write("Put your 10 words into the correct blanks to make the story logical!")
    
    words = st.session_state.user_words
    story_templates = [
        "Once upon a time, a young explorer found a mysterious {0} in the woods.",
        "It was so {1} that everyone in the village came to see it.",
        "The explorer decided to {2} it carefully to understand its secret.",
        "Suddenly, the sky became {3} and a strange sound started.",
        "A wise old man said, 'This is no ordinary {4}, it belongs to the stars!'",
        "The explorer felt {5} and promised to protect the discovery.",
        "He used a {6} to record everything he saw that night.",
        "People started to {7} that the world was about to change.",
        "With a {8} heart, the explorer continued his journey.",
        "In the end, this {9} lesson taught everyone the power of curiosity."
    ]

    if "story_answers" not in st.session_state:
        st.session_state.story_answers = ["Select"] * 10

    col_story, col_bank = st.columns([2, 1])
    with col_bank:
        st.markdown("### 🎯 Word Bank")
        st.write(", ".join([f"`{w}`" for w in words]))
        
    with col_story:
        for i, sentence in enumerate(story_templates):
            # 动态排除已选单词
            selected = [w for idx, w in enumerate(st.session_state.story_answers) if w != "Select" and idx != i]
            options = ["Select"] + [w for w in words if w not in selected]
            
            st.session_state.story_answers[i] = st.selectbox(
                f"Sentence {i+1}", options, 
                index=options.index(st.session_state.story_answers[i]) if st.session_state.story_answers[i] in options else 0,
                key=f"st_{i}", help=sentence.format("___")
            )
            st.write(sentence.format(f":orange[{st.session_state.story_answers[i]}]"))

    if st.button("Submit Story"):
        if "Select" in st.session_state.story_answers:
            st.warning("Fill all blanks!")
        else:
            st.balloons()
            st.success("Masterpiece Complete! Read your story below:")
            full_story = " ".join([s.format(w) for s, w in zip(story_templates, st.session_state.story_answers)])
            st.write(full_story)
            st.session_state.game_started = False

# ------------------- 4. Streamlit 主界面 -------------------
st.set_page_config(page_title="Vocabuddy", layout="wide")
st.markdown(THEME_CSS, unsafe_allow_html=True)

st.title("Hi, Welcome to Vocabuddy 📚")

# 初始化 Session State
if "user_words" not in st.session_state: st.session_state.user_words = []
if "game_started" not in st.session_state: st.session_state.game_started = False

# --- 第一步：输入单词 ---
st.markdown("### 1. Provide 10 words")
c1, c2, c3 = st.columns([2, 1, 1])
with c1:
    txt = st.text_area("Type words (space/enter):", height=100)
    if txt: st.session_state.user_words = [w.strip() for w in txt.split() if w.strip()]
with c2:
    f = st.file_uploader("Upload File", type=["txt","csv","docx","pdf"])
    if f: st.session_state.user_words = read_file(f)
with c3:
    img_f = st.file_uploader("Upload Image (OCR)", type=["png","jpg","jpeg"])
    if img_f: st.session_state.user_words = read_image(img_f)

if st.session_state.user_words:
    st.info(f"Loaded {len(st.session_state.user_words)} words: {', '.join(st.session_state.user_words)}")
    if len(st.session_state.user_words) != 10:
        st.warning("Please adjust to exactly 10 words.")

# --- 第二步：选择并开始游戏 ---
if len(st.session_state.user_words) == 10:
    st.markdown("### 2. Choose a game")
    mode = st.selectbox("Game Mode:", 
        ["Story Challenge", "Scrambled Letters Game", "Matching Game", "Listen & Choose", "Fill-in-the-Blank"])
    
    if st.button("Start Game"):
        st.session_state.game_started = True
        st.session_state.game_mode = mode
        # 重置所有游戏状态
        st.session_state.listen_index = 0
        st.session_state.listen_score = 0
        st.session_state.fib_idx = 0
        st.session_state.fib_score = 0
        st.session_state.story_answers = ["Select"] * 10
        st.session_state.matching_words_generated = False
        random.shuffle(st.session_state.user_words)

# --- 第三步：运行游戏逻辑 ---
if st.session_state.game_started:
    st.divider()
    m = st.session_state.game_mode
    if m == "Story Challenge": play_story_game()
    elif m == "Matching Game": play_matching_game()
    elif m == "Listen & Choose": play_listen_game()
    elif m == "Fill-in-the-Blank": play_fib_game()
    elif m == "Scrambled Letters Game":
        # 简单集成原始拼写逻辑
        st.subheader("Spell the words!")
        for i, w in enumerate(st.session_state.user_words):
            st.text_input(f"Scrambled: {scramble_word(w)}", key=f"sc_{i}")
        if st.button("Finish"): st.session_state.game_started = False
