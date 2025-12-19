
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

# ============ initialization: session_state ============
# Streamlit re-runs the entire script on every widget interaction.
# We use st.session_state to persist multi-step game progress (index/score/answers)
# across reruns, so the app behaves like a real interactive web app
# restarting on every click.


if "user_words" not in st.session_state:
    st.session_state.user_words = []
if "game_started" not in st.session_state:
    st.session_state.game_started = False
if "game_mode" not in st.session_state:
    st.session_state.game_mode = "Scrambled Letters Game"

if "scramble_index" not in st.session_state:
    st.session_state.scramble_index = 0
if "scramble_score" not in st.session_state:
    st.session_state.scramble_score = 0
if "scramble_answers" not in st.session_state:
    st.session_state.scramble_answers = [""] * 10
if "scramble_scrambled" not in st.session_state:
    st.session_state.scramble_scrambled = [""] * 10

if "matching_words_generated" not in st.session_state:
    st.session_state.matching_words_generated = False
if "matching_answers" not in st.session_state:
    st.session_state.matching_answers = {}
if "matching_score" not in st.session_state:
    st.session_state.matching_score = 0

if "Listen_index" not in st.session_state:
    st.session_state.Listen_index = 0
if "Listen_score" not in st.session_state:
    st.session_state.Listen_score = 0
if "Listen_answers" not in st.session_state:
    st.session_state.Listen_answers = [""] * 10
if "Listen_played_words" not in st.session_state:
    st.session_state.Listen_played_words = []
if "waiting_for_next" not in st.session_state:
    st.session_state.waiting_for_next = False

if "fb_index" not in st.session_state:
    st.session_state.fb_index = 0
if "fb_score" not in st.session_state:
    st.session_state.fb_score = 0
if "fb_total_questions" not in st.session_state:
    st.session_state.fb_total_questions = 0
if "fb_answers" not in st.session_state:
    st.session_state.fb_answers = [""] * 10
if "fb_correct_answers" not in st.session_state:
    st.session_state.fb_correct_answers = []
if "fb_blanked_sentences" not in st.session_state:
    st.session_state.fb_blanked_sentences = []
if "fb_original_sentences" not in st.session_state:
    st.session_state.fb_original_sentences = []
if "fb_is_fallback" not in st.session_state:
    st.session_state.fb_is_fallback = []
if "fb_played_order" not in st.session_state:
    st.session_state.fb_played_order = []
if "fb_waiting_for_next" not in st.session_state:
    st.session_state.fb_waiting_for_next = False

if "translation_cache" not in st.session_state:
    st.session_state.translation_cache = {}

# ------------------- generate audio ------------------------
# This module handles text-to-speech audio generation for vocabulary words.
# It creates MP3 audio files using gTTS (Google Text-to-Speech) and caches them locally to avoid regenerating audio for the same words. This enables the Listen
# & Choose game where users hear word pronunciations and select the correct word.
# The audio files are stored in a dedicated folder for efficient reuse.

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
# This module provides translation functionality from English to Chinese using
# Baidu Translate API. It supports the Matching Game by translating vocabulary
# words into Chinese definitions. The module includes caching to avoid repeated
# API calls for the same words and gracefully falls back to the original word
# if the API call fails. This ensures the game can continue even without internet
# connectivity or valid API credentials.

import streamlit as st

APPID = st.secrets["BAIDU_APPID"]
KEY = st.secrets["BAIDU_KEY"]


if not APPID or not KEY:
    st.warning("Missing BAIDU_APPID / BAIDU_KEY. Please set secrets or environment variables.")
 

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

# ------------------- End Screen -------------------
# This module provides reusable game completion screens with consistent UI elements.
# It displays final scores, accuracy metrics, and detailed results tables while
# offering standardized navigation options to replay, switch games, or return to
# the main menu. The modular design avoids code duplication across different games
# and ensures uniform user experience regardless of which game was played.

def _clear_keys_with_prefix(prefix: str):
    for k in list(st.session_state.keys()):
        if k.startswith(prefix):
            del st.session_state[k]

