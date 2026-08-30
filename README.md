# Book Discovery & Reading Companion

A Streamlit app for searching books (via Open Library), keeping a personal
reading list with statuses, finding similar books, and generating
AI-powered reading guides (via Gemini).

## Project structure

```
app.py                  Streamlit entry point
models/book.py          Book data class
services/                Open Library, reading list, Gemini, similar books,
                          reading guide logic
ui/components.py         Reusable Streamlit UI components
utils/validators.py      ISBN validation
data/                    Local JSON storage (reading list + saved guides)
```

## Setup instructions (Windows)

These steps assume you already have the project folder (e.g. downloaded
as a ZIP or cloned from a shared repo) and are working in **Command
Prompt** or **PowerShell**.

### 1. Install Python

If you don't already have Python installed, download Python 3.11 or
newer from [python.org/downloads](https://www.python.org/downloads/).
During installation, make sure to check **"Add Python to PATH"**.

Confirm it installed correctly:

```
python --version
```

### 2. Open the project folder

```
cd path\to\Book_Discovery_Companion
```

(Replace the path with wherever you saved/extracted the project.)

### 3. Create a virtual environment

```
python -m venv .venv
```

### 4. Activate the virtual environment (Windows)

**Command Prompt:**
```
.venv\Scripts\activate.bat
```

**PowerShell:**
```
.venv\Scripts\Activate.ps1
```

If PowerShell blocks the script with an execution-policy error, run this
once first, then try activating again:
```
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

You'll know it worked because your prompt will now start with `(.venv)`.

### 5. Install the required packages

```
pip install -r requirements.txt
```

### 6. Create your own `.env` file

Copy the example file:
```
copy .env.example .env
```

### 7. Add your own Gemini API key

Open the new `.env` file in any text editor and replace the placeholder
with your real key:
```
GEMINI_API_KEY=your_actual_key_here
```

You can get a free key from [Google AI Studio](https://aistudio.google.com/apikey).

**Never commit your `.env` file or share your real key with anyone.**
Reading guide generation won't work without a valid key, but every other
feature (search, reading list, similar books) works fine without one.

### 8. Run the application

```
streamlit run app.py
```

### 9. Open it in your browser

Streamlit will print a local URL in the terminal, usually:
```
Local URL: http://localhost:8501
```
It should also open automatically in your default browser. If not, copy
that URL into your browser manually.

## What NOT to share / commit

- **`.env`** — contains your real Gemini API key. Never share this file
  or paste its contents anywhere public. It's already excluded via
  `.gitignore`.
- **`.venv/`** — your local virtual environment. It's large, OS-specific,
  and everyone can recreate it themselves from `requirements.txt`. Also
  excluded via `.gitignore`.
- **`__pycache__/` and `*.pyc` files** — compiled Python cache, regenerated
  automatically. Also excluded.

Each group member should create their **own** `.env` file locally (Step 6
above) using their **own** Gemini API key — don't pass around a shared
key or a shared `.env` file.

## What's safe to share

Everything else: `app.py`, `models/`, `services/`, `ui/`, `utils/`,
`requirements.txt`, `.env.example`, `.gitignore`, and this `README.md`.
The `data/` folder (`reading_list.json`, `reading_guides.json`) can be
shared too if you want group members to start with the same saved data,
or left out if everyone wants their own empty list to start.