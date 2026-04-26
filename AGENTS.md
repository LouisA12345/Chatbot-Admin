# AGENTS.md

## Overview

This repository is a Flask-based chatbot project with:

- a backend API
- an admin portal
- a test website that embeds the widget
- local SQLite databases
- site-specific knowledge/config data stored under `data/`

Most backend logic now lives inside the `chatbot_app/` package.  
`app.py` remains the main local entrypoint for running the project.

## High-Level Architecture

- `app.py` starts the Flask server.
- `chatbot_app/__init__.py` creates the Flask app and registers blueprints.
- `chatbot_app/routes/` contains HTTP endpoints.
- `chatbot_app/services/` contains orchestration and persistence logic.
- `chatbot_app/db/` contains database access and DB action execution.
- `chatbot_app/ai/` contains embedding, retrieval, and LLM response logic.
- `admin.html` is the admin UI.
- `test_site.html` is the test storefront page.
- `widget.js` is the embeddable chat widget used by the frontend pages.

## Full File Structure

```text
.
|-- .env
|-- admin.html
|-- AGENTS.md
|-- app.py
|-- create_db.py
|-- customer.db
|-- owner.db
|-- setup_databases.py
|-- test.pdf
|-- test_site.html
|-- test_store.db
|-- widget.js
|-- chatbot_app/
|   |-- __init__.py
|   |-- config.py
|   |-- security.py
|   |-- ai/
|   |   |-- __init__.py
|   |   `-- engine.py
|   |-- db/
|   |   |-- __init__.py
|   |   `-- service.py
|   |-- routes/
|   |   |-- __init__.py
|   |   |-- admin.py
|   |   |-- auth.py
|   |   |-- chat.py
|   |   `-- public.py
|   `-- services/
|       |-- __init__.py
|       |-- chat_service.py
|       `-- site_store.py
|-- data/
|   `-- site123/
|       |-- chunks.json
|       |-- config.json
|       |-- db_configs.json
|       |-- index.faiss
|       `-- pdf_chunks.json
|-- __pycache__/
|   |-- app.cpython-312.pyc
|   |-- auth_db.cpython-312.pyc
|   |-- auth_routes.cpython-312.pyc
|   |-- db_connector.cpython-312.pyc
|   `-- nlp_engine.cpython-312.pyc
`-- chatbot_app/**/__pycache__/
    `-- generated Python bytecode caches
```

## Root Files

- `.env`
  - Local environment variables.
  - Expected to include secrets/settings such as `ADMIN_API_KEY` and `GROQ_API_KEY`.
  - Do not hardcode these values into source files.

- `admin.html`
  - Browser-based admin portal.
  - Used to manage sites, upload PDFs, connect databases, edit widget settings, and inspect chunks.

- `AGENTS.md`
  - This project guide.
  - Describes structure, responsibilities, workflow, and safe editing rules.

- `app.py`
  - Main run entrypoint.
  - Creates the app by calling `chatbot_app.create_app()`.
  - Use this when starting the backend locally with `python app.py`.

- `create_db.py`
  - Small helper script for creating a simple sample SQLite database.
  - Mostly useful for quick experiments or earlier testing.
  - Not part of the core runtime flow.

- `customer.db`
  - Main customer-facing SQLite database.
  - Stores data such as customers, products, FAQs, and promotions.
  - Read by the chatbot and auth flows.

- `owner.db`
  - Internal/business SQLite database.
  - Stores orders, sessions, and admin-side business records.
  - Used for order writes and auth session persistence.

- `setup_databases.py`
  - Script to recreate/reset the main SQLite databases.
  - Useful for local setup and demo data seeding.
  - Be careful: running it can replace current DB contents.

- `test.pdf`
  - Sample PDF knowledge source.
  - Useful for testing PDF ingestion and chunk indexing.

- `test_site.html`
  - Test storefront page.
  - Loads the widget so the chatbot can be tested in a simple frontend context.

- `test_store.db`
  - Extra sample SQLite database used for testing/demo purposes.
  - Not the main production-like DB used by the app runtime.

- `widget.js`
  - Frontend chat widget script.
  - Handles rendering, user interaction, auth prompts, message formatting, and API calls to the backend.

## Backend Package: `chatbot_app/`

### Package Root

- `chatbot_app/__init__.py`
  - App factory module.
  - Builds the Flask app, enables CORS, loads shared config, and registers all route blueprints.

- `chatbot_app/config.py`
  - Central config and shared path definitions.
  - Loads `.env`, defines paths like `DATA_DIR`, `CUSTOMER_DB_PATH`, and `OWNER_DB_PATH`, and stores `DEFAULT_CONFIG` for widget/site settings.

- `chatbot_app/security.py`
  - Shared security helpers.
  - Currently contains the admin API key decorator used to protect admin endpoints.

### AI Layer: `chatbot_app/ai/`

- `chatbot_app/ai/__init__.py`
  - Re-exports the main AI components for cleaner imports.

- `chatbot_app/ai/engine.py`
  - Core AI and retrieval module.
  - Contains:
  - `KnowledgeBase`
  - embedding model loading
  - FAISS index building/search
  - PDF text extraction
  - LLM system prompt
  - structured JSON response generation/parsing
  - This is one of the most important backend modules.

### Database Layer: `chatbot_app/db/`

