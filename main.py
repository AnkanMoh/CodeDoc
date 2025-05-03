import streamlit as st
import requests
import base64
import os
import re
from dotenv import load_dotenv
from groq import Groq
from fpdf import FPDF
from functools import lru_cache
import difflib

load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_PAT")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
ANOTHER_LLM_API_KEY = os.getenv("ANOTHER_LLM_API_KEY")  

if not GITHUB_TOKEN:
    st.error("❌ GitHub API Token not found. Set 'GITHUB_PAT' in your .env' file.")
    st.stop()
if not GROQ_API_KEY:
    st.error("❌ Groq API Key not found. Set 'GROQ_API_KEY' in your .env' file.")
    st.stop()
if not ANOTHER_LLM_API_KEY:
    st.error("❌ Another LLM API Key not found. Set 'ANOTHER_LLM_API_KEY' in your .env' file.")
    st.stop()

client = Groq(api_key=GROQ_API_KEY)
llm_client = Groq(api_key=ANOTHER_LLM_API_KEY) 


def extract_file_path(issue_body, repo_files):
    """Extracts file path from GitHub issue body. Supports absolute URL or relative path."""
    try:
        
        response = llm_client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an AI that extracts file paths from GitHub issue descriptions. "
                        "Your task is to find and return the exact GitHub file path or relative file path mentioned. "
                        "Return only the path part, like 'src/main.py' or 'test/CMakeLists.txt'. If none found, reply 'not there'."
                    )
                },
                {
                    "role": "user",
                    "content": f"Extract file path (absolute or relative) from:\n\n{issue_body}"
                }
            ],
            model="mixtral-8x7b-32768",
        )
        
        extracted_text = response.choices[0].message.content.strip()
        print(f"[LLM Output] {extracted_text}")

        if not extracted_text or not repo_files:
            return None

        github_url_match = re.search(
            r"https://github\.com/[^/]+/[^/]+/blob/[^/]+/([^\s`'\"#)>\]]+)", extracted_text
        )
        if github_url_match:
            file_path = github_url_match.group(1).strip()
            normalized_file_path = file_path.lower().strip()
            normalized_repo_files = [f.lower().strip() for f in repo_files]

            if normalized_file_path in normalized_repo_files:
                print(f"[✅ Absolute Path Match] {file_path}")
                return file_path

            
            close_matches = difflib.get_close_matches(
                normalized_file_path, normalized_repo_files, n=1, cutoff=0.6
            )
            if close_matches:
                best_match_index = normalized_repo_files.index(close_matches[0])
                print(f"[🔍 Fuzzy Absolute Match] {repo_files[best_match_index]}")
                return repo_files[best_match_index]

       
        relative_path_candidate = extracted_text.strip()
        normalized_candidate = relative_path_candidate.lower()
        normalized_repo_files = [f.lower().strip() for f in repo_files]

        if normalized_candidate in normalized_repo_files:
            print(f"[✅ Relative Path Match] {relative_path_candidate}")
            return relative_path_candidate

        close_matches = difflib.get_close_matches(
            normalized_candidate, normalized_repo_files, n=1, cutoff=0.6
        )
        if close_matches:
            best_match_index = normalized_repo_files.index(close_matches[0])
            print(f"[🔍 Fuzzy Relative Match] {repo_files[best_match_index]}")
            return repo_files[best_match_index]

        print(f"[❌ No Match] '{relative_path_candidate}' not found in repo.")
        return None

    except Exception as e:
        print(f"[❌ Exception] {e}")
        return None



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

# def fetch_repo_files(owner, repo, branch):
#     """Fetch all source files from the repo, ignoring directories."""
#     url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
#     headers = {"Authorization": f"token {GITHUB_TOKEN}"}
#     response = requests.get(url, headers=headers)
#     # print([file for file in response.json().get("tree", [])])
#     return [file["path"] for file in response.json().get("tree", []) if "path" in file and file["type"] == "blob"] if response.status_code == 200 else []


import requests

def fetch_repo_files(owner, repo, branch):
    """Fetch all source files from the repo, handling pagination properly."""
    url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        print("Error:", response.status_code, response.json())
        return []

    tree = response.json().get("tree", [])
    
    # Debugging: Check if test/CMakeLists.txt is present
    for file in tree:
        if file["path"] == "test/CMakeLists.txt":
            print("File Found:", file)

    return [file["path"] for file in tree if file["type"] == "blob"]



@lru_cache(maxsize=10)
def fetch_github_issues_cached(owner, repo):
    """Fetch issues with caching to prevent redundant API calls."""
    return fetch_github_issues(owner, repo)

@lru_cache(maxsize=10)
def fetch_repo_files_cached(owner, repo, branch):
    """Fetch repo files with caching."""
    return fetch_repo_files(owner, repo, branch)



def fetch_buggy_code(owner, repo, file_path, branch):
    """Fetch buggy file content from GitHub using the extracted full file path."""
    if not file_path:
        return None

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
    keywords = ["error", "exception", "traceback", ".py", ".cpp", ".js", ".c", ".java", ".txt"]
    return any(keyword in issue_body.lower() for keyword in keywords)



