import json
import urllib.request

from rime_tts.synthesize import api_key

PHONEMIZE_URL = "https://optimize.rime.ai/phonemize"


def phonemize(audio_path: str) -> str:
    with open(audio_path, "rb") as f:
        audio_bytes = f.read()

    headers = {
        "Authorization": f"Bearer {api_key()}",
        "Content-Type": "audio/wav"
    }

    request = urllib.request.Request(
        PHONEMIZE_URL,
        data=audio_bytes,
        headers=headers,
        method="POST"
    )

    with urllib.request.urlopen(request) as response:
        response_body = response.read().decode("utf-8")

    result = json.loads(response_body)
    phoneme_string = result["phonemeString"]

    return phoneme_string.rstrip(" !?.")


if __name__ == "__main__":
    rpa = phonemize("output.wav")
    print(f"RPA string: {rpa}")