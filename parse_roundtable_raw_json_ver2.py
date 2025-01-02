#!/usr/bin/env python3

import os
import json
import openai
import getpass
import time
import random
import signal
import sys

# Constants
MAX_API_WAIT_SEC = 10
MIN_API_DELAY_SEC = 1
MAX_API_DELAY_SEC = 2

# Timeout exception
class TimeoutException(Exception):
    pass

def timeout_handler(signum, frame):
    raise TimeoutException("[ERROR] API call timed out.")

# Register our custom signal handler for SIGALRM on Unix-based systems
if hasattr(signal, 'SIGALRM'):
    signal.signal(signal.SIGALRM, timeout_handler)

# Prompt for the API key
openai.api_key = getpass.getpass("Enter your OpenAI API key: ")

def analyze_roundtable_with_gpt(roundtable):
    """
    Calls an LLM to analyze the roundtable, returning new fields:
      1) description_one-sentence
      2) description_summary
      3) keywords
      4) panelist_ct
      5) institutions
      6) specialities
    """

    roundtable_id = roundtable.get("id", "")
    title = roundtable.get("title", "")
    description = roundtable.get("description", "")
    panelists_data = roundtable.get("panelist", {})

    panelists_str = ""
    for key, val in panelists_data.items():
        panelists_str += f"{key}: {val}\n"

    system_message = {
        "role": "system",
        "content": (
            "You are an assistant that analyzes roundtable data. "
            "You will be given a roundtable 'description' plus its 'panelist' information. "
            "Please generate and return new fields as structured JSON."
        ),
    }

    user_message = {
        "role": "user",
        "content": (
            f"Roundtable ID: {roundtable_id}\n"
            f"Title: {title}\n\n"
            f"Description:\n{description}\n\n"
            f"Panelists:\n{panelists_str}\n\n"
            "TASKS:\n"
            "1) description_one-sentence: Summarize 'description' in exactly one sentence.\n"
            "2) description_summary: Summarize 'description' in exactly 2 or 3 sentences.\n"
            "3) keywords: Extract 3-6 short topical keywords or key phrases.\n"
            "4) panelist_ct: The integer count of the total number of panelists.\n"
            "5) institutions: A list of institutions or affiliations gleaned from 'title_{n}' or 'description_{n}'.\n"
            "6) specialities: A list of the specialized subject areas gleaned from 'title_{n}' or 'description_{n}'.\n\n"
            "Return your answer ONLY as valid JSON with these exact fields:\n"
            "{\n"
            "   \"description_one-sentence\": ...,\n"
            "   \"description_summary\": ...,\n"
            "   \"keywords\": [...],\n"
            "   \"panelist_ct\": number,\n"
            "   \"institutions\": [...],\n"
            "   \"specialities\": [...]\n"
            "}"
        ),
    }

    try:
        if hasattr(signal, 'SIGALRM'):
            signal.alarm(MAX_API_WAIT_SEC)

        print(f"[DEBUG] --> Sending request to LLM for roundtable ID={roundtable_id} ...")
        # Updated to openai.Chat.create for openai>=1.0.0
        response = openai.Chat.create(
            model="gpt-3.5-turbo",  # or your custom model
            messages=[system_message, user_message],
            max_tokens=500,
            temperature=0.2,
        )

        # Cancel the alarm
        if hasattr(signal, 'SIGALRM'):
            signal.alarm(0)

        # new approach: response.choices[0].message.content
        # raw_answer = response.choices[0].message.content.strip()
        raw_answer = response.choices[0].message.content

        print(f"[DEBUG] --> Raw LLM response:\n{raw_answer}\n")

        new_fields = json.loads(raw_answer)

        print(f"[DEBUG] --> description_one-sentence: {new_fields.get('description_one-sentence', '')}")
        print(f"[DEBUG] --> description_summary: {new_fields.get('description_summary', '')}")
        print(f"[DEBUG] --> keywords: {new_fields.get('keywords', [])}")
        print(f"[DEBUG] --> panelist_ct: {new_fields.get('panelist_ct', 0)}")
        print(f"[DEBUG] --> institutions: {new_fields.get('institutions', [])}")
        print(f"[DEBUG] --> specialities: {new_fields.get('specialities', [])}")
        print("---------------------------------------------------------")

        return new_fields

    except TimeoutException as te:
        print(f"{te} for roundtable id={roundtable_id}")
        return {
            "description_one-sentence": "",
            "description_summary": "",
            "keywords": [],
            "panelist_ct": 0,
            "institutions": [],
            "specialities": []
        }

    except Exception as e:
        print(f"[ERROR] LLM call or JSON parsing failed for roundtable id={roundtable_id}:\n{e}\n")
        return {
            "description_one-sentence": "",
            "description_summary": "",
            "keywords": [],
            "panelist_ct": 0,
            "institutions": [],
            "specialities": []
        }

def main():
    input_filename = "helixcenter_openai_20241231-141845.json"
    output_filename = "helixcenter_openai_20241231-141845_cleaned.json"

    with open(input_filename, "r", encoding="utf-8") as f:
        roundtables = json.load(f)

    for idx, rt in enumerate(roundtables, start=1):
        rt_id = rt.get("id")
        print(f"[INFO] Processing roundtable index={idx}, ID={rt_id}")
        new_fields = analyze_roundtable_with_gpt(rt)

        rt.update(new_fields)

        # Random delay between calls
        delay = random.uniform(MIN_API_DELAY_SEC, MAX_API_DELAY_SEC)
        print(f"[DEBUG] Waiting for {delay:.2f} seconds before next call...")
        time.sleep(delay)

    with open(output_filename, "w", encoding="utf-8") as f:
        json.dump(roundtables, f, indent=2, ensure_ascii=False)

    print(f"[INFO] Wrote updated data to {output_filename}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[INFO] Process interrupted by user.")
        sys.exit(0)
