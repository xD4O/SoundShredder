"""Local AudioSep text conditioning, using the already verified sound checkpoint."""
from __future__ import annotations

import contextlib
import gc
import hashlib
import json
import os
import unicodedata
import urllib.request
import uuid
from pathlib import Path

import numpy as np

from .audio import read_json, sha256, write_json
from .certificates import configure_macos_certificates

MAX_PROMPT_CHARS = 200
TOKENIZER_REVISION = "e2da8e2f811d1448a5b465c236feacd80ffbac7b"
TOKENIZER_SHA = "847bbeab6174d66a88898f729d52fa8d355fafe1bea101cf960dd404581df70e"
TOKENIZER_URL = f"https://huggingface.co/FacebookAI/roberta-base/resolve/{TOKENIZER_REVISION}/tokenizer.json"
ENCODER_VERSION = "audiosep-roberta-pooler-relu-normalized-v1"


def validate_prompt(text):
    if not isinstance(text, str):
        raise ValueError("Describe one sound to remove.")
    if any(unicodedata.category(char).startswith("C") for char in text):
        raise ValueError("Use a short sound description without control characters.")
    text = " ".join(text.split())
    if not text or len(text) > MAX_PROMPT_CHARS:
        raise ValueError(f"Describe one sound in 1–{MAX_PROMPT_CHARS} characters.")
    return text


def tokenizer_file(folder: Path, progress):
    destination = folder / "roberta-tokenizer.json"
    if destination.is_file() and sha256(destination) == TOKENIZER_SHA:
        return destination
    configure_macos_certificates()
    progress(0.17, "Downloading the local sound-description tokenizer (1.4 MB).")
    temporary = folder / f"tokenizer-{uuid.uuid4().hex}.part"
    try:
        with urllib.request.urlopen(TOKENIZER_URL, timeout=45) as response, temporary.open("wb") as output:
            received = 0
            while chunk := response.read(256 * 1024):
                received += len(chunk)
                if received > 2 * 1024 * 1024:
                    raise RuntimeError("The sound-description tokenizer download is larger than expected.")
                output.write(chunk)
        if sha256(temporary) != TOKENIZER_SHA:
            raise RuntimeError("The sound-description tokenizer failed verification. Retry cleanup.")
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def encode_text(text, checkpoint_path, tokenizer_path):
    """Reproduce AudioSep's frozen CLAP text branch; never load remote model code."""
    import torch
    from tokenizers import Tokenizer
    from transformers import RobertaConfig, RobertaModel

    torch.set_num_threads(max(1, min(8, (os.cpu_count() or 2) // 2)))
    tokenizer = Tokenizer.from_file(str(tokenizer_path))
    tokenizer.enable_padding(length=512, pad_id=1, pad_token="<pad>")
    tokens = tokenizer.encode(text)
    if len(tokens.ids) > 512:
        raise ValueError("That description is too long for the model. Name a single sound more briefly.")
    config = RobertaConfig(vocab_size=50265, max_position_embeddings=514, type_vocab_size=1,
                          layer_norm_eps=1e-5, pad_token_id=1, bos_token_id=0, eos_token_id=2)
    config._attn_implementation = "eager"
    # mmap avoids allocating a second complete copy of the 1.2 GB sound checkpoint.
    # PyTorch 2.2 (the last Intel Mac wheel) requires a string for mmap;
    # newer Torch versions also accept pathlib.Path here.
    state = torch.load(str(checkpoint_path), map_location="cpu", weights_only=True, mmap=True)["state_dict"]
    prefix = "query_encoder.model.text_branch."
    weights = {k.removeprefix(prefix): v for k, v in state.items()
               if k.startswith(prefix) and not k.endswith("position_ids")}
    model = RobertaModel(config).eval()
    model.load_state_dict(weights, strict=True)
    projection = torch.nn.Sequential(torch.nn.Linear(768, 512), torch.nn.ReLU(), torch.nn.Linear(512, 512)).eval()
    prefix = "query_encoder.model.text_projection."
    projection.load_state_dict({k.removeprefix(prefix): v for k, v in state.items() if k.startswith(prefix)}, strict=True)
    with torch.inference_mode():
        pooled = model(input_ids=torch.tensor([tokens.ids]),
                       attention_mask=torch.tensor([tokens.attention_mask])).pooler_output
        vector = torch.nn.functional.normalize(projection(pooled), dim=-1)[0].numpy().copy()
    return vector


def prompt_vector(text, checkpoint_path, progress):
    from .bubble import MODEL_SHA

    text = validate_prompt(text)
    identity = {"prompt": text, "encoder": ENCODER_VERSION, "model_sha256": MODEL_SHA,
                "tokenizer_sha256": TOKENIZER_SHA}
    key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode("utf-8")).hexdigest()
    folder = Path(checkpoint_path).parent
    cache = folder / "prompts" / f"{key}.json"
    if cache.is_file():
        with contextlib.suppress(OSError, ValueError, KeyError, TypeError):
            saved = read_json(cache)
            vector = np.asarray(saved["vector"], dtype=np.float32)
            if saved["identity"] == identity and valid_vector(vector):
                progress(0.19, "Reusing your locally saved sound description.")
                return vector
    tokenizer = tokenizer_file(folder, progress)
    progress(0.18, "Understanding your sound description on this computer…")
    try:
        vector = encode_text(text, checkpoint_path, tokenizer)
    except ImportError as exc:
        raise RuntimeError("Custom prompts need the updated engine. Run setup again, then retry.") from exc
    finally:
        gc.collect()
    if not valid_vector(vector):
        raise RuntimeError("The description produced an invalid sound embedding. Try a different description.")
    cache.parent.mkdir(exist_ok=True)
    write_json(cache, {"identity": identity, "vector": vector.tolist()})
    return vector


def valid_vector(vector):
    return vector.shape == (512,) and np.isfinite(vector).all() and abs(float(np.linalg.norm(vector)) - 1) < 0.001
