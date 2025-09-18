from flask import Flask, request, jsonify
import requests
from requests.auth import HTTPBasicAuth
import os

app = Flask(__name__)

AZURE_ORG = "customstechnologies"
AZURE_PROJECT = "CustomsOnline"
REPO_ID = "ff0446c2-c9c2-4dea-a598-2226fb886392"
PAT = os.environ.get("AZURE_PAT")

@app.route("/newBranch")
def new_branch():
    ticket = request.args.get("ticket")
    if not ticket:
        return jsonify({"error": "ticket param required"}), 400

    ref_url = f"https://dev.azure.com/{AZURE_ORG}/{AZURE_PROJECT}/_apis/git/repositories/{REPO_ID}/refs/heads/dev?api-version=7.1-preview.1"
    r = requests.get(ref_url, auth=HTTPBasicAuth('', PAT))
    r.raise_for_status()
    sha = r.json()["objectId"]

    branch_name = f"feature/{ticket}"
    create_url = f"https://dev.azure.com/{AZURE_ORG}/{AZURE_PROJECT}/_apis/git/repositories/{REPO_ID}/refs?api-version=7.1-preview.1"
    payload = [{
        "name": f"refs/heads/{branch_name}",
        "oldObjectId": "0000000000000000000000000000000000000000",
        "newObjectId": sha
    }]
    r2 = requests.post(create_url, json=payload, auth=HTTPBasicAuth('', PAT))
    r2.raise_for_status()

    return jsonify({"message": f"Branch '{branch_name}' created!", "status": r2.status_code})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
