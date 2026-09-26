# Bundled LLMSlim package

`llmslim-0.7.0-py3-none-any.whl` is the local wheel built from this repository's
0.7.0 source release. `web/requirements.txt` installs it for the Studio
server functions, including its `sarvam` and `mongodb` extras.

SHA-256: `d5d5c9ee52467e9ef00e3139e9bff781dcc661e5a13fa42fecd7df0f774f071d`

Rebuild with `python -m build --no-isolation`, replace the wheel here, and
update the hash whenever package source changes. This does not represent a
PyPI publication.
