"""Customer membership and avatar actions; never turn points into wallet money."""

from cyberhub_manager.domain.exceptions import ValidationError, NotFoundError
from .avatar import normalize_avatar


class PortalMembershipMixin:
    def member(self, principal, page=1):
        if type(page) is not int or not 1 <= page <= 1_000_000:
            raise ValidationError(field_errors={"page": "Trang không hợp lệ"})
        with self._errors(), self._transaction() as conn:
            principal = self._principal(conn, principal)
            return dict(
                **self._repo.loyalty_summary(conn, principal.customer_id),
                history=self._repo.loyalty_history(conn, principal.customer_id, page),
            )

    def avatar(self, principal):
        with self._errors(), self._transaction() as conn:
            principal = self._principal(conn, principal)
            image = self._repo.avatar_image(conn, principal.account_id)
            if image is None:
                raise NotFoundError()
            return image

    def update_avatar(self, principal, content):
        # Revalidate before decoding as well as before the write.
        self.validate(principal)
        data, digest = normalize_avatar(content)
        with self._errors(), self._transaction() as conn:
            principal = self._principal(conn, principal)
            self._repo.save_avatar(conn, principal.account_id, data, digest)
        return dict(avatar_version=digest)

    def remove_avatar(self, principal):
        with self._errors(), self._transaction() as conn:
            principal = self._principal(conn, principal)
            self._repo.delete_avatar(conn, principal.account_id)
        return dict(avatar_version=None)
