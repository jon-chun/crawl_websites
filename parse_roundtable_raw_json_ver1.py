#!/usr/bin/env python3

import os
import json
import openai
import getpass

# ---------------------------------------------------------------------
# 1) CONFIGURE THE OPENAI API
# Replace with your actual API key (or manage via environment variables).
# ---------------------------------------------------------------------

# openai.api_key = os.getenv("OPENAI_API_KEY")  # or just assign a string if appropriate
openai.api_key = getpass.getpass("Enter your OpenAI API key: ")

# ---------------------------------------------------------------------
# 2) HELPER FUNCTION: CREATE A PROMPT & CALL THE MODEL
#    We pass the entire roundtable data, specifically:
#     - The "description"
#     - The "panelist" dictionary
#    We instruct the model to return the new fields.
# ---------------------------------------------------------------------
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
    # Grab the relevant data from the roundtable
    roundtable_id = roundtable.get("id", "")
    title = roundtable.get("title", "")
    description = roundtable.get("description", "")
    panelists_data = roundtable.get("panelist", {})

    # Convert the panelists dictionary to a more readable string
    # for the prompt. Alternatively, you can send the raw structure.
    # Example: create a text summarizing each panelist’s title & description.
    panelists_str = ""
    for key, val in panelists_data.items():
        # e.g., name_1, title_1, description_1...
        # We'll group them by index (1, 2, 3...) to produce a short readable summary.
        panelists_str += f"{key}: {val}\n"

    # ----------------------------------------------------------------
    # 2a) Build a structured system or user prompt instructing the LLM
    # ----------------------------------------------------------------
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

    # ----------------------------------------------------------------
    # 2b) Call the ChatCompletion or Completion API
    # ----------------------------------------------------------------
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",  # or your custom model, e.g. "gpt-4o-mini"
            messages=[system_message, user_message],
            max_tokens=500,
            temperature=0.2,
        )
        # Extract content
        raw_answer = response["choices"][0]["message"]["content"].strip()
        # We'll parse the raw_answer as JSON
        # The model *should* return valid JSON. In production, add error handling.
        new_fields = json.loads(raw_answer)

        return new_fields

    except Exception as e:
        print(f"[ERROR] LLM call or JSON parsing failed for roundtable id={roundtable_id}: {e}")
        # Return an empty fallback so we don't crash
        return {
            "description_one-sentence": "",
            "description_summary": "",
            "keywords": [],
            "panelist_ct": 0,
            "institutions": [],
            "specialities": []
        }


# ---------------------------------------------------------------------
# 3) MAIN: READ THE ###ROUNDTABLE_JSON, PROCESS, WRITE NEW JSON
# ---------------------------------------------------------------------
def main():
    input_filename = "helixcenter_openai_20241231-141845.json"  # or your actual input path
    output_filename = "helixcenter_openai_20241231-141845_cleaned.json"

    # 3a) Read the JSON file
    with open(input_filename, "r", encoding="utf-8") as f:
        roundtables = json.load(f)

    # 3b) For each roundtable, call the analysis function
    for rt in roundtables:
        print(f"[INFO] Processing roundtable ID={rt.get('id')}")
        new_fields = analyze_roundtable_with_gpt(rt)

        # 3c) Merge new fields into the original roundtable dictionary
        rt.update(new_fields)

    # 3d) Write out the updated roundtables
    with open(output_filename, "w", encoding="utf-8") as f:
        json.dump(roundtables, f, indent=2, ensure_ascii=False)

    print(f"[INFO] Wrote updated data to {output_filename}")


if __name__ == "__main__":
    main()