def show_end_screen(game_tag: str, reset_current_game_fn):
    """Reusable 'What would you like to do next?' screen.
    - game_tag: unique tag for widget keys (e.g., 'scramble', 'matching', 'listen', 'fb')
    - reset_current_game_fn: function that resets only the current game's session_state
    """
    st.markdown("---")
    st.write("### What would you like to do next?")
    col1, col2, col3 = st.columns([1, 1, 1])

    with col1:
        if st.button("🔄 Play Again", key=f"{game_tag}_play_again", use_container_width=True,
                     help="Play the same game again with new random order"):
            reset_current_game_fn()
            st.rerun()

    with col2:
        if st.button("🎮 Try Another Game", key=f"{game_tag}_try_another", use_container_width=True,
                     help="Go back to choose a different game mode"):
            reset_current_game_fn()
            st.session_state.game_started = False
            st.rerun()

    with col3:
        if st.button("🏠 Main Menu", key=f"{game_tag}_main_menu", use_container_width=True,
                     help="Return to the main menu"):
            # Go back to main menu
            st.session_state.game_started = False
            st.session_state.game_mode = None
            reset_current_game_fn()
            st.rerun()


def _maybe_balloons(flag_key: str):
    """Show balloons only once per end screen to avoid repeating on rerun."""
    if not st.session_state.get(flag_key, False):
        st.balloons()
        st.session_state[flag_key] = True

def show_game_results(
    game_tag: str,
    game_title: str,
    score: int,
    total: int,
    df: pd.DataFrame | None,
    reset_current_game_fn,
    column_config: dict | None = None,
    score_note: str | None = None,
):
    """Unified result summary (like Listen & Choose) + reusable end screen buttons."""
    # Celebration (only once)
    _maybe_balloons(f"{game_tag}_balloons_shown")

    # Score + accuracy
    if total and total > 0:
        accuracy = (score / total) * 100
        headline = f"🎮 Game Finished! Your score: **{score}/{total}**"
        if score_note:
            headline += f"  \n\n{score_note}"
        st.success(headline)

        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Total Score", f"{score}/{total}")
        with c2:
            st.metric("Accuracy", f"{accuracy:.1f}%")
        with c3:
            if accuracy >= 80:
                performance = "🏆 Excellent"
            elif accuracy >= 60:
                performance = "👍 Good"
            else:
                performance = "📚 Needs Practice"
            st.metric("Performance", performance)
    else:
        st.success("🎮 Game Finished!")
        accuracy = None
        if score_note:
            st.info(score_note)

    # Results table
    st.subheader("📊 Your Results")
    if df is not None and len(df) > 0:
        st.dataframe(
            df,
            column_config=column_config or {},
            hide_index=True,
            use_container_width=True
        )
    else:
        st.info("No results to display.")

    # End screen actions
    show_end_screen(game_tag, reset_current_game_fn)

def reset_scrambled_game():
    st.session_state.pop('scramble_balloons_shown', None)
    st.session_state.scramble_index = 0
    st.session_state.scramble_score = 0
    st.session_state.scramble_answers = [""] * 10
    # re-scramble next time
    st.session_state.scramble_scrambled = [scramble_word(w) for w in st.session_state.user_words]
    st.session_state.scramble_input = ""

def reset_matching_game():
    st.session_state.pop('matching_balloons_shown', None)
    st.session_state.matching_words_generated = False
    st.session_state.matching_answers = {}
    st.session_state.matching_score = 0
    _clear_keys_with_prefix("matching_")

def reset_listen_choose_game():
    st.session_state.pop('listen_balloons_shown', None)
    st.session_state.Listen_index = 0
    st.session_state.Listen_score = 0
    st.session_state.Listen_answers = [""] * 10
    st.session_state.Listen_played_words = []
    st.session_state.waiting_for_next = False
    _clear_keys_with_prefix("selected_")

def reset_fill_blank_game():
    st.session_state.pop('fb_balloons_shown', None)
    st.session_state.fb_index = 0
    st.session_state.fb_score = 0
    st.session_state.fb_total_questions = 0
    st.session_state.fb_answers = [""] * 10
    st.session_state.fb_correct_answers = []
    st.session_state.fb_blanked_sentences = []
    st.session_state.fb_original_sentences = []
    st.session_state.fb_is_fallback = []
    st.session_state.fb_played_order = []
    st.session_state.fb_waiting_for_next = False
    _clear_keys_with_prefix("fb_selected_")

# ------------------- read files -------------------
def read_file(file):
    """Read words from txt/csv/docx/pdf file-like object (Streamlit UploadFile)."""
    words = []
    name = file.name.lower()
    try:
        if name.endswith((".txt", ".csv")):
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
                if text:
                    words += text.split()
    except Exception:
        return []
    return [w.strip() for w in words if w.strip()]

