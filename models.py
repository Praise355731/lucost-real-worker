"""
The three AI stages of the real worker. Each stage is a placeholder until a model is chosen.

A model is only plugged in after its licence has been checked for commercial use (see the README).
Until then each stage raises ModelNotConfigured, and the job fails with that reason. Nothing fake is shipped.
"""

import os


class ModelNotConfigured(RuntimeError):
    pass


VOICE_MODEL = os.getenv("VOICE_MODEL", "")          # e.g. "cosyvoice" once its licence is confirmed
FACE_MODEL = os.getenv("FACE_MODEL", "")            # e.g. "pulid" once its licence is confirmed
LIPSYNC_MODEL = os.getenv("LIPSYNC_MODEL", "")      # e.g. "musetalk" once its licence is confirmed


def synthesize_speech(text: str, voice_snippet_path: str, language: str, out_wav: str) -> str:
    """Speak `text` in the voice of `voice_snippet_path` and write a WAV file to `out_wav`."""
    if not VOICE_MODEL:
        raise ModelNotConfigured("Voice model not chosen yet. Its licence must allow commercial use first.")
    raise ModelNotConfigured(f"Voice model '{VOICE_MODEL}' is named but not implemented yet.")


def animate_face(face_image_path: str, speech_wav: str, out_mp4: str) -> str:
    """Make the face in `face_image_path` speak `speech_wav` with matching mouth movement, into `out_mp4`."""
    if not FACE_MODEL or not LIPSYNC_MODEL:
        raise ModelNotConfigured("Face and lip-sync models not chosen yet. Their licences must allow commercial use first.")
    raise ModelNotConfigured(f"Face model '{FACE_MODEL}' with lip-sync '{LIPSYNC_MODEL}' is named but not implemented yet.")
