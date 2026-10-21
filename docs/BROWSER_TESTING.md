# Browser E2E tests — W43-07

The Playwright suite exercises the real React UI and FastAPI API for registration/login, team creation, membership management, and catalog administration. Use only a disposable PostgreSQL database and the demo accounts created for that database. Never point the browser suite at a personal, shared, staging, or production database.

## Local setup (Windows PowerShell)

Install the backend dependencies and browser-test dependencies, and install Chromium:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r ..\frontend\e2e\requirements.txt
.\.venv\Scripts\python.exe -m playwright install chromium
cd ..\frontend
npm ci
cd ..
```

Create a dedicated PostgreSQL database such as `esports_tournament_w43_e2e_test`. Do not reuse `DB_NAME` from `backend/.env`. Seed it using a test-only password; `seed_demo.py` rejects a target equal to the configured application database:

```powershell
cd backend
$credential = Get-Credential -UserName 'e2e' -Message 'Test-only demo password (8-128 characters)'
$env:DEMO_PASSWORD = $credential.GetNetworkCredential().Password
$env:E2E_DEMO_PASSWORD = $env:DEMO_PASSWORD
try {
    .\.venv\Scripts\python.exe seed_demo.py --database esports_tournament_w43_e2e_test --migrate
    if ($LASTEXITCODE -ne 0) { throw 'Demo seed failed' }
} finally {
    Remove-Item Env:DEMO_PASSWORD -ErrorAction SilentlyContinue
    Remove-Variable credential
}
cd ..
```

Run the backend in one terminal, overriding only that process's database name:

```powershell
cd backend
$env:DB_NAME = 'esports_tournament_w43_e2e_test'
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Run Vite in a second terminal:

```powershell
cd frontend
$env:VITE_API_URL = 'http://127.0.0.1:8000/api/v1'
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

In a third terminal, use the same test-only password supplied to the seed command:

```powershell
cd frontend
$env:E2E_BROWSER_PATH = 'C:\Program Files\Google\Chrome\Application\chrome.exe' # Optional when Chromium download is unavailable
$env:E2E_DEMO_PASSWORD = Read-Host 'Test-only demo password'
npm run test:e2e
Remove-Item Env:E2E_DEMO_PASSWORD -ErrorAction SilentlyContinue
Remove-Item Env:E2E_BROWSER_PATH -ErrorAction SilentlyContinue
```

The suite creates uniquely named browser-test accounts, teams, and catalog records. It writes a JUnit report to `frontend/e2e-artifacts/junit.xml`; on failure it also saves a full-page screenshot and Playwright trace there. Artifacts are ignored by Git. To clean local test data, stop the servers and drop/recreate only `esports_tournament_w43_e2e_test`; do not drop the database from `.env`.

## CI

The `Browser E2E (Playwright)` job creates its own PostgreSQL service database, seeds a separate `_test` database, starts the API and Vite, and runs `npm run test:e2e`. JUnit, screenshots, traces, and server logs are uploaded as the `browser-e2e-results` artifact even when the job fails. The demo password is fixed only inside that disposable, job-scoped database and is not used outside CI.
