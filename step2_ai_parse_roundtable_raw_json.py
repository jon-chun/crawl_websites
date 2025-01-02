#!/usr/bin/env python3

import os
import json
import getpass
import time
import random
import signal
import sys
from openai import OpenAI

# Constants
MAX_API_WAIT_SEC = 10
MIN_API_DELAY_SEC = 1
MAX_API_DELAY_SEC = 2

class TimeoutException(Exception):
    pass

def timeout_handler(signum, frame):
    raise TimeoutException("[ERROR] API call timed out.")

if hasattr(signal, 'SIGALRM'):
    signal.signal(signal.SIGALRM, timeout_handler)

api_key = getpass.getpass("Enter your OpenAI API key: ")
client = OpenAI(api_key=api_key)

def save_intermediate_results(roundtables, filename):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(roundtables, f, indent=2, ensure_ascii=False)

def analyze_roundtable_with_gpt(roundtable, total_ct, current_idx):
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
            "3) keywords: Extract 3-6 short topical keywords.\n"
            "4) panelist_ct: The integer count of total panelists.\n"
            "5) institutions: A list of affiliations gleaned from 'title_{n}' or 'description_{n}'.\n"
            "6) specialities: A list of specialized subject areas gleaned from 'title_{n}' or 'description_{n}'.\n\n"
            "Return answer ONLY as valid JSON with exactly these fields:\n"
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
        
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[system_message, user_message],
            max_tokens=500,
            temperature=0.2
        )

        if hasattr(signal, 'SIGALRM'):
            signal.alarm(0)

        raw_answer = response.choices[0].message.content
        print(f"[DEBUG] --> Raw LLM response:\n{raw_answer}\n")

        new_fields = json.loads(raw_answer)

        progress = (current_idx / total_ct) * 100
        print(f"\n\n========== PROCESSED {progress:.1f}% of {total_ct} roundtables ==========\n\n")

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
    intermediate_filename = "helixcenter_openai_20241231-141845_clean-intermediate.json"
    output_filename = "helixcenter_openai_20241231-141845_cleaned.json"

    with open(input_filename, "r", encoding="utf-8") as f:
        roundtables = json.load(f)
    
    total_roundtable_ct = len(roundtables)
    start_idx = 0

    # Check for intermediate results
    if os.path.exists(intermediate_filename):
        with open(intermediate_filename, "r", encoding="utf-8") as f:
            processed_roundtables = json.load(f)
            start_idx = len(processed_roundtables)
            roundtables[:start_idx] = processed_roundtables
            print(f"[INFO] Resuming from index {start_idx}")

    for idx in range(start_idx, total_roundtable_ct):
        rt = roundtables[idx]
        rt_id = rt.get("id")
        print(f"[INFO] Processing roundtable index={idx+1}, ID={rt_id}")
        
        new_fields = analyze_roundtable_with_gpt(rt, total_roundtable_ct, idx + 1)
        rt.update(new_fields)

        # Save intermediate results
        save_intermediate_results(roundtables[:idx + 1], intermediate_filename)

        delay = random.uniform(MIN_API_DELAY_SEC, MAX_API_DELAY_SEC)
        print(f"[DEBUG] Waiting for {delay:.2f} seconds before next call...")
        time.sleep(delay)

    # Save final results
    save_intermediate_results(roundtables, output_filename)
    print(f"[INFO] Wrote final data to {output_filename}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[INFO] Process interrupted by user.")
        sys.exit(0)