from config import settings


def main() -> None:
    print("crypto trading data miner")
    print(f"env={settings.app_env} db={settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}")


if __name__ == "__main__":
    main()
