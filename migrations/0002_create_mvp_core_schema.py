"""Create the minimum schema for the member purchase MVP."""

from yoyo import step


__depends__ = {"0001_create_company_settings"}


steps = [
    step(
        """
        CREATE TABLE roles (
            id SMALLINT PRIMARY KEY,
            name VARCHAR(32) NOT NULL UNIQUE
        );

        INSERT INTO roles (id, name) VALUES
            (1, 'admin'),
            (2, 'member');

        CREATE TABLE subscription_plans (
            id BIGSERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL UNIQUE,
            description TEXT,
            price NUMERIC(14, 2) NOT NULL CHECK (price > 0),
            currency CHAR(3) NOT NULL DEFAULT 'INR',
            lucky_draw_coupons INTEGER NOT NULL DEFAULT 0 CHECK (lucky_draw_coupons >= 0),
            direct_commission NUMERIC(7, 4) NOT NULL DEFAULT 0 CHECK (direct_commission BETWEEN 0 AND 100),
            level_commissions JSONB NOT NULL DEFAULT '{}'::jsonb,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            image_url TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE INDEX subscription_plans_active_price_idx
            ON subscription_plans (price)
            WHERE is_active;

        CREATE TABLE users (
            id BIGSERIAL PRIMARY KEY,
            role_id SMALLINT NOT NULL DEFAULT 2 REFERENCES roles(id),
            full_name VARCHAR(255) NOT NULL,
            email TEXT NOT NULL,
            phone VARCHAR(32) NOT NULL,
            password_hash TEXT NOT NULL,
            referral_code VARCHAR(32) NOT NULL,
            sponsor_id BIGINT REFERENCES users(id),
            package_id BIGINT REFERENCES subscription_plans(id),
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            activated_at TIMESTAMPTZ,
            kyc_status VARCHAR(24) NOT NULL DEFAULT 'pending',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT users_email_unique UNIQUE (email),
            CONSTRAINT users_phone_unique UNIQUE (phone),
            CONSTRAINT users_referral_code_unique UNIQUE (referral_code),
            CONSTRAINT users_kyc_status_check CHECK (kyc_status IN ('pending', 'approved', 'rejected'))
        );

        CREATE INDEX users_sponsor_id_idx ON users (sponsor_id);
        CREATE INDEX users_created_at_idx ON users (created_at DESC);

        CREATE TABLE kyc_details (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
            status VARCHAR(24) NOT NULL DEFAULT 'pending',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT kyc_details_status_check CHECK (status IN ('pending', 'approved', 'rejected'))
        );

        CREATE TABLE plan_images (
            id BIGSERIAL PRIMARY KEY,
            plan_id BIGINT NOT NULL REFERENCES subscription_plans(id) ON DELETE CASCADE,
            image_path TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE TABLE package_commission_rates (
            package_id BIGINT NOT NULL REFERENCES subscription_plans(id) ON DELETE CASCADE,
            level SMALLINT NOT NULL CHECK (level BETWEEN 0 AND 10),
            percentage NUMERIC(7, 4) NOT NULL CHECK (percentage BETWEEN 0 AND 100),
            PRIMARY KEY (package_id, level)
        );

        CREATE TABLE payment_orders (
            id UUID PRIMARY KEY,
            user_id BIGINT NOT NULL REFERENCES users(id),
            package_id BIGINT NOT NULL REFERENCES subscription_plans(id),
            amount NUMERIC(14, 2) NOT NULL CHECK (amount > 0),
            currency CHAR(3) NOT NULL,
            provider VARCHAR(32) NOT NULL,
            provider_order_id VARCHAR(128) UNIQUE,
            provider_payment_id VARCHAR(128) UNIQUE,
            status VARCHAR(24) NOT NULL,
            provider_payload JSONB,
            verified_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT payment_orders_status_check CHECK (status IN ('created', 'pending', 'verified', 'failed', 'refunded'))
        );

        CREATE INDEX payment_orders_user_created_idx ON payment_orders (user_id, created_at DESC);
        CREATE INDEX payment_orders_verified_idx ON payment_orders (created_at DESC) WHERE status = 'verified';

        CREATE TABLE user_packages (
            id BIGSERIAL PRIMARY KEY,
            payment_order_id UUID UNIQUE REFERENCES payment_orders(id),
            user_id BIGINT NOT NULL REFERENCES users(id),
            package_id BIGINT NOT NULL REFERENCES subscription_plans(id),
            amount NUMERIC(14, 2) NOT NULL CHECK (amount > 0),
            status VARCHAR(24) NOT NULL DEFAULT 'active',
            activated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT user_packages_status_check CHECK (status = 'active')
        );

        CREATE INDEX user_packages_user_created_idx ON user_packages (user_id, created_at DESC);

        CREATE TABLE commissions (
            id BIGSERIAL PRIMARY KEY,
            activation_id BIGINT REFERENCES user_packages(id),
            earner_id BIGINT NOT NULL REFERENCES users(id),
            from_user_id BIGINT NOT NULL REFERENCES users(id),
            level SMALLINT NOT NULL CHECK (level BETWEEN 0 AND 10),
            percentage NUMERIC(7, 4) NOT NULL CHECK (percentage BETWEEN 0 AND 100),
            amount NUMERIC(14, 2) NOT NULL CHECK (amount >= 0),
            commission_type VARCHAR(32) NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT commissions_activation_earner_level_type_unique
                UNIQUE NULLS NOT DISTINCT (activation_id, earner_id, level, commission_type)
        );

        CREATE INDEX commissions_earner_created_idx ON commissions (earner_id, created_at DESC);
        CREATE INDEX commissions_from_user_idx ON commissions (from_user_id);

        CREATE TABLE wallet_ledger (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL REFERENCES users(id),
            commission_id BIGINT UNIQUE REFERENCES commissions(id),
            amount NUMERIC(14, 2) NOT NULL CHECK (amount <> 0),
            transaction_type VARCHAR(32) NOT NULL,
            reference_id VARCHAR(160) NOT NULL UNIQUE,
            description TEXT,
            closing_balance NUMERIC(14, 2),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE INDEX wallet_ledger_user_created_idx ON wallet_ledger (user_id, created_at DESC);
        """,
        """
        DROP TABLE wallet_ledger;
        DROP TABLE commissions;
        DROP TABLE user_packages;
        DROP TABLE payment_orders;
        DROP TABLE package_commission_rates;
        DROP TABLE plan_images;
        DROP TABLE kyc_details;
        DROP TABLE users;
        DROP TABLE subscription_plans;
        DROP TABLE roles;
        """,
    )
]
