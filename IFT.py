import os
import json
import re
import difflib
import requests
import javalang
import tempfile
import subprocess
import streamlit as st
import numpy as np
from dotenv import load_dotenv
from urllib.parse import urlparse
from difflib import SequenceMatcher
from rouge import Rouge
from nltk.translate.bleu_score import sentence_bleu, SmoothingFunction

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# List your four models here
MODELS = [
    "llama-3.3-70b-versatile",
    "gemma2-9b-it",
    "llama3-70b-8192",
    "llama3-8b-8192",
]

def parse_bug_sample(path):
    try:
        with open(os.path.join(path, "bug.json")) as f:
            bug_meta = json.load(f)
        with open(os.path.join(path, "method_before.txt")) as f:
            before = f.read()
        with open(os.path.join(path, "method_after.txt")) as f:
            after = f.read()
        return {"bug_meta": bug_meta, "before": before, "after": after}
    except Exception as e:
        st.error(f"Error reading files: {e}")
        return None

def call_groq_fix_model(code, meta, model_name):
    prompt = (
        "You are an expert Java developer. Fix the following buggy method, preserving its logic.\n"
        f"Bug Type: {meta.get('bug_type','Unknown')}\n"
        f"Severity: {meta.get('severity','Unknown')}\n"
        f"Location: Line {meta.get('line_number','Unknown')}\n\n"
        "Buggy Method:\n"
        f"```java\n{code.strip()}\n```\n\n"
        "Respond ONLY with the corrected method in a Java code block."
    )
    r = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
        json={
            "model": model_name,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.0,
            "top_p": 1.0,
            "max_tokens": 1024
        },
    )
    if r.status_code == 200:
        return r.json()["choices"][0]["message"]["content"]
    st.error(f"API error {r.status_code}: {r.text}")
    return ""

def strip_md(code):
    return re.sub(r'```[a-z]*\n([\s\S]*?)```', r'\1', code).strip()

def normalize(code):
    code = re.sub(r'//.*', '', code)
    code = re.sub(r'/\*[\s\S]*?\*/', '', code)
    code = re.sub(r'\s+', ' ', code)
    return code.strip().lower()

def ast_sim(c1, c2):
    try:
        t1 = javalang.parse.parse(c1)
        t2 = javalang.parse.parse(c2)
        return SequenceMatcher(None, str(t1), str(t2)).ratio()
    except:
        return 0.0

def evaluate_fix(ref, pred):
    r = strip_md(ref)
    p = strip_md(pred)
    rn = normalize(r)
    pn = normalize(p)
    smoothie = SmoothingFunction().method4
    bleu = sentence_bleu([re.findall(r'\w+', rn)], re.findall(r'\w+', pn), smoothing_function=smoothie)
    try:
        rouge_l = Rouge().get_scores(pn, rn)[0]["rouge-l"]["f"]
    except:
        rouge_l = 0.0
    lev = SequenceMatcher(None, pn, rn).ratio()
    return {
        "BLEU": round(bleu * 100, 2),
        "ROUGE-L": round(rouge_l * 100, 2),
        "Levenshtein": round(lev * 100, 2),
    }

def show_diff(a, b):
    return "\n".join(difflib.unified_diff(
        a.splitlines(), b.splitlines(),
        fromfile="LLM Fix", tofile="Ground Truth", lineterm=""
    ))

def traverse_and_fix(root, model_name):
    results = []
    count = 0
    for d, _, files in os.walk(root):
        if count >= 10:
            break
        if {"bug.json", "method_before.txt", "method_after.txt"} <= set(files):
            sample = parse_bug_sample(d)
            if not sample:
                continue
            st.markdown(f"#### 🐞 Bug #{count+1}: {d}")
            st.code(sample["before"], language="java")
            fix = call_groq_fix_model(sample["before"], sample["bug_meta"], model_name)
            m = evaluate_fix(sample["after"], fix)
            results.append(m)
            count += 1
    return results

def clone_repo(url):
    parts = urlparse(url).path.strip("/").split("/")
    if len(parts) < 2:
        st.error("Invalid GitHub URL.")
        return None, None
    owner, repo = parts[:2]
    tmp = tempfile.mkdtemp()
    subprocess.run(["git", "clone", f"https://github.com/{owner}/{repo}.git", tmp], check=True)
    sub = "/".join(parts[3:]) if "tree" in parts else ""
    p = os.path.join(tmp, sub)
    return tmp, p if os.path.isdir(p) else tmp

st.set_page_config(page_title="InferredBugs LLM Fixer", layout="wide")
st.title("CodeDoc IFT")

repo = st.text_input("GitHub URL to subdirectory")
if repo and st.button("Clone & Compare Models"):
    with st.spinner("Cloning and analyzing across models..."):
        tmp, path = clone_repo(repo)
        if not path or not os.path.isdir(path):
            st.error("Bad path after clone.")
        else:
            table = []
            for model in MODELS:
                st.write(f"## Running on model: **{model}**")
                res = traverse_and_fix(path, model)
                avg_bleu = np.mean([r["BLEU"] for r in res])
                avg_rouge = np.mean([r["ROUGE-L"] for r in res])
                avg_lev   = np.mean([r["Levenshtein"] for r in res])
                table.append({
                    "Model": model,
                    "Avg BLEU": f"{avg_bleu:.2f}",
                    "Avg ROUGE-L": f"{avg_rouge:.2f}",
                    "Avg Levenshtein": f"{avg_lev:.2f}"
                })
            st.subheader("📊 Model Comparison")
            st.table(table)
