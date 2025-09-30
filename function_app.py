import azure.functions as func
import logging
import os
import json

app = func.FunctionApp()

# Repo mapping
REPO_MAP = {
    "CustomsOnlineAI": "4890959d-88d1-4ca0-a3ed-f114ac012f13",
    "CustomsOnlineAngular": "8b7baf0c-0000-49d2-a874-254bc6478103",
    "CustomsOnlineBackEnd": "ff0446c2-c9c2-4dea-a598-2226fb886392",
    "CustomsOnlineMobile": "d00d23f3-a9e2-4869-b711-86a4005f214b"
}

# Branch regex kontrolü - SADECE STRING OLARAK
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
        
        # REGEX kontrolü - BASIT STRING KONTROL
        # Format: AI-123-feature-name veya BE-456-fix-bug
        ticket_upper = ticket.upper()
        valid_prefixes = ["AI-", "BE-", "CT-", "DO-", "FE-", "MP-", "SQL-", "TD-", "UI-"]
        
        if not any(ticket_upper.startswith(prefix) for prefix in valid_prefixes):
            return func.HttpResponse(
                json.dumps({
                    "error": f"Ticket '{ticket}' does not start with valid prefix", 
                    "valid_prefixes": valid_prefixes,
                    "example": "AI-123-feature-name"
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
        
        # SIMÜLASYON - Gerçek API çağrısı yapmayacağız şimdilik
        response_data = {
            "message": f"Branch '{ticket}' would be created in repo '{repo_name}'",
            "branch": ticket,
            "repo": repo_name,
            "repo_id": repo_id,
            "validation": "passed",
            "status": "simulated"
        }
        
        logging.info(f"Simulated branch creation: {ticket}")
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
