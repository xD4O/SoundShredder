# AudioSep inference components

`base.py` and `resunet.py` derive from the MIT-licensed [Audio-AGI/AudioSep](https://github.com/Audio-AGI/AudioSep) repository, commit `944583f18b84589dc965de3ad77525c945334252`. Copyright Xubo Liu; the complete upstream LICENSE is included here. Imports were localized, unused training helpers/chunk inference were removed, and the frozen TorchLibrosa STFT/ISTFT were replaced with equivalent native PyTorch transforms. Learned layers and weights are unchanged.

The official checkpoint is downloaded separately from the author's Hugging Face Space at revision `5638854dccfaea5c5fa4f634c00fe74fbb119244`, SHA-256 `f8cda01bfd0ebd141eef45d41db7a3ada23a56568465840d3cff04b8010ce82c`. It is not bundled in release ZIPs.

`bubble-prompts.json` contains four fixed, normalized 512-dimensional query embeddings generated from that checkpoint's frozen RoBERTa/CLAP text encoder and projection. This avoids installing a tokenizer or language model on the user's computer for a fixed preset. Prompts are recorded beside their vectors. The same checkpoint, RoBERTa-base tokenizer/config, ReLU projection and normalization were used. These are preset conditions, not fine-tuned weights.

Cleanup uses the target estimate to form a shared stereo spectral mask, then subtracts only the resulting candidate sound from the original. It does not resynthesize the rest of the soundtrack. Selection boundaries are faded inside the selected interval. Similar sounds can still be confused with bubbles; the removed-sound preview is part of the workflow.