# ------------------- reading from images -------------------
def read_image(image_file):
    """Run OCR via pytesseract; return list of words. If OCR fails, return []."""
    try:
        img = Image.open(io.BytesIO(image_file.read()))
        text = pytesseract.image_to_string(img)
        words = [w.strip() for w in text.split() if w.strip()]
        return words
    except UnidentifiedImageError:
        return []
    except Exception:
        return []

# ------------------- Streamlit Design -------------------
st.set_page_config(page_title="Vocabuddy", layout="centered")
st.title("Hi, Welcome to Vocabuddy")

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
        ["Listen & Choose", "Scrambled Letters Game", "Matching Game",  "Fill-in-the-Blank Game"],
        index=0
    )
if st.button("Start Game"):
    st.session_state.game_started = True
    original_words = st.session_state.user_words.copy()
    
    # create copies of word list for 4 games 
    st.session_state.scramble_words = original_words.copy()
    random.shuffle(st.session_state.scramble_words)
    
    st.session_state.matching_words = original_words.copy()
    st.session_state.listen_words = original_words.copy()  
    st.session_state.fill_blank_words = original_words.copy()
    
    # reset Scramble Game
    st.session_state.scramble_index = 0
    st.session_state.scramble_score = 0
    st.session_state.scramble_answers = [""] * 10
    st.session_state.scramble_scrambled = [""] * 10
    
    # reset Matching Game
    st.session_state.matching_answers = {}
    st.session_state.matching_score = 0
    st.session_state.matching_words_generated = False
    
    # reset Listen & Choose Game 
    st.session_state.Listen_index = 0
    st.session_state.Listen_score = 0
    st.session_state.Listen_answers = [""] * 10
    st.session_state.Listen_played_words = []  
    st.session_state.Listen_options_list = []  
    st.session_state.waiting_for_next = False  
    
    # reset Fill-in-the-Blank Game
    st.session_state.fb_index = 0
    st.session_state.fb_score = 0
    st.session_state.fb_total_questions = 0
    st.session_state.fb_answers = [""] * 10
    st.session_state.fb_correct_answers = []
    st.session_state.fb_blanked_sentences = []
    st.session_state.fb_original_sentences = []
    st.session_state.fb_is_fallback = []
    st.session_state.fb_played_order = []
    st.session_state.fb_waiting_for_next = False
        
    for key in list(st.session_state.keys()):
        if key.startswith("selected_") or key.startswith("fb_selected_"):
            del st.session_state[key]
        
    st.rerun()

# -------------------- 1. Listen & Choose ----------------------
# This module implements the "Listen & Choose" vocabulary game where users hear
# audio pronunciations and select the matching word from options. It manages audio
# playback, word shuffling, answer submission, and scoring. The game progresses
# through all 10 words, providing immediate feedback on each selection and tracking
# cumulative performance. Audio is generated dynamically using TTS and played
# automatically to simulate real listening comprehension exercises.

