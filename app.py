# app.py
from flask import Flask, request, jsonify
import os
import requests
from requests.auth import HTTPBasicAuth
import re

app = Flask(__name__)

# Repo mapping
REPO_MAP = {
    "CustomsOnline": "079ce68b-4516-49a1-bc33-460eaddd89ae",
    "CustomsOnlineAI": "4890959d-88d1-4ca0-a3ed-f114ac012f13",
    "CustomsOnlineAngular": "8b7baf0c-0000-49d2-a874-254bc6478103",
    "CustomsOnlineBackEnd": "ff0446c2-c9c2-4dea-a598-2226fb886392",
    "CustomsOnlineMobile": "d00d23f3-a9e2-4869-b711-86a4005f214b"
}

# Branch regex
BRANCH_REGEX = r"(?i)^(?!.*\s)(?:AI|BE|CT|DO|FE|MP|SQL|TD|UI)-\d+(?:-[a-z0-9]+){2,}$"

AZURE_ORG = "customstechnologies"
AZURE_PROJECT = "CustomsOnline"
AZURE_PAT = os.environ.get("AZURE_PAT")

if not AZURE_PAT:
    raise ValueError("AZURE_PAT environment variable not set!")


@app.route("/newBranch", methods=["GET"])
def new_branch():
    ticket = request.args.get("ticket")
    repo_name = request.args.get("repo")
    
    if not ticket or not repo_name:
        return jsonify({"error": "ticket and repo query parameters required"}), 400
    if repo_name not in REPO_MAP:
        return jsonify({"error": f"Unknown repo '{repo_name}'"}), 400
    
    # Regex kontrolü
    if not re.match(BRANCH_REGEX, ticket):
        return jsonify({"error": f"Ticket '{ticket}' does not match branch regex"}), 400
    
    repo_id = REPO_MAP[repo_name]
    
    # 1️⃣ Dev branch'in son commit SHA'sini al
    ref_url = f"https://dev.azure.com/{AZURE_ORG}/{AZURE_PROJECT}/_apis/git/repositories/{repo_id}/refs/heads/dev?api-version=7.1-preview.1"
    r = requests.get(ref_url, auth=HTTPBasicAuth('', AZURE_PAT))
    
    if r.status_code != 200:
        return jsonify({"error": "Failed to get dev branch info", "status": r.status_code, "text": r.text}), 500
    
    try:
        sha = r.json()["value"][0]["objectId"]
    except Exception as e:
        return jsonify({"error": "Failed to parse dev branch SHA", "details": str(e), "response_text": r.text}), 500
    
    # 2️⃣ Yeni branch oluştur (prefix yok)
    new_branch_name = ticket
    create_ref_url = f"https://dev.azure.com/{AZURE_ORG}/{AZURE_PROJECT}/_apis/git/repositories/{repo_id}/refs?api-version=7.1-preview.1"
    
    payload = {
        "name": f"refs/heads/{new_branch_name}",
        "oldObjectId": "0000000000000000000000000000000000000000",
        "newObjectId": sha
    }
    
    r2 = requests.post(create_ref_url, json=[payload], auth=HTTPBasicAuth('', AZURE_PAT))
    
    if r2.status_code not in (200, 201):
        return jsonify({"error": "Failed to create branch", "status": r2.status_code, "text": r2.text}), 500
    
    return jsonify({
        "message": f"Branch '{new_branch_name}' created successfully in repo '{repo_name}'",
        "branch": new_branch_name,
        "repo": repo_name,
        "commit": sha
    })

# ✅ Healthcheck endpoint
@app.route("/healthcheck", methods=["GET"])
def healthcheck():
    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
