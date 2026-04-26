Chatbot Test Guide
==================

Run everything from the project root.

Quick Setup
-----------

Install dependencies:

```powershell
pip install -r requirements.txt
```

If needed, use:

```powershell
python -m pip install -r requirements.txt
```

Unit Tests
----------

Fast isolated tests for backend logic.

```powershell
python -m pytest tests/unit
python -m pytest tests\unit --cov=chatbot_app --cov-report=term --basetemp C:\Users\LENOVO\AppData\Local\Temp\chatbot_pytest_unit
python -m pytest tests/unit/test_db_service.py
python -m pytest tests/unit/test_site_store.py
python -m pytest tests/unit/test_ai_engine.py
python -m pytest tests/unit/test_chat_service.py
```

Integration Tests
-----------------

Flask route tests using the test client.

```powershell
python -m pytest tests/integration
python -m pytest tests\integration --cov=chatbot_app --cov-report=term --basetemp C:\Users\LENOVO\AppData\Local\Temp\chatbot_pytest_integration
python -m pytest tests/integration/test_chat_routes.py
python -m pytest tests/integration/test_auth_routes.py
python -m pytest tests/integration/test_admin_routes.py
```

Full Suite
----------

Run all tests:

```powershell
python -m pytest
```

Run all tests with coverage:

```powershell
python -m pytest --cov=chatbot_app --cov-report=term-missing
```

Performance Checks
------------------

Start the app first:

```powershell
python app.py
```

Then run the performace tests (latency_test and load_test):

```powershell

Safe Mode (under free API Token limit of 6000 TPM)
python tests\performance\latency_test.py --token-budget-per-minute 6000 --estimated-tokens-per-request 300 --safety-factor 0.5 --requests 6 --message "Hi" --timeout-seconds 45
python tests\performance\load_test.py --users 2 --requests-per-user 2 --token-budget-per-minute 6000 --estimated-tokens-per-request 300 --safety-factor 0.5 --message "Hi" --timeout-seconds 45

Intense Mode (over free API Token limit of 6000 TPM)
python tests\performance\latency_test.py --token-budget-per-minute 9000 --estimated-tokens-per-request 350 --safety-factor 0.65 --requests 10 --message "Hi." --timeout-seconds 60
python tests\performance\load_test.py --users 3 --requests-per-user 3 --token-budget-per-minute 9000 --estimated-tokens-per-request 350 --safety-factor 0.6 --message "Hi" --timeout-seconds 60
```

Notes
-----

- Unit and integration tests use mocks/stubs for external AI calls.
- `.pytest_cache`, `.pytest_tmp`, `__pycache__`, and `.coverage` are generated files and do not affect the program when deleted.
