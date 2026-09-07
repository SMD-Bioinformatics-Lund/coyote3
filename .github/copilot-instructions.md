# GitHub Copilot PR Review Instructions

When reviewing a pull request for this project, follow these guidelines:

1. **Project Structure Awareness**
   - Ensure new files and changes are placed in the correct folders:
     - Application code should go in `coyote/` and its subfolders.
     - Flask blueprints must be organized under `coyote/blueprints/`.
     - Documentation updates should be in the `docs/` folder.
     - Tests should be in a top-level `tests/` folder (if present).

2. **Code Quality**
   - Enforce PEP8 compliance and consistent formatting.
   - Require type annotations for all functions and methods.
   - Check for clear, descriptive docstrings and comments.

3. **Documentation**
   - All new features, modules, or endpoints must be documented in the appropriate Markdown files in `docs/`.
   - Update `docs/api.md` for API changes, and `docs/structure.md` if the project structure changes.

4. **Testing**
   - Ensure new features include corresponding tests.
   - Test files should be named `test_*.py` and placed in `tests/`.
   - All tests must pass before merging.

5. **Configuration**
   - Sensitive information (e.g., secrets, database URIs) must not be hardcoded.
   - Configuration changes should be documented in `docs/configuration.md`.

6. **Blueprints and Routing**
   - New routes should be added to the correct blueprint in `coyote/blueprints/`.
   - Register new blueprints in `coyote/__init__.py` if needed.

7. **General**
   - Avoid adding binary files to the repository.
   - Keep the repository clean and organized according to the documented structure.

Review PRs with these points in mind to maintain code quality and project consistency.