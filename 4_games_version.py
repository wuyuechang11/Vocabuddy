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
import time
import re

# ------------------- TTS Audio Generation -------------------
#use gTTS (Google Text-to-Speech) library to generate English pronunciation audio for vocabulary words

AUDIO_DIR = "audio"

def ensure_audio_folder():
    os.makedirs(AUDIO_DIR, exist_ok=True)

def generate_tts_audio(word):
    """If audio doesn't exist, generate TTS."""
    ensure_audio_folder()
    audio_path = os.path.join(AUDIO_DIR, f"{word}.mp3")

    if not os.path.exists(audio_path):
        tts = gTTS(word, lang='en')
        tts.save(audio_path)

    return audio_path

# ------------------- Baidu Translate API -------------------
# Facilitate English-to-Chinese translation for vocabulary reinforcement

def baidu_translate(q, from_lang="auto", to_lang="zh"):
    """Translate q using Baidu Translate. Returns q itself on failure."""
    if not q or not isinstance(q, str):
        return q
    # If user hasn't provided API keys, skip actual API calls and return the original word
    if APPID == "" or KEY == "":
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
            # fallback to original word if API returns an error
            return q
        return data["trans_result"][0]["dst"]
    except Exception:
        return q

# ------------------- Reading files -------------------
#Extract vocabulary words from various document formats， Supported Formats: .txt, .csv, .docx, 

def read_file(file):
    """Read words from txt/csv/docx/pdf file-like object (Streamlit UploadFile)."""
    words = []
    name = file.name.lower()
    try:
        if name.endswith((".txt", ".csv")):
            # UploadFile.read() returns bytes
            content = file.read().decode("utf-8", errors="ignore")
            words = content.split()
        elif name.endswith(".docx"):
            # docx.Document accepts a path or a file-like object (works in-memory)
            doc = docx.Document(io.BytesIO(file.read()))
            for para in doc.paragraphs:
                words += para.text.split()
        elif name.endswith(".pdf"):
            reader = PyPDF2.PdfReader(io.BytesIO(file.read()))
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    words += text.split()
    except Exception:
        # if any error reading, return empty list (caller can show warning)
        return []
    return [w.strip() for w in words if w.strip()]
    

# ------------------- reading from images -------------------
# Extract English text from images through OCR

def read_image(image_file):
    """Run OCR via pytesseract; return list of words. If OCR fails, return []."""
    try:
        # image_file is UploadFile; use BytesIO
        img = Image.open(io.BytesIO(image_file.read()))
        text = pytesseract.image_to_string(img)
        words = [w.strip() for w in text.split() if w.strip()]
        return words
    except UnidentifiedImageError:
        return []
    except Exception:
        # If pytesseract or tesseract binary is missing, return []
        return []
    
# ------------------- define Scramble Game -------------------
# Enhance spelling and word formation skills
#Core Algorithm: 1）Randomly shuffles letters of target words 2）Ensures scrambled version differs from original 3）Validates user input against correct spelling 4）Maintains sequential progression through vocabulary set

def scramble_word(w):
    letters = list(w)
    if len(letters) <= 1:
        return w
    random.shuffle(letters)
    scrambled = "".join(letters)
    # ensure scrambled is different (try a few times)
    tries = 0
    while scrambled == w and tries < 10:
        random.shuffle(letters)
        scrambled = "".join(letters)
        tries += 1
    return scrambled

# ------------------- Matching Game helpers -------------------
#Reinforce semantic connections between English words and Chinese translations
#Design Features: 1）Presents shuffled English words and Chinese translations 2）Requires users to establish correct word-meaning pairs 3）Employs optimized translation caching system 4）Tracks matching accuracy and response patterns

def generate_matching_game_once(user_words):
    """
    Generate (and translate) only once. Returns en_shuffled, cn_shuffled, mapping.
    This function DOES NOT change session_state; caller should store results.
    """
    word_en = []
    word_cn = []
    mapping = {}
    for w in user_words:
        # use cached translations if available (session_state)
        if "translation_cache" in st.session_state and w in st.session_state.translation_cache:
            cn = st.session_state.translation_cache[w]
        else:
            cn = baidu_translate(w)
            # cache it locally
            if "translation_cache" not in st.session_state:
                st.session_state.translation_cache = {}
            st.session_state.translation_cache[w] = cn
        word_en.append(w)
        word_cn.append(cn)
        mapping[w] = cn
    en_shuffled = word_en[:]
    cn_shuffled = word_cn[:]
    random.shuffle(en_shuffled)
    random.shuffle(cn_shuffled)
    return en_shuffled, cn_shuffled, mapping

