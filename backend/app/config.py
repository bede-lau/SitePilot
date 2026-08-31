from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite+aiosqlite:///./fieldbot.db"

    telegram_bot_token: str = ""

    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_vision_model: str = ""
    llm_text_model: str = ""

    # Outbound RFQ email (SMTP) + inbound quote intake (IMAP).
    # Leave SMTP unset to keep the procurement flow on the simulated-quote path.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""  # defaults to smtp_user if blank

    imap_host: str = ""
    imap_port: int = 993
    imap_user: str = ""  # defaults to smtp_user if blank
    imap_password: str = ""  # defaults to smtp_password if blank
    rfq_poll_seconds: int = 20
    rfq_batch_timeout_seconds: int = 120  # finalize a batch even if not every vendor replied

    # --- ElevenLabs voice (ARD §8 / D1). Empty key -> voice.py stub responses. ---
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = ""
    elevenlabs_stt_model: str = "scribe_v1"

    # Static FX rate used to normalise USD supplier quotes to MYR (ARD §5.4/§9).
    usd_myr_rate: float = 4.72

    frontend_base_url: str = "http://localhost:5173"
    # Identity of the demo user. With Telegram this is the numeric chat id (as a
    # string) of the account that messages the bot — set it so the seeded session
    # (which binds this id to the first project) matches your inbound chat.
    demo_phone_number: str = "0"

    @property
    def telegram_api_base(self) -> str:
        return f"https://api.telegram.org/bot{self.telegram_bot_token}"

    @property
    def telegram_file_base(self) -> str:
        return f"https://api.telegram.org/file/bot{self.telegram_bot_token}"

    @property
    def email_enabled(self) -> bool:
        """Real RFQ email loop is active only when SMTP send is configured."""
        return bool(self.smtp_host and self.smtp_user and self.smtp_password)

    @property
    def imap_enabled(self) -> bool:
        host = self.imap_host or ("imap.gmail.com" if "gmail" in self.smtp_host else "")
        return bool(host and (self.imap_user or self.smtp_user) and (self.imap_password or self.smtp_password))

    @property
    def effective_smtp_from(self) -> str:
        return self.smtp_from or self.smtp_user

    @property
    def effective_imap_host(self) -> str:
        return self.imap_host or ("imap.gmail.com" if "gmail" in self.smtp_host else "")

    @property
    def effective_imap_user(self) -> str:
        return self.imap_user or self.smtp_user

    @property
    def effective_imap_password(self) -> str:
        return self.imap_password or self.smtp_password

    @property
    def voice_enabled(self) -> bool:
        return bool(self.elevenlabs_api_key)


settings = Settings()
