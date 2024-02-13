# Easy-to-use text-to-speech synthesizer

## Introduction

Alfred 5 workflow that makes Text-to-Speech (TTS) synthesizing readily available.

The codebase allows making use of remote server with CUDA support, thus facilitating quick processing of text.
Of course, you may still install the TTS models locally on macOS.

## Dependencies

### Local

- `ffmpeg`

Optional:

- [`mpg123`](https://www.mpg123.de): If not installed, will fall back to QuickTime Player.

### Remote

- [`TTS`](https://github.com/mozilla/TTS)

## Installation

1. Clone this repository to `/path/to/repo`.
2. Install `ffmpeg`, e.g. using `brew install ffmpeg`, if not yet installed.
3. Create a virtualenv, activate it, and install the codebase:

```bash
python3 -m virtualenv venv
. venv/bin/activate
pip install .
```

4. Copy the python runtime by issuing the command under above virtualenv:

```bash
which python3 | tr -d '\n' | pbcopy
```

5. If `TTS` is to be installed on remote host, create a virtualenv (`python3.9` works for me) and install `TTS` within it:

```bash
conda create -n alfred-say python=3.9 pip
conda activate alfred-say
pip install TTS
```

If `TTS` is to be installed locally, install `TTS` directly in the `venv` where the codebase was installed:

```bash
pip install TTS
```

6. In either case, copy the path to the `tts` executable. For remote installation using `conda`, it should be `~/miniconda3/envs/alfred-say/bin/tts`. For local installation using virtualenv, it should be `/path/to/repo/venv/bin/tts`.
7. Double-click `Say.alfredworkflow`, paste the python runtime path to field `Python Runtime`, and paste the path to `tts` to field `TTS Executable`.
8. Fill in the field `Host` the IP address or the host alias configured in `~/.config/ssh/config`. Also fill in `cuda` if the remote host has CUDA installed.

## Usage

It should be straightforward after installing `Say.alfredworkflow`.

A trick worth mentioning: you may launch `says` (or its variants), close the Alfred popup, and issue keyword `playagain` once you receive notification "TTS Processing Complete".
This way, you won't need to keep the Alfred popup frontmost while waiting, preventing you from doing anything else.

## License

To use certain models included in TTS, you'll need to agree [CPML](https://coqui.ai/cpml).

The codebase is issued under MIT.
