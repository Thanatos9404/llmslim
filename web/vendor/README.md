# Bundled LLMSlim package (historical)

Nothing here is installed any more. Since 0.8.0 the Studio server functions
install the released Core from PyPI through `web/requirements.txt`, at the
version pinned there; see `web/VERCEL_STUDIO_DEPLOYMENT.md`.

`llmslim-0.7.1-py3-none-any.whl` and `llmslim-0.7.0-py3-none-any.whl` were built
from this repository's 0.7.1 and 0.7.0 source releases. Until 0.8.0,
`web/requirements.txt` fetched the 0.7.1 wheel from the `v0.7.1` GitHub tag with
a SHA-256 pin, including its `sarvam` and `mongodb` extras.

0.7.1 SHA-256: `6e713fdb31c41d5d85099b90e9cdda446a65cb993a4c046ef023fa7a7302313b`

0.7.0 SHA-256: `d5d5c9ee52467e9ef00e3139e9bff781dcc661e5a13fa42fecd7df0f774f071d`

Neither wheel represents a PyPI publication.
