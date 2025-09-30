import azure.functions as func
import logging
import os
import json
import requests
from requests.auth import HTTPBasicAuth
import re

app = func.FunctionApp()

# Repo mapping
REPO_MAP = {
    "CustomsOnlineAI": "4890959d-88d1-4ca0-a3ed-f114ac012f13",
    "CustomsOnlineAngular": "8b7baf0c-0000-49d2-a874-254bc6478103",
    "CustomsOnlineBackEnd": "ff0446c2-c9c2-4dea-a598-2226fb886392",
    "CustomsOnlineMobile": "d00d23f3-a9e2-4869-b711-86a4005f214b"
}

# Branch regex kontrolü
BRANCH_REGEX = r"(?i)^(?!.*\s)(?:AI|BE|CT|DO|FE|MP|SQL|TD|UI)-\d+(?:-[a-z0-9]+){2,}$"

AZURE_ORG = "customstechnologies"
AZURE_PROJECT = "CustomsOnline"

@app.function_name(name="HttpExample")
@app.route(route="test", methods=["get", "post"])
def test_function(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    name = req.params.get('name')
    if not name:
        try:
            req_body = req.get_json()
        except ValueError:
            pass
        else:
            name = req_body.get('name')

    if name:
        return func.HttpResponse(f"Hello, {name}. This HTTP triggered function executed successfully.")
    else:
        return func.HttpResponse(
             "This HTTP triggered function executed successfully. Pass a name in the query string or in the request body for a personalized response.",
             status_code=200
        )


@app.function_name(name="NewBranch")
@app.route(route="newBranch", methods=["get"])
def new_branch(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('NewBranch function called.')
    
    try:
        # Parametreleri al
        ticket = req.params.get('ticket')
        repo_name = req.params.get('repo')
        
        # Basit kontroller
        if not ticket or not repo_name:
            return func.HttpResponse(
                json.dumps({"error": "ticket and repo query parameters required"}),
                status_code=400,
                mimetype="application/json"
            )
        
        if repo_name not in REPO_MAP:
            return func.HttpResponse(
                json.dumps({"error": f"Unknown repo '{repo_name}'. Available repos: {list(REPO_MAP.keys())}"}),
                status_code=400,
                mimetype="application/json"
            )
        
        # REGEX kontrolü - Branch ismi formatı
        if not re.match(BRANCH_REGEX, ticket):
            return func.HttpResponse(
                json.dumps({
                    "error": f"Ticket '{ticket}' does not match branch regex", 
                    "required_format": "Example: AI-123-feature-name, BE-456-fix-bug"
                }),
                status_code=400,
                mimetype="application/json"
            )
        
        # AZURE_PAT kontrolü
        azure_pat = os.environ.get("AZURE_PAT")
        if not azure_pat:
            return func.HttpResponse(
                json.dumps({"error": "AZURE_PAT environment variable not set"}),
                status_code=500,
                mimetype="application/json"
            )
        
        repo_id = REPO_MAP[repo_name]
        new_branch_name = ticket
        
        # 🔍 1. Branch'in zaten var olup olmadığını kontrol et
        check_branch_url = f"https://dev.azure.com/{AZURE_ORG}/{AZURE_PROJECT}/_apis/git/repositories/{repo_id}/refs/heads/{new_branch_name}?api-version=7.1-preview.1"
        branch_check = requests.get(check_branch_url, auth=HTTPBasicAuth('', azure_pat))
        
        if branch_check.status_code == 200:
            logging.warning(f"Branch '{new_branch_name}' already exists in repo '{repo_name}'")
            return func.HttpResponse(
                json.dumps({
                    "error": f"Branch '{new_branch_name}' already exists in repository '{repo_name}'",
                    "branch": new_branch_name,
                    "repo": repo_name,
                    "status": "already_exists"
                }),
                status_code=409,
                mimetype="application/json"
            )
        
        # 📥 2. Dev branch'in son commit SHA'sini al
        ref_url = f"https://dev.azure.com/{AZURE_ORG}/{AZURE_PROJECT}/_apis/git/repositories/{repo_id}/refs/heads/dev?api-version=7.1-preview.1"
        r = requests.get(ref_url, auth=HTTPBasicAuth('', azure_pat))
        
        if r.status_code != 200:
            logging.error(f"Failed to get dev branch info: {r.status_code} - {r.text}")
            return func.HttpResponse(
                json.dumps({"error": "Failed to get dev branch info", "details": r.text}),
                status_code=500,
                mimetype="application/json"
            )
        
        try:
            sha = r.json()["value"][0]["objectId"]
            logging.info(f"Got dev branch SHA: {sha}")
        except (KeyError, IndexError) as e:
            logging.error(f"Failed to parse dev branch SHA: {str(e)}")
            return func.HttpResponse(
                json.dumps({"error": "Failed to parse dev branch SHA", "response": r.text}),
                status_code=500,
                mimetype="application/json"
            )
        
        # 🌿 3. Yeni branch oluştur
        create_ref_url = f"https://dev.azure.com/{AZURE_ORG}/{AZURE_PROJECT}/_apis/git/repositories/{repo_id}/refs?api-version=7.1-preview.1"
        
        payload = [{
            "name": f"refs/heads/{new_branch_name}",
            "oldObjectId": "0000000000000000000000000000000000000000",
            "newObjectId": sha
        }]
        
        r2 = requests.post(create_ref_url, json=payload, auth=HTTPBasicAuth('', azure_pat))
        
        if r2.status_code not in (200, 201):
            logging.error(f"Failed to create branch: {r2.status_code} - {r2.text}")
            return func.HttpResponse(
                json.dumps({"error": "Failed to create branch", "details": r2.text}),
                status_code=500,
                mimetype="application/json"
            )
        
        # ✅ Başarılı response
        response_data = {
            "message": f"Branch '{new_branch_name}' created successfully in repo '{repo_name}'",
            "branch": new_branch_name,
            "repo": repo_name,
            "repo_id": repo_id,
            "commit": sha
        }
        
        logging.info(f"Successfully created branch: {new_branch_name}")
        return func.HttpResponse(
            json.dumps(response_data),
            status_code=200,
            mimetype="application/json"
        )
        
    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}")
        return func.HttpResponse(
            json.dumps({"error": "Internal server error", "details": str(e)}),
            status_code=500,
            mimetype="application/json"
        )


@app.function_name(name="HealthCheck")
@app.route(route="healthcheck", methods=["get"])
def healthcheck(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('HealthCheck function called.')
    return func.HttpResponse("OK - All systems working!")