def fix_code_with_ai(code_snippet, language, issue_body):
    """Generates AI-powered bug fixes with clear explanations based on the given GitHub issue."""
    try:
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are an AI  that fixes code and suggests optimizations and suggest code whenever required. \n"
                                                  "Strictly follow this format:\n\n"
                                                  "**Root Cause:** (Clearly explain the issue in one line.)\n\n"
                                                  "**Fixed Code:** (Provide only the corrected code.)\n\n"
                                                  "**Explanation:** (Summarize how the fix solves the issue.)"},
                {"role": "user", "content": f"Fix this {language} code strictly based on the given GitHub issue. \n\n"
                                              f"### GitHub Issue:\n{issue_body}\n\n"
                                              f"### Buggy Code:\n```{language}\n{code_snippet}\n```"},
            ],
            model="llama-3.3-70b-versatile",
        )

        # 🔍 Debug: Print full AI response
        ai_response = response.choices[0].message.content.strip()
        # st.write("### 🔍 Raw AI Response:")
        # st.code(ai_response, language="markdown")

        # Use regex to extract sections
        root_cause_match = re.search(r"\*\*Root Cause:\*\*\s*(.*?)\n", ai_response, re.DOTALL)
        fixed_code_match = re.search(r"\*\*Fixed Code:\*\*\s*```(?:\w+)?\n(.*?)```", ai_response, re.DOTALL)
        explanation_match = re.search(r"\*\*Explanation:\*\*\s*(.*)", ai_response, re.DOTALL)

        formatted_sections = {
            "Root Cause": root_cause_match.group(1).strip() if root_cause_match else "Not Found",
            "Fixed Code": fixed_code_match.group(1).strip() if fixed_code_match else "Not Found",
            "Explanation": explanation_match.group(1).strip() if explanation_match else "Not Found",
        }

        # 🔍 Debug: Print extracted sections
        st.write("### 🛠 Extracted Sections from AI:")
        st.write(f"**Root Cause:** {formatted_sections['Root Cause']}")
        st.code(formatted_sections["Fixed Code"], language=language.lower() if language != "Unknown" else "plaintext")
        st.write(f"**Explanation:** {formatted_sections['Explanation']}")

        # Check if fixed code is missing
        if formatted_sections["Fixed Code"] == "Not Found":
            st.warning("⚠️ AI did not generate a fix. Retrying...")
            return fix_code_with_ai(code_snippet, language, issue_body)  # Retry once

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
                
                st.subheader("🐞 Processing GitHub Issues")
                pdf = FPDF()
                pdf.add_page()
                pdf.set_font("Arial", size=12)

                filtered_issues = [issue for issue in issues if is_code_related(issue.get("body", ""))]



                for idx, issue in enumerate(filtered_issues):

                    print('start1')
                    file_path = extract_file_path(issue["body"], repo_files)
                    
                    # Extract issue status (open or closed)
                    issue_status = issue.get("state", "unknown").capitalize()

                    st.markdown(f"### 🔍 Issue {idx+1}: {issue['title']} ({issue_status})")
                    st.write(issue["body"])
                    print(idx+1)
                    print('start2')
                    # Debugging: Print all repo files
                    # st.write(f"🔍 Available repo files: {repo_files}")

                    # Debugging: Print extracted file path
                    # if file_path:
                    #     st.markdown(f"✅ **Matched File:** `{file_path}`")
                    # else:
                    #     st.warning(f"⚠️ No matching file found for issue {idx+1}.")
                    #     continue  # Skip this issue if no file path is found

                    if not file_path:
                        st.warning(f"⚠️ No valid file path found for issue {idx+1}. Skipping to the next issue.")
                        continue  # Skip to the next issue

                    st.markdown(f"✅ **Matched File:** `{file_path}`")

                    # Fetch buggy code
                    buggy_code = fetch_buggy_code(owner, repo, file_path, branch)

                    # Detect language from file extension
                    file_extension = os.path.splitext(file_path)[1].lower()
                    language_map = {
                        ".py": "Python", ".cpp": "C++", ".js": "JavaScript",
                        ".c": "C", ".java": "Java", ".txt": "",
                    }
                    language = language_map.get(file_extension, "Unknown")

                    # Debugging: Print extracted code snippet and language
                    if buggy_code:
                        st.markdown(f"### 📝 Extracted Code Snippet")
                        st.code(buggy_code, language=language.lower() if language != "Unknown" else "plaintext")
                        st.markdown(f"🌍 **Detected Language:** `{language}`")

                        fix_details = fix_code_with_ai(buggy_code, language, issue["body"])
                        if fix_details:
                            st.markdown(f"### 🔍 Root Cause\n{fix_details['Root Cause']}")
                            st.code(fix_details["Fixed Code"], language=language.lower() if language != "Unknown" else "plaintext")
                            st.markdown(f"### 📝 Explanation\n{fix_details['Explanation']}")
                    else:
                        st.warning(f"⚠️ Failed to retrieve the code from `{file_path}`.")



    else:
        st.warning("⚠️ Please enter a GitHub repository link.")

st.markdown("**🚀 Built with ❤️ by Ankan Moh, Hanvik S and Sanjay Maj.**")
