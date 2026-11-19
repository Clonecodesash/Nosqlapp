"""Change the role of an existing account from the command line.

Usage (from the infra folder, with the app running):

    docker compose exec backend python make_teacher.py <username>
    docker compose exec backend python make_teacher.py <username> --student

The first form promotes the user to teacher; --student demotes them back.
The user must log out and in again for the interface to show the new role
(the backend already uses the new role on the next request).
"""

import asyncio
import sys

from sqlalchemy.future import select

from database import AsyncSessionLocal, engine
from models import User, UserRole


async def set_role(username: str, role: UserRole) -> int:
    try:
        return await _set_role(username, role)
    finally:
        # Close the connection pool in the same event loop that opened it.
        await engine.dispose()


async def _set_role(username: str, role: UserRole) -> int:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.username == username))
        user = result.scalars().first()
        if user is None:
            print(f"No user named '{username}'.")
            return 1
        if user.role == role:
            print(f"'{username}' is already a {role.value}.")
            return 0
        user.role = role
        await db.commit()
        print(f"'{username}' is now a {role.value}. They must log out and in again.")
        return 0


def main() -> int:
    args = sys.argv[1:]
    if not args or args[0].startswith("-"):
        print(__doc__)
        return 2
    role = UserRole.student if "--student" in args[1:] else UserRole.teacher
    return asyncio.run(set_role(args[0], role))


if __name__ == "__main__":
    sys.exit(main())
