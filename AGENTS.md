# Repository Guidelines

This repository contains a Home Assistant integration for Zhong Hong VRF systems.

* Use **Python 3.12** style with 4 space indentation.
* After making changes run the following command to check for syntax errors:
  ```bash
  python -m py_compile $(git ls-files '*.py')
  ```
* There are no automated tests.
* Documentation lives in `README.md` and `PROTO.md`.
