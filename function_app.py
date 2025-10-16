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
    "CustomsOnlineMobile": "d00d23f3-a9e2-4869-b711-86a4005f214b",
    "CTJira": "37b3a1ae-60f2-4ab8-9d2b-da5d8ba743e2"
}

# Branch regex kontrolü - SADECE STRING OLARAK
BRANCH_REGEX = r"(?i)^(?!.*\s)(?:AI|BE|CT|DO|FE|MP|SQL|TD|UI)-\d+(?:-[a-z0-9]+){2,}$"

AZURE_ORG = "customstechnologies"
AZURE_PROJECT = "CustomsOnline"

def format_pr_title(branch_name: str) -> str:
    """
    Branch ismini PR title formatına çevirir.
    Örnek: ramazan-altinsoy/CT-8594-firma-firma-ekle-ilgililer 
    -> CT-8594: Firma Firma Ekle İlgililer
    """
    # Folder varsa sadece branch kısmını al
    if '/' in branch_name:
        actual_branch = branch_name.split('/')[-1]
    else:
        actual_branch = branch_name
    
    # Branch formatı: CT-8594-firma-firma-ekle-ilgililer
    parts = actual_branch.split('-')
    if len(parts) < 3:
        return actual_branch  # Format uygun değilse olduğu gibi döndür
    
    # İlk iki parça ticket kodu: CT-8594
    ticket_code = f"{parts[0]}-{parts[1]}"
    
    # Geri kalan kısım description: firma-firma-ekle-ilgililer
    description_parts = parts[2:]
    
    # Her kelimenin ilk harfini büyüt, - işaretlerini boşluğa çevir
    formatted_description = ' '.join([word.capitalize() for word in description_parts])
    
    # Final format: CT-8594: Firma Firma Ekle İlgililer
    return f"{ticket_code}: {formatted_description}"

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
        user_email = req.params.get('user_email')  # Jira webhook'tan gelen user email
        
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


@app.function_name(name="DevMerge")
@app.route(route="devmerge", methods=["get"], auth_level=func.AuthLevel.ANONYMOUS)
def dev_merge(req: func.HttpRequest) -> func.HttpResponse:
    """
    Feature branch'i 'dev' branch'ine merge eder (branch'i silmez).
    Hem 'In Development -> Code Review' hem 'Code Review -> Analyst Appr.' için kullanılır.
    """
    logging.info('DevMerge function called.')
    
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

        def _dm_do_request(url: str, method: str = 'GET', payload: dict = None) -> dict:
            """DevMerge fonksiyonuna özel request yardımcısı."""
            headers = {
                "Authorization": f"Basic {base64.b64encode(f':{azure_pat}'.encode()).decode()}",
                "Content-Type": "application/json"
            }
            data = json.dumps(payload).encode() if payload is not None else None
            req_obj = urllib.request.Request(url, data=data, method=method, headers=headers)
            with urllib.request.urlopen(req_obj) as resp:
                txt = resp.read().decode()
                return json.loads(txt) if txt else {}

        def _dm_get_branch_sha(branch_name: str) -> str:
            """DevMerge fonksiyonuna özel SHA alma yardımcısı."""
            encoded_branch = urllib.parse.quote(branch_name, safe='')
            url = f"https://dev.azure.com/{AZURE_ORG}/{AZURE_PROJECT}/_apis/git/repositories/{repo_id}/refs?filter=heads/{encoded_branch}&api-version=7.1-preview.1"
            refs = _dm_do_request(url)
            if 'value' in refs and len(refs['value']) > 0:
                return refs['value'][0]['objectId']
            raise ValueError(f"Branch '{branch_name}' not found or SHA could not be retrieved.")

        # --- 3. Ana Akış ---
        # Branch SHA'larını al
        source_sha = _dm_get_branch_sha(ticket)
        target_sha = _dm_get_branch_sha('dev')
        
        # Eğer branch'ler aynı SHA'ya sahipse, merge gerekli değil
        if source_sha == target_sha:
            logging.info(f"Branch '{ticket}' already up to date with dev")
            return func.HttpResponse(json.dumps({
                "status": "ALREADY_UP_TO_DATE",
                "message": f"✅ Branch '{ticket}' is already up to date with dev.",
                "branch": ticket,
                "repo": repo_name,
                "dev_sha": target_sha
            }), status_code=200, mimetype="application/json")
        else:
            # Basic 3-way merge (merge commit oluşturur)
            merge_url = f"https://dev.azure.com/{AZURE_ORG}/{AZURE_PROJECT}/_apis/git/repositories/{repo_id}/merges?api-version=7.1-preview.1"
            merge_payload = {
                "parents": [source_sha, target_sha],
                "comment": f"Merge {ticket} into dev"
            }
            try:
                merge_result = _dm_do_request(merge_url, method='POST', payload=merge_payload)
                new_merge_commit_sha = merge_result['commitId']
                logging.info(f"Successfully created merge commit: {new_merge_commit_sha}")
                
                # Dev branch'ini yeni merge commit'e güncelle
                update_ref_url = f"https://dev.azure.com/{AZURE_ORG}/{AZURE_PROJECT}/_apis/git/repositories/{repo_id}/refs?api-version=7.1-preview.1"
                update_payload = [{"name": "refs/heads/dev", "oldObjectId": target_sha, "newObjectId": new_merge_commit_sha}]
                _dm_do_request(update_ref_url, method='POST', payload=update_payload)
                logging.info(f"Successfully updated dev branch to merge commit: {new_merge_commit_sha}")
                
            except urllib.error.HTTPError as merge_err:
                if merge_err.code == 409:
                    return func.HttpResponse(json.dumps({"status": "MERGE_CONFLICT", "message": f"⚠️ Merge conflict: '{ticket}' has conflicts with dev. Manual merge required."}), status_code=409, mimetype="application/json")
                raise

        # Başarılı Sonuç
        resp = {
            "status": "DEV_MERGE_OK",
            "message": f"✅ Successfully merged '{ticket}' into dev.",
            "branch": ticket,
            "repo": repo_name,
            "dev_old_sha": target_sha,
            "dev_new_sha": new_merge_commit_sha,
            "merge_commit": new_merge_commit_sha
        }
        return func.HttpResponse(json.dumps(resp), status_code=200, mimetype="application/json")

    except (ValueError, urllib.error.HTTPError) as e:
        error_message = str(e)
        if isinstance(e, urllib.error.HTTPError):
            error_message = e.read().decode()
        logging.error(f"Error in DevMerge: {error_message}")
        return func.HttpResponse(json.dumps({"status": "EXECUTION_ERROR", "message": "❌ An error occurred during execution.", "error": error_message}), status_code=500, mimetype="application/json")
    except Exception as e:
        logging.error(f"Unexpected error in DevMerge: {str(e)}")
        return func.HttpResponse(json.dumps({"status": "UNEXPECTED_ERROR", "message": "❌ An unexpected error occurred."}), status_code=500, mimetype="application/json")