if st.session_state.get("game_started", False) and st.session_state.get("game_mode") == "Listen & Choose":
    st.subheader("🎧 Listen & Choose Game")
    
    idx = st.session_state.Listen_index
    user_words = st.session_state.listen_words  
    
    if idx == 0 and len(st.session_state.Listen_played_words) == 0:
        shuffled_words = user_words.copy()
        random.shuffle(shuffled_words)
        st.session_state.Listen_played_words = shuffled_words
    
    if idx < len(user_words):
        current_audio_word = st.session_state.Listen_played_words[idx]  
        correct_word = current_audio_word  
        
        st.info(f"🎵 Word {idx + 1} of {len(user_words)}")
        
        audio_file = generate_tts_audio(current_audio_word)
        st.audio(audio_file, format="audio/mp3", autoplay=True)
        
        # show 10 words 
        st.write("**Select the word you heard:**")
        
        cols = st.columns(2) 
        
        user_choice = None
        for i, word in enumerate(user_words):
            col_idx = i % 2  
            with cols[col_idx]:
                if st.button(
                    word,
                    key=f"word_btn_{idx}_{i}",
                    use_container_width=True,
                    type="primary" if st.session_state.get(f"selected_{idx}") == word else "secondary"
                ):
                    user_choice = word
                    st.session_state[f"selected_{idx}"] = word
                    st.rerun()
        
        if st.session_state.get(f"selected_{idx}"):
            st.markdown(f"**Your current selection:** `{st.session_state[f'selected_{idx}']}`")
        
        col1, col2 = st.columns(2)
        
        submit_disabled = st.session_state.get(f"selected_{idx}") is None
        
        with col1:
            if st.button("✅ Submit Answer", 
                        key=f"Listen_submit_{idx}", 
                        disabled=submit_disabled,
                        use_container_width=True):
                user_choice = st.session_state.get(f"selected_{idx}", "")
                
                st.session_state.Listen_answers[idx] = user_choice
                
                if user_choice == correct_word:
                    st.session_state.Listen_score += 1
                    st.success(f"✅ Correct! **'{correct_word}'** is right!")
                else:
                    st.error(f"❌ Wrong. You selected **'{user_choice}'**. The correct answer was **'{correct_word}'**.")
                
                if f"selected_{idx}" in st.session_state:
                    del st.session_state[f"selected_{idx}"]
                
                st.session_state.waiting_for_next = True
        
        if st.session_state.get("waiting_for_next", False):
            with col2:
                if st.button("➡️ Next Word", 
                            key=f"next_{idx}", 
                            use_container_width=True):
                    st.session_state.Listen_index += 1
                    st.session_state.waiting_for_next = False
                    st.rerun()
    else:
        df_data = []
        for i in range(len(user_words)):
            audio_word = st.session_state.Listen_played_words[i]
            user_answer = st.session_state.Listen_answers[i]
            is_correct = user_answer == audio_word
            df_data.append({
                "Audio Word": audio_word,
                "Your Choice": user_answer,
                "Correct?": "✅" if is_correct else "❌"
            })
        df = pd.DataFrame(df_data)

        show_game_results(
            game_tag="listen",
            game_title="Listen & Choose",
            score=st.session_state.Listen_score,
            total=len(user_words),
            df=df,
            reset_current_game_fn=reset_listen_choose_game,
            column_config={
                "Audio Word": "Heard Word",
                "Your Choice": "Your Answer",
                "Correct?": st.column_config.TextColumn("Result", help="✅ = Correct, ❌ = Wrong"),
            },
        )

# ------------------- 2. Scrambled Letters Game -------------------
# This module implements the "Scrambled Letters Game" where users unscramble
# jumbled letters to form correct English words. Each target word's letters are
# randomly shuffled, ensuring the scrambled version differs from the original.
# Users type their answers in a text input field, and the system validates
# spelling against the correct word. The game progresses sequentially through
# all vocabulary words, tracking correct answers and displaying scrambled forms
# that refresh automatically for each new word.

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

# ------------------- Scrambled Game -------------------
if st.session_state.get("game_started") and st.session_state.get("game_mode") == "Scrambled Letters Game":
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
        # Game finished: unified results screen
        correct_flags = [
            ua.strip().lower() == w.lower()
            for ua, w in zip(st.session_state.scramble_answers, st.session_state.user_words)
        ]
        data = {
            "Word": st.session_state.user_words,
            "Scrambled": st.session_state.scramble_scrambled,
            "Your Answer": st.session_state.scramble_answers,
            "Correct?": ["✅" if ok else "❌" for ok in correct_flags]
        }
        df = pd.DataFrame(data)
        show_game_results(
            game_tag="scramble",
            game_title="Scrambled Letters Game",
            score=st.session_state.scramble_score,
            total=len(st.session_state.user_words),
            df=df,
            reset_current_game_fn=reset_scrambled_game,
            column_config={
                "Word": "Original Word",
                "Scrambled": "Scrambled",
                "Your Answer": "Your Answer",
                "Correct?": st.column_config.TextColumn("Result", help="✅ = Correct, ❌ = Wrong"),
            },
        )

# ------------------- 3. Matching Game helpers -------------------
# This module provides the core functionality for the "Matching Game" where users
# pair English vocabulary words with their Chinese translations. It handles word
# translation using Baidu API, shuffles both English and Chinese lists independently,
# and manages user selection through interactive dropdown menus. The system tracks
# matches in real-time and calculates scores based on correct pairings between
# words and their corresponding translations.

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
    if st.session_state.get("game_started", False) and st.session_state.get("game_mode") == "Matching Game":
        if not st.session_state.get("matching_words_generated", False):
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
        current_choice = st.session_state.matching_answers.get(en_word, "Select")
        sel = st.selectbox(
            f"{en_word} ->",
            options=["Select"] + cn_list,
            index=(0 if current_choice not in (["Select"] + cn_list) else (["Select"] + cn_list).index(current_choice)),
            key=f"matching_{en_word}"
        )
        st.session_state.matching_answers[en_word] = sel

    st.markdown("---")
    if st.button("✅ Submit Matching Game"):
        score = 0
        for w in en_list:
            if st.session_state.matching_answers.get(w) == mapping.get(w):
                score += 1
        st.success(f"You scored: {score}/{len(en_list)}")
        st.session_state.matching_score = score

        # Build results dataframe
        correct_flags = [st.session_state.matching_answers[w] == mapping[w] for w in en_list]
        df = pd.DataFrame({
            "Word": en_list,
            "Correct Meaning": [mapping[w] for w in en_list],
            "Your Answer": [st.session_state.matching_answers[w] for w in en_list],
            "Correct?": ["✅" if ok else "❌" for ok in correct_flags]
        })

        # Use unified results screen
        show_game_results(
            game_tag="matching",
            game_title="Matching Game",
            score=sum(1 for ok in correct_flags if ok),
            total=len(en_list),
            df=df,
            reset_current_game_fn=reset_matching_game,
            column_config={
                "Word": "English Word",
                "Correct Meaning": "Correct Meaning",
                "Your Answer": "Your Answer",
                "Correct?": st.column_config.TextColumn("Result", help="✅ = Correct, ❌ = Wrong"),
            },
        )

        
