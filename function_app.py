@app.function_name(name="CodeReviewTransition")
//... existing code ...
        # 2. Branch SHA'larını Al
        try:
            source_ref_data = do_request(f"https://dev.azure.com/{AZURE_ORG}/{AZURE_PROJECT}/_apis/git/repositories/{repo_id}/refs?filter=heads/{ticket}&api-version=7.1-preview.1")
            target_ref_data = do_request(f"https://dev.azure.com/{AZURE_ORG}/{AZURE_PROJECT}/_apis/git/repositories/{repo_id}/refs?filter=heads/dev&api-version=7.1-preview.1")

            source_sha = (source_ref_data.get('value') or [{}])[0].get('objectId')
            target_sha = (target_ref_data.get('value') or [{}])[0].get('objectId')

            if not source_sha or not target_sha:
                raise ValueError("Could not retrieve valid SHA for source or target branch.")

        except (IndexError, KeyError, urllib.error.HTTPError, ValueError) as e:
            return func.HttpResponse(json.dumps({"status": "BRANCH_NOT_FOUND", "message": "❌ Source or dev branch not found or SHA could not be retrieved.", "error": str(e), "success": False}), status_code=404, mimetype="application/json")
//... existing code ...import azure.functions as func
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
@app.route(route="test", methods=["get", "post"], auth_level=func.AuthLevel.ANONYMOUS)
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
@app.route(route="newBranch", methods=["get"], auth_level=func.AuthLevel.ANONYMOUS)
def new_branch(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('NewBranch function called.')
    
    try:
        # Parametreleri al
        ticket = req.params.get('ticket')
        repo_name = req.params.get('repo')
        
        # Basit kontroller
        if not ticket or not repo_name:
            return func.HttpResponse(
                json.dumps({
                    "status": "MISSING_PARAMETERS",
                    "message": "❌ ERROR: Missing required parameters",
                    "error": "Both 'ticket' and 'repo' parameters are required",
                    "success": False
                }),
                status_code=400,
                mimetype="application/json"
            )
        
        if repo_name not in REPO_MAP:
            return func.HttpResponse(
                json.dumps({
                    "status": "INVALID_REPO",
                    "message": f"❌ ERROR: Unknown repository '{repo_name}'",
                    "error": f"Available repos: {', '.join(REPO_MAP.keys())}",
                    "success": False
                }),
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
                    "status": "BRANCH_NAME_WRONG",
                    "message": f"❌ BRANCH NAME ERROR: '{ticket}' format is invalid",
                    "error": f"Ticket must start with valid prefix: {', '.join(valid_prefixes)}",
                    "example": "AI-123-feature-name",
                    "ticket": ticket,
                    "success": False
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
        
        # 🌐 GERÇEK AZURE DEVOPS API ÇAĞRISI - urllib kullanarak
        import urllib.request
        import urllib.parse
        import base64
        
        # Basic Authentication için header hazırla
        credentials = f":{azure_pat}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        
        try:
            # 0️⃣ Branch'in zaten var olup olmadığını kontrol et (Azure DevOps bazı durumlarda duplicate create'e hata döndürmeyebiliyor)
            existing_url = f"https://dev.azure.com/{AZURE_ORG}/{AZURE_PROJECT}/_apis/git/repositories/{repo_id}/refs/heads/{ticket}?api-version=7.1-preview.1"
            existing_req = urllib.request.Request(existing_url)
            existing_req.add_header("Authorization", f"Basic {encoded_credentials}")
            existing_req.add_header("Content-Type", "application/json")
            import urllib.error
            try:
                with urllib.request.urlopen(existing_req) as existing_resp:
                    existing_data = json.loads(existing_resp.read().decode())
                    if existing_data.get("value"):
                        logging.info(f"Branch already exists (pre-check): {ticket}")
                        return func.HttpResponse(
                            json.dumps({
                                "status": "BRANCH_CONFLICT",
                                "message": f"⚠️ CONFLICT: Branch '{ticket}' already exists in '{repo_name}'",
                                "branch": ticket,
                                "repo": repo_name,
                                "error": "Branch already exists",
                                "success": False
                            }),
                            status_code=409,
                            mimetype="application/json"
                        )
            except urllib.error.HTTPError as pre_check_err:
                # 404 => branch yok, devam et; diğer durumlarda hatayı fırlat
                if pre_check_err.code != 404:
                    error_msg = pre_check_err.read().decode() if pre_check_err.fp else str(pre_check_err)
                    logging.error(f"Branch existence check failed: {pre_check_err.code} - {error_msg}")
                    return func.HttpResponse(
                        json.dumps({
                            "status": "BRANCH_CHECK_ERROR",
                            "message": "❌ ERROR: Failed while checking if branch exists",
                            "error": error_msg,
                            "success": False
                        }),
                        status_code=500,
                        mimetype="application/json"
                    )

            # 1️⃣ Dev branch'in SHA'sını al
            dev_url = f"https://dev.azure.com/{AZURE_ORG}/{AZURE_PROJECT}/_apis/git/repositories/{repo_id}/refs/heads/dev?api-version=7.1-preview.1"
            
            req_dev = urllib.request.Request(dev_url)
            req_dev.add_header("Authorization", f"Basic {encoded_credentials}")
            req_dev.add_header("Content-Type", "application/json")
            
            with urllib.request.urlopen(req_dev) as response:
                dev_data = json.loads(response.read().decode())
                sha = dev_data["value"][0]["objectId"]
                logging.info(f"Got dev branch SHA: {sha}")
            
            # 2️⃣ Yeni branch oluştur
            create_url = f"https://dev.azure.com/{AZURE_ORG}/{AZURE_PROJECT}/_apis/git/repositories/{repo_id}/refs?api-version=7.1-preview.1"
            
            payload = [{
                "name": f"refs/heads/{ticket}",
                "oldObjectId": "0000000000000000000000000000000000000000",
                "newObjectId": sha
            }]
            
            data = json.dumps(payload).encode()
            
            req_create = urllib.request.Request(create_url, data=data, method='POST')
            req_create.add_header("Authorization", f"Basic {encoded_credentials}")
            req_create.add_header("Content-Type", "application/json")
            
            with urllib.request.urlopen(req_create) as response:
                create_result = json.loads(response.read().decode())
                logging.info(f"Branch created successfully: {ticket}")
            
            # ✅ Başarılı response
            response_data = {
                "status": "BRANCH_CREATED",
                "message": f"✅ SUCCESS: Branch '{ticket}' created successfully in '{repo_name}'",
                "branch": ticket,
                "repo": repo_name,
                "repo_id": repo_id,
                "commit": sha,
                "success": True
            }
            
            return func.HttpResponse(
                json.dumps(response_data),
                status_code=200,
                mimetype="application/json"
            )
            
        except urllib.error.HTTPError as e:
            error_msg = e.read().decode() if e.fp else str(e)
            logging.error(f"Azure DevOps API error: {e.code} - {error_msg}")
            
            if e.code == 409:
                return func.HttpResponse(
                    json.dumps({
                        "status": "BRANCH_CONFLICT",
                        "message": f"⚠️ CONFLICT: Branch '{ticket}' already exists in '{repo_name}'",
                        "branch": ticket,
                        "repo": repo_name,
                        "error": "Branch already exists",
                        "success": False
                    }),
                    status_code=409,
                    mimetype="application/json"
                )
            else:
                return func.HttpResponse(
                    json.dumps({"error": "Azure DevOps API error", "details": error_msg}),
                    status_code=500,
                    mimetype="application/json"
                )
        
        except Exception as api_error:
            logging.error(f"API call failed: {str(api_error)}")
            return func.HttpResponse(
                json.dumps({"error": "Failed to create branch", "details": str(api_error)}),
                status_code=500,
                mimetype="application/json"
            )
        
    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}")
        return func.HttpResponse(
            json.dumps({"error": "Internal server error", "details": str(e)}),
            status_code=500,
            mimetype="application/json"
        )


@app.function_name(name="DeleteBranch")
@app.route(route="deleteBranch", methods=["get"], auth_level=func.AuthLevel.ANONYMOUS)
def delete_branch(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('DeleteBranch function called.')
    
    try:
        # Parametreleri al
        ticket = req.params.get('ticket')
        repo_name = req.params.get('repo')
        
        # Basit kontroller
        if not ticket or not repo_name:
            return func.HttpResponse(
                json.dumps({
                    "status": "MISSING_PARAMETERS",
                    "message": "❌ ERROR: Missing required parameters",
                    "error": "Both 'ticket' and 'repo' parameters are required",
                    "success": False
                }),
                status_code=400,
                mimetype="application/json"
            )
        
        if repo_name not in REPO_MAP:
            return func.HttpResponse(
                json.dumps({
                    "status": "INVALID_REPO",
                    "message": f"❌ ERROR: Unknown repository '{repo_name}'",
                    "error": f"Available repos: {', '.join(REPO_MAP.keys())}",
                    "success": False
                }),
                status_code=400,
                mimetype="application/json"
            )
        
        # Main/master/dev branch'lerini korumalı kontrol
        protected_branches = ["main", "master", "dev", "develop", "release"]
        if ticket.lower() in protected_branches:
            return func.HttpResponse(
                json.dumps({
                    "status": "PROTECTED_BRANCH",
                    "message": f"❌ ERROR: Cannot delete protected branch '{ticket}'",
                    "error": f"Protected branches: {', '.join(protected_branches)}",
                    "success": False
                }),
                status_code=403,
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
        
        # 🌐 GERÇEK AZURE DEVOPS API ÇAĞRISI - urllib kullanarak
        import urllib.request
        import urllib.parse
        import base64
        
        # Basic Authentication için header hazırla
        credentials = f":{azure_pat}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        
        try:
            # 1️⃣ Önce branch'in var olup olmadığını kontrol et
            check_url = f"https://dev.azure.com/{AZURE_ORG}/{AZURE_PROJECT}/_apis/git/repositories/{repo_id}/refs/heads/{ticket}?api-version=7.1-preview.1"
            
            req_check = urllib.request.Request(check_url)
            req_check.add_header("Authorization", f"Basic {encoded_credentials}")
            req_check.add_header("Content-Type", "application/json")
            
            try:
                with urllib.request.urlopen(req_check) as response:
                    branch_data = json.loads(response.read().decode())
                    current_sha = branch_data["value"][0]["objectId"]
                    logging.info(f"Found branch '{ticket}' with SHA: {current_sha}")
            except urllib.error.HTTPError as check_error:
                if check_error.code == 404:
                    return func.HttpResponse(
                        json.dumps({
                            "status": "BRANCH_NOT_FOUND",
                            "message": f"⚠️ NOT FOUND: Branch '{ticket}' does not exist in '{repo_name}'",
                            "branch": ticket,
                            "repo": repo_name,
                            "error": "Branch not found",
                            "success": False
                        }),
                        status_code=404,
                        mimetype="application/json"
                    )
                else:
                    raise check_error
            
            # 2️⃣ Branch'i sil
            delete_url = f"https://dev.azure.com/{AZURE_ORG}/{AZURE_PROJECT}/_apis/git/repositories/{repo_id}/refs?api-version=7.1-preview.1"
            
            payload = [{
                "name": f"refs/heads/{ticket}",
                "oldObjectId": current_sha,
                "newObjectId": "0000000000000000000000000000000000000000"
            }]
            
            data = json.dumps(payload).encode()
            
            req_delete = urllib.request.Request(delete_url, data=data, method='POST')
            req_delete.add_header("Authorization", f"Basic {encoded_credentials}")
            req_delete.add_header("Content-Type", "application/json")
            
            with urllib.request.urlopen(req_delete) as response:
                delete_result = json.loads(response.read().decode())
                logging.info(f"Branch deleted successfully: {ticket}")
            
            # ✅ Başarılı response
            response_data = {
                "status": "BRANCH_DELETED",
                "message": f"✅ SUCCESS: Branch '{ticket}' deleted successfully from '{repo_name}'",
                "branch": ticket,
                "repo": repo_name,
                "repo_id": repo_id,
                "success": True
            }
            
            return func.HttpResponse(
                json.dumps(response_data),
                status_code=200,
                mimetype="application/json"
            )
            
        except urllib.error.HTTPError as e:
            error_msg = e.read().decode() if e.fp else str(e)
            logging.error(f"Azure DevOps API error: {e.code} - {error_msg}")
            
            if e.code == 404:
                return func.HttpResponse(
                    json.dumps({
                        "status": "BRANCH_NOT_FOUND",
                        "message": f"⚠️ NOT FOUND: Branch '{ticket}' does not exist in '{repo_name}'",
                        "branch": ticket,
                        "repo": repo_name,
                        "error": "Branch not found",
                        "success": False
                    }),
                    status_code=404,
                    mimetype="application/json"
                )
            else:
                return func.HttpResponse(
                    json.dumps({"error": "Azure DevOps API error", "details": error_msg}),
                    status_code=500,
                    mimetype="application/json"
                )
        
        except Exception as api_error:
            logging.error(f"API call failed: {str(api_error)}")
            return func.HttpResponse(
                json.dumps({"error": "Failed to delete branch", "details": str(api_error)}),
                status_code=500,
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
@app.route(route="healthcheck", methods=["get"], auth_level=func.AuthLevel.ANONYMOUS)
def healthcheck(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('HealthCheck function called.')
    return func.HttpResponse("OK - All systems working!")


@app.function_name(name="CodeReviewTransition")
@app.route(route="codeReviewTransition", methods=["get"], auth_level=func.AuthLevel.ANONYMOUS)
def code_review_transition(req: func.HttpRequest) -> func.HttpResponse:
    """
    Jira 'In Development' -> 'Code Review' geçişi tetiklendiğinde çağrılır.
    1. Feature branch (ticket) -> dev otomatik merge (branch silinmez)
       - Conflict varsa işlemi durdur ve hata döndür.
    2. Aynı feature branch -> test branch'ine PR aç.
    """
    logging.info('CodeReviewTransition function called.')
    
    try:
        ticket = req.params.get('ticket')
        repo_name = req.params.get('repo')

        # 1. Parametre ve PAT Kontrolleri
        if not ticket or not repo_name:
            return func.HttpResponse(json.dumps({"status": "MISSING_PARAMETERS", "message": "❌ 'ticket' and 'repo' parameters are required", "success": False}), status_code=400, mimetype="application/json")
        
        if repo_name not in REPO_MAP:
            return func.HttpResponse(json.dumps({"status": "INVALID_REPO", "message": f"❌ Unknown repository '{repo_name}'", "success": False}), status_code=400, mimetype="application/json")

        azure_pat = os.environ.get("AZURE_PAT")
        if not azure_pat:
            return func.HttpResponse(json.dumps({"error": "AZURE_PAT environment variable not set"}), status_code=500, mimetype="application/json")

        repo_id = REPO_MAP[repo_name]
        
        import urllib.request, urllib.error, base64

        credentials = f":{azure_pat}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        auth_header = {"Authorization": f"Basic {encoded_credentials}", "Content-Type": "application/json"}

        def do_request(url: str, method: str = 'GET', payload=None):
            data = json.dumps(payload).encode() if payload is not None else None
            req_obj = urllib.request.Request(url, data=data, method=method, headers=auth_header)
            with urllib.request.urlopen(req_obj) as resp:
                txt = resp.read().decode()
                return json.loads(txt) if txt else None

        # 2. Branch SHA'larını Al
        try:
            source_ref_data = do_request(f"https://dev.azure.com/{AZURE_ORG}/{AZURE_PROJECT}/_apis/git/repositories/{repo_id}/refs?filter=heads/{ticket}&api-version=7.1-preview.1")
            target_ref_data = do_request(f"https://dev.azure.com/{AZURE_ORG}/{AZURE_PROJECT}/_apis/git/repositories/{repo_id}/refs?filter=heads/dev&api-version=7.1-preview.1")

            source_sha = (source_ref_data.get('value') or [{}])[0].get('objectId')
            target_sha = (target_ref_data.get('value') or [{}])[0].get('objectId')

            if not source_sha or not target_sha:
                raise ValueError("Could not retrieve valid SHA for source or target branch.")

        except (IndexError, KeyError, urllib.error.HTTPError, ValueError) as e:
            return func.HttpResponse(json.dumps({"status": "BRANCH_NOT_FOUND", "message": "❌ Source or dev branch not found or SHA could not be retrieved.", "error": str(e), "success": False}), status_code=404, mimetype="application/json")

        # 3. Merge Conflict Kontrolü (PR açmadan)
        try:
            merge_check_url = f"https://dev.azure.com/{AZURE_ORG}/{AZURE_PROJECT}/_apis/git/repositories/{repo_id}/merges?api-version=7.1-preview.1"
            merge_check_payload = {"parents": [source_sha, target_sha]}
            merge_commit = do_request(merge_check_url, method='POST', payload=merge_check_payload)
            new_merge_commit_sha = merge_commit['commitId']
        except urllib.error.HTTPError as e:
            if e.code == 409: # Conflict
                return func.HttpResponse(json.dumps({"status": "MERGE_CONFLICT", "message": f"⚠️ Merge conflict: '{ticket}' cannot be merged into dev.", "success": False}), status_code=409, mimetype="application/json")
            else:
                raise

        # 4. 'dev' Branch'ini Güncelle (Merge işlemini tamamla)
        update_ref_url = f"https://dev.azure.com/{AZURE_ORG}/{AZURE_PROJECT}/_apis/git/repositories/{repo_id}/refs?api-version=7.1-preview.1"
        update_payload = [{
            "name": "refs/heads/dev",
            "oldObjectId": target_sha,
            "newObjectId": new_merge_commit_sha
        }]
        do_request(update_ref_url, method='POST', payload=update_payload)
        logging.info(f"Successfully merged '{ticket}' into dev. New dev SHA: {new_merge_commit_sha}")

        # 5. 'test' Branch'ine PR Aç
        pr_create_url = f"https://dev.azure.com/{AZURE_ORG}/{AZURE_PROJECT}/_apis/git/repositories/{repo_id}/pullrequests?api-version=7.1-preview.1"
        pr_payload_test = {
            "sourceRefName": f"refs/heads/{ticket}",
            "targetRefName": "refs/heads/test",
            "title": f"Code Review: {ticket} -> test",
            "description": f"Automated PR from '{ticket}' to 'test' after successful merge into 'dev'."
        }
        test_pr = do_request(pr_create_url, method='POST', payload=pr_payload_test)
        test_pr_id = test_pr.get("pullRequestId")
        logging.info(f"Successfully created PR to test: #{test_pr_id}")

        # 6. Başarılı Sonuç
        resp = {
            "status": "CODE_REVIEW_OK",
            "message": f"✅ Merged '{ticket}' into dev and opened PR to test.",
            "branch": ticket,
            "repo": repo_name,
            "dev_merge_commit": new_merge_commit_sha,
            "test_pr_id": test_pr_id,
            "test_pr_url": f"https://dev.azure.com/{AZURE_ORG}/{AZURE_PROJECT}/_git/{repo_name}/pullrequest/{test_pr_id}",
            "success": True
        }
        return func.HttpResponse(json.dumps(resp), status_code=200, mimetype="application/json")

    except Exception as e:
        logging.error(f"Unexpected error in CodeReviewTransition: {str(e)}")
        return func.HttpResponse(json.dumps({"status": "UNEXPECTED_ERROR", "message": "❌ Unexpected failure", "error": str(e), "success": False}), status_code=500, mimetype="application/json")

