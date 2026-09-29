"""Bounded Gemini Live connectivity probe for the Dot; never logs credentials or audio."""

import argparse
import asyncio
import json
from pathlib import Path
from urllib.parse import quote

from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed


ENDPOINT = (
    "wss://generativelanguage.googleapis.com/ws/"
    "google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent"
)


async def probe(key: str, model: str, trace: dict[str, str]) -> dict[str, int | bool]:
    url = f"{ENDPOINT}?key={quote(key, safe='')}"
    audio_bytes = 0
    completed = False
    async with asyncio.timeout(35):
        trace["stage"] = "connect"
        async with connect(url, max_size=4 * 1024 * 1024) as ws:
            trace["stage"] = "setup"
            await ws.send(json.dumps({"setup": {
                "model": f"models/{model}",
                "outputAudioTranscription": {},
                "generationConfig": {
                    "responseModalities": ["AUDIO"],
                    "speechConfig": {"voiceConfig": {
                        "prebuiltVoiceConfig": {"voiceName": "Aoede"}}},
                },
            }}))
            message = json.loads(await ws.recv())
            if "setupComplete" not in message:
                raise RuntimeError("setup not acknowledged")
            trace["stage"] = "reply"
            await ws.send(json.dumps({"clientContent": {
                "turns": [{"role": "user", "parts": [
                    {"text": "قل مرحباً بكلمة واحدة فقط"}]}],
                "turnComplete": True,
            }}, ensure_ascii=False))
            while not completed:
                message = json.loads(await ws.recv())
                content = message.get("serverContent", {})
                for part in content.get("modelTurn", {}).get("parts", []):
                    audio_bytes += len(part.get("inlineData", {}).get("data", "")) * 3 // 4
                completed = bool(content.get("turnComplete"))
    return {"setup": True, "turn_complete": completed, "audio_bytes": audio_bytes}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    trace = {"stage": "start"}
    try:
        result = asyncio.run(probe(config["api_key"], config["model"], trace))
    except Exception as exc:
        # WebSocket exceptions can contain the URL, including its secret query.
        status = {"ok": False, "error_type": type(exc).__name__, **trace}
        if isinstance(exc, ConnectionClosed):
            status["close_code"] = exc.rcvd.code if exc.rcvd else None
        print(json.dumps(status))
        raise SystemExit(1) from None
    print(json.dumps({"ok": result["turn_complete"] and result["audio_bytes"] > 0,
                      **result}))


if __name__ == "__main__":
    main()