def prepare_matching_game():
    """Ensure matching game data exists in session_state (generate once per Start Game)."""
    if "matching_words_generated" not in st.session_state or not st.session_state.matching_words_generated:
        en_list, cn_list, mapping = generate_matching_game_once(st.session_state.user_words)
        st.session_state.en_list = en_list
        st.session_state.cn_list = cn_list
        st.session_state.mapping = mapping
        st.session_state.matching_answers = {w: "Select" for w in en_list}
        st.session_state.matching_words_generated = True

def play_matching_game():
    prepare_matching_game()
    en_list = st.session_state.en_list
    cn_list = st.session_state.cn_list
    mapping = st.session_state.mapping

    st.subheader("Match English words with their Chinese meaning")

    # Build selectboxes — keys must be stable
    for en_word in en_list:
        # Use the stored answer as the default value. Provide options of cn_list (shuffled)
        current_choice = st.session_state.matching_answers.get(en_word, "Select")
        sel = st.selectbox(
            f"{en_word} ->",
            options=["Select"] + cn_list,
            index=(0 if current_choice not in (["Select"] + cn_list) else (["Select"] + cn_list).index(current_choice)),
            key=f"matching_{en_word}"
        )
        # Save selection into session_state mapping for persistence
        st.session_state.matching_answers[en_word] = sel

    if st.button("Submit Matching Game"):
        score = 0
        for w in en_list:
            if st.session_state.matching_answers.get(w) == mapping.get(w):
                score += 1
        st.success(f"You scored: {score}/{len(en_list)}")
        st.session_state.matching_score = score

        df = pd.DataFrame({
            "Word": en_list,
            "Correct Meaning": [mapping[w] for w in en_list],
            "Your Answer": [st.session_state.matching_answers[w] for w in en_list],
            "Correct?": [st.session_state.matching_answers[w] == mapping[w] for w in en_list]
        })
        st.subheader("Your results")
        st.table(df)
        # end game
        st.session_state.game_started = False
        
# ------------------- Fill-in-the-blank Game -------------------
MW_API_KEY = "b03334be-a55f-4416-9ff4-782b15a4dc77"  

