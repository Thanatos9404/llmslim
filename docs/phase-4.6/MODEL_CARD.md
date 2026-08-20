# Optional semantic retrieval model card

- **Model:** `intfloat/multilingual-e5-small`
- **Pinned revision:** `0e60b8d9d2166d80387f86e3b48ec9ced55f4d15`
- **License:** MIT
- **Model:** 117.65M parameters, 384-dimensional embeddings, 512-token input
  limit, 94-language model family.
- **Expected files:** `model.safetensors`, tokenizer JSON/config, SentencePiece
  model, `modules.json`, `1_Pooling/config.json`, and config files. The planned
  download is 492.8 MB for the required subset; the public repository is larger
  because it also contains ONNX/OpenVINO variants.
- **Local artifact integrity:** cached `model.safetensors` SHA-256:
  `1A55775F53449DAC10A2BCBC312469FAC40B96D53198C407081A831F81C98477`.
- **Runtime:** optional `sentence-transformers` + PyTorch on CPU; no model
  weight is put in the wheel. The normal package has no semantic dependency.
- **Loading policy:** explicit setup/download only, `local_files_only=True` at
  runtime, `trust_remote_code=False`, safetensors preferred. Missing artifacts
  raise a clear optional-feature error instead of downloading.
- **Known limitations:** embedding similarity always returns neighbours, so it
  is not no-tool detection or authorization. CPU cold start/memory can be high
  relative to lexical retrieval. This is an off-the-shelf model, not trained by
  LLMSlim.
