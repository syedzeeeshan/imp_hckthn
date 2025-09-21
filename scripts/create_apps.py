#!/usr/bin/env python
"""
Script to create all Django apps for Campus Club Management Suite
Windows-compatible version with better error handling
"""
import os
import sys
import subprocess
import shutil
import time
from pathlib import Path

def safe_move_directory(source, target, retries=3):
    """Safely move directory with retries for Windows"""
    for attempt in range(retries):
        try:
            if target.exists():
                shutil.rmtree(target)
            shutil.move(str(source), str(target))
            return True
        except PermissionError as e:
            if attempt < retries - 1:
                print(f"  ⚠️  Permission error, retrying in 2 seconds... (attempt {attempt + 1})")
                time.sleep(2)
                continue
            else:
                print(f"  ❌ Failed after {retries} attempts: {e}")
                return False
        except Exception as e:
            print(f"  ❌ Unexpected error: {e}")
            return False
    return False

def create_django_apps():
    """Create all required Django applications"""
    
    # Check if we're in the right directory
    if not Path('manage.py').exists():
        print("❌ Error: manage.py not found!")
        print("Please run this script from the project root directory.")
        return False
    
    apps = [
        'authentication',
        'clubs', 
        'events',
        'analytics',
        'collaboration',
        'notifications',
        'gamification',
        'messaging',
        'common'
    ]
    
    print("🚀 Creating Django applications for Campus Club Management Suite...")
    print(f"📍 Working directory: {os.getcwd()}")
    
    # Create apps directory
    apps_dir = Path('apps')
    apps_dir.mkdir(exist_ok=True)
    print(f"✓ Created/verified apps directory")
    
    successful_apps = []
    failed_apps = []
    
    for app in apps:
        print(f"\n📱 Creating {app} app...")
        
        try:
            # Create the app
            result = subprocess.run([sys.executable, 'manage.py', 'startapp', app], 
                                  check=True, capture_output=True, text=True)
            
            # Check if app was created
            app_path = Path(app)
            target_path = apps_dir / app
            
            if app_path.exists():
                # Try to move the app
                print(f"  📁 Moving {app} to apps/ directory...")
                
                if safe_move_directory(app_path, target_path):
                    # Update apps.py
                    apps_py_file = target_path / 'apps.py'
                    if apps_py_file.exists():
                        content = apps_py_file.read_text()
                        content = content.replace(f"name = '{app}'", f"name = 'apps.{app}'")
                        apps_py_file.write_text(content)
                        print(f"  ✓ {app} app created successfully")
                        successful_apps.append(app)
                    else:
                        print(f"  ⚠️  {app} moved but apps.py not found")
                        successful_apps.append(app)
                else:
                    print(f"  ❌ Failed to move {app} app")
                    failed_apps.append(app)
            else:
                print(f"  ❌ {app} app directory not created")
                failed_apps.append(app)
                
        except subprocess.CalledProcessError as e:
            print(f"  ❌ Failed to create {app} app: {e}")
            failed_apps.append(app)
        except Exception as e:
            print(f"  ❌ Unexpected error with {app}: {e}")
            failed_apps.append(app)
    
    # Summary
    print(f"\n{'='*60}")
    print(f"📊 SUMMARY")
    print(f"{'='*60}")
    print(f"✅ Successfully created: {len(successful_apps)} apps")
    for app in successful_apps:
        print(f"   ✓ apps.{app}")
    
    if failed_apps:
        print(f"\n❌ Failed to create: {len(failed_apps)} apps")
        for app in failed_apps:
            print(f"   ✗ {app}")
    
    if successful_apps:
        print(f"\n📝 Add these to INSTALLED_APPS in settings.py:")
        for app in successful_apps:
            print(f"   'apps.{app}',")
    
    return len(failed_apps) == 0

if __name__ == '__main__':
    success = create_django_apps()
    if not success:
        print(f"\n💡 TIP: Try running as Administrator or create remaining apps manually")
    print(f"\n🎯 Next: python manage.py makemigrations")