@app.function_name(name="PrOpen")
@app.route(route="propen", methods=["get"], auth_level=func.AuthLevel.ANONYMOUS)
def pr_open(req: func.HttpRequest) -> func.HttpResponse:
    """
    Feature branch'ten 'test' branch'ine PR açar.
    'In Development -> Code Review' workflow'u için kullanılır.
    """
    logging.info('PrOpen function called.')
    
    try:
        ticket = req.params.get('ticket')
        repo_name = req.params.get('repo')
        user_email = req.params.get('user_email')  # Jira webhook'tan gelen user email

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

        def _po_do_request(url: str, method: str = 'GET', payload: dict = None) -> dict:
            """PrOpen fonksiyonuna özel request yardımcısı."""
            headers = {
                "Authorization": f"Basic {base64.b64encode(f':{azure_pat}'.encode()).decode()}",
                "Content-Type": "application/json"
            }
            data = json.dumps(payload).encode() if payload is not None else None
            req_obj = urllib.request.Request(url, data=data, method=method, headers=headers)
            with urllib.request.urlopen(req_obj) as resp:
                txt = resp.read().decode()
                return json.loads(txt) if txt else {}

        def _po_get_branch_sha(branch_name: str) -> str:
            """PrOpen fonksiyonuna özel SHA alma yardımcısı."""
            encoded_branch = urllib.parse.quote(branch_name, safe='')

        def _po_get_azure_user(email: str) -> dict:
            """Email ile Azure DevOps user bilgisini bulur."""
            if not email:
                return None
            try:
                # Azure DevOps Users API ile email'e göre user ara
                search_url = f"https://vssps.dev.azure.com/{AZURE_ORG}/_apis/graph/users?api-version=7.1-preview.1"
                users = _po_do_request(search_url)
                
                for user in users.get('value', []):
                    if user.get('mailAddress', '').lower() == email.lower():
                        return {
                            "id": user.get('originId'),
                            "displayName": user.get('displayName'),
                            "uniqueName": user.get('mailAddress')
                        }
                return None
            except Exception as e:
                logging.warning(f"Could not find Azure user for email {email}: {str(e)}")
                return None
            url = f"https://dev.azure.com/{AZURE_ORG}/{AZURE_PROJECT}/_apis/git/repositories/{repo_id}/refs?filter=heads/{encoded_branch}&api-version=7.1-preview.1"
            refs = _po_do_request(url)
            if 'value' in refs and len(refs['value']) > 0:
                return refs['value'][0]['objectId']
            raise ValueError(f"Branch '{branch_name}' not found or SHA could not be retrieved.")

        # --- 3. Ana Akış ---
        # Branch'lerin varlığını kontrol et
        try:
            source_sha = _po_get_branch_sha(ticket)
            test_sha = _po_get_branch_sha('test')
        except ValueError as e:
            if 'test' in str(e):
                return func.HttpResponse(json.dumps({"status": "TARGET_BRANCH_NOT_FOUND", "message": "❌ Target branch 'test' does not exist in repository. Please create 'test' branch first."}), status_code=404, mimetype="application/json")
            else:
                return func.HttpResponse(json.dumps({"status": "SOURCE_BRANCH_NOT_FOUND", "message": f"❌ Source branch '{ticket}' does not exist in repository."}), status_code=404, mimetype="application/json")

        # 'test' Branch'ine PR Aç
        pr_create_url = f"https://dev.azure.com/{AZURE_ORG}/{AZURE_PROJECT}/_apis/git/repositories/{repo_id}/pullrequests?api-version=7.1-preview.1"
        formatted_title = format_pr_title(ticket)
        
        # User bilgisini bul
        azure_user = _po_get_azure_user(user_email) if user_email else None
        
        pr_payload_test = {
            "sourceRefName": f"refs/heads/{ticket}",
            "targetRefName": "refs/heads/test",
            "title": formatted_title,
            "description": f"Automated PR from '{ticket}' to 'test' for code review process."
        }
        
        # Eğer user bilgisi bulunduysa createdBy ekle
        if azure_user:
            pr_payload_test["createdBy"] = azure_user
            logging.info(f"Setting PR author to: {azure_user.get('displayName')} ({azure_user.get('uniqueName')})")
        else:
            logging.warning(f"Could not find Azure user for email: {user_email}")
            
        test_pr = _po_do_request(pr_create_url, method='POST', payload=pr_payload_test)
        test_pr_id = test_pr.get("pullRequestId")
        logging.info(f"Successfully created PR to test: #{test_pr_id}")

        # Başarılı Sonuç
        resp = {
            "status": "PR_OPENED",
            "message": f"✅ Successfully opened PR from '{ticket}' to test.",
            "branch": ticket,
            "repo": repo_name,
            "pr_id": test_pr_id,
            "pr_url": f"https://dev.azure.com/{AZURE_ORG}/{AZURE_PROJECT}/_git/{repo_name}/pullrequest/{test_pr_id}"
        }
        return func.HttpResponse(json.dumps(resp), status_code=200, mimetype="application/json")

    except (ValueError, urllib.error.HTTPError) as e:
        error_message = str(e)
        if isinstance(e, urllib.error.HTTPError):
            error_message = e.read().decode()
        logging.error(f"Error in PrOpen: {error_message}")
        return func.HttpResponse(json.dumps({"status": "EXECUTION_ERROR", "message": "❌ An error occurred during execution.", "error": error_message}), status_code=500, mimetype="application/json")
    except Exception as e:
        logging.error(f"Unexpected error in PrOpen: {str(e)}")
        return func.HttpResponse(json.dumps({"status": "UNEXPECTED_ERROR", "message": "❌ An unexpected error occurred."}), status_code=500, mimetype="application/json")


