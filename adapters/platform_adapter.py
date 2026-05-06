import platform
from core.control_plane.manager import ControlPlaneManager

def get_platform_adapter(control_plane):
    os_name = platform.system().lower()
    if os_name == "darwin":
        from platforms.darwin.fs_enforcement import DarwinFilesystemEnforcement
        from platforms.darwin.net_enforcement import DarwinNetworkEnforcement
        from platforms.darwin.process_enforcement import DarwinProcessEnforcement
        return {
            "fs": DarwinFilesystemEnforcement(control_plane),
            "net": DarwinNetworkEnforcement(control_plane),
            "proc": DarwinProcessEnforcement(control_plane)
        }
    elif os_name == "linux":
        from platforms.linux.fs_enforcement import LinuxFilesystemEnforcement
        from platforms.linux.net_enforcement import LinuxNetworkEnforcement
        from platforms.linux.process_enforcement import LinuxProcessEnforcement
        return {
            "fs": LinuxFilesystemEnforcement(control_plane),
            "net": LinuxNetworkEnforcement(control_plane),
            "proc": LinuxProcessEnforcement(control_plane)
        }
    else:
        raise NotImplementedError(f"Platform {os_name} not supported")
