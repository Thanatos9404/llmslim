"""Reference flow for a long-running Sarvam voice agent.

Speech transport deliberately stays outside LLMSlim. Configure the current
official Saaras STT and Bulbul TTS SDKs in the marked application functions.
"""

from typing import Dict, List

from llmslim import plan_context


def transcribe_with_saaras(audio_path: str) -> str:
    raise NotImplementedError("Connect the current Sarvam Saaras SDK in your application")


def synthesize_with_bulbul(text: str, output_path: str) -> None:
    raise NotImplementedError("Connect the current Sarvam Bulbul SDK in your application")


def prepare_voice_turn(history: List[Dict[str, str]], transcript: str) -> str:
    messages = history + [{"role": "user", "content": transcript}]
    plan = plan_context(
        messages=messages,
        query=transcript,
        model="sarvam-105b-conversations",
        max_input_tokens=16_000,
        reserve_output_tokens=512,
    )
    return plan.final_context


if __name__ == "__main__":
    print("Flow: Saaras STT -> prepare_voice_turn -> Sarvam chat -> Bulbul TTS")
