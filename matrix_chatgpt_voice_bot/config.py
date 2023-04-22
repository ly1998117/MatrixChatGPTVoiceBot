from simplematrixbotlib import Config
from os import environ


class FileConfig(Config):
    keys = ["homeserver", "username", "password", "login_token",
            "access_token", "OPEN_AI_KEY", "REPLICATE_API_TOKEN", "ENABLE_ENCRYPTION"]

    def __init__(self, config_path):
        super().__init__()
        if "CONFIG_PATH" in environ.keys():
            config_path = environ["CONFIG_PATH"]
        if config_path is None:
            config_path = "config/config.yml"
        self._load_env_dict()
        self.load_toml(config_path)
        if hasattr(self, "ENABLE_ENCRYPTION") and self.ENABLE_ENCRYPTION:
            self._enable_encryption()

    def _enable_encryption(self):
        self.encryption_enabled = True
        self.emoji_verify = True
        self.ignore_unverified_devices = True
        self.store_path = './crypto_store/'

    def _load_env_dict(self):
        for key in self.keys:
            if key in environ.keys():
                setattr(self, key.upper(), environ[key])

    def _load_config_dict(self, config_dict: dict) -> None:
        for key, value in config_dict.items():
            key = key.upper()
            if hasattr(self, key) and getattr(self, key) is not None:
                continue
            if value == 'True' or value == 'true':
                value = True
            elif value == 'False' or value == 'false':
                value = False

            setattr(self, key, value)
