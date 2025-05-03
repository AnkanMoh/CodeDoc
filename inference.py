import streamlit as st
import json
import os
from dotenv import load_dotenv
from difflib import SequenceMatcher, ndiff
import pandas as pd
from groq import Groq

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    st.error("❌ Please set GROQ_API_KEY in your .env file.")
    st.stop()

groq_client = Groq(api_key=GROQ_API_KEY)

st.set_page_config(page_title="Code-Doctor Debug", layout="wide")
st.title("🔍 Code-Doctor: Evaluation")
st.caption("Debugging sudden score drops by inspecting prompts & outputs")

uploaded_file = st.file_uploader("📁 Upload a ⁠ .jsonl ⁠ file", type=["jsonl"])

def compute_similarity(predicted, actual):
    a = predicted.strip().replace(" ", "").replace("\n", "")
    b = actual.strip().replace(" ", "").replace("\n", "")
    return SequenceMatcher(None, a, b).ratio()

def get_diff(old, new):
    return "\n".join(ndiff(old.splitlines(), new.splitlines()))

def clean_prediction(pred):
    lines = pred.strip().split("\n")
    return "\n".join([l for l in lines if l and not l.startswith("//") and "```" not in l and "**" not in l])

def build_prompt(old_code, diff, comment):
    return f"""You are an elite AI trained to fix buggy code using reviewer comments and diffs.

Revise the original code based ONLY on the diff and comment. Apply minimal edits. Do not explain.

Original Code:
{old_code}

Diff:
{diff}

Comment:
{comment}

Respond with ONLY the updated code:
"""

def generate_fix(prompt):
    try:
        return groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}]
        ).choices[0].message.content.strip()
    except Exception as e:
        return f"[ERROR] {e}"

if uploaded_file and st.button("Run Debugging"):
    dataset = [json.loads(line) for line in uploaded_file.readlines()][:300]
    results = []
    scores = []

    for i, sample in enumerate(dataset):
        required = ["old", "hunk", "comment", "new"]
        if not all(k in sample for k in required):
            st.error(f"Sample {i+1} missing required keys.")
            continue

        old = sample["old"]
        diff = sample["hunk"]
        comment = sample["comment"]
        target = sample["new"]

        prompt = build_prompt(old, diff, comment)
        if len(prompt.split()) > 1500:
            st.warning(f"Sample {i+1}: Prompt too long for LLaMA (tokens={len(prompt.split())})")

        response = generate_fix(prompt)
        if response.startswith("[ERROR]"):
            st.error(f"Sample {i+1}: {response}")
            continue

        cleaned = clean_prediction(response)
        sim = compute_similarity(cleaned, target)
        scores.append(sim)

        results.append({
            "Sample #": i + 1,
            "Similarity (%)": round(sim * 100, 2),
            "Comment": comment,
            "Prediction": cleaned,
            "Target": target,
            "Prompt Tokens": len(prompt.split())
        })

        with st.expander(f"🧠 Sample {i+1} (Sim: {round(sim*100,2)}%)"):
            st.markdown("*🧾 Prompt:*")
            st.code(prompt)
            st.markdown("*🔧 Prediction:*")
            st.code(cleaned)
            st.markdown("*✅ Target:*")
            st.code(target)
            st.markdown("*🧮 Diff:*")
            st.code(get_diff(target, cleaned), language="diff")

    if scores:
        avg = round(sum(scores) / len(scores) * 100, 2)
        st.metric("Average Similarity", f"{avg}%")
        df = pd.DataFrame(results)
        st.dataframe(df)
        st.download_button("📥 Download Results", df.to_csv(index=False).encode(), file_name="debug_results.csv")
