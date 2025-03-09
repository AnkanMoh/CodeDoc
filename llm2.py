import streamlit as st
import requests
import base64
import os
from dotenv import load_dotenv
from groq import Groq
from fpdf import FPDF

# Load API Keys
load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_PAT")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GITHUB_TOKEN:
    st.error("❌ GitHub API Token not found. Set 'GITHUB_PAT' in your .env' file.")
    st.stop()
if not GROQ_API_KEY:
    st.error("❌ Groq API Key not found. Set 'GROQ_API_KEY' in your .env' file.")
    st.stop()

# Initialize AI Client
client = Groq(api_key=GROQ_API_KEY)

# UI Configuration
st.set_page_config(page_title="Code-Doctor: AI GitHub Bug Fixer", page_icon="🐙", layout="wide")

st.markdown("<h1 style='text-align: center; color:#1D3557;'>Code-Doctor: AI-powered Bug Fixer</h1>", unsafe_allow_html=True)
st.markdown("<h4 style='text-align: center; color:#457B9D;'>Debugging made smarter with AI.</h4>", unsafe_allow_html=True)
st.markdown("<hr>", unsafe_allow_html=True)

# User Inputs
github_url = st.text_input("🔗 Enter GitHub Repository Link:", placeholder="https://github.com/user/repo")
branch = st.radio("📂 Select Branch:", ["main", "master"])

# Functions
def extract_repo_details(github_url):
    parts = github_url.rstrip("/").split("/")
    return (parts[-2], parts[-1]) if len(parts) >= 2 else (None, None)

def fetch_github_issues(owner, repo):
    url = f"https://api.github.com/repos/{owner}/{repo}/issues"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    response = requests.get(url, headers=headers)
    return response.json() if response.status_code == 200 else []

def fetch_repo_files(owner, repo, branch):
    url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    response = requests.get(url, headers=headers)
    return [file["path"] for file in response.json().get("tree", []) if "path" in file and file["path"].endswith((".py", ".cpp", ".js", ".c", ".java"))] if response.status_code == 200 else []

def extract_file_path(issue_body, repo_files):
    if not issue_body or not repo_files:
        return None
    for line in issue_body.split("\n"):
        for repo_file in repo_files:
            if line.strip() in repo_file:
                return repo_file
    return None

def fetch_buggy_code(owner, repo, file_path, branch):
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{file_path}?ref={branch}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    response = requests.get(url, headers=headers)
    return base64.b64decode(response.json()["content"]).decode("utf-8") if response.status_code == 200 else None

def fix_code_with_ai(code_snippet, language):
    try:
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are an expert AI software engineer. Your task is to debug and optimize code with clear explanations. "
                                              "Provide the following details:\n"
                                              "1. **Root Cause:** Explain why the bug occurs.\n"
                                              "2. **Fixed Code:** Provide the corrected code in a proper format.\n"
                                              "3. **Explanation:** Clearly explain what was fixed and why, in a professional manner."},
                {"role": "user", "content": f"Debug and optimize this {language} code:\n```{code_snippet}```"},
            ],
            model="mixtral-8x7b-32768",
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        st.error(f"❌ AI Error: {e}")
        return None

# Fetch Issues & Fix Bugs
if st.button("🔍 Fetch & Fix All Issues"):
    if github_url.strip():
        owner, repo = extract_repo_details(github_url)
        with st.spinner("📡 Fetching GitHub issues..."):
            issues = fetch_github_issues(owner, repo)

        if issues:
            repo_files = fetch_repo_files(owner, repo, branch)
            st.subheader("🐞 Open GitHub Issues (Processing All)")

            filtered_issues = []
            for issue in issues:
                file_path = extract_file_path(issue["body"], repo_files)
                if file_path:
                    filtered_issues.append({"title": issue["title"], "body": issue["body"], "file_path": file_path})

            if filtered_issues:
                pdf = FPDF()
                pdf.add_page()
                pdf.set_font("Arial", size=12)

                for idx, issue in enumerate(filtered_issues):
                    st.markdown(f"### 🔍 Issue {idx+1}: {issue['title']}")
                    st.write(issue["body"])
                    st.markdown(f"**✅ Matched File:** `{issue['file_path']}`")

                    with st.spinner(f"📡 Fetching source code for `{issue['file_path']}`..."):
                        buggy_code = fetch_buggy_code(owner, repo, issue["file_path"], branch)

                    if buggy_code:
                        with st.spinner("AI is generating a fix..."):
                            fixed_code = fix_code_with_ai(buggy_code, "Python")

                        if fixed_code:
                            st.subheader("AI-Generated Fix Report")
                            sections = fixed_code.split("\n\n")
                            report_text = f"Issue: {issue['title']}\n\n"

                            for section in sections:
                                if "**Root Cause:**" in section:
                                    st.markdown(f"### Root Cause\n{section.replace('**Root Cause:**', '').strip()}")
                                    report_text += f"\nRoot Cause:\n{section.replace('**Root Cause:**', '').strip()}\n\n"
                                elif "**Fixed Code:**" in section:
                                    st.subheader("Fixed Code")
                                    st.code(section.replace('**Fixed Code:**', '').strip(), language="python")
                                    report_text += f"\nFixed Code:\n{section.replace('**Fixed Code:**', '').strip()}\n\n"
                                elif "**Explanation:**" in section:
                                    st.markdown(f"### Explanation\n{section.replace('**Explanation:**', '').strip()}")
                                    report_text += f"\nExplanation:\n{section.replace('**Explanation:**', '').strip()}\n\n"

                            pdf.multi_cell(0, 10, report_text)
                        else:
                            st.error("❌ AI could not generate a fix.")
                    else:
                        st.error(f"❌ Could not fetch `{issue['file_path']}` from the repository.")

                pdf_output = "/mnt/data/Fix_Report.pdf"
                pdf.output(pdf_output)
                st.success("✅ All Issues Fixed & Report Generated!")
                st.download_button(label="📥 Download Fix Report PDF", data=open(pdf_output, "rb"), file_name="Fix_Report.pdf", mime="application/pdf")

            else:
                st.warning("⚠️ No issues found with valid file paths.")
    else:
        st.warning("⚠️ Please enter a GitHub repository link.")

st.markdown("**Built with ❤️ by Ankan Moh.**")