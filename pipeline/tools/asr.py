#!/usr/bin/env python3
"""Transcribe audio clips with faster-whisper.

Reads {"model": "small", "lang": "zh", "files": [...]} on stdin, writes {"texts": [...]} on stdout.
Audio is decoded with ffmpeg, so any format ffmpeg reads will do.
"""
import json
import subprocess
import sys

import numpy as np
from faster_whisper import WhisperModel

# Whisper writes Chinese in either script; a simplified-Chinese prompt keeps it to one.
PROMPTS = {"zh": "以下是普通话的句子。"}


def load(path):
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", path, "-ar", "16000", "-ac", "1", "-f", "f32le", "-"],
        capture_output=True, check=True,
    ).stdout
    return np.frombuffer(raw, dtype=np.float32)


def main():
    req = json.load(sys.stdin)
    lang = req.get("lang", "zh")
    model = WhisperModel(req.get("model", "small"), device="cpu", compute_type="int8")
    texts = []
    for path in req["files"]:
        segments, _ = model.transcribe(
            load(path), language=lang, beam_size=5,
            initial_prompt=PROMPTS.get(lang), condition_on_previous_text=False,
        )
        texts.append("".join(s.text for s in segments).strip())
    json.dump({"texts": texts}, sys.stdout, ensure_ascii=False)


if __name__ == "__main__":
    main()
