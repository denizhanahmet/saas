import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


from datetime import datetime
from firebase_realtime import get_data, set_data
from firebase_realtime_transaction import atomic_update

def backfill_created_at():
    users = get_data('users') or {}
    updated = 0
    for user_id, user in users.items():
        if not user.get('created_at'):
            # Use kvkk_accepted_at if available, else set to now
            created_at = user.get('kvkk_accepted_at')
            try:
                # Try to parse kvkk_accepted_at to ISO if possible
                if created_at:
                    dt = datetime.fromisoformat(created_at)
                    created_at = dt.isoformat()
                else:
                    created_at = datetime.utcnow().isoformat()
            except Exception:
                created_at = datetime.utcnow().isoformat()
            def updater(current):
                if not current:
                    return user
                current['created_at'] = created_at
                return current
            atomic_update(f'users/{user_id}', updater)
            updated += 1
    print(f"Updated {updated} users with missing created_at.")

if __name__ == "__main__":
    backfill_created_at()
