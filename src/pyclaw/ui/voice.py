"""Voice interaction UI — edge-tts synthesis + whisper transcription.

Provides a Flet panel for voice input/output with:
- Text-to-speech via edge-tts
- Speech-to-text via OpenAI Whisper API
- Mic recording (via platform audio capture)
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Any, cast

from pyclaw.ui.i18n import t

logger = logging.getLogger(__name__)


async def synthesize_speech(
    text: str,
    voice: str = "en-US-AriaNeural",
    output_path: str | None = None,
) -> str:
    """Synthesize speech using edge-tts. Returns path to audio file."""
    try:
        import edge_tts
    except ImportError:
        raise RuntimeError("edge-tts required: pip install edge-tts")

    if not output_path:
        output_path = tempfile.mktemp(suffix=".mp3")

    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_path)
    return output_path


async def list_voices(language: str = "en") -> list[dict[str, str]]:
    """List available edge-tts voices for a language."""
    try:
        import edge_tts
    except ImportError:
        return []

    voices = await edge_tts.list_voices()
    return [
        {"name": v["Name"], "locale": v["Locale"], "gender": v["Gender"]}
        for v in voices
        if v["Locale"].startswith(language)
    ]


async def transcribe_audio(
    audio_path: str,
    api_key: str = "",
    model: str = "whisper-1",
) -> str:
    """Transcribe audio using OpenAI Whisper API."""
    try:
        import openai
    except ImportError:
        raise RuntimeError("openai required: pip install openai")

    client = openai.AsyncOpenAI(api_key=api_key) if api_key else openai.AsyncOpenAI()

    with open(audio_path, "rb") as f:
        transcript = await client.audio.transcriptions.create(model=model, file=f)

    return transcript.text


# --- Flet UI component ---


def build_voice_panel(
    on_transcribed: Any = None,
    on_synthesized: Any = None,
    api_key: str = "",
    tts_voice: str = "en-US-AriaNeural",
) -> Any:
    """Build a Flet voice interaction panel.

    Returns a ``ft.Column`` with record/playback controls.
    """
    try:
        import flet as ft
    except ImportError:
        return None

    recording = False
    status_text = ft.Text(t("voice.ready"), size=14)
    text_input = ft.TextField(label=t("voice.text_label"), multiline=True, min_lines=2, expand=True)

    async def handle_tts(e: Any) -> None:
        text = text_input.value
        if not text:
            return
        status_text.value = t("voice.synthesizing")
        status_text.update()
        try:
            path = await synthesize_speech(text, voice=tts_voice)
            status_text.value = t("voice.saved", name=Path(path).name)
            if on_synthesized:
                await on_synthesized(path)
        except Exception as exc:
            status_text.value = t("voice.error", error=str(exc))
        status_text.update()

    transcription_result = ft.TextField(
        label=t("voice.transcription_result", default="Transcription"),
        multiline=True,
        min_lines=2,
        read_only=True,
        expand=True,
    )

    async def handle_transcribe(e: Any) -> None:
        files = await ft.FilePicker().pick_files(
            dialog_title=t("voice.select_audio", default="Select audio file"),
            allowed_extensions=["mp3", "wav", "ogg", "m4a", "flac", "webm", "mp4"],
            allow_multiple=False,
        )
        if not files:
            return
        picked = files[0]
        if not picked.path:
            return
        status_text.value = t("voice.transcribing", default="Transcribing...")
        status_text.update()
        try:
            result = await transcribe_audio(picked.path, api_key=api_key)
            transcription_result.value = result
            status_text.value = t(
                "voice.transcribed", default="Transcribed ({n} chars)", n=len(result)
            )
            if on_transcribed:
                await on_transcribed(result)
        except Exception as exc:
            status_text.value = t("voice.error", error=str(exc))
        status_text.update()
        transcription_result.update()

    tts_btn = ft.Button(t("voice.speak"), icon=ft.Icons.VOLUME_UP, on_click=handle_tts)
    stt_btn = ft.Button(
        t("voice.transcribe"), icon=ft.Icons.MIC, on_click=handle_transcribe
    )

    return ft.Column(
        controls=[
            ft.Text(t("voice.title"), size=20, weight=ft.FontWeight.BOLD),
            text_input,
            ft.Row([tts_btn, stt_btn]),
            transcription_result,
            status_text,
        ],
        spacing=12,
    )
