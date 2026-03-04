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
from typing import Any

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

    status_text = ft.Text(t("voice.ready"), size=14)
    text_input = ft.TextField(
        label=t("voice.text_label"),
        multiline=True,
        min_lines=2,
        expand=True,
        border_radius=12,
    )

    voice_options: list[ft.dropdown.Option] = [
        ft.dropdown.Option(tts_voice, tts_voice),
    ]
    voice_dropdown = ft.Dropdown(
        label=t("voice.voice_select", default="Voice"),
        value=tts_voice,
        options=voice_options,
        width=300,
    )

    async def _load_voices(e: Any = None) -> None:
        try:
            locale_prefix = "en"
            if tts_voice and "-" in tts_voice:
                locale_prefix = tts_voice.split("-")[0]
            voices = await list_voices(locale_prefix)
            if voices:
                voice_dropdown.options = [ft.dropdown.Option(v["name"], f"{v['name']} ({v['gender']})") for v in voices]
                if voice_dropdown.page:
                    voice_dropdown.update()
        except Exception:
            pass

    load_voices_btn = ft.IconButton(
        icon=ft.Icons.REFRESH,
        tooltip=t("voice.refresh_voices", default="Refresh voices"),
        on_click=_load_voices,
        icon_size=18,
    )

    async def handle_tts(e: Any) -> None:
        text = text_input.value
        if not text:
            return
        selected_voice = voice_dropdown.value or tts_voice
        status_text.value = t("voice.synthesizing")
        status_text.update()
        try:
            path = await synthesize_speech(text, voice=selected_voice)
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
        border_radius=12,
    )

    async def handle_transcribe(e: Any) -> None:
        picker = ft.FilePicker()
        page = e.control.page
        if page:
            page.overlay.append(picker)
            page.update()

        result = await picker.pick_files_async(
            dialog_title=t("voice.select_audio", default="Select audio file"),
            allowed_extensions=["mp3", "wav", "ogg", "m4a", "flac", "webm", "mp4"],
            allow_multiple=False,
        )
        if not result or not result.files:
            if page and picker in page.overlay:
                page.overlay.remove(picker)
                page.update()
            return
        picked = result.files[0]
        if not picked.path:
            if page and picker in page.overlay:
                page.overlay.remove(picker)
                page.update()
            return
        status_text.value = t("voice.transcribing", default="Transcribing...")
        status_text.update()
        try:
            text_result = await transcribe_audio(picked.path, api_key=api_key)
            transcription_result.value = text_result
            status_text.value = t("voice.transcribed", default="Transcribed ({n} chars)", n=len(text_result))
            if on_transcribed:
                await on_transcribed(text_result)
        except Exception as exc:
            status_text.value = t("voice.error", error=str(exc))
        status_text.update()
        transcription_result.update()

        if page and picker in page.overlay:
            page.overlay.remove(picker)
            page.update()

    tts_btn = ft.Button(t("voice.speak"), icon=ft.Icons.VOLUME_UP, on_click=handle_tts)
    stt_btn = ft.Button(t("voice.transcribe"), icon=ft.Icons.MIC, on_click=handle_transcribe)

    return ft.Column(
        controls=[
            ft.Row(
                [
                    ft.Icon(ft.Icons.MIC, size=20, color=ft.Colors.PRIMARY),
                    ft.Container(width=8),
                    ft.Text(t("voice.title"), size=20, weight=ft.FontWeight.BOLD),
                ]
            ),
            ft.Divider(height=1),
            ft.Text(t("voice.tts_section", default="Text-to-Speech"), size=16, weight=ft.FontWeight.W_500),
            text_input,
            ft.Row([voice_dropdown, load_voices_btn], spacing=8),
            ft.Row([tts_btn], spacing=8),
            ft.Container(height=8),
            ft.Text(t("voice.stt_section", default="Speech-to-Text"), size=16, weight=ft.FontWeight.W_500),
            ft.Row([stt_btn]),
            transcription_result,
            ft.Container(height=4),
            status_text,
        ],
        spacing=12,
        expand=True,
        scroll=ft.ScrollMode.AUTO,
    )
