"""Settings → Admin → Mail: the SMTP server, and a test message through it (ADR 27)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from hera_accounts import Accounts
from hera_core import letters
from hera_core.config import load as load_config
from hera_core.config import save as save_config
from hera_core.deps import Admin, AdminOnly, Container, Db
from hera_core.mail import MailError
from hera_core.schemas import MailOut, MailPatch

router = APIRouter(tags=["mail"])


@router.get("/mail", response_model=MailOut, dependencies=[AdminOnly])
def read_mail() -> MailOut:
    config = load_config()
    return MailOut.of(config.mail, public_url=config.instance.public_url)


@router.patch("/mail", response_model=MailOut, dependencies=[AdminOnly])
def write_mail(payload: MailPatch) -> MailOut:
    try:
        config = load_config().with_mail(**payload.model_dump(exclude_none=True))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from None
    save_config(config)
    return MailOut.of(config.mail, public_url=config.instance.public_url)


@router.post("/mail/test", status_code=status.HTTP_204_NO_CONTENT)
def send_test(admin: Admin, container: Container, db: Db) -> None:
    """A message to the admin asking, through the server as it is saved now. The mail server's
    own complaint is the answer when it fails, because that is what there is to fix."""
    config = load_config()
    user = Accounts(db).get(admin.id)
    if user is None:  # pragma: no cover - a signed-in admin has a row
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no such user")
    letter = letters.trial(to=user.email, instance=config.instance.name)
    try:
        container.mailer.send(config.mail, letter, sender_name=config.instance.name)
    except MailError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from None
