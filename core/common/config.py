import yaml
import os

class ConfigLoader:
    @staticmethod
    def load(config_path: str = "rudi-config.yaml") -> dict:
        if not os.path.exists(config_path):
            return {
                "default_deny": True,
                "approval_timeout": 60,
                "log_level": "INFO",
                "enforcement_strict": True
            }
        
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
