# Claude knowledge base about this repository

- We are using a virtual environment for running this.
  - If the .venv directory does not exist at the top level, then create it using `python3 -m venv .venv`
  - When it does exist, use that `.venv` as the Python virtual environment for all Python commands and scripts.
- If you are working off a plan in a Markdown file (or elsewhere), update the file when you have completed work you derived from that file, to indicate that that task or phase is complete, and elaborate as appropriate as to the details of your work.
- Before committing, be sure that the pre-commit will work by running the `.githooks/pre-commit` script with environment variable `SKIP_VERSION_BUMP=1` set before you actually run `git commit`.
