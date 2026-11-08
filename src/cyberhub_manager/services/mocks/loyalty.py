"""Demo adapter shares the same invoice award and membership functions as MySQL."""

from cyberhub_manager.domain.loyalty import membership, invoice_award


class MemoryLoyaltyRepositoryMixin:
    def loyalty_settings(self, conn, lock=False):
        return self.data.loyalty_settings

    def save_loyalty_settings(self, conn, settings):
        self.data.loyalty_settings = settings

    def _award(self, invoice):
        return self.data.invoice_loyalty.get(
            invoice.id,
            dict(eligible_amount=0, points=0, unit_amount=10000, rule_version=1),
        )

    def loyalty_summary(self, conn, customer_id):
        awards = [
            self._award(i)
            for i in self.data.invoices.values()
            if i.customer_id == customer_id and str(i.status) == "PAID"
        ]
        return membership(
            sum(a["points"] for a in awards),
            sum(a["eligible_amount"] for a in awards),
            self.data.loyalty_settings,
        )

    def loyalty_history(self, conn, customer_id, page=1, page_size=10):
        invoices = sorted(
            [i for i in self.data.invoices.values() if i.customer_id == customer_id],
            key=lambda i: (i.created_at, i.id),
            reverse=True,
        )
        return dict(
            items=[
                dict(
                    id=i.id,
                    code=i.code,
                    status=str(i.status),
                    **self._award(i),
                    effective_points=(
                        self._award(i)["points"] if str(i.status) == "PAID" else 0
                    ),
                    created_at=i.created_at,
                    store_name=self.data.get_store(i.store_id).name,
                )
                for i in invoices[(page - 1) * page_size : page * page_size]
            ],
            total=len(invoices),
            page=page,
            page_size=page_size,
        )

    def target_customer_exists(self, conn, customer_id):
        return customer_id in self.data.customers

    def avatar_metadata(self, conn, account_id):
        value = self.avatars.get(account_id)
        return value["digest"] if value else None

    def avatar_image(self, conn, account_id):
        return self.avatars.get(account_id)

    def save_avatar(self, conn, account_id, image, digest):
        self.avatars[account_id] = dict(image_data=image, digest=digest)

    def delete_avatar(self, conn, account_id):
        self.avatars.pop(account_id, None)