def clean_html_tags(text):
    """Clean HTML-like tags from Merriam-Webster API response"""
    import re
    text = re.sub(r'\{/?wi\}', '', text)
    text = re.sub(r'\{/?it\}', '', text)
    text = re.sub(r'\{/?[^}]+?\}', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def get_example_sentence_mw(word):
    """
    Get example sentence from Merriam-Webster Collegiate API.
    Fallback to a template if no sentence is found.
    """
    url = f"https://www.dictionaryapi.com/api/v3/references/collegiate/json/{word}?key={MW_API_KEY}"
    try:
        r = requests.get(url)
        data = r.json()
        if not data or not isinstance(data[0], dict):
            return f"DEFAULT SENTECT: I LIKE TO {word} EVERY DAY."
        defs = data[0].get("def", [])
        for d in defs:
            sseq = d.get("sseq", [])
            for sense_group in sseq:
                for sense in sense_group:
                    dt = sense[1].get("dt", [])
                    for item in dt:
                        if item[0] == "vis":  # example sentences
                            vis_list = item[1]
                            if vis_list:
                                raw_sentence = vis_list[0]["t"]
                                cleaned_sentence = clean_html_tags(raw_sentence)
                                return cleaned_sentence
        return f"DEFAULT SENTECT: I LIKE TO {word} EVERY DAY."
    except Exception as e:
        print(f"Error getting example sentence for {word}: {e}")
        return f"DEFAULT SENTECT: I LIKE TO {word} EVERY DAY."

def create_blank_sentence(word, sentence):
    """Replace the target word with blanks in the sentence, handling variations"""
    import re
    
    cleaned_sentence = clean_html_tags(sentence)
    
    pattern_base = re.compile(rf'\b{re.escape(word)}\b', re.IGNORECASE)
    if pattern_base.search(cleaned_sentence):
        match = pattern_base.search(cleaned_sentence)
        actual_word = cleaned_sentence[match.start():match.end()]
        return cleaned_sentence.replace(actual_word, "_____")
    
    word_lower = word.lower()
    words_in_sentence = re.findall(r'\b\w+\b', cleaned_sentence)
    
    for i, w in enumerate(words_in_sentence):
        if w.lower() == word_lower:
            pattern_specific = re.compile(rf'\b{re.escape(w)}\b')
            match = pattern_specific.search(cleaned_sentence)
            if match:
                start, end = match.start(), match.end()
                return cleaned_sentence[:start] + "_____" + cleaned_sentence[end:]
    
    variants = [
        word + 's',  
        word + 'es',  
        word + 'ed',  
        word + 'ing', 
        word + 'er',  
        word + 'est',  
        word[:-1] + 'ies' if word.endswith('y') else None,  
        word + 'd' if not word.endswith('e') else None,  
    ]
    
    for variant in variants:
        if variant:
            variant_pattern = re.compile(rf'\b{re.escape(variant)}\b', re.IGNORECASE)
            if variant_pattern.search(cleaned_sentence):
                match = variant_pattern.search(cleaned_sentence)
                actual_variant = cleaned_sentence[match.start():match.end()]
                return cleaned_sentence.replace(actual_variant, "_____")
    
    if word_lower in cleaned_sentence.lower():
        start = cleaned_sentence.lower().find(word_lower)
        end = start + len(word)

        if (start == 0 or not cleaned_sentence[start-1].isalnum()) and \
           (end >= len(cleaned_sentence) or not cleaned_sentence[end].isalnum()):
            return cleaned_sentence[:start] + "_____" + cleaned_sentence[end:]
    
    return cleaned_sentence + f" (Fill in: _____)"
    
def play_fill_blank_game():
    st.subheader("Fill-in-the-Blank Game")

    st.info(
        'When no dictionary example is available, a default sentence will be used '
        '("I LIKE TO ___ EVERY DAY.").'
    )
    
    if "user_words" not in st.session_state or len(st.session_state.user_words) != 10:
        st.warning("Please provide exactly 10 words first.")
        return

    user_words = st.session_state.user_words

    # ---------------- Initialization ----------------
    should_reinit = False

    if "fb_index" not in st.session_state:
        should_reinit = True
    elif "fb_correct_answers" not in st.session_state:
        should_reinit = True
    elif len(st.session_state.fb_correct_answers) != 10:
        should_reinit = True
    
    if should_reinit:
        st.session_state.fb_index = 0
        st.session_state.fb_score = 0

        st.session_state.fb_correct_answers = user_words.copy()

        st.session_state.fb_answers = [""] * 10
        st.session_state.fb_sentences = []
        st.session_state.fb_blanked = []
        st.session_state.fb_order = []
        st.session_state.fb_options = []  

        for w in st.session_state.fb_correct_answers:
            sentence = get_example_sentence_mw(w)
            st.session_state.fb_sentences.append(sentence)
            st.session_state.fb_blanked.append(
                create_blank_sentence(w, sentence)
            )

        order = list(range(10))
        random.shuffle(order)
        st.session_state.fb_order = order
        
        st.session_state.fb_options = []
        for i in range(10):
            options = st.session_state.fb_correct_answers.copy()
            random.shuffle(options)
            st.session_state.fb_options.append(options)

    idx = st.session_state.fb_index

    # ---------------- Game finished ----------------
    if idx >= 10:
        st.success(f"Game finished! Your score: {st.session_state.fb_score}/10")

        results = []
        for i in range(10):
            original_idx = st.session_state.fb_order[i] if i < len(st.session_state.fb_order) else i
            user_answer = st.session_state.fb_answers[original_idx] if original_idx < len(st.session_state.fb_answers) else ""
            correct_answer = st.session_state.fb_correct_answers[original_idx] if original_idx < len(st.session_state.fb_correct_answers) else ""
            
            results.append({
                "Original Sentence": st.session_state.fb_sentences[original_idx] if original_idx < len(st.session_state.fb_sentences) else "",
                "Blanked Sentence": st.session_state.fb_blanked[original_idx] if original_idx < len(st.session_state.fb_blanked) else "",
                "Your Answer": user_answer,
                "Correct Answer": correct_answer,
            })

        df = pd.DataFrame(results)
        st.table(df)

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Play Again"):

                st.session_state.fb_index = 0
                st.session_state.fb_score = 0
                st.session_state.fb_answers = [""] * 10

                order = list(range(10))
                random.shuffle(order)
                st.session_state.fb_order = order
                st.session_state.fb_options = []
                for i in range(10):
                    options = st.session_state.fb_correct_answers.copy()
                    random.shuffle(options)
                    st.session_state.fb_options.append(options)
                st.rerun()
        
        with col2:
            if st.button("Back to Main Menu"):
                st.session_state.game_started = False
                st.rerun()
        
        return

    # ---------------- Current question ----------------
    if idx < len(st.session_state.fb_order):
        original_idx = st.session_state.fb_order[idx]
    else:
        original_idx = idx

    if original_idx < len(st.session_state.fb_correct_answers):
        word = st.session_state.fb_correct_answers[original_idx]
    else:
        st.error("Game data error. Please restart the game.")
        return

    if original_idx < len(st.session_state.fb_blanked):
        blanked = st.session_state.fb_blanked[original_idx]
    else:
        blanked = "Error: No blanked sentence available"

    st.write(f"**Question {idx + 1}/10**")
    st.write(blanked)

    with st.expander("Show original sentence (for reference)"):
        if original_idx < len(st.session_state.fb_sentences):
            st.write(st.session_state.fb_sentences[original_idx])
        else:
            st.write("Original sentence not available")

    if idx < len(st.session_state.fb_options):
        options = st.session_state.fb_options[idx]
    else:
        options = st.session_state.fb_correct_answers.copy()

    choice = st.radio(
        "Choose the correct word:",
        options=options,
        key=f"fb_choice_{idx}"  
    )

    if st.button("Submit", key=f"fb_submit_{idx}"):
        if original_idx < len(st.session_state.fb_answers):
            st.session_state.fb_answers[original_idx] = choice

            if choice.lower() == word.lower():
                st.session_state.fb_score += 1
                st.success("Correct!")
            else:
                st.error(f"Wrong. Correct answer: {word}")

            st.session_state.fb_index += 1
            st.rerun()
            
# ------------------- Streamlit Design -------------------
st.set_page_config(page_title="Vocabuddy", layout="centered")
st.title("Hi, Welcome to Vocabuddy")

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
    st.session_state.scramble_answers = [""] * 10
if "scramble_scrambled" not in st.session_state:
    st.session_state.scramble_scrambled = [""] * 10

# translation cache
if "translation_cache" not in st.session_state:
    st.session_state.translation_cache = {}

# ------------------- Users Input -------------------
st.markdown("### 1. Provide 10 words")
words_input = st.text_area("Please enter 10 words (use space or enter in another line)", height=120)
if words_input:
    st.session_state.user_words = [w.strip() for w in words_input.split() if w.strip()]

col1, col2 = st.columns(2)
with col1:
    uploaded_file = st.file_uploader("Upload a file (txt/csv/docx/pdf)", type=["txt","csv","docx","pdf"])
    if uploaded_file:
        words_from_file = read_file(uploaded_file)
        if words_from_file:
            st.session_state.user_words = words_from_file
        else:
            st.warning("Couldn't read file or file empty. Make sure it's a supported format and contains text.")

with col2:
    uploaded_image = st.file_uploader("Upload an image (OCR)", type=["png","jpg","jpeg","bmp","tiff","tif"])
    if uploaded_image:
        words_from_image = read_image(uploaded_image)
        if words_from_image:
            st.session_state.user_words = words_from_image
        else:
            st.warning("OCR failed or no text found in image. Ensure tesseract is installed and image contains text.")

# ------------------- make sure 10 words -------------------
if st.session_state.user_words:
    st.info(f"Current words ({len(st.session_state.user_words)}): {st.session_state.user_words}")
    if len(st.session_state.user_words) != 10:
        st.warning("Please provide exactly 10 words to play (you can enter/upload more and then edit).")

# ------------------- choose game mode -------------------
if st.session_state.user_words and len(st.session_state.user_words) == 10:
    st.markdown("### 2. Choose a game and start")
    st.session_state.game_mode = st.selectbox(
        "Choose game mode",
        ["Scrambled Letters Game", "Matching Game", "Listen & Choose", "Fill-in-the-Blank Game"],
        index=0
    )

    # Start Game button: also reset per-game session flags
    if st.button("Start Game"):
        st.session_state.game_started = True
        # reset Scramble Game
        st.session_state.scramble_index = 0
        st.session_state.scramble_score = 0
        st.session_state.scramble_answers = [""] * 10
        st.session_state.scramble_scrambled = [""] * 10
        # reset Matching Game
        st.session_state.matching_answers = {}
        st.session_state.matching_score = 0
        st.session_state.matching_words_generated = False
        # shuffle words for scramble game (store as new list)
        random.shuffle(st.session_state.user_words)

# ------------------- Scrambled Game -------------------
if st.session_state.game_started and st.session_state.game_mode == "Scrambled Letters Game":
    st.subheader("Spell the word in correct order")
    idx = st.session_state.scramble_index

    if idx < len(st.session_state.user_words):
        current_word = st.session_state.user_words[idx]

        if not st.session_state.scramble_scrambled[idx]:
            scrambled = scramble_word(current_word)
            st.session_state.scramble_scrambled[idx] = scrambled
        else:
            scrambled = st.session_state.scramble_scrambled[idx]

        def submit_answer():
            answer = st.session_state.scramble_input
            st.session_state.scramble_answers[idx] = answer.strip()
            if answer.strip().lower() == current_word.lower():
                st.session_state.scramble_score += 1
            st.session_state.scramble_index += 1
            st.session_state.scramble_input = ""

        st.text_input(
            f"Word {idx + 1}: {scrambled}",
            key="scramble_input",
            on_change=submit_answer
        )
    else:
        st.success(f"Game finished! Your score: {st.session_state.scramble_score}/10")
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

# ------------------- Listen & Choose -------------------
if st.session_state.game_started and st.session_state.game_mode == "Listen & Choose":
    st.subheader("Listen & Choose Game")

    if "listen_index" not in st.session_state:
        st.session_state.listen_index = 0
    if "listen_score" not in st.session_state:
        st.session_state.listen_score = 0
    if "listen_answers" not in st.session_state:
        st.session_state.listen_answers = [""] * 10

    idx = st.session_state.listen_index
    user_words = st.session_state.user_words

    if idx < len(user_words):
        current_word = user_words[idx]
        audio_file = generate_tts_audio(current_word)

        st.audio(audio_file, format="audio/mp3")
        st.info(f"Word {idx + 1} of {len(user_words)}")

        user_choice = st.radio(
            "Which word did you hear?",
            options=user_words,
            key=f"listen_choice_{idx}"
        )

        if st.button("Submit", key=f"listen_submit_{idx}"):
            st.session_state.listen_answers[idx] = user_choice
            if user_choice == current_word:
                st.session_state.listen_score += 1
                st.success("Correct! 🎉")
            else:
                st.error(f"Wrong. The correct answer was **{current_word}**.")
            st.session_state.listen_index += 1
            

    else:
        st.success(f"Game finished! Your score: {st.session_state.listen_score}/{len(user_words)}")
        df = pd.DataFrame({
            "Word": user_words,
            "Your Answer": st.session_state.listen_answers,
            "Correct?": [
                ua == w for ua, w in zip(st.session_state.listen_answers, user_words)
            ]
        })
        st.subheader("Your results")
        st.table(df)

        st.session_state.game_started = False
        st.session_state.listen_index = 0
        st.session_state.listen_score = 0
        st.session_state.listen_answers = [""] * 10
        
# ------------------- Fill-in-the-Blank  -------------------
if st.session_state.game_started and st.session_state.game_mode == "Fill-in-the-Blank Game":
    play_fill_blank_game()

