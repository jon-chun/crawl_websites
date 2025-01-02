#!/usr/bin/env python3

import json
import getpass
from openai import OpenAI
from collections import Counter

INPUT_JSON_FILENAME = "helixcenter_openai_20241231-141845_cleaned.json"
OUTPUT_NORM_MAP_JSON = INPUT_JSON_FILENAME.replace('_cleaned.json', '_norm_map.json')
OUTPUT_JSON_NORM_FILENAME = INPUT_JSON_FILENAME.replace('_cleaned.json', '_normed.json')

def setup_openai():
    api_key = getpass.getpass("Enter your OpenAI API key: ")
    return OpenAI(api_key=api_key)

def get_unique_values(data, field):
    values = set()
    for item in data:
        if isinstance(item.get(field), list):
            values.update(item[field])
    return sorted(list(values))

def normalize_values(client, field_name, values):
    prompt = f"""Here are unique {field_name} from academic roundtable discussions:
{', '.join(values)}

Please normalize these terms by:
1. Combining very similar concepts
2. Using the most universal/standard phrasing
3. Return ONLY a JSON mapping of original terms to normalized terms

Example format:
{{"original_term": "normalized_term"}}"""

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a data standardization assistant."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2
    )
    
    return json.loads(response.choices[0].message.content)

def update_json_with_normalized_values(data, norm_maps):
    normalized_data = []
    for item in data:
        new_item = item.copy()
        for field, mapping in norm_maps.items():
            if isinstance(item.get(field), list):
                new_item[field] = [mapping.get(val, val) for val in item[field]]
        normalized_data.append(new_item)
    return normalized_data

def main():
    client = setup_openai()
    
    with open(INPUT_JSON_FILENAME, 'r', encoding='utf-8') as f:
        data = json.load(f)

    fields = ['keywords', 'institutions', 'specialities']
    normalization_maps = {}
    
    for field in fields:
        print(f"\nProcessing {field}...")
        unique_values = get_unique_values(data, field)
        normalization_maps[field] = normalize_values(client, field, unique_values)

    # Save normalization maps
    with open(OUTPUT_NORM_MAP_JSON, 'w', encoding='utf-8') as f:
        json.dump(normalization_maps, f, indent=2, ensure_ascii=False)
    print(f"\nNormalization maps saved to {OUTPUT_NORM_MAP_JSON}")

    # Apply normalizations and save result
    normalized_data = update_json_with_normalized_values(data, normalization_maps)
    with open(OUTPUT_JSON_NORM_FILENAME, 'w', encoding='utf-8') as f:
        json.dump(normalized_data, f, indent=2, ensure_ascii=False)
    print(f"Normalized data saved to {OUTPUT_JSON_NORM_FILENAME}")

if __name__ == "__main__":
    main()