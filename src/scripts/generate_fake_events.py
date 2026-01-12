#!/usr/bin/env python3
"""
Generate fake OTT events for testing the compliance pipeline.

Usage:
    python src/scripts/generate_fake_events.py --events 100 --concurrency 5

This script simulates Smart TV clients sending events to the /events endpoint.
"""

import argparse
import random
import string
import time
import requests
import concurrent.futures
from datetime import datetime, timedelta

# Base URL for the API
API_BASE = "http://localhost:8000"

# Event templates
EVENT_TYPES = ["play", "pause", "stop", "seek", "error", "login", "logout"]
REGIONS = ["US", "EU", "CA", "UK", "DE", "FR", "JP", "KR"]
CONTENT_IDS = [f"content_{i}" for i in range(1, 21)]
DEVICE_IDS = [f"tv_{i}" for i in range(1, 51)]
USER_IDS = [f"user_{i}" for i in range(1, 101)]

def random_string(length=8):
    """Generate a random string."""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def generate_event(event_id=None):
    """Generate a single fake event."""
    if event_id is None:
        event_id = f"evt_{random_string(12)}"

    user_id = random.choice(USER_IDS)
    device_id = random.choice(DEVICE_IDS)
    content_id = random.choice(CONTENT_IDS)
    event_type = random.choice(EVENT_TYPES)
    region = random.choice(REGIONS)
    is_eu = region in ["EU", "UK", "DE", "FR"]
    has_consent = random.choice([True, False]) if is_eu else True  # EU users may not consent
    ip_address = f"{random.randint(1,255)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,255)}"
    timestamp = (datetime.utcnow() - timedelta(minutes=random.randint(0, 60))).isoformat() + "Z"

    # Add some error codes for error events
    error_code = None
    if event_type == "error":
        error_code = random.choice(["NETWORK_ERROR", "CONTENT_NOT_FOUND", "DEVICE_ERROR", "AUTH_FAILED"])

    event = {
        "event_id": event_id,
        "user_id": user_id,
        "device_id": device_id,
        "content_id": content_id,
        "event_type": event_type,
        "timestamp": timestamp,
        "region": region,
        "is_eu": is_eu,
        "has_consent": has_consent,
        "ip_address": ip_address,
        "error_code": error_code,
        "extra_metadata": {
            "app_version": f"1.{random.randint(0,5)}.{random.randint(0,10)}",
            "network_type": random.choice(["wifi", "ethernet", "mobile"])
        }
    }

    return event

def send_event(event, session=None):
    """Send an event to the API."""
    try:
        if session:
            response = session.post(f"{API_BASE}/events", json=event)
        else:
            response = requests.post(f"{API_BASE}/events", json=event, timeout=5)
        return response.status_code == 202
    except Exception as e:
        print(f"Failed to send event {event['event_id']}: {e}")
        return False

def generate_and_send_batch(batch_size, session=None):
    """Generate and send a batch of events."""
    success_count = 0
    for _ in range(batch_size):
        event = generate_event()
        if send_event(event, session):
            success_count += 1
        time.sleep(random.uniform(0.01, 0.1))  # Small delay between events
    return success_count

def main():
    parser = argparse.ArgumentParser(description="Generate fake OTT events")
    parser.add_argument("--events", type=int, default=100, help="Total number of events to generate")
    parser.add_argument("--concurrency", type=int, default=1, help="Number of concurrent threads")
    parser.add_argument("--batch-size", type=int, default=10, help="Events per batch per thread")

    args = parser.parse_args()

    total_events = args.events
    concurrency = args.concurrency
    batch_size = args.batch_size

    print(f"Generating {total_events} fake events with {concurrency} concurrent threads...")
    print(f"API endpoint: {API_BASE}/events")

    start_time = time.time()

    # Calculate batches per thread
    events_per_thread = total_events // concurrency
    remainder = total_events % concurrency

    futures = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        for i in range(concurrency):
            thread_events = events_per_thread + (1 if i < remainder else 0)
            batches = (thread_events + batch_size - 1) // batch_size  # Ceiling division

            for _ in range(batches):
                batch_events = min(batch_size, thread_events)
                thread_events -= batch_events
                futures.append(executor.submit(generate_and_send_batch, batch_events))

    # Collect results
    total_success = sum(future.result() for future in concurrent.futures.as_completed(futures))

    end_time = time.time()
    duration = end_time - start_time

    print("\nResults:")
    print(f"  Total events attempted: {total_events}")
    print(f"  Successful sends: {total_success}")
    print(f"  Failed sends: {total_events - total_success}")
    print(f"  Success rate: {total_success / total_events * 100:.1f}%")
    print(f"  Duration: {duration:.2f} seconds")
    print(f"  Events per second: {total_events / duration:.1f}")

    if total_success > 0:
        print("\nTip: Now run 'curl http://localhost:8000/process/drain' to process the events,")
        print("      or visit http://localhost:8000 to see the dashboard.")

if __name__ == "__main__":
    main()