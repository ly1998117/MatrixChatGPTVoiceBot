from simplematrixbotlib import Config
from os import environ


class FileConfig(Config):
    keys = ["HOMESERVER", "USERNAME", "PASSWORD", "LOGIN_TOKEN",
            "ACCESS_TOKEN", "OPEN_AI_KEY", "REPLICATE_API_TOKEN", "ENABLE_ENCRYPTION"]

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

    def _set_attr(self, key, value):
        print(f"Setting {key} to {value}")
        setattr(self, key, value)

    def _enable_encryption(self):
        self.encryption_enabled = True
        self.emoji_verify = True
        self.ignore_unverified_devices = True
        self.store_path = './crypto_store/'

    def _load_env_dict(self):
        for key in self.keys:
            if key.upper() in environ.keys():
                self._set_attr(key.upper(), environ[key.upper()])
            if key.lower() in environ.keys():
                self._set_attr(key.upper(), environ[key.lower()])

    def _load_config_dict(self, config_dict: dict) -> None:
        for key, value in config_dict.items():
            key = key.upper()
            if hasattr(self, key) and getattr(self, key) is not None:
                continue
            if value == 'True' or value == 'true':
                value = True
            elif value == 'False' or value == 'false':
                value = False

            self._set_attr(key, value)
