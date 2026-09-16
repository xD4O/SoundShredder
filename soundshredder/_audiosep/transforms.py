"""Native Torch equivalents of AudioSep's frozen TorchLibrosa transforms.

The upstream graph uses a 2048-point periodic Hann window and a 320-sample hop.
No librosa, compiler, tokenizer or extra runtime package is required.
"""
import torch
from torch import nn


def magphase(real, imag):
    magnitude = (real.square() + imag.square()).sqrt()
    denominator = magnitude.clamp_min(1e-10)
    return magnitude, real / denominator, imag / denominator


class STFT(nn.Module):
    def __init__(self, n_fft, hop_length, win_length, window, center, pad_mode, freeze_parameters):
        super().__init__()
        assert window == "hann" and center and freeze_parameters
        self.n_fft, self.hop_length, self.pad_mode = n_fft, hop_length, pad_mode
        self.register_buffer("window", torch.hann_window(win_length), persistent=False)

    def forward(self, audio):
        spectrum = torch.stft(
            audio, self.n_fft, self.hop_length, window=self.window,
            center=True, pad_mode=self.pad_mode, return_complex=True,
        ).transpose(-1, -2).unsqueeze(1)
        return spectrum.real, spectrum.imag


class ISTFT(STFT):
    def forward(self, real, imag, length):
        spectrum = torch.complex(real[:, 0], imag[:, 0]).transpose(-1, -2)
        return torch.istft(spectrum, self.n_fft, self.hop_length, window=self.window, center=True, length=length)
