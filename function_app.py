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


@app.function_name(name="TaskTransition")
@app.route(route="taskTransition", methods=["get", "post"], auth_level=func.AuthLevel.ANONYMOUS)
def task_transition(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('TaskTransition function called.')
    
    try:
        # Parametreleri al (GET veya POST body'den)
        if req.method == "GET":
            ticket = req.params.get('ticket')
            repo_name = req.params.get('repo')
            from_status = req.params.get('from')
            to_status = req.params.get('to')
        else:
            try:
                req_body = req.get_json()
                ticket = req_body.get('ticket')
                repo_name = req_body.get('repo')
                from_status = req_body.get('from')
                to_status = req_body.get('to')
            except:
                return func.HttpResponse(
                    json.dumps({
                        "status": "INVALID_JSON",
                        "message": "❌ ERROR: Invalid JSON in request body",
                        "success": False
                    }),
                    status_code=400,
                    mimetype="application/json"
                )
        
        # Basit kontroller
        if not all([ticket, repo_name, from_status, to_status]):
            return func.HttpResponse(
                json.dumps({
                    "status": "MISSING_PARAMETERS",
                    "message": "❌ ERROR: Missing required parameters",
                    "error": "Required: ticket, repo, from, to parameters",
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
        
        # Sadece belirli geçişleri destekle
        if from_status.lower() != "in development" or to_status.lower() != "code review":
            return func.HttpResponse(
                json.dumps({
                    "status": "UNSUPPORTED_TRANSITION",
                    "message": f"❌ ERROR: Transition '{from_status}' → '{to_status}' not supported",
                    "error": "Only 'In Development' → 'Code Review' transition is supported",
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
        
        # 🌐 AZURE DEVOPS API ÇAĞRILARI
        import urllib.request
        import urllib.parse
        import base64
        
        # Basic Authentication için header hazırla
        credentials = f":{azure_pat}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        
        try:
            # 1️⃣ Task branch'inin varlığını kontrol et
            branch_url = f"https://dev.azure.com/{AZURE_ORG}/{AZURE_PROJECT}/_apis/git/repositories/{repo_id}/refs/heads/{ticket}?api-version=7.1-preview.1"
            
            req_branch = urllib.request.Request(branch_url)
            req_branch.add_header("Authorization", f"Basic {encoded_credentials}")
            
            try:
                with urllib.request.urlopen(req_branch) as response:
                    branch_data = json.loads(response.read().decode())
                    task_branch_sha = branch_data["value"][0]["objectId"]
                    logging.info(f"Found task branch '{ticket}' with SHA: {task_branch_sha}")
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    return func.HttpResponse(
                        json.dumps({
                            "status": "TASK_BRANCH_NOT_FOUND",
                            "message": f"❌ ERROR: Task branch '{ticket}' not found in '{repo_name}'",
                            "error": "Create the branch first using newBranch endpoint",
                            "success": False
                        }),
                        status_code=404,
                        mimetype="application/json"
                    )
                else:
                    raise e
            
            # 2️⃣ Dev branch'inin SHA'sını al
            dev_url = f"https://dev.azure.com/{AZURE_ORG}/{AZURE_PROJECT}/_apis/git/repositories/{repo_id}/refs/heads/dev?api-version=7.1-preview.1"
            
            req_dev = urllib.request.Request(dev_url)
            req_dev.add_header("Authorization", f"Basic {encoded_credentials}")
            
            with urllib.request.urlopen(req_dev) as response:
                dev_data = json.loads(response.read().decode())
                dev_sha = dev_data["value"][0]["objectId"]
                logging.info(f"Got dev branch SHA: {dev_sha}")
            
            # 3️⃣ Test branch'inin SHA'sını al
            test_url = f"https://dev.azure.com/{AZURE_ORG}/{AZURE_PROJECT}/_apis/git/repositories/{repo_id}/refs/heads/test?api-version=7.1-preview.1"
            
            req_test = urllib.request.Request(test_url)
            req_test.add_header("Authorization", f"Basic {encoded_credentials}")
            
            try:
                with urllib.request.urlopen(req_test) as response:
                    test_data = json.loads(response.read().decode())
                    test_sha = test_data["value"][0]["objectId"]
                    logging.info(f"Got test branch SHA: {test_sha}")
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    return func.HttpResponse(
                        json.dumps({
                            "status": "TEST_BRANCH_NOT_FOUND",
                            "message": f"❌ ERROR: Test branch not found in '{repo_name}'",
                            "error": "Test branch must exist for PR creation",
                            "success": False
                        }),
                        status_code=404,
                        mimetype="application/json"
                    )
                else:
                    raise e
            
            # 4️⃣ Task branch'ini dev ile merge et (conflict kontrolü ile)
            merge_url = f"https://dev.azure.com/{AZURE_ORG}/{AZURE_PROJECT}/_apis/git/repositories/{repo_id}/merges?api-version=7.1-preview.1"
            
            merge_payload = {
                "parents": [dev_sha, task_branch_sha],
                "commitMessage": f"Merge {ticket} into dev - Task transition to Code Review"
            }
            
            merge_data = json.dumps(merge_payload).encode()
            
            req_merge = urllib.request.Request(merge_url, data=merge_data, method='POST')
            req_merge.add_header("Authorization", f"Basic {encoded_credentials}")
            req_merge.add_header("Content-Type", "application/json")
            
            try:
                with urllib.request.urlopen(req_merge) as response:
                    merge_result = json.loads(response.read().decode())
                    merge_commit_sha = merge_result["commitId"]
                    logging.info(f"Merge successful, commit SHA: {merge_commit_sha}")
            except urllib.error.HTTPError as merge_error:
                error_msg = merge_error.read().decode() if merge_error.fp else str(merge_error)
                if "conflict" in error_msg.lower() or merge_error.code == 409:
                    return func.HttpResponse(
                        json.dumps({
                            "status": "MERGE_CONFLICT",
                            "message": f"⚠️ CONFLICT: Cannot merge '{ticket}' into dev due to conflicts",
                            "error": "Resolve conflicts manually before transitioning to Code Review",
                            "branch": ticket,
                            "repo": repo_name,
                            "success": False
                        }),
                        status_code=409,
                        mimetype="application/json"
                    )
                else:
                    raise merge_error
            
            # 5️⃣ Dev branch'ini yeni merge commit ile güncelle
            update_dev_url = f"https://dev.azure.com/{AZURE_ORG}/{AZURE_PROJECT}/_apis/git/repositories/{repo_id}/refs?api-version=7.1-preview.1"
            
            update_payload = [{
                "name": "refs/heads/dev",
                "oldObjectId": dev_sha,
                "newObjectId": merge_commit_sha
            }]
            
            update_data = json.dumps(update_payload).encode()
            
            req_update = urllib.request.Request(update_dev_url, data=update_data, method='POST')
            req_update.add_header("Authorization", f"Basic {encoded_credentials}")
            req_update.add_header("Content-Type", "application/json")
            
            with urllib.request.urlopen(req_update) as response:
                update_result = json.loads(response.read().decode())
                logging.info(f"Dev branch updated successfully")
            
            # 6️⃣ Task branch'inden test branch'ine PR oluştur
            pr_url = f"https://dev.azure.com/{AZURE_ORG}/{AZURE_PROJECT}/_apis/git/repositories/{repo_id}/pullrequests?api-version=7.1-preview.1"
            
            pr_payload = {
                "sourceRefName": f"refs/heads/{ticket}",
                "targetRefName": "refs/heads/test",
                "title": f"[{ticket}] Ready for Testing",
                "description": f"Task {ticket} has been merged into dev and is ready for testing.\n\nStatus Transition: In Development → Code Review",
                "isDraft": False
            }
            
            pr_data = json.dumps(pr_payload).encode()
            
            req_pr = urllib.request.Request(pr_url, data=pr_data, method='POST')
            req_pr.add_header("Authorization", f"Basic {encoded_credentials}")
            req_pr.add_header("Content-Type", "application/json")
            
            with urllib.request.urlopen(req_pr) as response:
                pr_result = json.loads(response.read().decode())
                pr_id = pr_result["pullRequestId"]
                pr_url_web = pr_result["_links"]["web"]["href"]
                logging.info(f"PR created successfully: {pr_id}")
            
            # ✅ Başarılı response
            response_data = {
                "status": "TRANSITION_SUCCESS",
                "message": f"✅ SUCCESS: Task '{ticket}' transitioned from 'In Development' to 'Code Review'",
                "ticket": ticket,
                "repo": repo_name,
                "actions_completed": [
                    f"Merged '{ticket}' into dev branch",
                    f"Created PR #{pr_id} from '{ticket}' to test branch"
                ],
                "merge_commit": merge_commit_sha,
                "pr_id": pr_id,
                "pr_url": pr_url_web,
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
            return func.HttpResponse(
                json.dumps({"error": "Azure DevOps API error", "details": error_msg}),
                status_code=500,
                mimetype="application/json"
            )
        
        except Exception as api_error:
            logging.error(f"API call failed: {str(api_error)}")
            return func.HttpResponse(
                json.dumps({"error": "Failed to process task transition", "details": str(api_error)}),
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