# ------------------- Merriam-Webster API -------------------
# This module implements contextual vocabulary practice by retrieving real example
# sentences from Merriam-Webster API and creating cloze exercises. For each target
# word, it fetches authentic usage examples, replaces the target word with blanks,
# and presents them as completion tasks. The system includes intelligent fallback
# mechanisms for words without available examples and distinguishes between
# API-sourced and default sentences in scoring.

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
    if st.session_state.get("game_started", False) and st.session_state.get("game_mode") == "Fill-in-the-Blank Game":
        st.subheader("📝 Fill-in-the-Blank Game")
        
        st.info(
            'When no dictionary example is available, a default sentence will be used '
            '("I LIKE TO ___ EVERY DAY.").'
        )
        
        if "fb_index" not in st.session_state:
            st.session_state.fb_index = 0
            st.session_state.fb_score = 0
            st.session_state.fb_total_questions = 0  
            st.session_state.fb_answers = [""] * 10
            st.session_state.fb_correct_answers = []
            st.session_state.fb_blanked_sentences = []
            st.session_state.fb_original_sentences = []
            st.session_state.fb_is_fallback = []  
            st.session_state.fb_played_order = []  
            st.session_state.fb_waiting_for_next = False
        
        idx = st.session_state.fb_index
        user_words = st.session_state.fill_blank_words  
        
        if idx == 0 and len(st.session_state.fb_correct_answers) == 0:
            st.session_state.fb_correct_answers = user_words.copy()
            
            st.session_state.fb_blanked_sentences = []
            st.session_state.fb_original_sentences = []
            st.session_state.fb_is_fallback = []  
            st.session_state.fb_total_questions = 0 
            
            st.info("⏳ Generating example sentences...")
            progress_bar = st.progress(0)
            
            for i, word in enumerate(user_words):
                sentence = get_example_sentence_mw(word)
                st.session_state.fb_original_sentences.append(sentence)
                
                blanked_sentence = create_blank_sentence(word, sentence)
                st.session_state.fb_blanked_sentences.append(blanked_sentence)
                
                is_fallback = "DEFAULT SENTENCE" in sentence.upper() or "DEFAULT SENTENCE" in blanked_sentence.upper()
                st.session_state.fb_is_fallback.append(is_fallback)
                
                if not is_fallback:
                    st.session_state.fb_total_questions += 1
                
                progress_bar.progress((i + 1) / len(user_words))
            
            progress_bar.empty()
            
            shuffled_order = list(range(len(user_words)))
            random.shuffle(shuffled_order)
            st.session_state.fb_played_order = shuffled_order
        
        if idx < len(user_words):
            current_order = st.session_state.fb_played_order[idx] 
            current_sentence = st.session_state.fb_blanked_sentences[current_order]
            correct_word = st.session_state.fb_correct_answers[current_order]
            original_sentence = st.session_state.fb_original_sentences[current_order]
            is_fallback = st.session_state.fb_is_fallback[current_order]
            
            if is_fallback:
                st.info(f"📝 Question {idx + 1} of {len(user_words)} (🎯 Default Sentence - Not Counted)")
            else:
                st.info(f"📝 Question {idx + 1} of {len(user_words)}")
            
            st.markdown(f"### {current_sentence}")
            st.write("**Select the correct word to fill in the blank:**")
            
            cols = st.columns(2) 
            
            for i, word in enumerate(user_words):
                col_idx = i % 2  
                with cols[col_idx]:
                    is_selected = st.session_state.get(f"fb_selected_{idx}") == word
                    button_type = "primary" if is_selected else "secondary"
                    
                    if st.button(
                        word,
                        key=f"fb_word_btn_{idx}_{i}",
                        use_container_width=True,
                        type=button_type
                    ):
                        st.session_state[f"fb_selected_{idx}"] = word
                        st.rerun()
            
            if st.session_state.get(f"fb_selected_{idx}"):
                st.markdown(f"**Your current selection:** `{st.session_state[f'fb_selected_{idx}']}`")
            
            col1, col2 = st.columns(2)
            
            submit_disabled = st.session_state.get(f"fb_selected_{idx}") is None
            
            with col1:
                if st.button("✅ Submit Answer", 
                            key=f"fb_submit_{idx}", 
                            disabled=submit_disabled,
                            use_container_width=True):
                    user_choice = st.session_state.get(f"fb_selected_{idx}", "")
                    
                    st.session_state.fb_answers[current_order] = user_choice
                    
                    with st.expander("📖 Show original sentence"):
                        st.write(f"**Original sentence:** {original_sentence}")
                        if is_fallback:
                            st.warning("⚠️ This is a default sentence - not counted in final score")
                    
                    if user_choice.lower() == correct_word.lower():
                        if not is_fallback:
                            st.session_state.fb_score += 1
                            st.success(f"✅ Correct! **'{correct_word}'** fits perfectly!")
                        else:
                            st.success(f"✅ Correct! **'{correct_word}'** fits perfectly! (Default sentence - not scored)")
                    else:
                        if not is_fallback:
                            st.error(f"❌ Wrong. You selected **'{user_choice}'**. The correct answer was **'{correct_word}'**.")
                        else:
                            st.error(f"❌ Wrong. You selected **'{user_choice}'**. The correct answer was **'{correct_word}'**. (Default sentence - not scored)")
                    
                    if f"fb_selected_{idx}" in st.session_state:
                        del st.session_state[f"fb_selected_{idx}"]
                    
                    st.session_state.fb_waiting_for_next = True
            
            if st.session_state.get("fb_waiting_for_next", False):
                with col2:
                    if st.button("➡️ Next Question", 
                                key=f"fb_next_{idx}", 
                                use_container_width=True):
                        st.session_state.fb_index += 1
                        st.session_state.fb_waiting_for_next = False
                        st.rerun()
        else:
            valid_questions = st.session_state.fb_total_questions
            score_note = None
            if valid_questions > 0:
                score_note = "(Score excludes default/fallback sentences)"
            else:
                score_note = "All sentences were default/fallback sentences — no score calculated."

            df_data = []
            for i in range(len(user_words)):
                original_idx = st.session_state.fb_played_order[i]
                blanked_sentence = st.session_state.fb_blanked_sentences[original_idx]
                user_answer = st.session_state.fb_answers[original_idx]
                correct_answer = st.session_state.fb_correct_answers[original_idx]
                original_sentence = st.session_state.fb_original_sentences[original_idx]
                is_fallback = st.session_state.fb_is_fallback[original_idx]
                is_correct = (user_answer or "").strip().lower() == (correct_answer or "").strip().lower()

                df_data.append({
                    "Word": user_words[i],
                    "Sentence (Blank)": blanked_sentence,
                    "Your Answer": user_answer,
                    "Correct Answer": correct_answer,
                    "Correct?": "✅" if is_correct else "❌",
                    "Source": "Default" if is_fallback else "API",
                    "Original Sentence": original_sentence
                })

            df = pd.DataFrame(df_data)

            show_game_results(
                game_tag="fb",
                game_title="Fill-in-the-Blank Game",
                score=st.session_state.fb_score,
                total=valid_questions,
                df=df,
                reset_current_game_fn=reset_fill_blank_game,
                column_config={
                    "Word": "Target Word",
                    "Sentence (Blank)": "Sentence",
                    "Your Answer": "Your Answer",
                    "Correct Answer": "Correct Answer",
                    "Correct?": st.column_config.TextColumn("Result", help="✅ = Correct, ❌ = Wrong"),
                    "Source": "Sentence Source",
                    "Original Sentence": "Original",
                },
                score_note=score_note,
            )

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
    
# ------------------- Matching Game -------------------
if st.session_state.game_started and st.session_state.game_mode == "Matching Game":
    play_matching_game()    
        
# ------------------- Fill-in-the-Blank  -------------------
if st.session_state.game_started and st.session_state.game_mode == "Fill-in-the-Blank Game":
    play_fill_blank_game()
