import streamlit as st
import random
import pandas as pd
import pytesseract
from PIL import Image
import docx
import PyPDF2
import requests
import hashlib

# ------------------- Baidu Translate API -------------------
APPID = "20251130002509027"
KEY = "GtRhonqtdzGpchMRJuCq"

def baidu_translate(q, from_lang="auto", to_lang="zh"):
    if not q or not isinstance(q, str):
        return "Error: empty input"
    salt = str(random.randint(10000, 99999))
    sign_str = APPID + q + salt + KEY
    sign = hashlib.md5(sign_str.encode("utf-8")).hexdigest()
    url = "https://fanyi-api.baidu.com/api/trans/vip/translate"
    params = {"q": q, "from": from_lang, "to": to_lang,
              "appid": APPID, "salt": salt, "sign": sign}
    try:
        response = requests.get(url, params=params)
        data = response.json()
        if "error_code" in data:
            return f"Error: {data['error_code']} - {data.get('error_msg','')}"
        return data["trans_result"][0]["dst"]
    except Exception as e:
        return f"Request failed: {str(e)}"

# ------------------- Reading files -------------------
def read_file(file):
    words = []
    if file.name.endswith((".txt", ".csv")):
        content = file.read().decode("utf-8")
        words = content.split()
    elif file.name.endswith(".docx"):
        doc = docx.Document(file)
        for para in doc.paragraphs:
            words += para.text.split()
    elif file.name.endswith(".pdf"):
        reader = PyPDF2.PdfReader(file)
        for page in reader.pages:
            text = page.extract_text()
            if text:
                words += text.split()
    return [w.strip() for w in words if w.strip()]

# ------------------- reading from images -------------------
def read_image(image_file):
    text = pytesseract.image_to_string(Image.open(image_file))
    words = [w.strip() for w in text.split() if w.strip()]
    return words

# ------------------- define Scramble Game -------------------
def scramble_word(w):
    letters = list(w)
    random.shuffle(letters)
    scrambled = "".join(letters)
    while scrambled == w:
        random.shuffle(letters)
        scrambled = "".join(letters)
    return scrambled

# ------------------- Streamlit Design -------------------
st.title("Hi, Welcome Vocabuddy ")

# ------------------- session_state，a function to keep data in Streamlit -------------------
if "user_words" not in st.session_state:
    st.session_state.user_words = []
if "game_started" not in st.session_state:
    st.session_state.game_started = False
if "game_mode" not in st.session_state:
    st.session_state.game_mode = None

# Status of Scrambled Game 
if "scramble_index" not in st.session_state:
    st.session_state.scramble_index = 0
if "scramble_score" not in st.session_state:
    st.session_state.scramble_score = 0
if "scramble_answers" not in st.session_state:
    st.session_state.scramble_answers = [""] * 10  # save users' answers
if "scramble_scrambled" not in st.session_state:
    st.session_state.scramble_scrambled = [""] * 10  # make sure the questions are out of order

# ------------------- Users Input -------------------
words_input = st.text_area("please enter 10 words（use space or enter in another line）")
if words_input:
    st.session_state.user_words = [w.strip() for w in words_input.split() if w.strip()]

uploaded_file = st.file_uploader("upload a file(txt/csv/docx/pdf)", type=["txt","csv","docx","pdf"])
if uploaded_file:
    st.session_state.user_words = read_file(uploaded_file)

uploaded_image = st.file_uploader("upload an image(OCR)", type=["png","jpg","jpeg","bmp","tiff","tif"])
if uploaded_image:
    st.session_state.user_words = read_image(uploaded_image)

# ------------------- make the amount of 10 words-------------------
if st.session_state.user_words:
    st.write(f"The words: {st.session_state.user_words}")
    if len(st.session_state.user_words) != 10:
        st.warning("please upload only 10 words")

# ------------------- choose game mode-------------------
if st.session_state.user_words and len(st.session_state.user_words) == 10:
    st.session_state.game_mode = st.selectbox("choose game mode", ["Scrambled Letters Game"], index=0)

    if st.button("game start"):
        st.session_state.game_started = True
        st.session_state.scramble_index = 0
        st.session_state.scramble_score = 0
        st.session_state.scramble_answers = [""] * 10
        st.session_state.scramble_scrambled = [""] * 10
        random.shuffle(st.session_state.user_words)

# ------------------- Scrambled Game -------------------
if st.session_state.game_started and st.session_state.game_mode == "Scrambled Letters Game":
    st.subheader("spell the word in correct order")
    idx = st.session_state.scramble_index

    if idx < len(st.session_state.user_words):
        current_word = st.session_state.user_words[idx]

        # make the word list out of order
        if not st.session_state.scramble_scrambled[idx]:
            scrambled = scramble_word(current_word)
            st.session_state.scramble_scrambled[idx] = scrambled
        else:
            scrambled = st.session_state.scramble_scrambled[idx]

        # get users'answer and save data
        def submit_answer():
            answer = st.session_state.scramble_input  # get text_input 
            st.session_state.scramble_answers[idx] = answer.strip()
            # make sure it ignores upper/lower letters
            if answer.strip().lower() == current_word.lower():
                st.session_state.scramble_score += 1
            st.session_state.scramble_index += 1
            # clear input
            st.session_state.scramble_input = ""

        # allow users to use Enter to upload input
        st.text_input(
            f"Word {idx + 1}: {scrambled}",
            key="scramble_input",
            on_change=submit_answer
        )

    else:
        st.success(f"Game finished your score: {st.session_state.scramble_score}/10")

        # use a table to show the result of the game
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
