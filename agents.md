# AGENTS.md - rules for every coding agent working on BookLoop
## The project
BookLoop is a book-swap app for Nova students, built with Python and Streamlit.
The full plan is in docs/PLAN.tex. Before every task, read the section for
the person you are working for ("Each person's part").
## How to run things
- Install or update the libraries: uv sync
- Rebuild the local demo database: uv run python seed.py
- Start the app: uv run streamlit run app.py
- Run all tests: uv run pytest
## Who owns which files
Every file has one owner (see the folder tree in docs/PLAN.tex,
section "How the code is organized").
- Only create or edit files owned by the person you are working for.
- Shared files belong to Person 1: app.py, seed.py, pyproject.toml, uv.lock,
everything in db/, bookloop/models.py, bookloop/auth.py,
bookloop/storage/db.py, bookloop/rules/decision.py,
bookloop/rules/permissions.py, bookloop/services/notify.py,
tests/conftest.py, .github/ and this file.
Only Person 1 may edit them. If one of them needs to change for
someone else's task, stop and say so: the user will ask Person 1.
- Never change the name, inputs or outputs of a shared function.
- Never add, remove or upgrade libraries (only Person 1 does that).
## How the code is organized
- Every "is this allowed?" decision goes in bookloop/rules/ as a plain
function that returns Decision.yes() or Decision.no("reason").
Rules never import streamlit and never touch the database.
- Only files in bookloop/storage/ read or write the database.
Changes that must happen together use transaction().
- Pages in pages/ show data, ask a rule, save through storage, and always
end with st.success(...) or st.error(reason).
- Every page starts with current_user() or require_role(...).
- Show something sensible when there is nothing to show yet.
## Tests
- Every rule gets tests: one accepted case, one rejected case (check the
data did not change) and one edge case.
- Use the fixtures and factories in tests/conftest.py. If you need another
helper, write it at the top of the test file you are working on.
- Tests never use the internet or the real database.
- Never edit or delete existing tests to make them pass. Fix the code.
- After every change, run: uv run pytest and show the full output.
## Secrets
- Secrets come only from environment variables or Streamlit secrets:
DATABASE_URL, SUPABASE_URL, SUPABASE_KEY.
- Never write a key or password in any file, and never print or log one.
- Never create or commit .env, .streamlit/secrets.toml or bookloop.db.
## Git
- Do not run git commands. Git is handled in GitHub Desktop.
## Style
- Simple, readable Python: short functions, clear names, short comments
where something is not obvious.
- Messages to users are short and say what happened or why it was refused.
- When you finish, explain in simple words what you changed and why,
as if to a beginner.
