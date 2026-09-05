-- ============================================================================
--  RK TRENDZ MLM :: 0006 — WITHDRAWAL TDS / ADMIN-FEE DEDUCTIONS (proper books)
--  Idempotent. Safe on live & test data.
-- ----------------------------------------------------------------------------
--  When a member withdraws amount A:
--     TDS       = A * tds_rate        (tax withheld -> owed to government, LIABILITY)
--     Admin fee = A * admin_rate      (processing charge -> company INCOME)
--     Net paid  = A - TDS - admin fee (what is actually sent to the member)
--  The member's wallet is debited the GROSS amount A; the company retains the
--  fee (income) and holds the TDS (tax payable). This table records that split
--  per approved withdrawal so the financial report reads REAL booked figures.
--  Existing approved (test) withdrawals are back-filled using the current
--  configured rates.
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.withdrawal_deductions (
    id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    withdrawal_id    BIGINT NOT NULL REFERENCES public.withdraw_requests(id) ON DELETE CASCADE,
    user_id          BIGINT NOT NULL,
    gross_amount     NUMERIC(12,2) NOT NULL,
    tds_amount       NUMERIC(12,2) NOT NULL DEFAULT 0,
    admin_fee_amount NUMERIC(12,2) NOT NULL DEFAULT 0,
    net_payable      NUMERIC(12,2) NOT NULL,
    tds_rate         NUMERIC(5,2),
    admin_rate       NUMERIC(5,2),
    created_at       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (withdrawal_id)
);

CREATE INDEX IF NOT EXISTS idx_wd_user ON public.withdrawal_deductions (user_id);

-- Back-fill a deduction record for every APPROVED withdrawal that does not have
-- one yet, using the currently configured TDS / admin-fee percentages.
INSERT INTO public.withdrawal_deductions
    (withdrawal_id, user_id, gross_amount, tds_amount, admin_fee_amount,
     net_payable, tds_rate, admin_rate)
SELECT
    wr.id,
    wr.user_id,
    wr.amount,
    ROUND(wr.amount * tds.r  / 100, 2),
    ROUND(wr.amount * adm.r  / 100, 2),
    wr.amount
        - ROUND(wr.amount * tds.r / 100, 2)
        - ROUND(wr.amount * adm.r / 100, 2),
    tds.r, adm.r
FROM public.withdraw_requests wr
CROSS JOIN LATERAL (
    SELECT COALESCE((SELECT percentage_value FROM public.global_commissions
                     WHERE setting_key = 'tds_percentage'), 10) AS r
) tds
CROSS JOIN LATERAL (
    SELECT COALESCE((SELECT percentage_value FROM public.global_commissions
                     WHERE setting_key = 'admin_fee_percentage'), 10) AS r
) adm
WHERE LOWER(wr.status) = 'approved'
  AND NOT EXISTS (
      SELECT 1 FROM public.withdrawal_deductions d WHERE d.withdrawal_id = wr.id
  );

-- NOTE: fee income and TDS liability are NOT inserted into wallet_ledger.
-- That ledger tracks MEMBER money; the member is already debited the gross
-- amount on approval. The company's fee income / tax liability are read from
-- this withdrawal_deductions table by the financial report (adding them to the
-- member ledger would incorrectly increase spendable balances).

-- ===========================================================================
-- VERIFY:
--   SELECT COUNT(*), COALESCE(SUM(admin_fee_amount),0), COALESCE(SUM(tds_amount),0)
--   FROM withdrawal_deductions;
-- ===========================================================================
