import sys
import select
from core.models.models import CapabilityRequest, GrantType
from typing import Tuple, Optional

class CLIDialog:
    def ask_approval(self, request: CapabilityRequest, timeout: int = 60) -> Tuple[bool, GrantType, int]:
        """
        Returns (approved, grant_type, duration_seconds)
        """
        bg_tag = "[BACKGROUND] " if request.background else ""
        print("\n" + "="*40)
        print(f"{bg_tag}R.U.D.I. CAPABILITY REQUEST")
        print(f"Agent:   {request.agent_id}")
        print(f"Action:  {request.capability}")
        print(f"Scope:   {request.scope}")
        print(f"Purpose: {request.purpose}")
        print("="*40)
        
        print(f"Options (Timeout in {timeout}s):")
        print(" [1] Allow Once (Default)")
        print(" [2] Time-Boxed (Specify seconds)")
        print(" [3] Session (until agent restarts or timeout)")
        print(" [4] PERMANENT (Requires extra confirmation)")
        print(" [n] Deny")
        
        print("\nSelect an option [1-4, n]: ", end="", flush=True)
        
        rlist, _, _ = select.select([sys.stdin], [], [], timeout)
        
        if rlist:
            choice = sys.stdin.readline().strip().lower()
        else:
            print(f"\n[Timeout] User unreachable after {timeout}s. Automatically DENYING.")
            return False, GrantType.ALLOW_ONCE, 0
        
        if choice == '1' or choice == '':
            return True, GrantType.ALLOW_ONCE, 0
        elif choice == '2':
            try:
                print("Duration in seconds: ", end="", flush=True)
                rlist, _, _ = select.select([sys.stdin], [], [], 10)
                if rlist:
                    seconds = int(sys.stdin.readline().strip())
                    return True, GrantType.TIME_BOXED, seconds
                else:
                    print("\n[Timeout] Defaulting to Allow Once.")
                    return True, GrantType.ALLOW_ONCE, 0
            except ValueError:
                print("Invalid duration. Defaulting to Allow Once.")
                return True, GrantType.ALLOW_ONCE, 0
        elif choice == '3':
            return True, GrantType.SESSION, 3600
        elif choice == '4':
            print("\n!!! WARNING: PERMANENT GRANT REQUESTED !!!")
            print("This grant will never expire and can only be removed manually.")
            print("Type 'CONFIRM' to approve: ", end="", flush=True)
            rlist, _, _ = select.select([sys.stdin], [], [], 15)
            if rlist:
                confirm = sys.stdin.readline().strip().upper()
                if confirm == "CONFIRM":
                    return True, GrantType.PERMANENT, 0
            print("Permanent grant NOT confirmed. Denying.")
            return False, GrantType.ALLOW_ONCE, 0
        else:
            return False, GrantType.ALLOW_ONCE, 0

    def show_active_grants(self, grants):
        print("\n" + "-"*40)
        print("ACTIVE GRANTS")
        for g in grants:
            expiry = f"Expires: {g.expires_at}" if g.expires_at else "No expiry (PERMANENT)"
            print(f"ID: {g.id[:8]} | {g.capability} | {expiry}")
        print("-"*40)
