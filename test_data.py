#!/usr/bin/env python
"""
Test data creation script for Campus Club Management Suite
Run this to populate your database with sample data for testing
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
django.setup()

from django.utils import timezone
from datetime import timedelta, datetime
from apps.authentication.models import User, College, UserProfile
from apps.clubs.models import Club, ClubCategory, ClubMembership, ClubAnnouncement
from apps.events.models import Event, EventRegistration
from apps.notifications.utils import create_default_notification_types
from apps.gamification.utils import create_default_badges, create_default_achievements
from apps.gamification.models import UserPoints

def create_test_data():
    """Create comprehensive test data"""
    
    print("🚀 Creating test data for Campus Club Management Suite...")
    
    # 1. Create Colleges (Already done)
    print("📚 Getting colleges...")
    colleges = list(College.objects.all())
    print(f"   ✅ Found {len(colleges)} colleges")
    
    # 2. Create Club Categories (Already done)
    print("🏷️ Getting club categories...")
    categories = list(ClubCategory.objects.all())
    print(f"   ✅ Found {len(categories)} categories")
    
    # 3. Get Test Users (Already created)
    print("👥 Getting test users...")
    users = list(User.objects.filter(email__in=[
        'student1@stanford.edu',
        'student2@mit.edu', 
        'faculty1@harvard.edu',
        'admin@berkeley.edu',
        'student3@stanford.edu'
    ]))
    print(f"   ✅ Found {len(users)} test users")
    
    # 4. Create Clubs with all required fields
    print("🎯 Creating clubs...")
    clubs = []
    
    if len(colleges) > 0 and len(users) > 0 and len(categories) > 0:
        club_data = [
            {
                "name": "Tech Innovation Club",
                "description": "A club for students passionate about technology and innovation",
                "short_description": "Tech enthusiasts unite!",
                "category": categories[0] if len(categories) > 0 else None,
                "college": colleges[0],  # Required field
                "created_by": users[0],  # Required field
                "status": "active",
                "privacy": "public",
                "is_active": True,
                "is_verified": True,
                "requires_approval": False,
                "max_members": 100,
                "email": "tech@stanford.edu",
                "website": "https://tech.stanford.edu",
                "meeting_location": "Tech Building Room 101",
                "meeting_schedule": "Every Tuesday 6 PM"
            },
            {
                "name": "Football Club",
                "description": "University football team and sports enthusiasts",
                "short_description": "Football team and fans",
                "category": categories[1] if len(categories) > 1 else categories[0],
                "college": colleges[1] if len(colleges) > 1 else colleges[0],
                "created_by": users[1] if len(users) > 1 else users[0],
                "status": "active",
                "privacy": "public", 
                "is_active": True,
                "is_verified": True,
                "requires_approval": True,
                "max_members": 50,
                "email": "football@mit.edu",
                "meeting_location": "Sports Complex",
                "meeting_schedule": "Monday, Wednesday, Friday 4 PM"
            },
            {
                "name": "Art & Design Society",
                "description": "Creative minds exploring art and design",
                "short_description": "Creative arts community",
                "category": categories[2] if len(categories) > 2 else categories[0],
                "college": colleges[2] if len(colleges) > 2 else colleges[0],
                "created_by": users[2] if len(users) > 2 else users[0],
                "status": "active",
                "privacy": "public",
                "is_active": True,
                "is_verified": True,
                "requires_approval": False,
                "max_members": 75,
                "email": "art@harvard.edu",
                "meeting_location": "Art Studio",
                "meeting_schedule": "Thursday 7 PM"
            },
        ]
        
        for club_info in club_data:
            try:
                club, created = Club.objects.get_or_create(
                    name=club_info['name'],
                    defaults=club_info
                )
                clubs.append(club)
                if created:
                    print(f"   ✅ Created club: {club.name}")
                    
                    # Create founder membership
                    membership, mem_created = ClubMembership.objects.get_or_create(
                        club=club,
                        user=club_info['created_by'],
                        defaults={
                            'status': 'active',
                            'role': 'founder'
                        }
                    )
                    if mem_created:
                        print(f"      👑 Made {club_info['created_by'].full_name} founder of {club.name}")
                        
            except Exception as e:
                print(f"   ⚠️ Could not create club {club_info['name']}: {e}")
    
    # 5. Create Club Memberships
    print("🤝 Creating club memberships...")
    if len(clubs) > 0 and len(users) > 3:
        membership_data = [
            {"club": clubs[0], "user": users[1], "role": "member"},
            {"club": clubs[0], "user": users[4] if len(users) > 4 else users[3], "role": "leader"},
            {"club": clubs[1] if len(clubs) > 1 else clubs[0], "user": users[0], "role": "member"},
        ]
        
        for membership_info in membership_data:
            try:
                membership, created = ClubMembership.objects.get_or_create(
                    club=membership_info['club'],
                    user=membership_info['user'],
                    defaults={
                        'status': 'active',
                        'role': membership_info['role'],
                    }
                )
                if created:
                    print(f"   ✅ Added {membership.user.full_name} to {membership.club.name}")
            except Exception as e:
                print(f"   ⚠️ Could not create membership: {e}")
    
    # 6. Create Events
    print("📅 Creating events...")
    events = []
    now = timezone.now()
    
    if len(clubs) > 0 and len(users) > 0:
        # Check Event model fields first
        from apps.events.models import Event
        event_fields = [f.name for f in Event._meta.get_fields()]
        print(f"   📋 Event fields: {event_fields}")
        
        event_data = [
            {
                "title": "Tech Workshop: AI & Machine Learning",
                "description": "Hands-on workshop about AI and ML fundamentals",
                "start_datetime": now + timedelta(days=7),
                "end_datetime": now + timedelta(days=7, hours=3),
                "location": "Tech Lab 101",
                "max_attendees": 50,
                "organizer": clubs[0],
                "created_by": users[0],
                "status": "published"
            },
            {
                "title": "Football Tournament",
                "description": "Annual inter-college football championship", 
                "start_datetime": now + timedelta(days=14),
                "end_datetime": now + timedelta(days=16),
                "location": "Sports Complex",
                "max_attendees": 200,
                "organizer": clubs[1] if len(clubs) > 1 else clubs[0],
                "created_by": users[1] if len(users) > 1 else users[0],
                "status": "published"
            },
        ]
        
        for event_info in event_data:
            try:
                # Only include fields that exist in the model
                filtered_event_info = {}
                for key, value in event_info.items():
                    if key in event_fields or key in ['title', 'description', 'start_datetime', 'end_datetime', 'location']:
                        filtered_event_info[key] = value
                
                event, created = Event.objects.get_or_create(
                    title=filtered_event_info['title'],
                    defaults=filtered_event_info
                )
                events.append(event)
                if created:
                    print(f"   ✅ Created event: {event.title}")
            except Exception as e:
                print(f"   ⚠️ Could not create event: {e}")
    
    # 7. Create Event Registrations
    if len(events) > 0 and len(users) > 1:
        print("🎫 Creating event registrations...")
        registration_data = [
            {"event": events[0], "user": users[1] if len(users) > 1 else users[0]},
            {"event": events[0], "user": users[2] if len(users) > 2 else users[0]}, 
        ]
        
        for reg_info in registration_data:
            try:
                registration, created = EventRegistration.objects.get_or_create(
                    event=reg_info['event'],
                    user=reg_info['user'],
                    defaults={'status': 'registered'}
                )
                if created:
                    print(f"   ✅ Registered {registration.user.full_name} for {registration.event.title}")
            except Exception as e:
                print(f"   ⚠️ Could not create registration: {e}")
    
    # 8. Create Club Announcements
    if len(clubs) > 0 and len(users) > 0:
        print("📢 Creating club announcements...")
        for i, club in enumerate(clubs[:2]):  # Only first 2 clubs
            try:
                announcement, created = ClubAnnouncement.objects.get_or_create(
                    club=club,
                    title=f"Welcome to {club.name}!",
                    defaults={
                        "author": users[i] if i < len(users) else users[0],
                        "content": f"We're excited to have you join {club.name}! Check out our upcoming events.",
                        "priority": "normal",
                        "is_published": True
                    }
                )
                if created:
                    print(f"   ✅ Created announcement for {club.name}")
            except Exception as e:
                print(f"   ⚠️ Could not create announcement: {e}")
    
    # 9. Initialize Gamification
    print("🎮 Setting up gamification...")
    try:
        create_default_notification_types()
        print("   ✅ Created notification types")
    except Exception as e:
        print(f"   ⚠️ Notification types: {e}")
    
    try:
        create_default_badges()
        print("   ✅ Created badges")
    except Exception as e:
        print(f"   ⚠️ Badges: {e}")
    
    try:
        create_default_achievements()
        print("   ✅ Created achievements")
    except Exception as e:
        print(f"   ⚠️ Achievements: {e}")
    
    # 10. Give users some points
    print("⭐ Adding user points...")
    for i, user in enumerate(users):
        try:
            user_points, created = UserPoints.objects.get_or_create(
                user=user,
                defaults={
                    'total_points': 100 + (i * 50),
                    'activity_points': 50,
                    'social_points': 25,
                    'leadership_points': 15,
                    'academic_points': 10,
                }
            )
            if created:
                print(f"   ✅ Added points for {user.full_name}")
        except Exception as e:
            print(f"   ⚠️ Could not add points for {user.full_name}: {e}")
    
    print("\n🎉 Test data creation completed!")
    print("\n📊 Summary:")
    print(f"   • {College.objects.count()} Colleges")
    print(f"   • {User.objects.count()} Users")
    print(f"   • {Club.objects.count()} Clubs") 
    print(f"   • {Event.objects.count()} Events")
    print(f"   • {ClubMembership.objects.count()} Club Memberships")
    print(f"   • {EventRegistration.objects.count()} Event Registrations")
    print(f"   • {ClubAnnouncement.objects.count()} Club Announcements")
    
    # Test data verification
    print("\n🔍 Data Verification:")
    for club in Club.objects.all()[:3]:
        member_count = club.memberships.count()
        print(f"   📋 {club.name}: {member_count} members, College: {club.college.name}")
    
    for event in Event.objects.all()[:3]:
        registration_count = event.registrations.count() if hasattr(event, 'registrations') else 0
        print(f"   🎫 {event.title}: {registration_count} registrations")

if __name__ == "__main__":
    create_test_data()
