#!/usr/bin/env python3

import json
import getpass
import os
from openai import OpenAI
from collections import Counter

MAX_API_WAIT_SEC = 60
CHUNK_SIZE = 50  # Process values in smaller chunks
INPUT_JSON_FILENAME = "helixcenter_openai_20241231-141845_cleaned.json"
OUTPUT_NORM_MAP_JSON = INPUT_JSON_FILENAME.replace('_cleaned.json', '_norm_map.json')
OUTPUT_JSON_NORM_FILENAME = INPUT_JSON_FILENAME.replace('_cleaned.json', '_normed.json')
OUTPUT_REPORT_FILENAME = INPUT_JSON_FILENAME.replace('_cleaned.json', '_norm_report.txt')
INTERMEDIATE_FILE = INPUT_JSON_FILENAME.replace('_cleaned.json', '_intermediate.json')

def setup_openai():
    api_key = getpass.getpass("Enter your OpenAI API key: ")
    return OpenAI(api_key=api_key)

def chunk_list(lst, n):
    """Split list into chunks of size n"""
    return [lst[i:i + n] for i in range(0, len(lst), n)]

def normalize_values(client, field_name, values):
    print(f"\n[DEBUG] Processing {len(values)} {field_name} terms...")
    
    # Split values into chunks
    chunks = chunk_list(values, CHUNK_SIZE)
    normalized_map = {}
    
    for i, chunk in enumerate(chunks, 1):
        print(f"Processing chunk {i} of {len(chunks)}")
        prompt = f"""Normalize these {field_name} terms (combine similar concepts, use standard phrasing). Return only JSON mapping of original to normalized terms:
{', '.join(chunk)}"""

        try:
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a data standardization assistant."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                timeout=MAX_API_WAIT_SEC
            )
            chunk_result = json.loads(response.choices[0].message.content)
            normalized_map.update(chunk_result)
            print(f"Processed {len(chunk_result)} terms")
        except Exception as e:
            print(f"[ERROR] Failed chunk {i}: {str(e)}")
            # On error, map terms to themselves
            normalized_map.update({val: val for val in chunk})
    
    return normalized_map

def load_intermediate_state():
    if os.path.exists(INTERMEDIATE_FILE):
        with open(INTERMEDIATE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'processed_fields': [], 'normalization_maps': {}}

def save_intermediate_state(processed_fields, normalization_maps):
    state = {
        'processed_fields': processed_fields,
        'normalization_maps': normalization_maps
    }
    with open(INTERMEDIATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

def get_unique_values(data, field):
    values = set()
    for item in data:
        if isinstance(item.get(field), list):
            values.update(item[field])
    return sorted(list(values))

def update_json_with_normalized_values(data, norm_maps):
    normalized_data = []
    for item in data:
        new_item = item.copy()
        for field, mapping in norm_maps.items():
            if isinstance(item.get(field), list):
                new_item[field] = [mapping.get(val, val) for val in item[field]]
        normalized_data.append(new_item)
    return normalized_data

def generate_normalization_report(norm_maps):
    report = ["=== NORMALIZATION REPORT ===\n"]
    for field, mapping in norm_maps.items():
        report.append(f"\n{field.upper()}\n{'-' * len(field)}\n")
        normalized_groups = {}
        for original, normalized in mapping.items():
            normalized_groups.setdefault(normalized, []).append(original)
        for normalized, originals in normalized_groups.items():
            if len(originals) > 1:
                report.append(f"\nNormalized Term: {normalized}")
                report.append("Original Terms:")
                for term in sorted(originals):
                    report.append(f"  - {term}")
    return "\n".join(report)

def main():
    client = setup_openai()
    state = load_intermediate_state()
    
    with open(INPUT_JSON_FILENAME, 'r', encoding='utf-8') as f:
        data = json.load(f)

    fields = ['keywords', 'institutions', 'specialities']
    remaining_fields = [f for f in fields if f not in state['processed_fields']]
    
    for field in remaining_fields:
        try:
            print(f"\nProcessing {field}...")
            unique_values = get_unique_values(data, field)
            state['normalization_maps'][field] = normalize_values(client, field, unique_values)
            state['processed_fields'].append(field)
            save_intermediate_state(state['processed_fields'], state['normalization_maps'])
            progress = (len(state['processed_fields']) / len(fields)) * 100
            print(f"Progress: {progress:.1f}% complete")
        except KeyboardInterrupt:
            print("\n[INFO] Interrupted. Progress saved.")
            return
        except Exception as e:
            print(f"\n[ERROR] Failed processing {field}: {str(e)}")
            continue

    if len(state['processed_fields']) == len(fields):
        finalize_output(data, state['normalization_maps'])
        os.remove(INTERMEDIATE_FILE)
        print("Processing complete")

def finalize_output(data, normalization_maps):
    # Save normalization maps
    with open(OUTPUT_NORM_MAP_JSON, 'w', encoding='utf-8') as f:
        json.dump(normalization_maps, f, indent=2, ensure_ascii=False)

    # Generate and save report
    report = generate_normalization_report(normalization_maps)
    with open(OUTPUT_REPORT_FILENAME, 'w', encoding='utf-8') as f:
        f.write(report)

    # Apply normalizations and save result
    normalized_data = update_json_with_normalized_values(data, normalization_maps)
    with open(OUTPUT_JSON_NORM_FILENAME, 'w', encoding='utf-8') as f:
        json.dump(normalized_data, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    main()