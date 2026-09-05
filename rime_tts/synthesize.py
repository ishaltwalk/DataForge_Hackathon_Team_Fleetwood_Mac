import json
import os
import urllib.request

RIME_API_KEY = os.environ["RIME_API_KEY"]
SYNTH_URL = "https://users.rime.ai/v1/rime-tts"

def synthesize(text: str, speaker: str = "falcon", rpa: str | None = None, output_path: str = "output.wav") -> str:

    payload_text = f"{{{rpa}}}" if rpa else text    

    uses_custom_pronunciation = "{" in payload_text and "}" in payload_text

    headers = {
    "Accept" : "audio/wav",
    "Authorization" : f"Bearer {RIME_API_KEY}",
    "Content-Type": "application/json"
    }

    payload = {
    "text" : payload_text,
    "speaker" : speaker,
    "modelId" : "mistv3"
    }

    if uses_custom_pronunciation:
        payload["phonemizeBetweenBrackets"] = True

    data = json.dumps(payload).encode("utf8")

    request = urllib.request.Request(
    SYNTH_URL,
    data = data,
    headers = headers,
    method = "POST"
    )

    with urllib.request.urlopen(request) as response:
        with open(output_path, "wb") as f:
            while chunk := response.read(4096):
                f.write(chunk)

    return output_path 
if __name__ == "__main__":
    path = synthesize("Hello! This is Rime speaking", speaker="falcon")
    print(f"Audio saved to {path}")