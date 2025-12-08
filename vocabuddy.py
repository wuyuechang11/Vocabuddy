# import tkinter to visualize the GUI
# import pytesseract for OCR functionality 
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import pytesseract
from PIL import Image
import docx
import PyPDF2
import requests
import hashlib
import random

# ------------------- Baidu Translate API -------------------
APPID = "ID"
KEY = "Key"

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

user_words = []

# ------------------- function of upload a file-------------------
# make sure it accepts different types of files
def upload_file():
    global user_words
    file_path = filedialog.askopenfilename(filetypes=[("All supported","*.txt *.csv *.docx *.pdf")])
    if not file_path:
        return
    try:
        words = []
        if file_path.endswith((".txt",".csv")):
            with open(file_path, 'r', encoding='utf-8') as f:
                words = f.read().split()
        elif file_path.endswith(".docx"):
            doc = docx.Document(file_path)
            for para in doc.paragraphs:
                words += para.text.split()
        elif file_path.endswith(".pdf"):
            with open(file_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    words += page.extract_text().split()
        words = [w.strip() for w in words if w.strip()]
        if len(words) != 10:
            messagebox.showerror("Error", "Please provide exactly 10 words!")
            return
        user_words[:] = words
        text_box.delete("1.0", tk.END)
        text_box.insert(tk.END, " ".join(words))
        messagebox.showinfo("Success", "File uploaded successfully!")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to read file: {e}")

# ------------------- Upload a picture(OCR) -------------------
# make sure it accepts different types of pictures
def upload_image():
    global user_words
    img_path = filedialog.askopenfilename(filetypes=[("Image files","*.png *.jpg *.jpeg *.bmp *.tiff *.tif")])
    if not img_path:
        return
    try:
        text = pytesseract.image_to_string(Image.open(img_path))
        words = [w.strip() for w in text.split() if w.strip()]
        if len(words) != 10:
            messagebox.showerror("Error", "Only ten words are allowed!")
            return
        user_words[:] = words
        text_box.delete("1.0", tk.END)
        text_box.insert(tk.END, " ".join(words))
        messagebox.showinfo("Success", "OCR upload successful!")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to read image: {e}")

# ------------------- choose game mode -------------------
def start_game():
    global user_words
    if not user_words:
        words_input = text_box.get("1.0", tk.END).strip()
        words = [w.strip() for w in words_input.split() if w.strip()]
        if len(words) != 10:
            messagebox.showerror("Error", "Please enter exactly 10 words!")
            return
        user_words[:] = words

    # offer game mode choice
    mode_window = tk.Toplevel(root)
    mode_window.title("Choose Game Mode")
    tk.Label(mode_window, text="Please choose your game mode:").pack(pady=10)

    tk.Button(mode_window, text="Matching Game",
              command=lambda: [mode_window.destroy(),
                               play_matching_game(*generate_matching_game(user_words))]).pack(pady=5)
    tk.Button(mode_window, text="Scrambled Letters Game",
              command=lambda: [mode_window.destroy(),
                               play_scrambled_game(user_words)]).pack(pady=5)

# ------------------- the first game_matching game -------------------
def generate_matching_game(user_words):
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

def play_matching_game(en_list, cn_list, mapping):
    game_win = tk.Toplevel(root)
    game_win.title("Matching Game")
    tk.Label(game_win, text="Match the words with their Chinese meaning:").pack(pady=5)

    dropdowns = {}
    for i, w in enumerate(en_list):
        tk.Label(game_win, text=f"{i+1}. {w}").pack()
        var = tk.StringVar()
        var.set("Select the correct meaning")
        dropdown = tk.OptionMenu(game_win, var, *cn_list)
        dropdown.pack()
        dropdowns[w] = var

    def submit():
        score = 0
        for w in en_list:
            if dropdowns[w].get() == mapping[w]:
                score += 1
        messagebox.showinfo("Score", f"You scored: {score}/{len(en_list)}")
        game_win.destroy()

    tk.Button(game_win, text="Finish", command=submit).pack(pady=10)

# ------------------- the second game_scrambled letters game -------------------
def play_scrambled_game(words):
    game_win = tk.Toplevel(root)
    game_win.title("Scrambled Letters Game")
    tk.Label(game_win, text="Unscramble the word:").pack(pady=5)

    random.shuffle(words)
    index = tk.IntVar(value=0)
    score = tk.IntVar(value=0)

    prompt_label = tk.Label(game_win, text="")
    prompt_label.pack(pady=10)
    answer_entry = tk.Entry(game_win)
    answer_entry.pack()

    def scramble_word(w):
        letters = list(w)
        random.shuffle(letters)
        scrambled = "".join(letters)
        while scrambled == w:
            random.shuffle(letters)
            scrambled = "".join(letters)
        return scrambled

    def update_question():
        current = words[index.get()]
        scrambled = scramble_word(current)
        prompt_label.config(text=f"Word {index.get()+1}: {scrambled}")

    def submit_answer():
        user = answer_entry.get().strip().lower()
        correct = words[index.get()].lower()
        if user == correct:
            score.set(score.get() + 1)
        index.set(index.get() + 1)
        if index.get() >= len(words):
            messagebox.showinfo("Score", f"You scored: {score.get()}/{len(words)}")
            game_win.destroy()
        else:
            answer_entry.delete(0, tk.END)
            update_question()

    tk.Button(game_win, text="Submit", command=submit_answer).pack(pady=10)
    update_question()

# ------------------- Main program window -------------------
root = tk.Tk()
root.title("Vocabuddy")

tk.Label(root, text="Please input 10 words（use whitespace or another line to spereate）:").pack(pady=5)
text_box = tk.Text(root, height=10, width=40)
text_box.pack(pady=5)

tk.Button(root, text="Upload a file (txt/csv/docx/pdf)", command=upload_file).pack(pady=5)
tk.Button(root, text="Upload a Picture", command=upload_image).pack(pady=5)
tk.Button(root, text="Game start", command=start_game).pack(pady=10)

root.mainloop()


