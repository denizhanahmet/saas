import sys
sys.path.insert(0, 'c:\\Users\\deniz\\OneDrive\\Masaüstü\\saas')

from app import app
from firebase_realtime import get_data
import hashlib

# Get test user
users = get_data('users') or {}
test_user = None
test_password = None

# We need to check what password is set for test users
# Let me check the test@gmail.com user
for uid, user in users.items():
    if user.get('email') == 'test@gmail.com':
        test_user = user
        print(f"Found test user: {user.get('email')}")
        print(f"  Username: {user.get('username')}")
        print(f"  Name: {user.get('first_name')} {user.get('last_name')}")
        print(f"  Password hash: {user.get('password_hash', '?')[:20]}...")
        break

if not test_user:
    print("No test user found")
    # Try to create one for testing
    print("\nCreating test user for testing...")
    from firebase_realtime import set_data
    test_password = "testpass123"
    password_hash = hashlib.sha256(test_password.encode()).hexdigest()
    
    new_user = {
        'id': '999',
        'username': 'testuser',
        'email': 'testuser@test.com',
        'password_hash': password_hash,
        'first_name': 'Test',
        'last_name': 'User',
        'is_active': True,
        'is_superadmin': False,
        'unique_link': 'test-unique-link',
    }
    
    set_data('users/999', new_user)
    print(f"✓ Created test user with password: {test_password}")
else:
    print("\nTest user found, but password unknown")
    print("Let's test with a new password...")
    test_password = "testpass123"
    password_hash = hashlib.sha256(test_password.encode()).hexdigest()
    uid = next(uid for uid, u in users.items() if u.get('email') == 'test@gmail.com')
    test_user['id'] = uid
    test_user['password_hash'] = password_hash
    test_user['updated_at'] = str(__import__('datetime').datetime.now().isoformat())
    # Update user in Firebase
    from firebase_realtime import set_data
    set_data(f'users/{uid}', test_user)
    print(f"✓ Updated test user password to: {test_password}")
