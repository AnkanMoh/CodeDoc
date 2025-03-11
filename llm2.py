import streamlit as st
import requests
import base64
import os
from dotenv import load_dotenv
from groq import Groq
from fpdf import FPDF
from functools import lru_cache

load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_PAT")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GITHUB_TOKEN:
    st.error("❌ GitHub API Token not found. Set 'GITHUB_PAT' in your .env' file.")
    st.stop()
if not GROQ_API_KEY:
    st.error("❌ Groq API Key not found. Set 'GROQ_API_KEY' in your .env' file.")
    st.stop()

client = Groq(api_key=GROQ_API_KEY)

st.set_page_config(page_title="Code-Doctor: AI GitHub Bug Fixer", page_icon="🐙", layout="wide")

st.markdown("<h1 style='text-align: center; color:#1D3557;'>Code-Doctor: AI-powered Bug Fixer</h1>", unsafe_allow_html=True)
st.markdown("<h4 style='text-align: center; color:#457B9D;'>Debugging & Feature Enhancements Automated.</h4>", unsafe_allow_html=True)
st.markdown("<hr>", unsafe_allow_html=True)

github_url = st.text_input("🔗 Enter GitHub Repository Link:", placeholder="https://github.com/user/repo")
branch = st.radio("📂 Select Branch:", ["main", "master"])

def extract_repo_details(github_url):
    """Extracts repository owner and name from GitHub URL."""
    parts = github_url.rstrip("/").split("/")
    return (parts[-2], parts[-1]) if len(parts) >= 2 else (None, None)

def fetch_github_issues(owner, repo):
    """Fetches open issues from GitHub."""
    url = f"https://api.github.com/repos/{owner}/{repo}/issues"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    response = requests.get(url, headers=headers)
    return response.json() if response.status_code == 200 else []

def fetch_repo_files(owner, repo, branch):
    """Fetch all source files from the repo, ignoring directories."""
    url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    response = requests.get(url, headers=headers)
    return [file["path"] for file in response.json().get("tree", []) if "path" in file and file["type"] == "blob"] if response.status_code == 200 else []

@lru_cache(maxsize=10)
def fetch_github_issues_cached(owner, repo):
    """Fetch issues with caching to prevent redundant API calls."""
    return fetch_github_issues(owner, repo)

@lru_cache(maxsize=10)
def fetch_repo_files_cached(owner, repo, branch):
    """Fetch repo files with caching."""
    return fetch_repo_files(owner, repo, branch)

def extract_file_path(issue_body, repo_files):
    """Extract a valid source file path from the issue description."""
    valid_extensions = [".py", ".cpp", ".js", ".c", ".java"]
    
    if not issue_body or not repo_files:
        return None

    issue_lines = issue_body.split("\n")  
    for line in issue_lines:  
        for repo_file in repo_files:
            if any(repo_file.endswith(ext) for ext in valid_extensions): 
                if line.strip() in repo_file or line.strip() == os.path.basename(repo_file):  
                    return repo_file  

    return None

def fetch_buggy_code(owner, repo, file_path, branch):
    """Fetch buggy file content from GitHub."""
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{file_path}?ref={branch}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    response = requests.get(url, headers=headers)
    response_data = response.json()

    if isinstance(response_data, dict) and "content" in response_data:
        try:
            return base64.b64decode(response_data["content"]).decode("utf-8")
        except Exception as e:
            st.error(f"❌ Error decoding file `{file_path}`: {e}")
            return None
    elif isinstance(response_data, list):
        st.error(f"❌ `{file_path}` appears to be a directory, not a file.")
    else:
        st.error(f"❌ Failed to fetch `{file_path}`: {response_data.get('message', 'Unknown error')}")
    return None

def is_code_related(issue_body):
    """Check if the issue references a code file or stack trace."""
    if not issue_body: 
        return False
    keywords = ["error", "exception", "traceback", ".py", ".cpp", ".js", ".c", ".java"]
    return any(keyword in issue_body.lower() for keyword in keywords)

def fix_code_with_ai(code_snippet, language):
    """Generates AI-powered bug fixes with clear explanations."""
    try:
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are an AI that fixes code and suggests optimizations. "
                                              "Strictly follow this format:\n\n"
                                              "**Root Cause:** (Clearly explain the issue in one line.)\n\n"
                                              "**Fixed Code:** (Provide only the corrected code.)\n\n"
                                              "**Explanation:** (Summarize how the fix solves the issue.)"},
                {"role": "user", "content": f"Fix this {language} code and provide a direct fix:\n```{code_snippet}```"},
            ],
            model="llama-3.3-70b-versatile",
        )

        ai_response = response.choices[0].message.content.strip()
        formatted_sections = {"Root Cause": "", "Fixed Code": "", "Explanation": ""}

        for section in ai_response.split("\n\n"):
            if "**Root Cause:**" in section:
                formatted_sections["Root Cause"] = section.replace("**Root Cause:**", "").strip()
            elif "**Fixed Code:**" in section:
                formatted_sections["Fixed Code"] = section.replace("**Fixed Code:**", "").strip()
            elif "**Explanation:**" in section:
                formatted_sections["Explanation"] = section.replace("**Explanation:**", "").strip()

        if not formatted_sections["Fixed Code"]:
            st.warning("⚠️ AI did not generate a fix. Requesting a reattempt...")
            return fix_code_with_ai(code_snippet, language) 

        return formatted_sections

    except Exception as e:
        st.error(f"❌ AI Error: {e}")
        return None

if st.button("🔍 Fetch & Fix All Issues"):
    if github_url.strip():
        owner, repo = extract_repo_details(github_url)
        
        if owner and repo:
            with st.spinner("📡 Fetching GitHub issues..."):
                issues = fetch_github_issues_cached(owner, repo)

            if issues:
                repo_files = fetch_repo_files_cached(owner, repo, branch)
                st.subheader("Processing GitHub Issues")
                pdf = FPDF()
                pdf.add_page()
                pdf.set_font("Arial", size=12)

                filtered_issues = [issue for issue in issues if is_code_related(issue.get("body", ""))]

                for idx, issue in enumerate(filtered_issues):
                    file_path = extract_file_path(issue["body"], repo_files)

                    if file_path:
                        st.markdown(f"### 🔍 Issue {idx+1}: {issue['title']}")
                        st.write(issue["body"])
                        st.markdown(f"✅ **Matched File:** `{file_path}`")

                        buggy_code = fetch_buggy_code(owner, repo, file_path, branch)
                        if buggy_code:
                            fix_details = fix_code_with_ai(buggy_code, "Python")
                            if fix_details:
                                st.markdown(f"### 🔍 Root Cause\n{fix_details['Root Cause']}")
                                st.code(fix_details["Fixed Code"], language="python")
                                st.markdown(f"### 📝 Explanation\n{fix_details['Explanation']}")

                pdf_output = "/mnt/data/Fix_Report.pdf"
                pdf.output(pdf_output)
                st.download_button(label="📥 Download Fix Report PDF", data=open(pdf_output, "rb"), file_name="Fix_Report.pdf", mime="application/pdf")

    else:
        st.warning("⚠️ Please enter a GitHub repository link.")

st.markdown("**🚀 Built with ❤️ by Ankan Moh.**")