- `chatbot_app/db/__init__.py`
  - Re-exports database service functions.

- `chatbot_app/db/service.py`
  - Main database access/service module.
  - Handles:
  - reading DB rows into knowledge chunks
  - testing DB connections
  - finding DBs with particular tables
  - user lookup
  - order creation
  - order history lookup
  - customer registration through DB actions

### Routes Layer: `chatbot_app/routes/`

- `chatbot_app/routes/__init__.py`
  - Re-exports route blueprints.

- `chatbot_app/routes/admin.py`
  - Admin API endpoints.
  - Handles:
  - site creation/deletion
  - PDF upload
  - database config management
  - chunk listing/edit/delete/deduplicate
  - site config load/save

- `chatbot_app/routes/auth.py`
  - Authentication endpoints and session logic.
  - Handles:
  - register
  - login
  - logout
  - current user lookup
  - order list for logged-in users

- `chatbot_app/routes/chat.py`
  - Thin `/chat` API route.
  - Delegates almost all work to `chat_service.py`.

- `chatbot_app/routes/public.py`
  - Public-facing config endpoint for the widget.
  - Lets the frontend fetch site config safely.

### Service Layer: `chatbot_app/services/`

- `chatbot_app/services/__init__.py`
  - Re-exports commonly used service functions.

- `chatbot_app/services/chat_service.py`
  - Main chat orchestration layer.
  - Handles:
  - chat request processing
  - live DB enrichment
  - user info enrichment
  - address validation
  - DB action execution
  - Python-side formatting for order confirmation/history
  - follow-up AI calls after DB actions

- `chatbot_app/services/site_store.py`
  - Site-level persistence layer.
  - Handles:
  - site directories under `data/`
  - loading/saving config
  - loading/saving PDF chunks
  - loading/saving FAISS indices
  - rebuilding per-site knowledge bases
  - deduplication helpers

## Data Directory

### `data/site123/`

This folder represents one configured chatbot site instance.

- `data/site123/chunks.json`
  - Stored text chunks currently in the site knowledge base.

- `data/site123/config.json`
  - Site-specific widget and behavior settings.
  - Overrides or extends defaults from `chatbot_app/config.py`.

- `data/site123/db_configs.json`
  - Saved database connection settings for this site.

- `data/site123/index.faiss`
  - FAISS vector index built from the stored chunks.
  - Used for semantic retrieval.

- `data/site123/pdf_chunks.json`
  - PDF-derived chunks saved separately so the site KB can be rebuilt cleanly.

## Generated / Cache Files

- `__pycache__/...`
- `chatbot_app/**/__pycache__/...`
- `*.pyc`

These are generated Python bytecode/cache files.

- They are not source files.
- They usually do not need manual editing.
- They can become stale after refactors.
- If needed, they can be deleted safely while the app is stopped; Python will recreate them.

Note:
- `__pycache__/auth_routes.cpython-312.pyc`
- `__pycache__/db_connector.cpython-312.pyc`
- `__pycache__/nlp_engine.cpython-312.pyc`

These appear to be leftover caches from older wrapper files that no longer exist in source form.

## Which Files Matter Most

If you are changing behavior, these are the highest-impact files:

- `widget.js`
- `admin.html`
- `chatbot_app/routes/admin.py`
- `chatbot_app/routes/auth.py`
- `chatbot_app/routes/chat.py`
- `chatbot_app/services/chat_service.py`
- `chatbot_app/services/site_store.py`
- `chatbot_app/db/service.py`
- `chatbot_app/ai/engine.py`
- `chatbot_app/config.py`

## Editing Guidance

- Prefer editing files inside `chatbot_app/` for backend changes.
- Keep route files thin and move reusable logic into `services/`, `db/`, or `ai/`.
- Keep API paths stable unless a task explicitly requires breaking API changes.
- If you change chat output, check both backend formatting and `widget.js`.
- If you change site persistence, update `site_store.py` first rather than duplicating file I/O elsewhere.
- If you change authentication or orders, inspect both `routes/auth.py` and `db/service.py`.
- Do not edit `.db`, `.faiss`, or `.pyc` files directly unless the task is specifically about generated data.

## Running The Project

Backend:

```powershell
python app.py
```

Optional static server for HTML pages:

```powershell
python -m http.server 8083
```

Then open:

- `http://localhost:8083/admin.html`
- `http://localhost:8083/test_site.html`

## Recommended Verification

After backend edits, run:

```powershell
python -m py_compile app.py chatbot_app\__init__.py chatbot_app\config.py chatbot_app\security.py chatbot_app\routes\admin.py chatbot_app\routes\auth.py chatbot_app\routes\chat.py chatbot_app\routes\public.py chatbot_app\services\chat_service.py chatbot_app\services\site_store.py chatbot_app\db\service.py chatbot_app\ai\engine.py
```

After frontend or chat-flow edits, manually test:

- admin portal loads
- test site loads
- normal Q&A works
- login/signup works
- order flow works
- order history works
- PDF upload and chunk management still work

## Practical Notes

- The embedding model is lazy-loaded in the AI layer, which helps app startup in environments without immediate network/model access.
- The current repo still contains generated cache files from earlier structure versions; they are not authoritative source code.
- The real source of truth is the `.py`, `.html`, `.js`, `.json`, `.db`, and `.faiss` files listed above, with source logic primarily under `chatbot_app/`.
