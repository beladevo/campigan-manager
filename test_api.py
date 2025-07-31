#!/usr/bin/env python3
"""
Simple test script for the Solara AI campaign system
"""

import requests
import json
import time

def test_campaign_creation():
    """Test creating a new campaign"""
    url = "http://localhost:3000/campaigns"
    payload = {
        "userId": "test-user-123",
        "prompt": "Create a beach scene with a cat playing in the sand"
    }
    
    print("Creating campaign...")
    print(f"POST {url}")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        
        campaign = response.json()
        print(f"Campaign created successfully!")
        print(f"Response: {json.dumps(campaign, indent=2)}")
        
        return campaign['id']
    except requests.exceptions.RequestException as e:
        print(f"Error creating campaign: {e}")
        return None

def test_campaign_status(campaign_id):
    """Test fetching campaign status"""
    url = f"http://localhost:3000/campaigns/{campaign_id}"
    
    print(f"\nFetching campaign status...")
    print(f"GET {url}")
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        
        campaign = response.json()
        print(f"Campaign status: {campaign['status']}")
        print(f"Response: {json.dumps(campaign, indent=2)}")
        
        return campaign
    except requests.exceptions.RequestException as e:
        print(f"Error fetching campaign: {e}")
        return None

def test_python_health():
    """Test Python service health"""
    url = "http://localhost:8000/health"
    
    print(f"\nChecking Python service health...")
    print(f"GET {url}")
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        
        health = response.json()
        print(f"Python service health: {json.dumps(health, indent=2)}")
        
        return health
    except requests.exceptions.RequestException as e:
        print(f"Error checking Python service health: {e}")
        return None

def main():
    print("=== Solara AI Campaign System Test ===\n")
    
    # Test Python service health
    health = test_python_health()
    if not health:
        print("Python service is not available. Make sure Docker Compose is running.")
        return
    
    # Create a campaign
    campaign_id = test_campaign_creation()
    if not campaign_id:
        print("Failed to create campaign. Check NestJS service.")
        return
    
    # Poll campaign status
    print(f"\nPolling campaign {campaign_id} status...")
    for i in range(10):
        campaign = test_campaign_status(campaign_id)
        if not campaign:
            break
            
        status = campaign.get('status', 'unknown')
        print(f"Attempt {i+1}: Status = {status}")
        
        if status in ['completed', 'failed']:
            break
            
        time.sleep(5)
    
    print("\n=== Test Complete ===")

if __name__ == "__main__":
    main()