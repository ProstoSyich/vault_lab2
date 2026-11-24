import argparse
import sys
from pathlib import Path

# Позволяет запускать скрипт как `python scripts/make_admin.py` из корня проекта.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.db.session import SessionLocal  # noqa: E402
from app.models.user import User  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Выдать пользователю Vault права администратора")
    parser.add_argument("--email", required=True, help="Email зарегистрированного пользователя")
    args = parser.parse_args()

    email = args.email.strip().lower()
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            print(f"Пользователь {email} не найден", file=sys.stderr)
            return 1

        user.is_admin = True
        user.is_active = True
        db.commit()

    print(f"Пользователь {email} теперь администратор")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
