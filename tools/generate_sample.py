# -*- coding: utf-8 -*-
import pandas as pd
import random
from datetime import datetime, timedelta
import os

def generate_sample_data(output_path: str, num_rows: int = 1000):
    user_ids = [f"user_{i:04d}" for i in range(1, 51)]
    
    event_types = [
        "page_view",
        "click_button",
        "scroll_down",
        "submit_form",
        "view_item",
        "add_to_cart",
        "search",
        "share"
    ]
    
    page_names = [
        "home",
        "product_list",
        "product_detail",
        "cart",
        "checkout",
        "profile",
        "search_results"
    ]
    
    actions = [
        "view",
        "click",
        "submit",
        "scroll",
        "share"
    ]
    
    base_time = datetime(2024, 1, 1, 0, 0, 0)
    
    data = []
    for i in range(num_rows):
        event_time = base_time + timedelta(
            days=random.randint(0, 29),
            hours=random.randint(0, 23),
            minutes=random.randint(0, 59),
            seconds=random.randint(0, 59)
        )
        
        row = {
            "event_id": f"evt_{i:06d}",
            "user_id": random.choice(user_ids),
            "event_type": random.choice(event_types),
            "page_name": random.choice(page_names),
            "action": random.choice(actions),
            "timestamp": event_time.strftime("%Y-%m-%d %H:%M:%S"),
            "session_id": f"sess_{random.randint(1, 200):04d}",
            "device_type": random.choice(["mobile", "desktop", "tablet"]),
            "duration_ms": random.randint(100, 30000)
        }
        data.append(row)
    
    df = pd.DataFrame(data)
    df = df.sort_values("timestamp")
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df.to_excel(output_path, index=False)
    print(f"Generated {num_rows} rows to {output_path}")
    print(f"Columns: {list(df.columns)}")
    print(f"Sample:\n{df.head()}")

if __name__ == "__main__":
    generate_sample_data("data/sample_data.xlsx", num_rows=1000)
