#!/usr/bin/env python
"""
Complete API endpoint testing for Campus Club Management Suite
"""
import requests
import json

BASE_URL = "http://localhost:8000"
TOKEN = None

def test_authentication():
    """Test authentication endpoints"""
    global TOKEN
    print("🔐 Testing Authentication...")
    
    # Test login
    login_data = {
        "email": "student1@stanford.edu", 
        "password": "testpass123"
    }
    
    response = requests.post(f"{BASE_URL}/api/v1/auth/login/", json=login_data)
    print(f"   Login Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        TOKEN = data.get('access_token') or data.get('access') or data.get('token')
        print(f"   ✅ Login successful, token received")
        return True
    else:
        print(f"   ❌ Login failed: {response.text}")
        return False

def test_protected_endpoint(endpoint, description):
    """Test a protected endpoint"""
    if not TOKEN:
        print(f"   ❌ {description}: No token available")
        return False
        
    headers = {"Authorization": f"Bearer {TOKEN}"}
    response = requests.get(f"{BASE_URL}{endpoint}", headers=headers)
    
    print(f"   {description}: {response.status_code}")
    if response.status_code == 200:
        try:
            data = response.json()
            print(f"     ✅ Response received ({len(str(data))} chars)")
            return True
        except:
            print(f"     ✅ Response received (non-JSON)")
            return True
    else:
        print(f"     ❌ Error: {response.text[:100]}...")
        return False

def run_api_tests():
    """Run comprehensive API tests"""
    print("🧪 Starting API Endpoint Tests...\n")
    
    # Test 1: Authentication
    auth_success = test_authentication()
    
    if not auth_success:
        print("❌ Cannot continue without authentication")
        return
    
    print("\n👤 Testing User Endpoints...")
    test_protected_endpoint("/api/v1/auth/profile/", "Get Profile")
    
    print("\n🏛️ Testing College Endpoints...")
    test_protected_endpoint("/api/v1/auth/colleges/", "List Colleges")
    
    print("\n🎯 Testing Club Endpoints...")
    test_protected_endpoint("/api/v1/clubs/", "List Clubs")
    test_protected_endpoint("/api/v1/clubs/discover/", "Discover Clubs")
    test_protected_endpoint("/api/v1/clubs/my-clubs/", "My Clubs")
    
    print("\n📅 Testing Event Endpoints...")
    test_protected_endpoint("/api/v1/events/", "List Events")
    test_protected_endpoint("/api/v1/events/upcoming/", "Upcoming Events")
    test_protected_endpoint("/api/v1/events/my-events/", "My Events")
    
    print("\n🎮 Testing Gamification Endpoints...")
    test_protected_endpoint("/api/v1/gamification/badges/", "List Badges")
    test_protected_endpoint("/api/v1/gamification/badges/my-badges/", "My Badges")
    test_protected_endpoint("/api/v1/gamification/points/my-profile/", "My Points")
    test_protected_endpoint("/api/v1/gamification/achievements/", "Achievements")
    
    print("\n🔔 Testing Notification Endpoints...")
    test_protected_endpoint("/api/v1/notifications/", "List Notifications")
    test_protected_endpoint("/api/v1/notifications/unread-count/", "Unread Count")
    
    print("\n💬 Testing Messaging Endpoints...")
    test_protected_endpoint("/api/v1/messaging/conversations/", "Conversations")
    
    print("\n📊 Testing Analytics Endpoints...")
    test_protected_endpoint("/api/v1/analytics/dashboard/", "Analytics Dashboard")
    test_protected_endpoint("/api/v1/analytics/stats/", "Platform Stats")
    
    print("\n🤝 Testing Collaboration Endpoints...")
    test_protected_endpoint("/api/v1/collaboration/", "Collaborations")
    test_protected_endpoint("/api/v1/collaboration/discover/", "Discover Collaborations")
    
    print("\n✅ API Testing Completed!")

if __name__ == "__main__":
    run_api_tests()