@app.function_name(name="PrApprove")
@app.route(route="prapprove", methods=["get"], auth_level=func.AuthLevel.ANONYMOUS)
def pr_approve(req: func.HttpRequest) -> func.HttpResponse:
    """
    PR'ı onaylar, test branch'ine merge eder ve feature branch'ini siler.
    'Code Review -> Analyst Appr.' workflow'u için kullanılır.
    """
    logging.info('PrApprove function called.')
    
    try:
        ticket = req.params.get('ticket')
        repo_name = req.params.get('repo')
        pr_id = req.params.get('pr_id')  # İsteğe bağlı, yoksa branch ismiyle bulur

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

        def _pa_do_request(url: str, method: str = 'GET', payload: dict = None) -> dict:
            """PrApprove fonksiyonuna özel request yardımcısı."""
            headers = {
                "Authorization": f"Basic {base64.b64encode(f':{azure_pat}'.encode()).decode()}",
                "Content-Type": "application/json"
            }
            data = json.dumps(payload).encode() if payload is not None else None
            req_obj = urllib.request.Request(url, data=data, method=method, headers=headers)
            with urllib.request.urlopen(req_obj) as resp:
                txt = resp.read().decode()
                return json.loads(txt) if txt else {}

        # --- 3. Ana Akış ---
        
        # PR ID'si verilmediyse, branch ismiyle PR'ı bul
        if not pr_id:
            # Branch'ten test'e açık PR'ları ara
            pr_list_url = f"https://dev.azure.com/{AZURE_ORG}/{AZURE_PROJECT}/_apis/git/repositories/{repo_id}/pullrequests?searchCriteria.sourceRefName=refs/heads/{urllib.parse.quote(ticket, safe='')}&searchCriteria.targetRefName=refs/heads/test&searchCriteria.status=active&api-version=7.1-preview.1"
            pr_list = _pa_do_request(pr_list_url)
            
            if not pr_list.get('value') or len(pr_list['value']) == 0:
                return func.HttpResponse(json.dumps({"status": "PR_NOT_FOUND", "message": f"❌ No active PR found from '{ticket}' to 'test' branch."}), status_code=404, mimetype="application/json")
            
            pr_id = pr_list['value'][0]['pullRequestId']
            logging.info(f"Found PR #{pr_id} for branch '{ticket}'")

        # PR'ı onayla ve merge et
        # Önce PR detaylarını al
        pr_details_url = f"https://dev.azure.com/{AZURE_ORG}/{AZURE_PROJECT}/_apis/git/repositories/{repo_id}/pullrequests/{pr_id}?api-version=7.1-preview.1"
        pr_details = _pa_do_request(pr_details_url)
        
        last_merge_source_commit = pr_details.get("lastMergeSourceCommit", {}).get("commitId")
        if not last_merge_source_commit:
            return func.HttpResponse(json.dumps({"status": "PR_DETAILS_ERROR", "message": "❌ Could not get PR source commit details."}), status_code=500, mimetype="application/json")

        pr_update_url = f"https://dev.azure.com/{AZURE_ORG}/{AZURE_PROJECT}/_apis/git/repositories/{repo_id}/pullrequests/{pr_id}?api-version=7.1-preview.1"
        formatted_title = format_pr_title(ticket)
        pr_update_payload = {
            "status": "completed",
            "lastMergeSourceCommit": {"commitId": last_merge_source_commit},
            "completionOptions": {
                "mergeCommitMessage": f"Approved and merged: {formatted_title}",
                "deleteSourceBranch": False,  # Branch'i silme, manuel DeleteBranch ile silinecek
                "mergeStrategy": "squash"  # Squash merge
            }
        }
        
        pr_result = _pa_do_request(pr_update_url, method='PATCH', payload=pr_update_payload)
        logging.info(f"Successfully approved and merged PR #{pr_id}")

        # Başarılı Sonuç
        resp = {
            "status": "PR_APPROVED_AND_MERGED",
            "message": f"✅ Successfully approved PR #{pr_id} and merged '{ticket}' to test. Branch remains active.",
            "branch": ticket,
            "repo": repo_name,
            "pr_id": pr_id,
            "pr_url": f"https://dev.azure.com/{AZURE_ORG}/{AZURE_PROJECT}/_git/{repo_name}/pullrequest/{pr_id}",
            "merge_status": pr_result.get("mergeStatus", "completed")
        }
        return func.HttpResponse(json.dumps(resp), status_code=200, mimetype="application/json")

    except (ValueError, urllib.error.HTTPError) as e:
        error_message = str(e)
        if isinstance(e, urllib.error.HTTPError):
            error_message = e.read().decode()
        logging.error(f"Error in PrApprove: {error_message}")
        return func.HttpResponse(json.dumps({"status": "EXECUTION_ERROR", "message": "❌ An error occurred during execution.", "error": error_message}), status_code=500, mimetype="application/json")
    except Exception as e:
        logging.error(f"Unexpected error in PrApprove: {str(e)}")
        return func.HttpResponse(json.dumps({"status": "UNEXPECTED_ERROR", "message": "❌ An unexpected error occurred."}), status_code=500, mimetype="application/json")
