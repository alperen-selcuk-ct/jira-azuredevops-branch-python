# Jira Azure DevOps Branch Management API

Bu proje, Jira workflow'larını Azure DevOps Git işlemleriyle entegre eden Azure Functions uygulamasıdır. Jira'da task durumu değiştiğinde otomatik olarak branch oluşturma, merge etme, PR açma ve onaylama işlemlerini gerçekleştirir.

## 🏗️ Mimari

- **Platform**: Azure Functions (Python v2 programming model)
- **API**: Azure DevOps REST API
- **Authentication**: Personal Access Token (PAT)
- **Repository**: Azure DevOps Git repositories

## 📋 Fonksiyonlar

### 1. **NewBranch** - Branch Oluşturma
Yeni Git branch'i oluşturur (`dev` branch'inden dallanır).

**Endpoint**: `/api/newBranch`

```powershell
# Normal branch format
curl "https://customstech-d6dpeegqavfjhcag.northeurope-01.azurewebsites.net/api/newBranch?ticket=AI-123-feature-name&repo=CustomsOnlineAI" -UseBasicParsing

# Folder/branch format
curl "https://customstech-d6dpeegqavfjhcag.northeurope-01.azurewebsites.net/api/newBranch?ticket=developer/AI-123-feature-name&repo=CustomsOnlineAI" -UseBasicParsing
```

**Özellikler**:
- ✅ Branch name validation (AI-, BE-, CT-, DO-, FE-, MP-, SQL-, TD-, UI- prefixes)
- ✅ Folder/branch format desteği (`folder/branch-name`)
- ✅ Duplicate branch handling (hata vermez, success döner)
- ✅ URL encoding desteği

---

