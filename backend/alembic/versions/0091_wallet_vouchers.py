"""Convert fixed vouchers to one-time personal wallet credits."""

from alembic import op


revision = "0091_wallet_vouchers"
down_revision = "0090_remove_legacy_need_setup_status"
branch_labels = None
depends_on = None


def upgrade():
    # Percentage codes are retired. Preserve already redeemed fixed vouchers by
    # moving their value to the redeemer's personal USD wallet.
    op.execute(
        """
        DELETE FROM billing.discount_redemptions r
        USING billing.discount_cards c
        WHERE r.card_id = c.id AND c.discount_type <> 'fixed'
        """
    )
    op.execute("DELETE FROM billing.discount_cards WHERE discount_type <> 'fixed'")
    op.execute(
        """
        INSERT INTO billing.wallets (id, discord_user_id, balance, currency, created_at, updated_at)
        SELECT gen_random_uuid(), u.discord_user_id, 0, 'USD', now(), now()
        FROM billing.discount_redemptions r
        JOIN billing.discount_cards c ON c.id = r.card_id AND c.discount_type = 'fixed'
        JOIN core.users u ON u.id = r.redeemed_by_user_id
        WHERE u.discord_user_id IS NOT NULL
        GROUP BY u.discord_user_id
        ON CONFLICT (discord_user_id, currency) DO NOTHING
        """
    )
    op.execute(
        """
        WITH credits AS (
            SELECT u.discord_user_id, sum(c.amount_usd) AS amount
            FROM billing.discount_redemptions r
            JOIN billing.discount_cards c ON c.id = r.card_id AND c.discount_type = 'fixed'
            JOIN core.users u ON u.id = r.redeemed_by_user_id
            WHERE u.discord_user_id IS NOT NULL AND c.amount_usd IS NOT NULL
            GROUP BY u.discord_user_id
        )
        UPDATE billing.wallets w
        SET balance = w.balance + credits.amount, updated_at = now()
        FROM credits
        WHERE w.discord_user_id = credits.discord_user_id AND w.currency = 'USD'
        """
    )
    op.execute(
        """
        WITH credits AS (
            SELECT u.discord_user_id, sum(c.amount_usd) AS amount
            FROM billing.discount_redemptions r
            JOIN billing.discount_cards c ON c.id = r.card_id AND c.discount_type = 'fixed'
            JOIN core.users u ON u.id = r.redeemed_by_user_id
            WHERE u.discord_user_id IS NOT NULL AND c.amount_usd IS NOT NULL
            GROUP BY u.discord_user_id
        )
        INSERT INTO billing.wallet_transactions
            (id, wallet_id, amount, balance_after, operation, comment, created_at)
        SELECT gen_random_uuid(), w.id, credits.amount, w.balance,
               'voucher_credit', 'Migrated fixed voucher', now()
        FROM credits
        JOIN billing.wallets w
          ON w.discord_user_id = credits.discord_user_id AND w.currency = 'USD'
        """
    )
    op.drop_constraint(
        "uq_billing_discount_redemption_card_guild",
        "discount_redemptions",
        schema="billing",
        type_="unique",
    )
    op.drop_constraint(
        "fk_discount_redemptions_guild_id_guilds",
        "discount_redemptions",
        schema="billing",
        type_="foreignkey",
    )
    op.alter_column("discount_redemptions", "guild_id", schema="billing", nullable=True)
    op.create_foreign_key(
        "fk_discount_redemptions_guild_id_guilds",
        "discount_redemptions",
        "guilds",
        ["guild_id"],
        ["guild_id"],
        source_schema="billing",
        referent_schema="discord",
        ondelete="SET NULL",
    )
    op.execute("DELETE FROM billing.discount_redemptions WHERE redeemed_by_user_id IS NULL")
    op.execute("UPDATE billing.discount_redemptions SET guild_id = NULL")
    op.create_unique_constraint(
        "uq_billing_voucher_redemption_user",
        "discount_redemptions",
        ["card_id", "redeemed_by_user_id"],
        schema="billing",
    )
    op.drop_column("discount_cards", "percent", schema="billing")
    op.drop_column("discount_cards", "discount_type", schema="billing")


def downgrade():
    raise RuntimeError("Wallet voucher migration is irreversible")
