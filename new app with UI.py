import streamlit as st
import random
import pandas as pd
import os
import io
import hashlib
from gtts import gTTS
import docx
import PyPDF2
import requests
from PIL import Image, UnidentifiedImageError
import pytesseract
import base64

# ------------------ 页面配置 ------------------
st.set_page_config(
    page_title="Vocabuddy 🎉",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ------------------ 背景图片 & 样式 ------------------
def set_bg_image(image):
    """
    设置页面背景
    image: 本地路径或 BytesIO 对象
    """
    if isinstance(image, str):
        with open(image, "rb") as f:
            img_bytes = f.read()
    else:
        img_bytes = image.read()
    encoded = base64.b64encode(img_bytes).decode()
    st.markdown(
        f"""
        <style>
        .stApp {{
            background-image: url("data:image/png;base64,{encoded}");
            background-size: cover;
            background-attachment: fixed;
            font-family: 'Comic Sans MS', sans-serif;
            color: #000000;
        }}
        .stButton>button {{
            background-color: #4CAF50;
            color: white;
            border-radius: 12px;
            height: 45px;
            width: 200px;
            font-size: 16px;
            margin-top:5px;
        }}
        .card {{
            background-color: #ffffffcc;
            padding: 20px;
            border-radius: 15px;
            margin-bottom: 15px;
            box-shadow: 3px 3px 15px #aaaaaa;
        }}
        </style>
        """,
        unsafe_allow_html=True
    )

# ------------------ 使用背景图片 ------------------
# 将图片放在项目文件夹里，例如 assets/background.png
set_bg_image("background.png")  # <-- 替换为你自己的图片

# ------------------ Sidebar ------------------
st.sidebar.title("🧩 Vocabuddy Menu")
st.sidebar.write("Welcome! Choose your game mode:")
game_mode = st.sidebar.radio("Game Mode", [
    "Scrambled Letters Game", 
    "Matching Game", 
    "Listen & Choose", 
    "Fill-in-the-Blank"
])
st.sidebar.markdown("---")
st.sidebar.write("💡 Tips:")
st.sidebar.write("- Provide exactly 10 words to play.")
st.sidebar.write("- Use Upload or Text Area for word input.")
st.sidebar.write("- Click Start Game to reset the game state.")

# ------------------ Audio / TTS ------------------
AUDIO_DIR = "audio"
os.makedirs(AUDIO_DIR, exist_ok=True)

def generate_tts_audio(word):
    path = os.path.join(AUDIO_DIR, f"{word}.mp3")
    if not os.path.exists(path):
        tts = gTTS(word, lang='en')
        tts.save(path)
    return path

# ------------------ Baidu Translate API ------------------
APPID = ""  # fill your APPID
KEY = ""    # fill your KEY

def baidu_translate(q, from_lang="auto", to_lang="zh"):
    if not q or not isinstance(q, str): return q
    if not APPID or not KEY: return q
    salt = str(random.randint(10000, 99999))
    sign = hashlib.md5(f"{APPID}{q}{salt}{KEY}".encode("utf-8")).hexdigest()
    try:
        r = requests.get("https://fanyi-api.baidu.com/api/trans/vip/translate",
                         params={"q":q,"from":from_lang,"to":to_lang,"appid":APPID,"salt":salt,"sign":sign},
                         timeout=3)
        data = r.json()
        if "trans_result" in data: return data["trans_result"][0]["dst"]
    except: pass
    return q

# ------------------ Reading Files & Images ------------------
def read_file(file):
    words = []
    name = file.name.lower()
    try:
        if name.endswith((".txt",".csv")):
            content = file.read().decode("utf-8", errors="ignore")
            words = content.split()
        elif name.endswith(".docx"):
            doc = docx.Document(io.BytesIO(file.read()))
            for para in doc.paragraphs:
                words += para.text.split()
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

# ------------------ Fill-in-the-Blank ------------------
def get_example_sentence(word):
    templates = [
        f"I really like the {word} in the park.",
        f"She bought a new {word} yesterday.",
        f"The {word} is very expensive.",
        f"Do you know where the {word} is?",
        f"He gave me a {word} as a gift.",
    ]
    return random.choice(templates)

def create_blank_sentence(word, sentence):
    import re
    return re.sub(rf"\b{re.escape(word)}\b","_____",sentence,flags=re.IGNORECASE)

# ------------------ Scramble ------------------
def scramble_word(w):
    if len(w)<=1: return w
    letters=list(w)
    random.shuffle(letters)
    scrambled = "".join(letters)
    tries=0
    while scrambled==w and tries<10:
        random.shuffle(letters)
        scrambled="".join(letters)
        tries+=1
    return scrambled

# ------------------ Matching ------------------
def generate_matching(user_words):
    en_list, cn_list, mapping = [], [], {}
    if "translation_cache" not in st.session_state:
        st.session_state.translation_cache={}
    for w in user_words:
        cn = st.session_state.translation_cache.get(w) or baidu_translate(w)
        st.session_state.translation_cache[w]=cn
        en_list.append(w)
        cn_list.append(cn)
        mapping[w]=cn
    random.shuffle(en_list)
    random.shuffle(cn_list)
    return en_list, cn_list, mapping

# ------------------ Session Defaults ------------------
if "user_words" not in st.session_state: st.session_state.user_words=[]
if "game_started" not in st.session_state: st.session_state.game_started=False

def init_game_state():
    st.session_state.scramble_index=0
    st.session_state.scramble_score=0
    st.session_state.scramble_answers=[""]*10
    st.session_state.scramble_scrambled=[""]*10

    st.session_state.listen_index=0
    st.session_state.listen_score=0
    st.session_state.listen_answers=[""]*10

    st.session_state.fib_idx=0
    st.session_state.fib_score=0
    st.session_state.fib_sentences=[get_example_sentence(w) for w in st.session_state.user_words]

    st.session_state.matching_words_generated=False
    st.session_state.matching_answers={}

# ------------------ Word Input ------------------
st.markdown("## 1️⃣ Provide 10 words")
words_input = st.text_area("Enter 10 words (space or newline separated)", height=120)
if words_input:
    st.session_state.user_words = [w.strip() for w in words_input.split() if w.strip()]
uploaded_file = st.file_uploader("Upload a file (txt/csv/docx/pdf)", type=["txt","csv","docx","pdf"])
if uploaded_file:
    words_file = read_file(uploaded_file)
    if words_file: st.session_state.user_words = words_file
uploaded_image = st.file_uploader("Upload an image (OCR)", type=["png","jpg","jpeg","bmp","tiff","tif"])
if uploaded_image:
    words_img = read_image(uploaded_image)
    if words_img: st.session_state.user_words = words_img

if st.session_state.user_words:
    st.markdown("### Current Words")
    for i,w in enumerate(st.session_state.user_words[:10]):
        st.markdown(f'<div class="card">Word {i+1}: <b>{w}</b></div>', unsafe_allow_html=True)
    if len(st.session_state.user_words)!=10:
        st.warning("Please provide exactly 10 words to play (only first 10 used).")

# ------------------ Start Game ------------------
if st.button("Start Game") and len(st.session_state.user_words)==10:
    st.session_state.game_started=True
    init_game_state()
    st.balloons()

# ------------------ Game Rendering ------------------
if st.session_state.get("game_started",False):
    st.markdown(f"## 🎮 {game_mode}")

    # ----------------- Scrambled Letters -----------------
    if game_mode=="Scrambled Letters Game":
        idx=st.session_state.get("scramble_index",0)
        user_words=st.session_state.user_words[:10]
        if idx<10 and idx<len(user_words):
            word=user_words[idx]
            scrambled=st.session_state.scramble_scrambled[idx] or scramble_word(word)
            st.session_state.scramble_scrambled[idx]=scrambled
            st.markdown(f'<div class="card">Word {idx+1}: <b>{scrambled}</b></div>', unsafe_allow_html=True)
            ans=st.text_input("Your Answer", key=f"scr_input_{idx}")
            if st.button("Submit", key=f"scr_submit_{idx}"):
                st.session_state.scramble_answers[idx] = ans.strip()
                if ans.strip().lower()==word.lower(): st.session_state.scramble_score+=1; st.success("🎉 Correct!")
                else: st.error(f"❌ Wrong! Correct: {word}")
                st.session_state.scramble_index+=1
                st.experimental_rerun()
        else:
            st.success(f"Game Finished! Score: {st.session_state.scramble_score}/10")
            st.balloons()

    # ----------------- Listen & Choose -----------------
    elif game_mode=="Listen & Choose":
        idx=st.session_state.get("listen_index",0)
        user_words=st.session_state.user_words[:10]
        if idx<10 and idx<len(user_words):
            word=user_words[idx]
            audio_file=generate_tts_audio(word)
            st.audio(audio_file)
            st.markdown(f'<div class="card">Word {idx+1}</div>', unsafe_allow_html=True)
            choice=st.radio("Which word did you hear?", user_words, key=f"listen_{idx}")
            if st.button("Submit", key=f"listen_submit_{idx}"):
                st.session_state.listen_answers[idx]=choice
                if choice==word: st.session_state.listen_score+=1; st.success("🎉 Correct!")
                else: st.error(f"❌ Wrong! Correct: {word}")
                st.session_state.listen_index+=1
                st.experimental_rerun()
        else:
            st.success(f"Game Finished! Score: {st.session_state.listen_score}/10")
            df=pd.DataFrame({"Word":user_words,"Your Answer":st.session_state.listen_answers,
                             "Correct?":[a==w for a,w in zip(st.session_state.listen_answers,user_words)]})
            st.table(df)
            st.balloons()

    # ----------------- Fill-in-the-Blank -----------------
    elif game_mode=="Fill-in-the-Blank":
        idx=st.session_state.get("fib_idx",0)
        user_words=st.session_state.user_words[:10]
        if idx<10 and idx<len(user_words):
            word=user_words[idx]
            sentence=st.session_state.fib_sentences[idx]
            blanked=create_blank_sentence(word,sentence)
            st.markdown(f'<div class="card">Sentence {idx+1}: {blanked}</div>', unsafe_allow_html=True)
            choice=st.radio("Choose the correct word:", user_words, key=f"fib_{idx}")
            if st.button("Submit", key=f"fib_submit_{idx}"):
                if choice.lower()==word.lower(): st.session_state.fib_score+=1; st.success("🎉 Correct!")
                else: st.error(f"❌ Wrong! Correct: {word}")
                st.session_state.fib_idx+=1
                st.experimental_rerun()
        else:
            st.success(f"Game Finished! Score: {st.session_state.fib_score}/10")
            st.balloons()

    # ----------------- Matching Game -----------------
    elif game_mode=="Matching Game":
        if not st.session_state.get("matching_words_generated",False):
            en_list, cn_list, mapping=generate_matching(st.session_state.user_words[:10])
            st.session_state.en_list=en_list
            st.session_state.cn_list=cn_list
            st.session_state.mapping=mapping
            st.session_state.matching_answers={w:"Select" for w in en_list}
            st.session_state.matching_words_generated=True

        for en_word in st.session_state.en_list:
            sel=st.selectbox(f"{en_word} ->", ["Select"]+st.session_state.cn_list,
                             index=(0 if st.session_state.matching_answers[en_word] not in ["Select"]+st.session_state.cn_list else (["Select"]+st.session_state.cn_list).index(st.session_state.matching_answers[en_word])),
                             key=f"match_{en_word}")
            st.session_state.matching_answers[en_word]=sel

        if st.button("Submit Matching Game"):
            score=sum([1 for w in st.session_state.en_list if st.session_state.matching_answers[w]==st.session_state.mapping[w]])
            st.success(f"Score: {score}/10")
            df=pd.DataFrame({
                "Word":st.session_state.en_list,
                "Correct Meaning":[st.session_state.mapping[w] for w in st.session_state.en_list],
                "Your Answer":[st.session_state.matching_answers[w] for w in st.session_state.en_list],
                "Correct?":[st.session_state.matching_answers[w]==st.session_state.mapping[w] for w in st.session_state.en_list]
            })
            st.table(df)
            st.balloons()
