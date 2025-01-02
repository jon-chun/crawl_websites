#!/usr/bin/env python3

import json
import pandas as pd
import os

def flatten_json(json_obj, parent_key='', sep='_'):
    items = []
    for k, v in json_obj.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        
        if isinstance(v, dict):
            items.extend(flatten_json(v, new_key, sep=sep).items())
        elif isinstance(v, list):
            # Convert list to string representation
            items.append((new_key, ', '.join(map(str, v))))
        else:
            items.append((new_key, v))
    return dict(items)

def main():
    INPUT_JSON_FILENAME = "helixcenter_openai_20241231-141845_cleaned.json"
    INPUT_JSON_FILENAME = "helixcenter_openai_20241231-141845_normed.json"
    OUTPUT_CSV_FILENAME = INPUT_JSON_FILENAME.rsplit('.', 1)[0] + '.csv'

    # Read JSON
    with open(INPUT_JSON_FILENAME, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Flatten each record
    flattened_data = [flatten_json(record) for record in data]

    # Convert to DataFrame
    df = pd.DataFrame(flattened_data)

    # Save to CSV
    df.to_csv(OUTPUT_CSV_FILENAME, index=False, encoding='utf-8')
    print(f"Converted {INPUT_JSON_FILENAME} to {OUTPUT_CSV_FILENAME}")

if __name__ == "__main__":
    main()