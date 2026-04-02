from config import settings


def main() -> None:
    print("crypto trading data miner")
    print(f"env={settings.app_env} db={settings.resolved_database_url}")


if __name__ == "__main__":
    main()
