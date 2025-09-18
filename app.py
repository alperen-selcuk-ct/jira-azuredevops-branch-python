from flask import Flask, request, jsonify
import requests
from requests.auth import HTTPBasicAuth
import os

app = Flask(__name__)

AZURE_ORG = "customstechnologies"
AZURE_PROJECT = "CustomsOnline"
PAT = os.environ.get("AZURE_PAT")

# Repo mapping
REPO_MAP = {
    "CustomsOnline": "079ce68b-4516-49a1-bc33-460eaddd89ae",
    "CustomsOnlineAI": "4890959d-88d1-4ca0-a3ed-f114ac012f13",
    "CustomsOnlineAngular": "8b7baf0c-0000-49d2-a874-254bc6478103",
    "CustomsOnlineBackEnd": "ff0446c2-c9c2-4dea-a598-2226fb886392",
    "CustomsOnlineMobile": "d00d23f3-a9e2-4869-b711-86a4005f214b"
}

@app.route("/newBranch", methods=["GET"])
def new_branch():
    ticket = request.args.get("ticket")
    repo_name = request.args.get("repo")

    if not ticket:
        return jsonify({"error": "ticket param required"}), 400
    if not repo_name or repo_name not in REPO_MAP:
        return jsonify({"error": "repo param missing or invalid"}), 400

    REPO_ID = REPO_MAP[repo_name]

    # dev branch commit SHA'sini al
    ref_url = f"https://dev.azure.com/{AZURE_ORG}/{AZURE_PROJECT}/_apis/git/repositories/{REPO_ID}/refs/heads/dev?api-version=7.1-preview.1"
    r = requests.get(ref_url, auth=HTTPBasicAuth('', PAT))
    r.raise_for_status()
    sha = r.json()["objectId"]

    branch_name = f"feature/{ticket}"

    # yeni branch yarat
    create_url = f"https://dev.azure.com/{AZURE_ORG}/{AZURE_PROJECT}/_apis/git/repositories/{REPO_ID}/refs?api-version=7.1-preview.1"
    payload = [{
        "name": f"refs/heads/{branch_name}",
        "oldObjectId": "0000000000000000000000000000000000000000",
        "newObjectId": sha
    }]
    r2 = requests.post(create_url, json=payload, auth=HTTPBasicAuth('', PAT))
    r2.raise_for_status()

    return jsonify({"message": f"Branch '{branch_name}' created in repo '{repo_name}'!", "status": r2.status_code})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
