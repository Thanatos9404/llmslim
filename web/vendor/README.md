# Bundled LLMSlim package

`llmslim-0.7.1-py3-none-any.whl` is the current wheel built from this
repository's 0.7.1 source release. `web/requirements.txt` fetches it from the
`v0.7.1` GitHub tag with a SHA-256 pin for the Studio server functions,
including its `sarvam` and `mongodb` extras. The 0.7.0 wheel remains here for
the previous release.

0.7.1 SHA-256: `6e713fdb31c41d5d85099b90e9cdda446a65cb993a4c046ef023fa7a7302313b`

0.7.0 SHA-256: `d5d5c9ee52467e9ef00e3139e9bff781dcc661e5a13fa42fecd7df0f774f071d`

Rebuild with `python -m build --no-isolation`, add the new wheel here, and
update the hash whenever package source changes. This does not represent a
PyPI publication.
