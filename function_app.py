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
        
        # REGEX kontrolü - FOLDER/BRANCH formatını da destekle
        # Format: AI-123-feature-name veya herhangi-folder/AI-123-feature-name
        ticket_upper = ticket.upper()
        valid_prefixes = ["AI-", "BE-", "CT-", "DO-", "FE-", "MP-", "SQL-", "TD-", "UI-"]
        
        # Folder varsa son kısmı kontrol et, yoksa direkt kontrol et
        if '/' in ticket:
            # folder/branch formatı: herhangi-folder/AI-123-feature -> AI-123-feature kısmını kontrol et
            branch_part = ticket.split('/')[-1].upper()
            if not any(branch_part.startswith(prefix) for prefix in valid_prefixes):
                return func.HttpResponse(
                    json.dumps({
                        "status": "BRANCH_NAME_WRONG",
                        "message": f"❌ BRANCH NAME ERROR: '{ticket}' format is invalid",
                        "error": f"Branch part '{branch_part}' must start with valid prefix: {', '.join(valid_prefixes)}",
                        "example": "developer/AI-123-feature-name or AI-123-feature-name",
                        "ticket": ticket,
                        "success": False
                    }),
                    status_code=400,
                    mimetype="application/json"
                )
        else:
            # Direkt branch formatı: AI-123-feature
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
                # Branch zaten var, ama hata vermeyelim - başarılı olarak gösterelim
                logging.info(f"Branch '{ticket}' already exists, returning success")
                return func.HttpResponse(
                    json.dumps({
                        "status": "BRANCH_ALREADY_EXISTS",
                        "message": f"✅ SUCCESS: Branch '{ticket}' already exists in '{repo_name}'",
                        "branch": ticket,
                        "repo": repo_name,
                        "repo_id": repo_id,
                        "note": "Branch was already created previously",
                        "success": True
                    }),
                    status_code=200,
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
            # URL encode ticket name for proper API call
            encoded_ticket = urllib.parse.quote(ticket, safe='')
            check_url = f"https://dev.azure.com/{AZURE_ORG}/{AZURE_PROJECT}/_apis/git/repositories/{repo_id}/refs/heads/{encoded_ticket}?api-version=7.1-preview.1"
            
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
    Jira 'In Development' -> 'Code Review' geçişi için:
    1. Feature branch'i 'dev'e merge eder (conflict yoksa).
    2. Feature branch'ten 'test'e PR açar.
    """
    logging.info('CodeReviewTransition function called.')
    
    try:
        ticket = req.params.get('ticket')
        repo_name = req.params.get('repo')

        # --- 1. Parametre ve Ortam Değişkeni Kontrolleri ---
        if not ticket or not repo_name:
            return func.HttpResponse(json.dumps({"status": "MISSING_PARAMETERS", "message": "❌ 'ticket' and 'repo' parameters are required"}), status_code=400, mimetype="application/json")
        
        if repo_name not in REPO_MAP:
            return func.HttpResponse(json.dumps({"status": "INVALID_REPO", "message": f"❌ Unknown repository '{repo_name}'"}), status_code=400, mimetype="application/json")

        azure_pat = os.environ.get("AZURE_PAT")
        if not azure_pat:
            return func.HttpResponse(json.dumps({"error": "AZURE_PAT environment variable not set"}), status_code=500, mimetype="application/json")

        repo_id = REPO_MAP[repo_name]
        
        # --- 2. İzole Yardımcı Fonksiyonlar ---
        import urllib.request, urllib.error, urllib.parse, base64

        def _cr_do_request(url: str, method: str = 'GET', payload: dict = None) -> dict:
            """Bu fonksiyona özel, izole request yardımcısı."""
            headers = {
                "Authorization": f"Basic {base64.b64encode(f':{azure_pat}'.encode()).decode()}",
                "Content-Type": "application/json"
            }
            data = json.dumps(payload).encode() if payload is not None else None
            req_obj = urllib.request.Request(url, data=data, method=method, headers=headers)
            with urllib.request.urlopen(req_obj) as resp:
                txt = resp.read().decode()
                return json.loads(txt) if txt else {}

        def _cr_get_branch_sha(branch_name: str) -> str:
            """Bu fonksiyona özel, izole SHA alma yardımcısı."""
            # URL encode branch name for proper API call
            encoded_branch = urllib.parse.quote(branch_name, safe='')
            url = f"https://dev.azure.com/{AZURE_ORG}/{AZURE_PROJECT}/_apis/git/repositories/{repo_id}/refs?filter=heads/{encoded_branch}&api-version=7.1-preview.1"
            refs = _cr_do_request(url)
            if 'value' in refs and len(refs['value']) > 0:
                return refs['value'][0]['objectId']
            raise ValueError(f"Branch '{branch_name}' not found or SHA could not be retrieved.")

        # --- 3. Ana Akış ---
        # Branch SHA'larını al
        source_sha = _cr_get_branch_sha(ticket)
        target_sha = _cr_get_branch_sha('dev')
        
        # Eğer branch'ler aynı SHA'ya sahipse, merge gerekli değil
        if source_sha == target_sha:
            logging.info(f"Branch '{ticket}' already up to date with dev")
        else:
            # 'dev' Branch'ini direkt güncelle (fast-forward merge)
            update_ref_url = f"https://dev.azure.com/{AZURE_ORG}/{AZURE_PROJECT}/_apis/git/repositories/{repo_id}/refs?api-version=7.1-preview.1"
            update_payload = [{"name": "refs/heads/dev", "oldObjectId": target_sha, "newObjectId": source_sha}]
            try:
                _cr_do_request(update_ref_url, method='POST', payload=update_payload)
                logging.info(f"Successfully fast-forward merged '{ticket}' into dev. New dev SHA: {source_sha}")
            except urllib.error.HTTPError as merge_err:
                if merge_err.code == 409:
                    return func.HttpResponse(json.dumps({"status": "MERGE_CONFLICT", "message": f"⚠️ Merge conflict: '{ticket}' cannot be fast-forward merged into dev. Manual merge required."}), status_code=409, mimetype="application/json")
                raise

        # 'test' Branch'ine PR Aç
        pr_create_url = f"https://dev.azure.com/{AZURE_ORG}/{AZURE_PROJECT}/_apis/git/repositories/{repo_id}/pullrequests?api-version=7.1-preview.1"
        pr_payload_test = {
            "sourceRefName": f"refs/heads/{ticket}",
            "targetRefName": "refs/heads/test",
            "title": f"Code Review: {ticket} -> test",
            "description": f"Automated PR from '{ticket}' to 'test' after successful merge into 'dev'."
        }
        test_pr = _cr_do_request(pr_create_url, method='POST', payload=pr_payload_test)
        test_pr_id = test_pr.get("pullRequestId")
        logging.info(f"Successfully created PR to test: #{test_pr_id}")

        # Başarılı Sonuç
        resp = {
            "status": "CODE_REVIEW_OK",
            "message": f"✅ Merged '{ticket}' into dev and opened PR to test.",
            "dev_new_sha": source_sha,
            "test_pr_id": test_pr_id,
            "test_pr_url": f"https://dev.azure.com/{AZURE_ORG}/{AZURE_PROJECT}/_git/{repo_name}/pullrequest/{test_pr_id}"
        }
        return func.HttpResponse(json.dumps(resp), status_code=200, mimetype="application/json")

    except (ValueError, urllib.error.HTTPError) as e:
        error_message = str(e)
        if isinstance(e, urllib.error.HTTPError):
            error_message = e.read().decode()
        logging.error(f"Error in CodeReviewTransition: {error_message}")
        return func.HttpResponse(json.dumps({"status": "EXECUTION_ERROR", "message": "❌ An error occurred during execution.", "error": error_message}), status_code=500, mimetype="application/json")
    except Exception as e:
        logging.error(f"Unexpected error in CodeReviewTransition: {str(e)}")
        return func.HttpResponse(json.dumps({"status": "UNEXPECTED_ERROR", "message": "❌ An unexpected error occurred."}), status_code=500, mimetype="application/json")