### 2. **DevMerge** - Dev Branch'ine Merge
Feature branch'i `dev` branch'ine merge eder (branch'i silmez).

**Endpoint**: `/api/devmerge`

```powershell
# Normal branch
curl "https://customstech-d6dpeegqavfjhcag.northeurope-01.azurewebsites.net/api/devmerge?ticket=AI-123-feature-name&repo=CustomsOnlineAI" -UseBasicParsing

# Folder/branch format
curl "https://customstech-d6dpeegqavfjhcag.northeurope-01.azurewebsites.net/api/devmerge?ticket=developer/AI-123-feature-name&repo=CustomsOnlineAI" -UseBasicParsing
```

**Kullanım Senaryoları**:
- "In Development" → "Code Review" geçişi
- "Code Review" → "Analyst Approval" geçişi

**Özellikler**:
- ✅ Fast-forward merge
- ✅ Conflict detection
- ✅ Already up-to-date kontrolü

---

### 3. **PrOpen** - Pull Request Açma
Feature branch'ten `test` branch'ine PR açar.

**Endpoint**: `/api/propen`

```powershell
# Normal branch
curl "https://customstech-d6dpeegqavfjhcag.northeurope-01.azurewebsites.net/api/propen?ticket=AI-123-feature-name&repo=CustomsOnlineAI" -UseBasicParsing

# Folder/branch format
curl "https://customstech-d6dpeegqavfjhcag.northeurope-01.azurewebsites.net/api/propen?ticket=developer/AI-123-feature-name&repo=CustomsOnlineAI" -UseBasicParsing
```

**Kullanım Senaryosu**:
- "In Development" → "Code Review" geçişi

**Özellikler**:
- ✅ Test branch varlık kontrolü
- ✅ PR başlığı = branch ismi
- ✅ Otomatik description

---

### 4. **PrApprove** - Pull Request Onaylama
PR'ı onaylar, `test` branch'ine merge eder ve feature branch'ini siler.

**Endpoint**: `/api/prapprove`

```powershell
# Branch ismi ile (PR'ı otomatik bulur)
curl "https://customstech-d6dpeegqavfjhcag.northeurope-01.azurewebsites.net/api/prapprove?ticket=AI-123-feature-name&repo=CustomsOnlineAI" -UseBasicParsing

# PR ID ile (opsiyonel)
curl "https://customstech-d6dpeegqavfjhcag.northeurope-01.azurewebsites.net/api/prapprove?ticket=AI-123-feature-name&repo=CustomsOnlineAI&pr_id=2500" -UseBasicParsing
```

**Kullanım Senaryosu**:
- "Code Review" → "Analyst Approval" geçişi

**Özellikler**:
- ✅ PR otomatik bulma
- ✅ Squash merge
- ✅ Branch otomatik silme
- ✅ Merge commit message

---

### 5. **DeleteBranch** - Branch Silme
Mevcut Git branch'ini siler.

**Endpoint**: `/api/deleteBranch`

```powershell
# Normal branch
curl "https://customstech-d6dpeegqavfjhcag.northeurope-01.azurewebsites.net/api/deleteBranch?ticket=AI-123-feature-name&repo=CustomsOnlineAI" -UseBasicParsing

# Folder/branch format
curl "https://customstech-d6dpeegqavfjhcag.northeurope-01.azurewebsites.net/api/deleteBranch?ticket=developer/AI-123-feature-name&repo=CustomsOnlineAI" -UseBasicParsing
```

**Özellikler**:
- ✅ Protected branch koruması (main, master, dev, develop, release)
- ✅ Branch existence kontrolü
- ✅ URL encoding desteği

---

### 6. **HealthCheck** - Sistem Durumu
Sistem sağlığını kontrol eder.

**Endpoint**: `/api/healthcheck`

```powershell
curl "https://customstech-d6dpeegqavfjhcag.northeurope-01.azurewebsites.net/api/healthcheck" -UseBasicParsing
```

## 🔄 Workflow Örnekleri

### Workflow 1: "In Development" → "Code Review"

```powershell
# 1. Yeni branch oluştur
curl "https://customstech-d6dpeegqavfjhcag.northeurope-01.azurewebsites.net/api/newBranch?ticket=AI-2024-new-feature&repo=CustomsOnlineAI" -UseBasicParsing

# 2. Dev'e merge et
curl "https://customstech-d6dpeegqavfjhcag.northeurope-01.azurewebsites.net/api/devmerge?ticket=AI-2024-new-feature&repo=CustomsOnlineAI" -UseBasicParsing

# 3. Test'e PR aç
curl "https://customstech-d6dpeegqavfjhcag.northeurope-01.azurewebsites.net/api/propen?ticket=AI-2024-new-feature&repo=CustomsOnlineAI" -UseBasicParsing
```

### Workflow 2: "Code Review" → "Analyst Approval"

```powershell
# 1. Dev'e merge et (tekrar)
curl "https://customstech-d6dpeegqavfjhcag.northeurope-01.azurewebsites.net/api/devmerge?ticket=AI-2024-new-feature&repo=CustomsOnlineAI" -UseBasicParsing

# 2. PR'ı onayla ve branch'i sil
curl "https://customstech-d6dpeegqavfjhcag.northeurope-01.azurewebsites.net/api/prapprove?ticket=AI-2024-new-feature&repo=CustomsOnlineAI" -UseBasicParsing
```

## 📚 Repository Mapping

| Repository Name | Description |
|----------------|-------------|
| `CustomsOnlineAI` | AI/ML related projects |
| `CustomsOnlineAngular` | Frontend Angular application |
| `CustomsOnlineBackEnd` | Backend API services |
| `CustomsOnlineMobile` | Mobile application |

## 🏷️ Branch Naming Convention

### Desteklenen Prefix'ler:
- `AI-` - Artificial Intelligence
- `BE-` - Backend
- `CT-` - Custom/General
- `DO-` - DevOps
- `FE-` - Frontend
- `MP-` - Mobile Platform
- `SQL-` - Database
- `TD-` - Technical Debt
- `UI-` - User Interface

### Format Örnekleri:
```bash
# Normal format
AI-123-feature-name
BE-456-api-endpoint
UI-789-button-design

# Folder format (developer/team organization)
john/AI-123-feature-name
team-lead/BE-456-api-endpoint
frontend-team/UI-789-button-design
```

## 📝 Response Formats

### Başarılı Response Örnekleri:

#### NewBranch Success:
```json
{
    "status": "BRANCH_CREATED",
    "message": "✅ SUCCESS: Branch 'AI-123-feature' created successfully in 'CustomsOnlineAI'",
    "branch": "AI-123-feature",
    "repo": "CustomsOnlineAI",
    "repo_id": "4890959d-88d1-4ca0-a3ed-f114ac012f13",
    "commit": "933cf193311565bf6f443cffd99220ffadaf7145",
    "success": true
}
```

#### DevMerge Success:
```json
{
    "status": "DEV_MERGE_OK",
    "message": "✅ Successfully merged 'AI-123-feature' into dev.",
    "branch": "AI-123-feature",
    "repo": "CustomsOnlineAI",
    "dev_old_sha": "933cf193311565bf6f443cffd99220ffadaf7145",
    "dev_new_sha": "d99cfa8cb1f46535e7c682aeb10599053213ea62"
}
```

#### PrOpen Success:
```json
{
    "status": "PR_OPENED",
    "message": "✅ Successfully opened PR from 'AI-123-feature' to test.",
    "branch": "AI-123-feature",
    "repo": "CustomsOnlineAI",
    "pr_id": 2500,
    "pr_url": "https://dev.azure.com/customstechnologies/CustomsOnline/_git/CustomsOnlineAI/pullrequest/2500"
}
```

#### PrApprove Success:
```json
{
    "status": "PR_APPROVED_AND_MERGED",
    "message": "✅ Successfully approved PR #2500, merged 'AI-123-feature' to test, and deleted branch.",
    "branch": "AI-123-feature",
    "repo": "CustomsOnlineAI",
    "pr_id": 2500,
    "pr_url": "https://dev.azure.com/customstechnologies/CustomsOnline/_git/CustomsOnlineAI/pullrequest/2500",
    "merge_status": "queued"
}
```

## ⚠️ Error Handling

### Yaygın Hata Kodları:

#### 400 - Bad Request:
```json
{
    "status": "MISSING_PARAMETERS",
    "message": "❌ 'ticket' and 'repo' parameters are required"
}
```

#### 404 - Not Found:
```json
{
    "status": "BRANCH_NOT_FOUND",
    "message": "❌ Source branch 'AI-123-feature' does not exist in repository."
}
```

#### 409 - Conflict:
```json
{
    "status": "MERGE_CONFLICT",
    "message": "⚠️ Merge conflict: 'AI-123-feature' cannot be fast-forward merged into dev. Manual merge required."
}
```

## 🔧 Deployment

### Prerequisites:
1. Azure Functions Core Tools
2. Azure CLI
3. Python 3.9+

### Deploy Command:
```bash
func azure functionapp publish customstech
```

## 🔒 Security

- Azure DevOps Personal Access Token (PAT) stored as environment variable
- Repository access controlled via Azure DevOps permissions
- Function-level authentication available (currently set to Anonymous for Jira webhook integration)

## 📊 Status Codes

| Status | Fonksiyon | Açıklama |
|--------|-----------|----------|
| `BRANCH_CREATED` | NewBranch | Branch başarıyla oluşturuldu |
| `BRANCH_ALREADY_EXISTS` | NewBranch | Branch zaten var (success olarak döner) |
| `DEV_MERGE_OK` | DevMerge | Dev merge başarılı |
| `ALREADY_UP_TO_DATE` | DevMerge | Branch zaten güncel |
| `PR_OPENED` | PrOpen | PR başarıyla açıldı |
| `PR_APPROVED_AND_MERGED` | PrApprove | PR onaylandı ve merge edildi |
| `BRANCH_DELETED` | DeleteBranch | Branch başarıyla silindi |

## 🚀 Quick Start

1. **Test the system**:
```powershell
curl "https://customstech-d6dpeegqavfjhcag.northeurope-01.azurewebsites.net/api/healthcheck" -UseBasicParsing
```

2. **Create a branch**:
```powershell
curl "https://customstech-d6dpeegqavfjhcag.northeurope-01.azurewebsites.net/api/newBranch?ticket=AI-test-branch&repo=CustomsOnlineAI" -UseBasicParsing
```

3. **Complete workflow**:
```powershell
# Merge to dev
curl "https://customstech-d6dpeegqavfjhcag.northeurope-01.azurewebsites.net/api/devmerge?ticket=AI-test-branch&repo=CustomsOnlineAI" -UseBasicParsing

# Open PR to test
curl "https://customstech-d6dpeegqavfjhcag.northeurope-01.azurewebsites.net/api/propen?ticket=AI-test-branch&repo=CustomsOnlineAI" -UseBasicParsing

# Approve PR and delete branch
curl "https://customstech-d6dpeegqavfjhcag.northeurope-01.azurewebsites.net/api/prapprove?ticket=AI-test-branch&repo=CustomsOnlineAI" -UseBasicParsing
```

---

**Created**: October 2025  
**Version**: 1.0  
**Author**: GitHub Copilot  
**License**: Custom License
