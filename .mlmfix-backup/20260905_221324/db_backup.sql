--
-- PostgreSQL database dump
--

\restrict Ug2wO60n5QDDfXyvoe8rNjPsZdbtKexamfaN1pq11yKWiG3UcyBrgvIr7RF4Qp0

-- Dumped from database version 15.19 (Debian 15.19-0+deb12u1)
-- Dumped by pg_dump version 15.19 (Debian 15.19-0+deb12u1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: ltree; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS ltree WITH SCHEMA public;


--
-- Name: EXTENSION ltree; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION ltree IS 'data type for hierarchical tree-like structures';


--
-- Name: pg_trgm; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA public;


--
-- Name: EXTENSION pg_trgm; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION pg_trgm IS 'text similarity measurement and index searching based on trigrams';


--
-- Name: activate_user_account(bigint); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.activate_user_account(p_user_id bigint) RETURNS void
    LANGUAGE plpgsql
    AS $$
BEGIN

    -- Activate user
    UPDATE users
    SET is_active = TRUE,
        activated_at = CURRENT_TIMESTAMP
    WHERE id = p_user_id
    AND is_active = FALSE;

    -- Distribute commission
    PERFORM distribute_activation_commission(p_user_id);

END;
$$;


ALTER FUNCTION public.activate_user_account(p_user_id bigint) OWNER TO postgres;

--
-- Name: after_user_insert_counters(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.after_user_insert_counters() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    -- +1 direct referral for the immediate sponsor
    IF NEW.sponsor_id IS NOT NULL THEN
        UPDATE public.users
           SET direct_count = direct_count + 1
         WHERE id = NEW.sponsor_id;
    END IF;

    -- +1 total team for EVERY ancestor (the whole upline chain), using ltree.
    -- NEW.tree_path <@ u.tree_path  => u is an ancestor of the new user.
    IF NEW.tree_path IS NOT NULL THEN
        UPDATE public.users u
           SET total_team_count = total_team_count + 1
         WHERE u.tree_path IS NOT NULL
           AND NEW.tree_path <@ u.tree_path
           AND u.id <> NEW.id;
    END IF;

    RETURN NEW;
END;
$$;


ALTER FUNCTION public.after_user_insert_counters() OWNER TO postgres;

--
-- Name: distribute_activation_commission(bigint); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.distribute_activation_commission(p_user_id bigint) RETURNS void
    LANGUAGE plpgsql
    AS $$
DECLARE
    current_sponsor BIGINT;
    current_level INTEGER := 1;
    max_level INTEGER := 10;
    commission_percent NUMERIC(5,2);
    commission_amount NUMERIC(12,2);
    joining_amount NUMERIC(12,2) := 3600;
    rows_inserted INTEGER;
BEGIN

    SELECT sponsor_id INTO current_sponsor
    FROM users
    WHERE id = p_user_id;

    WHILE current_sponsor IS NOT NULL AND current_level <= max_level LOOP

        SELECT percentage INTO commission_percent
        FROM commission_plan
        WHERE level = current_level;

        commission_amount := (joining_amount * commission_percent) / 100;

        INSERT INTO commissions (
            earner_id,
            from_user_id,
            level,
            amount,
            commission_type
        )
        VALUES (
            current_sponsor,
            p_user_id,
            current_level,
            commission_amount,
            'activation'
        )
        ON CONFLICT DO NOTHING;

        GET DIAGNOSTICS rows_inserted = ROW_COUNT;

        IF rows_inserted > 0 THEN
            INSERT INTO wallet_ledger (
                user_id,
                transaction_type,
                amount,
                reference_id,
                description
            )
            VALUES (
                current_sponsor,
                'credit',
                commission_amount,
                p_user_id,
                'Level ' || current_level || ' activation commission'
            );
        END IF;

        SELECT sponsor_id INTO current_sponsor
        FROM users
        WHERE id = current_sponsor;

        current_level := current_level + 1;

    END LOOP;

END;
$$;


ALTER FUNCTION public.distribute_activation_commission(p_user_id bigint) OWNER TO postgres;

--
-- Name: refresh_user_counters(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.refresh_user_counters() RETURNS void
    LANGUAGE plpgsql
    AS $$
BEGIN
    UPDATE public.users u SET
        direct_count = (
            SELECT COUNT(*) FROM public.users c WHERE c.sponsor_id = u.id
        ),
        total_team_count = (
            SELECT COUNT(*) FROM public.users d
            WHERE d.tree_path IS NOT NULL
              AND u.tree_path IS NOT NULL
              AND d.tree_path <@ u.tree_path
              AND d.id <> u.id
        );
END;
$$;


ALTER FUNCTION public.refresh_user_counters() OWNER TO postgres;

--
-- Name: sync_ledger_reference(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.sync_ledger_reference() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    IF NEW.reference IS NULL AND NEW.reference_id IS NOT NULL THEN
        NEW.reference := NEW.reference_id::text;
    ELSIF NEW.reference_id IS NULL AND NEW.reference IS NOT NULL THEN
        NEW.reference_id := NEW.reference;
    END IF;
    RETURN NEW;
END;
$$;


ALTER FUNCTION public.sync_ledger_reference() OWNER TO postgres;

--
-- Name: users_tree_maintenance(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.users_tree_maintenance() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF NEW.sponsor_id IS NULL THEN
            NEW.tree_path := text(NEW.id)::ltree;
        ELSE
            SELECT tree_path || NEW.id::text INTO NEW.tree_path
            FROM public.users WHERE id = NEW.sponsor_id;
        END IF;
        RETURN NEW;
    ELSIF TG_OP = 'UPDATE' THEN
        -- If the sponsor changed, re-root this whole subtree.
        IF NEW.sponsor_id IS DISTINCT FROM OLD.sponsor_id THEN
            IF NEW.sponsor_id IS NULL THEN
                NEW.tree_path := text(NEW.id)::ltree;
            ELSE
                SELECT tree_path || NEW.id::text INTO NEW.tree_path
                FROM public.users WHERE id = NEW.sponsor_id;
            END IF;
            -- Repath every descendant of this node.
            WITH RECURSIVE subtree AS (
                SELECT id, tree_path FROM public.users WHERE sponsor_id = NEW.id
                UNION ALL
                SELECT u.id, u.tree_path FROM public.users u
                JOIN subtree s ON u.sponsor_id = s.id
            )
            UPDATE public.users d
            SET tree_path = NEW.tree_path ||
                    subpath(d.tree_path, nlevel(NEW.tree_path) - 1)
            FROM subtree s
            WHERE d.id = s.id AND d.id <> NEW.id;
        END IF;
        RETURN NEW;
    END IF;
    RETURN NEW;
END;
$$;


ALTER FUNCTION public.users_tree_maintenance() OWNER TO postgres;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: _yoyo_log; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public._yoyo_log (
    id character varying(36) NOT NULL,
    migration_hash character varying(64),
    migration_id character varying(255),
    operation character varying(10),
    username character varying(255),
    hostname character varying(255),
    comment character varying(255),
    created_at_utc timestamp without time zone
);


ALTER TABLE public._yoyo_log OWNER TO postgres;

--
-- Name: _yoyo_migration; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public._yoyo_migration (
    migration_hash character varying(64) NOT NULL,
    migration_id character varying(255),
    applied_at_utc timestamp without time zone
);


ALTER TABLE public._yoyo_migration OWNER TO postgres;

--
-- Name: _yoyo_version; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public._yoyo_version (
    version integer NOT NULL,
    installed_at_utc timestamp without time zone
);


ALTER TABLE public._yoyo_version OWNER TO postgres;

--
-- Name: admin_activity_logs; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.admin_activity_logs (
    id integer NOT NULL,
    admin_id integer NOT NULL,
    action character varying(100) NOT NULL,
    target_user_id integer,
    description text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.admin_activity_logs OWNER TO postgres;

--
-- Name: admin_activity_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.admin_activity_logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.admin_activity_logs_id_seq OWNER TO postgres;

--
-- Name: admin_activity_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.admin_activity_logs_id_seq OWNED BY public.admin_activity_logs.id;


--
-- Name: admin_audit_logs; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.admin_audit_logs (
    id integer NOT NULL,
    admin_id integer,
    action character varying(50),
    target_user_id integer,
    amount numeric(12,2),
    remark text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.admin_audit_logs OWNER TO postgres;

--
-- Name: admin_audit_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.admin_audit_logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.admin_audit_logs_id_seq OWNER TO postgres;

--
-- Name: admin_audit_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.admin_audit_logs_id_seq OWNED BY public.admin_audit_logs.id;


--
-- Name: admin_logs; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.admin_logs (
    id integer NOT NULL,
    admin_id integer,
    action text,
    target_user_id integer,
    created_at timestamp without time zone,
    description text
);


ALTER TABLE public.admin_logs OWNER TO postgres;

--
-- Name: admin_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.admin_logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.admin_logs_id_seq OWNER TO postgres;

--
-- Name: admin_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.admin_logs_id_seq OWNED BY public.admin_logs.id;


--
-- Name: audit_logs; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.audit_logs (
    id integer NOT NULL,
    action character varying(100),
    user_id integer,
    admin_id integer,
    metadata jsonb,
    status character varying(20),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.audit_logs OWNER TO postgres;

--
-- Name: audit_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.audit_logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.audit_logs_id_seq OWNER TO postgres;

--
-- Name: audit_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.audit_logs_id_seq OWNED BY public.audit_logs.id;


--
-- Name: commission_plan; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.commission_plan (
    id integer NOT NULL,
    level integer NOT NULL,
    percentage numeric(5,2) NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    is_active boolean DEFAULT true NOT NULL
);


ALTER TABLE public.commission_plan OWNER TO postgres;

--
-- Name: commission_plan_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.commission_plan_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.commission_plan_id_seq OWNER TO postgres;

--
-- Name: commission_plan_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.commission_plan_id_seq OWNED BY public.commission_plan.id;


--
-- Name: commission_recalc_logs; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.commission_recalc_logs (
    id integer NOT NULL,
    admin_id integer,
    target_user_id integer,
    recalc_type character varying(50),
    reference_id integer,
    remark text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.commission_recalc_logs OWNER TO postgres;

--
-- Name: commission_recalc_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.commission_recalc_logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.commission_recalc_logs_id_seq OWNER TO postgres;

--
-- Name: commission_recalc_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.commission_recalc_logs_id_seq OWNED BY public.commission_recalc_logs.id;


--
-- Name: commissions; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.commissions (
    id bigint NOT NULL,
    earner_id bigint NOT NULL,
    from_user_id bigint NOT NULL,
    level integer NOT NULL,
    amount numeric(12,2) NOT NULL,
    commission_type character varying(50) NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    order_id bigint
);


ALTER TABLE public.commissions OWNER TO postgres;

--
-- Name: commissions_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.commissions_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.commissions_id_seq OWNER TO postgres;

--
-- Name: commissions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.commissions_id_seq OWNED BY public.commissions.id;


--
-- Name: company_profile; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.company_profile (
    id integer NOT NULL,
    company_name character varying(255) DEFAULT 'RK Trendz'::character varying,
    head_office_address text,
    branch_address text,
    support_email character varying(255),
    support_phone character varying(50),
    gst_number character varying(50),
    logo_url text,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.company_profile OWNER TO postgres;

--
-- Name: company_profile_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.company_profile_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.company_profile_id_seq OWNER TO postgres;

--
-- Name: company_profile_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.company_profile_id_seq OWNED BY public.company_profile.id;


--
-- Name: company_settings; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.company_settings (
    id integer NOT NULL,
    bank_name character varying(100),
    account_holder_name character varying(100),
    account_number character varying(50),
    ifsc_code character varying(20),
    upi_id character varying(100),
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    company_name character varying(255),
    gst_number character varying(50),
    logo_url character varying(255),
    support_email character varying(100),
    support_phone character varying(50),
    head_office_address text,
    branch_address text
);


ALTER TABLE public.company_settings OWNER TO postgres;

--
-- Name: company_settings_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.company_settings_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.company_settings_id_seq OWNER TO postgres;

--
-- Name: company_settings_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.company_settings_id_seq OWNED BY public.company_settings.id;


--
-- Name: cron_job_logs; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.cron_job_logs (
    id integer NOT NULL,
    job_name character varying(100) NOT NULL,
    status character varying(20) NOT NULL,
    message text,
    executed_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.cron_job_logs OWNER TO postgres;

--
-- Name: cron_job_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.cron_job_logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.cron_job_logs_id_seq OWNER TO postgres;

--
-- Name: cron_job_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.cron_job_logs_id_seq OWNED BY public.cron_job_logs.id;


--
-- Name: db_backup_logs; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.db_backup_logs (
    id integer NOT NULL,
    backup_file text,
    status character varying(20),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.db_backup_logs OWNER TO postgres;

--
-- Name: db_backup_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.db_backup_logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.db_backup_logs_id_seq OWNER TO postgres;

--
-- Name: db_backup_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.db_backup_logs_id_seq OWNED BY public.db_backup_logs.id;


--
-- Name: epins; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.epins (
    id integer NOT NULL,
    pin_code character varying(30) NOT NULL,
    package_id integer NOT NULL,
    amount numeric(10,2) NOT NULL,
    created_by integer NOT NULL,
    used_by integer,
    used_at timestamp without time zone,
    status character varying(20) DEFAULT 'unused'::character varying,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.epins OWNER TO postgres;

--
-- Name: epins_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.epins_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.epins_id_seq OWNER TO postgres;

--
-- Name: epins_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.epins_id_seq OWNED BY public.epins.id;


--
-- Name: global_commissions; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.global_commissions (
    setting_key character varying(50) NOT NULL,
    percentage_value numeric(5,2) NOT NULL,
    description text
);


ALTER TABLE public.global_commissions OWNER TO postgres;

--
-- Name: kyc_details; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.kyc_details (
    id integer NOT NULL,
    user_id integer,
    document_type text,
    document_number text,
    document_image text,
    selfie_image text,
    status character varying(20) DEFAULT 'Pending'::character varying,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.kyc_details OWNER TO postgres;

--
-- Name: kyc_details_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.kyc_details_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.kyc_details_id_seq OWNER TO postgres;

--
-- Name: kyc_details_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.kyc_details_id_seq OWNED BY public.kyc_details.id;


--
-- Name: kyc_requests; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.kyc_requests (
    id integer NOT NULL,
    user_id integer NOT NULL,
    document_type character varying(50),
    document_number character varying(100),
    document_image text,
    selfie_image text,
    status character varying(20) DEFAULT 'pending'::character varying,
    admin_note text,
    submitted_at timestamp without time zone DEFAULT now(),
    reviewed_at timestamp without time zone
);


ALTER TABLE public.kyc_requests OWNER TO postgres;

--
-- Name: kyc_requests_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.kyc_requests_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.kyc_requests_id_seq OWNER TO postgres;

--
-- Name: kyc_requests_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.kyc_requests_id_seq OWNED BY public.kyc_requests.id;


--
-- Name: level_commissions; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.level_commissions (
    level integer NOT NULL,
    commission_percentage numeric(5,2) NOT NULL
);


ALTER TABLE public.level_commissions OWNER TO postgres;

--
-- Name: notification_logs; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.notification_logs (
    id integer NOT NULL,
    user_id integer,
    notification_type character varying(50),
    message text,
    status character varying(50) DEFAULT 'sent'::character varying,
    sent_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.notification_logs OWNER TO postgres;

--
-- Name: notification_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.notification_logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.notification_logs_id_seq OWNER TO postgres;

--
-- Name: notification_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.notification_logs_id_seq OWNED BY public.notification_logs.id;


--
-- Name: notifications; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.notifications (
    id integer NOT NULL,
    user_id integer NOT NULL,
    type character varying(20),
    title text,
    message text,
    is_read boolean DEFAULT false,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.notifications OWNER TO postgres;

--
-- Name: notifications_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.notifications_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.notifications_id_seq OWNER TO postgres;

--
-- Name: notifications_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.notifications_id_seq OWNED BY public.notifications.id;


--
-- Name: orders; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.orders (
    id bigint NOT NULL,
    user_id bigint NOT NULL,
    package_id integer NOT NULL,
    amount numeric(12,2) NOT NULL,
    status character varying(30) DEFAULT 'completed'::character varying NOT NULL,
    payment_ref character varying(120),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


ALTER TABLE public.orders OWNER TO postgres;

--
-- Name: orders_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

ALTER TABLE public.orders ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.orders_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: otp_verifications; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.otp_verifications (
    id integer NOT NULL,
    user_id integer,
    identifier_type character varying(10) NOT NULL,
    new_identifier character varying(100) NOT NULL,
    otp_code character varying(6) NOT NULL,
    expires_at timestamp without time zone NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.otp_verifications OWNER TO postgres;

--
-- Name: otp_verifications_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.otp_verifications_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.otp_verifications_id_seq OWNER TO postgres;

--
-- Name: otp_verifications_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.otp_verifications_id_seq OWNED BY public.otp_verifications.id;


--
-- Name: packages; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.packages (
    id integer NOT NULL,
    name character varying(100),
    price numeric(10,2),
    description text
);


ALTER TABLE public.packages OWNER TO postgres;

--
-- Name: packages_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.packages_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.packages_id_seq OWNER TO postgres;

--
-- Name: packages_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.packages_id_seq OWNED BY public.packages.id;


--
-- Name: plan_images; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.plan_images (
    id integer NOT NULL,
    plan_id integer,
    image_path character varying(255) NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.plan_images OWNER TO postgres;

--
-- Name: plan_images_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.plan_images_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.plan_images_id_seq OWNER TO postgres;

--
-- Name: plan_images_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.plan_images_id_seq OWNED BY public.plan_images.id;


--
-- Name: rank_rules; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.rank_rules (
    id integer NOT NULL,
    level integer NOT NULL,
    rank_name character varying(50) NOT NULL,
    req_team_size integer NOT NULL,
    req_business_vol numeric(15,2) NOT NULL,
    bonus_percentage numeric(5,2) NOT NULL
);


ALTER TABLE public.rank_rules OWNER TO postgres;

--
-- Name: rank_rules_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.rank_rules_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.rank_rules_id_seq OWNER TO postgres;

--
-- Name: rank_rules_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.rank_rules_id_seq OWNED BY public.rank_rules.id;


--
-- Name: ranks; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.ranks (
    id integer NOT NULL,
    name character varying(50) NOT NULL,
    min_volume numeric(15,2) NOT NULL,
    reward character varying(255)
);


ALTER TABLE public.ranks OWNER TO postgres;

--
-- Name: ranks_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.ranks_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.ranks_id_seq OWNER TO postgres;

--
-- Name: ranks_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.ranks_id_seq OWNED BY public.ranks.id;


--
-- Name: roles; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.roles (
    id integer NOT NULL,
    role_name character varying(50) NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.roles OWNER TO postgres;

--
-- Name: roles_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.roles_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.roles_id_seq OWNER TO postgres;

--
-- Name: roles_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.roles_id_seq OWNED BY public.roles.id;


--
-- Name: subscription_plans; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.subscription_plans (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    price numeric(10,2) NOT NULL,
    lucky_draw_coupons integer DEFAULT 12,
    is_active boolean DEFAULT true,
    image_url character varying(500),
    product_cost numeric DEFAULT 0
);


ALTER TABLE public.subscription_plans OWNER TO postgres;

--
-- Name: subscription_plans_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.subscription_plans_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.subscription_plans_id_seq OWNER TO postgres;

--
-- Name: subscription_plans_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.subscription_plans_id_seq OWNED BY public.subscription_plans.id;


--
-- Name: support_tickets; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.support_tickets (
    id integer NOT NULL,
    user_id integer,
    subject character varying(255) NOT NULL,
    message text NOT NULL,
    admin_response text,
    status character varying(50) DEFAULT 'Open'::character varying,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.support_tickets OWNER TO postgres;

--
-- Name: support_tickets_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.support_tickets_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.support_tickets_id_seq OWNER TO postgres;

--
-- Name: support_tickets_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.support_tickets_id_seq OWNED BY public.support_tickets.id;


--
-- Name: team_target_bonuses; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.team_target_bonuses (
    id integer NOT NULL,
    min_volume numeric(15,2) NOT NULL,
    max_volume numeric(15,2) NOT NULL,
    bonus_percentage numeric(5,2) NOT NULL
);


ALTER TABLE public.team_target_bonuses OWNER TO postgres;

--
-- Name: team_target_bonuses_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.team_target_bonuses_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.team_target_bonuses_id_seq OWNER TO postgres;

--
-- Name: team_target_bonuses_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.team_target_bonuses_id_seq OWNED BY public.team_target_bonuses.id;


--
-- Name: ticket_messages; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.ticket_messages (
    id integer NOT NULL,
    ticket_id integer,
    sender_id integer,
    sender_role character varying(10),
    message text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.ticket_messages OWNER TO postgres;

--
-- Name: ticket_messages_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.ticket_messages_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.ticket_messages_id_seq OWNER TO postgres;

--
-- Name: ticket_messages_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.ticket_messages_id_seq OWNED BY public.ticket_messages.id;


--
-- Name: user_bonus_history; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.user_bonus_history (
    id integer NOT NULL,
    user_id integer,
    rank_level integer,
    bonus_amount numeric(15,2) NOT NULL,
    earned_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.user_bonus_history OWNER TO postgres;

--
-- Name: user_bonus_history_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.user_bonus_history_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.user_bonus_history_id_seq OWNER TO postgres;

--
-- Name: user_bonus_history_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.user_bonus_history_id_seq OWNED BY public.user_bonus_history.id;


--
-- Name: user_packages; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.user_packages (
    id integer NOT NULL,
    user_id integer,
    package_id integer,
    amount numeric(10,2),
    purchased_at timestamp without time zone DEFAULT now(),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.user_packages OWNER TO postgres;

--
-- Name: user_packages_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.user_packages_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.user_packages_id_seq OWNER TO postgres;

--
-- Name: user_packages_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.user_packages_id_seq OWNED BY public.user_packages.id;


--
-- Name: users; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.users (
    id bigint NOT NULL,
    role_id integer NOT NULL,
    full_name character varying(150) NOT NULL,
    email character varying(150),
    phone character varying(20),
    password_hash text NOT NULL,
    referral_code character varying(20) NOT NULL,
    sponsor_id bigint,
    is_active boolean DEFAULT false,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    activated_at timestamp without time zone,
    rank_id integer DEFAULT 1,
    kyc_status character varying(20) DEFAULT 'not_submitted'::character varying,
    pan_number character varying(20),
    aadhar_number character varying(20),
    bank_name character varying(100),
    bank_account_no character varying(50),
    bank_ifsc character varying(20),
    kyc_rejection_reason text,
    package_id integer,
    rank_level integer DEFAULT 1,
    current_volume numeric(15,2) DEFAULT 0.00,
    tree_path public.ltree,
    direct_count integer DEFAULT 0 NOT NULL,
    total_team_count integer DEFAULT 0 NOT NULL,
    alternate_phone character varying(20),
    dob date,
    address text,
    city character varying(80),
    state character varying(80),
    pincode character varying(12),
    designation character varying(60)
);


ALTER TABLE public.users OWNER TO postgres;

--
-- Name: users_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.users_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.users_id_seq OWNER TO postgres;

--
-- Name: users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;


--
-- Name: wallet_ledger; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.wallet_ledger (
    id bigint NOT NULL,
    user_id bigint NOT NULL,
    transaction_type character varying(50) NOT NULL,
    amount numeric(12,2) NOT NULL,
    reference_id text,
    description text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    closing_balance numeric,
    running_balance numeric(14,2),
    reference text
);


ALTER TABLE public.wallet_ledger OWNER TO postgres;

--
-- Name: wallet_ledger_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.wallet_ledger_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.wallet_ledger_id_seq OWNER TO postgres;

--
-- Name: wallet_ledger_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.wallet_ledger_id_seq OWNED BY public.wallet_ledger.id;


--
-- Name: wallets; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.wallets (
    user_id integer NOT NULL,
    balance numeric(12,2) DEFAULT 0
);


ALTER TABLE public.wallets OWNER TO postgres;

--
-- Name: withdraw_requests; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.withdraw_requests (
    id bigint NOT NULL,
    user_id bigint NOT NULL,
    amount numeric(12,2) NOT NULL,
    status character varying(30) DEFAULT 'pending'::character varying,
    requested_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    processed_at timestamp without time zone,
    payout_method character varying(50) DEFAULT 'bank'::character varying,
    payout_details text,
    admin_note text
);


ALTER TABLE public.withdraw_requests OWNER TO postgres;

--
-- Name: withdraw_requests_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.withdraw_requests_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.withdraw_requests_id_seq OWNER TO postgres;

--
-- Name: withdraw_requests_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.withdraw_requests_id_seq OWNED BY public.withdraw_requests.id;


--
-- Name: yoyo_lock; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.yoyo_lock (
    locked integer DEFAULT 1 NOT NULL,
    ctime timestamp without time zone,
    pid integer NOT NULL
);


ALTER TABLE public.yoyo_lock OWNER TO postgres;

--
-- Name: admin_activity_logs id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.admin_activity_logs ALTER COLUMN id SET DEFAULT nextval('public.admin_activity_logs_id_seq'::regclass);


--
-- Name: admin_audit_logs id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.admin_audit_logs ALTER COLUMN id SET DEFAULT nextval('public.admin_audit_logs_id_seq'::regclass);


--
-- Name: admin_logs id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.admin_logs ALTER COLUMN id SET DEFAULT nextval('public.admin_logs_id_seq'::regclass);


--
-- Name: audit_logs id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.audit_logs ALTER COLUMN id SET DEFAULT nextval('public.audit_logs_id_seq'::regclass);


--
-- Name: commission_plan id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.commission_plan ALTER COLUMN id SET DEFAULT nextval('public.commission_plan_id_seq'::regclass);


--
-- Name: commission_recalc_logs id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.commission_recalc_logs ALTER COLUMN id SET DEFAULT nextval('public.commission_recalc_logs_id_seq'::regclass);


--
-- Name: commissions id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.commissions ALTER COLUMN id SET DEFAULT nextval('public.commissions_id_seq'::regclass);


--
-- Name: company_profile id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.company_profile ALTER COLUMN id SET DEFAULT nextval('public.company_profile_id_seq'::regclass);


--
-- Name: company_settings id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.company_settings ALTER COLUMN id SET DEFAULT nextval('public.company_settings_id_seq'::regclass);


--
-- Name: cron_job_logs id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cron_job_logs ALTER COLUMN id SET DEFAULT nextval('public.cron_job_logs_id_seq'::regclass);


--
-- Name: db_backup_logs id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.db_backup_logs ALTER COLUMN id SET DEFAULT nextval('public.db_backup_logs_id_seq'::regclass);


--
-- Name: epins id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.epins ALTER COLUMN id SET DEFAULT nextval('public.epins_id_seq'::regclass);


--
-- Name: kyc_details id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.kyc_details ALTER COLUMN id SET DEFAULT nextval('public.kyc_details_id_seq'::regclass);


--
-- Name: kyc_requests id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.kyc_requests ALTER COLUMN id SET DEFAULT nextval('public.kyc_requests_id_seq'::regclass);


--
-- Name: notification_logs id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.notification_logs ALTER COLUMN id SET DEFAULT nextval('public.notification_logs_id_seq'::regclass);


--
-- Name: notifications id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.notifications ALTER COLUMN id SET DEFAULT nextval('public.notifications_id_seq'::regclass);


--
-- Name: otp_verifications id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.otp_verifications ALTER COLUMN id SET DEFAULT nextval('public.otp_verifications_id_seq'::regclass);


--
-- Name: packages id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.packages ALTER COLUMN id SET DEFAULT nextval('public.packages_id_seq'::regclass);


--
-- Name: plan_images id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.plan_images ALTER COLUMN id SET DEFAULT nextval('public.plan_images_id_seq'::regclass);


--
-- Name: rank_rules id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.rank_rules ALTER COLUMN id SET DEFAULT nextval('public.rank_rules_id_seq'::regclass);


--
-- Name: ranks id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.ranks ALTER COLUMN id SET DEFAULT nextval('public.ranks_id_seq'::regclass);


--
-- Name: roles id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.roles ALTER COLUMN id SET DEFAULT nextval('public.roles_id_seq'::regclass);


--
-- Name: subscription_plans id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.subscription_plans ALTER COLUMN id SET DEFAULT nextval('public.subscription_plans_id_seq'::regclass);


--
-- Name: support_tickets id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.support_tickets ALTER COLUMN id SET DEFAULT nextval('public.support_tickets_id_seq'::regclass);


--
-- Name: team_target_bonuses id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.team_target_bonuses ALTER COLUMN id SET DEFAULT nextval('public.team_target_bonuses_id_seq'::regclass);


--
-- Name: ticket_messages id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.ticket_messages ALTER COLUMN id SET DEFAULT nextval('public.ticket_messages_id_seq'::regclass);


--
-- Name: user_bonus_history id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_bonus_history ALTER COLUMN id SET DEFAULT nextval('public.user_bonus_history_id_seq'::regclass);


--
-- Name: user_packages id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_packages ALTER COLUMN id SET DEFAULT nextval('public.user_packages_id_seq'::regclass);


--
-- Name: users id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);


--
-- Name: wallet_ledger id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wallet_ledger ALTER COLUMN id SET DEFAULT nextval('public.wallet_ledger_id_seq'::regclass);


--
-- Name: withdraw_requests id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.withdraw_requests ALTER COLUMN id SET DEFAULT nextval('public.withdraw_requests_id_seq'::regclass);


--
-- Data for Name: _yoyo_log; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public._yoyo_log (id, migration_hash, migration_id, operation, username, hostname, comment, created_at_utc) FROM stdin;
23e2ed24-566c-11f1-9325-b0359f1ded90	8ba365c9c9d8e416d66070308defc81af432b78bf536f5175ea945bf1ee6a461	0001_create_company_settings	apply	sarvesh	localhost	\N	2026-05-23 05:56:28.391879
268d1db6-5774-11f1-ab8b-b0359f1ded90	f6c103929cdb64147a1d1ff245bca57818001f8a41e522b309c09cf820fef1e9	003_add_rank_columns_to_users	apply	sarvesh	localhost	\N	2026-05-24 13:26:19.999332
\.


--
-- Data for Name: _yoyo_migration; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public._yoyo_migration (migration_hash, migration_id, applied_at_utc) FROM stdin;
8ba365c9c9d8e416d66070308defc81af432b78bf536f5175ea945bf1ee6a461	0001_create_company_settings	2026-05-23 05:56:28.400704
f6c103929cdb64147a1d1ff245bca57818001f8a41e522b309c09cf820fef1e9	003_add_rank_columns_to_users	2026-05-24 13:26:20.007437
\.


--
-- Data for Name: _yoyo_version; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public._yoyo_version (version, installed_at_utc) FROM stdin;
2	2026-05-23 05:56:00.738434
\.


--
-- Data for Name: admin_activity_logs; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.admin_activity_logs (id, admin_id, action, target_user_id, description, created_at) FROM stdin;
\.


--
-- Data for Name: admin_audit_logs; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.admin_audit_logs (id, admin_id, action, target_user_id, amount, remark, created_at) FROM stdin;
\.


--
-- Data for Name: admin_logs; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.admin_logs (id, admin_id, action, target_user_id, created_at, description) FROM stdin;
\.


--
-- Data for Name: audit_logs; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.audit_logs (id, action, user_id, admin_id, metadata, status, created_at) FROM stdin;
1	withdraw_request_created	1	\N	{"amount": "500", "request_id": 1}	success	2026-04-21 12:43:49.473287
2	withdraw_reject_failed	\N	\N	{"error": "column \\"admin_note\\" of relation \\"withdraw_requests\\" does not exist\\nLINE 5:                     admin_note='Rejected by Admin during rev...\\n                            ^\\n", "request_id": 1}	failed	2026-04-21 15:59:19.428162
3	withdraw_approved	1	\N	{"amount": "500.00", "request_id": 1}	success	2026-04-21 15:59:25.563061
4	withdraw_approve_failed	\N	\N	{"error": "Already processed", "request_id": 1}	failed	2026-04-21 15:59:31.04656
5	withdraw_approve_failed	\N	\N	{"error": "Already processed", "request_id": 1}	failed	2026-04-21 16:00:00.886551
6	withdraw_reject_failed	\N	\N	{"error": "Already processed", "request_id": 1}	failed	2026-04-21 16:00:05.78309
7	withdraw_approve_failed	\N	\N	{"error": "Already processed", "request_id": 1}	failed	2026-04-21 16:00:45.343395
8	withdraw_approve_failed	\N	\N	{"error": "Already processed", "request_id": 1}	failed	2026-04-21 17:02:15.283047
9	withdraw_request_failed	5	\N	{"error": "'<' not supported between instances of 'dict' and 'decimal.Decimal'", "amount": "100.0"}	failed	2026-04-25 01:15:00.806977
10	withdraw_request_failed	5	\N	{"error": "'<' not supported between instances of 'dict' and 'decimal.Decimal'", "amount": "500.0"}	failed	2026-04-25 01:18:07.477621
11	withdraw_request_failed	5	\N	{"error": "'<' not supported between instances of 'dict' and 'decimal.Decimal'", "amount": "500.1"}	failed	2026-04-25 01:18:16.371606
12	withdraw_request_created	5	\N	{"amount": "100.0", "request_id": 2, "payout_method": "upi"}	success	2026-04-25 01:24:01.784461
13	withdraw_approved	5	\N	{"amount": "100.00", "request_id": 2}	success	2026-04-26 00:04:22.57391
14	withdraw_request_created	1	\N	{"amount": "100.0", "request_id": 3, "payout_method": "upi"}	success	2026-04-26 17:19:23.772322
15	withdraw_approved	1	\N	{"amount": "100.00", "request_id": 3}	success	2026-04-27 09:14:16.040132
16	withdraw_request_created	1	\N	{"amount": "100.0", "request_id": 4, "payout_method": "upi"}	success	2026-04-27 09:31:37.840519
17	withdraw_approved	1	\N	{"amount": "100.00", "request_id": 4}	success	2026-04-27 17:27:19.683188
18	withdraw_request_created	1	\N	{"amount": "1000.0", "request_id": 5, "payout_method": "upi"}	success	2026-04-28 11:39:21.323117
19	withdraw_approved	1	\N	{"amount": "1000.00", "request_id": 5}	success	2026-04-28 11:39:46.697366
20	withdraw_request_created	1	\N	{"amount": "2000.0", "request_id": 6, "payout_method": "upi"}	success	2026-04-28 11:41:01.48199
21	withdraw_approved	1	\N	{"amount": "2000.00", "request_id": 6}	success	2026-04-28 11:41:31.079893
22	withdraw_request_created	1	\N	{"amount": "5000.0", "request_id": 7, "payout_method": "upi"}	success	2026-04-28 11:48:13.949726
23	withdraw_approved	1	\N	{"amount": "5000.00", "request_id": 7}	success	2026-04-28 11:48:23.283812
24	withdraw_request_created	1	\N	{"amount": "2000.0", "request_id": 8, "payout_method": "upi"}	success	2026-04-28 12:27:32.304604
25	withdraw_approved	1	\N	{"amount": "2000.00", "request_id": 8}	success	2026-04-28 12:27:40.650316
26	withdraw_request_created	1	\N	{"amount": "1000.0", "request_id": 9, "payout_method": "upi"}	success	2026-04-28 12:37:45.069639
27	withdraw_approved	1	\N	{"amount": "1000.00", "request_id": 9}	success	2026-04-28 12:37:59.099074
28	withdraw_request_created	1	\N	{"amount": "5000.0", "request_id": 10, "payout_method": "upi"}	success	2026-05-26 00:27:45.901006
29	withdraw_approved	1	\N	{"amount": "5000.00", "request_id": 10}	success	2026-05-26 00:45:21.271564
30	withdraw_request_created	1	\N	{"amount": "1000.0", "request_id": 11, "payout_method": "upi"}	success	2026-05-26 00:45:58.419678
31	withdraw_rejected	1	\N	{"remark": "Rejected by Admin during review", "request_id": 11}	success	2026-05-26 11:25:23.656289
32	withdraw_request_created	1	\N	{"amount": "1000.0", "request_id": 12, "payout_method": "upi"}	success	2026-05-26 15:33:41.672086
33	withdraw_rejected	1	\N	{"remark": "Rejected by Admin during review", "request_id": 12}	success	2026-06-02 13:47:27.428079
34	withdraw_request_created	1	\N	{"amount": "1000.0", "request_id": 13, "payout_method": "upi"}	success	2026-06-02 13:48:33.170259
35	withdraw_rejected	1	\N	{"remark": "Rejected by Admin during review", "request_id": 13}	success	2026-06-02 14:34:35.707684
36	withdraw_request_created	1	\N	{"amount": "500.0", "request_id": 14, "payout_method": "upi"}	success	2026-08-24 13:05:00.496588
37	withdraw_rejected	1	\N	{"remark": "Rejected by Admin during review", "request_id": 14}	success	2026-08-24 13:14:02.156757
38	withdraw_request_created	1	\N	{"amount": "1000.0", "request_id": 15, "payout_method": "upi"}	success	2026-08-24 13:14:32.716351
39	withdraw_approved	1	\N	{"amount": "1000.00", "request_id": 15}	success	2026-08-24 13:30:15.747944
40	withdraw_request_created	1	\N	{"amount": "1000.0", "request_id": 16, "payout_method": "upi"}	success	2026-09-05 09:16:33.704739
41	withdraw_approved	1	\N	{"amount": "1000.00", "request_id": 16}	success	2026-09-05 09:19:10.704915
\.


--
-- Data for Name: commission_plan; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.commission_plan (id, level, percentage, created_at, is_active) FROM stdin;
1	1	10.00	2026-03-05 00:38:47.823437	t
2	2	3.00	2026-03-05 00:38:47.823437	t
3	3	2.50	2026-03-05 00:38:47.823437	t
4	4	2.00	2026-03-05 00:38:47.823437	t
5	5	1.50	2026-03-05 00:38:47.823437	t
6	6	1.50	2026-03-05 00:38:47.823437	t
7	7	1.50	2026-03-05 00:38:47.823437	t
8	8	1.00	2026-03-05 00:38:47.823437	t
9	9	1.00	2026-03-05 00:38:47.823437	t
10	10	1.00	2026-03-05 00:38:47.823437	t
\.


--
-- Data for Name: commission_recalc_logs; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.commission_recalc_logs (id, admin_id, target_user_id, recalc_type, reference_id, remark, created_at) FROM stdin;
\.


--
-- Data for Name: commissions; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.commissions (id, earner_id, from_user_id, level, amount, commission_type, created_at, order_id) FROM stdin;
1	1	3	1	30.00	unilevel	2026-03-08 22:16:20.245974	\N
2	1	1	1	10.00	daily_bonus	2026-03-10 15:02:11.069117	\N
3	3	3	1	10.00	daily_bonus	2026-03-10 15:02:11.126007	\N
23	5	5	0	90.00	self_cashback_5_inv_5_1776973907	2026-04-24 01:21:47.954465	\N
24	3	5	1	180.00	direct_referral_3_inv_5_1776973907	2026-04-24 01:21:47.954465	\N
25	3	5	1	45.00	team_target_bonus_3_inv_5_1776973907	2026-04-24 01:21:47.954465	\N
26	1	5	2	54.00	level_commission_1_2_inv_5_1776973907	2026-04-24 01:21:47.954465	\N
27	1	5	2	45.00	team_target_bonus_1_inv_5_1776973907	2026-04-24 01:21:47.954465	\N
28	5	5	0	180.00	self_cashback_5_inv_5_1776973916	2026-04-24 01:21:56.47795	\N
29	3	5	1	360.00	direct_referral_3_inv_5_1776973916	2026-04-24 01:21:56.47795	\N
30	3	5	1	90.00	team_target_bonus_3_inv_5_1776973916	2026-04-24 01:21:56.47795	\N
31	1	5	2	108.00	level_commission_1_2_inv_5_1776973916	2026-04-24 01:21:56.47795	\N
32	1	5	2	90.00	team_target_bonus_1_inv_5_1776973916	2026-04-24 01:21:56.47795	\N
33	5	5	0	90.00	self_cashback_5_inv_5_1776973995	2026-04-24 01:23:15.473231	\N
34	3	5	1	180.00	direct_referral_3_inv_5_1776973995	2026-04-24 01:23:15.473231	\N
35	3	5	1	45.00	team_target_bonus_3_inv_5_1776973995	2026-04-24 01:23:15.473231	\N
36	1	5	2	54.00	level_commission_1_2_inv_5_1776973995	2026-04-24 01:23:15.473231	\N
37	1	5	2	45.00	team_target_bonus_1_inv_5_1776973995	2026-04-24 01:23:15.473231	\N
38	5	5	0	90.00	self_cashback_5_inv_5_1776974117	2026-04-24 01:25:17.610567	\N
39	3	5	1	180.00	direct_referral_3_inv_5_1776974117	2026-04-24 01:25:17.610567	\N
40	3	5	1	45.00	team_target_bonus_3_inv_5_1776974117	2026-04-24 01:25:17.610567	\N
41	1	5	2	54.00	level_commission_1_2_inv_5_1776974117	2026-04-24 01:25:17.610567	\N
42	1	5	2	45.00	team_target_bonus_1_inv_5_1776974117	2026-04-24 01:25:17.610567	\N
43	5	5	0	90.00	self_cashback_5_inv_5_1776975030	2026-04-24 01:40:30.678767	\N
44	3	5	1	180.00	direct_referral_3_inv_5_1776975030	2026-04-24 01:40:30.678767	\N
45	3	5	1	45.00	team_target_bonus_3_inv_5_1776975030	2026-04-24 01:40:30.678767	\N
46	1	5	2	54.00	level_commission_1_2_inv_5_1776975030	2026-04-24 01:40:30.678767	\N
47	1	5	2	45.00	team_target_bonus_1_inv_5_1776975030	2026-04-24 01:40:30.678767	\N
48	10001	10001	0	180.00	cashback	2026-04-26 02:00:09.788015	\N
49	1	10001	1	360.00	direct_referral	2026-04-26 02:00:09.788015	\N
50	1	10001	1	90.00	team_target_bonus	2026-04-26 02:00:09.788015	\N
51	1	1	0	90.00	cashback	2026-04-26 02:12:10.578517	\N
\.


--
-- Data for Name: company_profile; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.company_profile (id, company_name, head_office_address, branch_address, support_email, support_phone, gst_number, logo_url, updated_at) FROM stdin;
1	RK Trendz	\N	\N	\N	\N	\N	\N	2026-04-25 15:16:03.3729
\.


--
-- Data for Name: company_settings; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.company_settings (id, bank_name, account_holder_name, account_number, ifsc_code, upi_id, updated_at, company_name, gst_number, logo_url, support_email, support_phone, head_office_address, branch_address) FROM stdin;
1	Setup Required	Setup Required	0000000000	XXXX0000000	yourname@upi	2026-05-23 02:51:18.143665	\N	\N	\N	\N	\N	\N	\N
\.


--
-- Data for Name: cron_job_logs; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.cron_job_logs (id, job_name, status, message, executed_at) FROM stdin;
\.


--
-- Data for Name: db_backup_logs; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.db_backup_logs (id, backup_file, status, created_at) FROM stdin;
1	backup_20260315_194401.sql	success	2026-03-16 01:14:05.286646
2	backup_20260315_194510.sql	success	2026-03-16 01:15:15.293269
3	backup_20260315_195956.dump	success	2026-03-16 01:30:01.447051
4	backup_failed	error	2026-03-18 02:00:02.436883
5	backup_failed	error	2026-03-29 02:00:01.983376
6	backup_failed	error	2026-04-05 02:00:02.717088
7	backup_20260413_203001.dump	success	2026-04-14 02:00:02.167265
8	backup_20260414_203001.dump	success	2026-04-15 02:00:02.292421
9	backup_20260415_203002.dump	success	2026-04-16 02:00:02.987844
10	backup_20260417_203002.dump	success	2026-04-18 02:00:02.970783
11	backup_20260420_203002.dump	success	2026-04-21 02:00:03.183423
12	backup_20260421_203001.dump	success	2026-04-22 02:00:02.509629
13	backup_20260423_203001.dump	success	2026-04-24 02:00:02.246681
14	backup_20260425_203001.dump	success	2026-04-26 02:00:02.504503
15	backup_20260428_203002.dump	success	2026-04-29 02:00:03.197678
16	backup_20260429_203001.dump	success	2026-04-30 02:00:02.742798
17	backup_20260514_203002.dump	success	2026-05-15 02:00:03.238762
18	backup_20260522_203001.dump	success	2026-05-23 02:00:02.607717
19	backup_20260524_203002.dump	success	2026-05-25 02:00:03.000758
20	backup_20260529_203002.dump	success	2026-05-30 02:00:03.413355
21	backup_20260604_203001.dump	success	2026-06-05 02:00:02.67089
\.


--
-- Data for Name: epins; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.epins (id, pin_code, package_id, amount, created_by, used_by, used_at, status, created_at) FROM stdin;
\.


--
-- Data for Name: global_commissions; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.global_commissions (setting_key, percentage_value, description) FROM stdin;
direct_commission	10.00	Direct sponsor commission (%) on package purchase
direct_referral	10.00	Direct referral income (Level 1)
self_cashback	5.00	Cashback to buyer on own purchase
repurchase_cashback	5.00	Cashback on repurchases
repurchase_referral	10.00	Sponsor commission on repurchase
admin_fee_percentage	10.00	Admin/processing fee on withdrawal
tds_percentage	10.00	TDS deducted on withdrawal
\.


--
-- Data for Name: kyc_details; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.kyc_details (id, user_id, document_type, document_number, document_image, selfie_image, status, created_at) FROM stdin;
1	\N	\N	\N	\N	\N	pending	2026-04-22 01:20:57.3916
2	\N	\N	\N	\N	\N	pending	2026-04-22 01:36:54.95645
3	5	\N	\N	\N	\N	pending	2026-04-22 01:44:09.502083
5	10001	\N	\N	\N	\N	pending	2026-04-26 01:59:26.681188
\.


--
-- Data for Name: kyc_requests; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.kyc_requests (id, user_id, document_type, document_number, document_image, selfie_image, status, admin_note, submitted_at, reviewed_at) FROM stdin;
\.


--
-- Data for Name: level_commissions; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.level_commissions (level, commission_percentage) FROM stdin;
1	10.00
2	3.00
3	2.50
4	2.00
5	1.50
6	1.50
7	1.50
8	1.00
9	1.00
10	1.00
\.


--
-- Data for Name: notification_logs; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.notification_logs (id, user_id, notification_type, message, status, sent_at) FROM stdin;
\.


--
-- Data for Name: notifications; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.notifications (id, user_id, type, title, message, is_read, created_at) FROM stdin;
\.


--
-- Data for Name: orders; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.orders (id, user_id, package_id, amount, status, payment_ref, created_at) FROM stdin;
1	5	1	3600.00	completed	LEGACY-1	2026-04-24 01:06:15.701022
2	5	1	1800.00	completed	LEGACY-7	2026-04-24 01:21:47.954465
3	5	2	3600.00	completed	LEGACY-8	2026-04-24 01:21:56.47795
4	5	1	1800.00	completed	LEGACY-9	2026-04-24 01:23:15.473231
5	5	1	1800.00	completed	LEGACY-10	2026-04-24 01:25:17.610567
6	5	1	1800.00	completed	LEGACY-11	2026-04-24 01:40:30.678767
7	10001	2	3600.00	completed	LEGACY-12	2026-04-26 02:00:09.788015
8	1	1	1800.00	completed	LEGACY-13	2026-04-26 02:12:10.578517
\.


--
-- Data for Name: otp_verifications; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.otp_verifications (id, user_id, identifier_type, new_identifier, otp_code, expires_at, created_at) FROM stdin;
1	5	phone	9999988777	232205	2026-04-22 14:36:43.216424	2026-04-22 14:26:43.216812
\.


--
-- Data for Name: packages; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.packages (id, name, price, description) FROM stdin;
1	Distributor Combo Pack	3600.00	RK Trendz Joining Pack
\.


--
-- Data for Name: plan_images; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.plan_images (id, plan_id, image_path, created_at) FROM stdin;
6	1	/static/uploads/packages/plan_1_lanhga.png	2026-04-28 11:17:38.277022
\.


--
-- Data for Name: rank_rules; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.rank_rules (id, level, rank_name, req_team_size, req_business_vol, bonus_percentage) FROM stdin;
1	1	Bronze	10	50000.00	2.00
2	2	Silver	25	200000.00	1.50
3	3	Gold	100	500000.00	1.00
4	4	Emerald	200	700000.00	1.00
5	5	Platinum	250	850000.00	1.00
6	6	Ruby	350	1000000.00	1.00
7	7	Diamond	450	1200000.00	1.00
8	8	Crown Diamond	550	1500000.00	1.00
\.


--
-- Data for Name: ranks; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.ranks (id, name, min_volume, reward) FROM stdin;
1	Active Affiliate	0.00	None
2	Bronze Director	100000.00	Smartwatch
3	Silver Director	500000.00	Smartphone
4	Gold Director	1000000.00	Laptop
5	Diamond Director	5000000.00	Car Fund
\.


--
-- Data for Name: roles; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.roles (id, role_name, created_at) FROM stdin;
1	admin	2026-03-05 00:09:14.62806
2	user	2026-03-05 00:09:14.62806
3	subadmin	2026-03-05 00:09:14.62806
\.


--
-- Data for Name: subscription_plans; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.subscription_plans (id, name, price, lucky_draw_coupons, is_active, image_url, product_cost) FROM stdin;
1	Starter	1800.00	12	t	/static/uploads/packages/plan_1_lanhga.png	1000
2	Bronze	3600.00	12	t	\N	0
3	Silver	7200.00	12	t	\N	0
4	Gold	14400.00	12	t	\N	0
5	Platinum	28800.00	12	t	\N	0
\.


--
-- Data for Name: support_tickets; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.support_tickets (id, user_id, subject, message, admin_response, status, created_at) FROM stdin;
\.


--
-- Data for Name: team_target_bonuses; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.team_target_bonuses (id, min_volume, max_volume, bonus_percentage) FROM stdin;
3	200001.00	500000.00	1.00
1	1000.00	50000.00	2.50
2	51000.00	200000.00	1.03
\.


--
-- Data for Name: ticket_messages; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.ticket_messages (id, ticket_id, sender_id, sender_role, message, created_at) FROM stdin;
\.


--
-- Data for Name: user_bonus_history; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.user_bonus_history (id, user_id, rank_level, bonus_amount, earned_at) FROM stdin;
\.


--
-- Data for Name: user_packages; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.user_packages (id, user_id, package_id, amount, purchased_at, created_at) FROM stdin;
1	5	1	3600.00	2026-03-12 13:11:09.806855	2026-04-24 01:06:15.701022
7	5	1	1800.00	2026-04-24 01:21:47.954465	2026-04-24 01:21:47.954465
8	5	2	3600.00	2026-04-24 01:21:56.47795	2026-04-24 01:21:56.47795
9	5	1	1800.00	2026-04-24 01:23:15.473231	2026-04-24 01:23:15.473231
10	5	1	1800.00	2026-04-24 01:25:17.610567	2026-04-24 01:25:17.610567
11	5	1	1800.00	2026-04-24 01:40:30.678767	2026-04-24 01:40:30.678767
12	10001	2	3600.00	2026-04-26 02:00:09.788015	2026-04-26 02:00:09.788015
13	1	1	1800.00	2026-04-26 02:12:10.578517	2026-04-26 02:12:10.578517
\.


--
-- Data for Name: users; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.users (id, role_id, full_name, email, phone, password_hash, referral_code, sponsor_id, is_active, created_at, activated_at, rank_id, kyc_status, pan_number, aadhar_number, bank_name, bank_account_no, bank_ifsc, kyc_rejection_reason, package_id, rank_level, current_volume, tree_path, direct_count, total_team_count, alternate_phone, dob, address, city, state, pincode, designation) FROM stdin;
10001	2	Akhilesh Kumar	akhileshkumar123@gmail.com	8888877777	$2b$12$PRb1NPz1nnaLTdR26KmsQeSI8qjILa4eBoWyjmzr.h6zkkuk2D/I.	EWOZ11MZ	1	t	2026-04-26 01:59:26.683112	2026-04-26 02:00:09.788015	1	not_submitted	\N	\N	\N	\N	\N	\N	2	1	0.00	1.10001	0	0	\N	\N	\N	\N	\N	\N	\N
1	1	Admin	ramkumarfall70@gmail.com	8009436702	$2b$12$CGDRs8DAGh8p9N.JniTxg.tg260rYUBVumGzIztwVo9sDWXnsieI6	ADMIN001	\N	t	2026-03-07 03:01:28.213989	2026-04-26 02:12:10.578517	1	not_submitted	\N	\N	\N	\N	\N	\N	1	1	0.00	1	2	3	\N	\N	\N	\N	\N	\N	\N
4	2	Suresh Kumar	\N	0000000000	scrypt:32768:8:1$FHnSOWlRZMOK9kzs$f5ea463bf8af41bc2074fe9ece700fb302841d285e4f49e9352ae7b1c4df5806fd9aa8b4da87ad37c18fb00df9814bf99039c1b9ca331149dca7020fb9b81dd1	PQ3JDL5	\N	t	2026-03-29 01:32:23.31146	\N	1	not_submitted	\N	\N	\N	\N	\N	\N	\N	1	0.00	4	0	0	\N	\N	\N	\N	\N	\N	\N
3	2	Ravi Kumar	\N	8888888888	scrypt:32768:8:1$YAdSqqIfEQMQdwrV$51889b9ba821e5635695d56b251a6a5a87cd8fdecfa23639160158c7c3918cafbdeee130e62329e4ac87c95d66b85c29bcd9de3e7df9e1c081415fe02f3cfcca	FDUU66AC	1	t	2026-03-07 04:46:13.699364	2026-03-07 05:07:32.322054	1	not_submitted	\N	\N	\N	\N	\N	\N	\N	1	0.00	1.3	1	1	\N	\N	\N	\N	\N	\N	\N
5	2	Ram Kumar	ramkumar@gmail.com	9999988888	$2b$12$nOgEdpzQLgYtA/NCoPq6wuMxpJt/smIfuGc/2Nu5Pj0PIhRgkCpMK	K4I9YJLL	3	t	2026-04-22 01:44:09.503332	2026-04-24 01:40:30.678767	1	not_submitted	\N	\N	\N	\N	\N	\N	1	1	0.00	1.3.5	0	0	\N	\N	\N	\N	\N	\N	\N
\.


--
-- Data for Name: wallet_ledger; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.wallet_ledger (id, user_id, transaction_type, amount, reference_id, description, created_at, closing_balance, running_balance, reference) FROM stdin;
1	1	commission_credit	30.00	3	Level 1 commission from user 3	2026-03-08 22:16:20.245974	\N	\N	\N
2	1	credit	5000.00	test_credit	Test credit	2026-04-21 12:43:22.412937	5000	\N	\N
3	1	credit	5000.00	test_credit_1_1776736781.841052	Test credit	2026-04-21 12:59:41.847084	10000.00	\N	\N
4	1	credit	5000.00	test_credit_1_1776736952.796957	Test credit	2026-04-21 13:02:32.797265	15000.00	\N	\N
5	1	credit	5000.00	test_credit_1_1776737169.946331	Test credit	2026-04-21 13:06:09.946674	20000.00	\N	\N
6	1	credit	5000.00	test_credit_1_1776737749.716537	Test credit	2026-04-21 13:15:49.71689	25000.00	\N	\N
7	1	credit	5000.00	test_credit_1_1776738451.284494	Test credit	2026-04-21 13:27:31.284947	30000.00	\N	\N
9	1	credit	5000.00	test_credit_1_1776774744.669017	Test credit	2026-04-21 23:32:24.669338	34500.00	\N	\N
29	5	credit	90.00	self_cashback_5_inv_5_1776973907	5.00% Cashback on package purchase	2026-04-24 01:21:47.954465	90.0000	\N	\N
30	3	credit	180.00	direct_referral_3_inv_5_1776973907	10.00% Direct Referral from User #5	2026-04-24 01:21:47.954465	180.0000	\N	\N
31	3	credit	45.00	team_target_bonus_3_inv_5_1776973907	2.50% Target Bonus (Team Vol: ₹5400.00)	2026-04-24 01:21:47.954465	225.0000	\N	\N
32	1	credit	54.00	level_commission_1_2_inv_5_1776973907	3.00% Level 2 Commission from User #5	2026-04-24 01:21:47.954465	34554.0000	\N	\N
33	1	credit	45.00	team_target_bonus_1_inv_5_1776973907	2.50% Target Bonus (Team Vol: ₹5400.00)	2026-04-24 01:21:47.954465	34599.0000	\N	\N
34	5	credit	180.00	self_cashback_5_inv_5_1776973916	5.00% Cashback on package purchase	2026-04-24 01:21:56.47795	270.0000	\N	\N
35	3	credit	360.00	direct_referral_3_inv_5_1776973916	10.00% Direct Referral from User #5	2026-04-24 01:21:56.47795	585.0000	\N	\N
36	3	credit	90.00	team_target_bonus_3_inv_5_1776973916	2.50% Target Bonus (Team Vol: ₹9000.00)	2026-04-24 01:21:56.47795	675.0000	\N	\N
37	1	credit	108.00	level_commission_1_2_inv_5_1776973916	3.00% Level 2 Commission from User #5	2026-04-24 01:21:56.47795	34707.0000	\N	\N
38	1	credit	90.00	team_target_bonus_1_inv_5_1776973916	2.50% Target Bonus (Team Vol: ₹9000.00)	2026-04-24 01:21:56.47795	34797.0000	\N	\N
39	5	credit	90.00	self_cashback_5_inv_5_1776973995	5.00% Cashback on package purchase	2026-04-24 01:23:15.473231	360.0000	\N	\N
40	3	credit	180.00	direct_referral_3_inv_5_1776973995	10.00% Direct Referral from User #5	2026-04-24 01:23:15.473231	855.0000	\N	\N
41	3	credit	45.00	team_target_bonus_3_inv_5_1776973995	2.50% Target Bonus (Team Vol: ₹10800.00)	2026-04-24 01:23:15.473231	900.0000	\N	\N
42	1	credit	54.00	level_commission_1_2_inv_5_1776973995	3.00% Level 2 Commission from User #5	2026-04-24 01:23:15.473231	34851.0000	\N	\N
43	1	credit	45.00	team_target_bonus_1_inv_5_1776973995	2.50% Target Bonus (Team Vol: ₹10800.00)	2026-04-24 01:23:15.473231	34896.0000	\N	\N
44	5	credit	90.00	self_cashback_5_inv_5_1776974117	5.00% Cashback on package purchase	2026-04-24 01:25:17.610567	450.0000	\N	\N
45	3	credit	180.00	direct_referral_3_inv_5_1776974117	10.00% Direct Referral from User #5	2026-04-24 01:25:17.610567	1080.0000	\N	\N
46	3	credit	45.00	team_target_bonus_3_inv_5_1776974117	2.50% Target Bonus (Team Vol: ₹12600.00)	2026-04-24 01:25:17.610567	1125.0000	\N	\N
47	1	credit	54.00	level_commission_1_2_inv_5_1776974117	3.00% Level 2 Commission from User #5	2026-04-24 01:25:17.610567	34950.0000	\N	\N
48	1	credit	45.00	team_target_bonus_1_inv_5_1776974117	2.50% Target Bonus (Team Vol: ₹12600.00)	2026-04-24 01:25:17.610567	34995.0000	\N	\N
49	5	credit	90.00	self_cashback_5_inv_5_1776975030	5.00% Cashback on package purchase	2026-04-24 01:40:30.678767	540.0000	\N	\N
50	3	credit	180.00	direct_referral_3_inv_5_1776975030	10.00% Direct Referral from User #5	2026-04-24 01:40:30.678767	1305.0000	\N	\N
51	3	credit	45.00	team_target_bonus_3_inv_5_1776975030	2.50% Target Bonus (Team Vol: ₹14400.00)	2026-04-24 01:40:30.678767	1350.0000	\N	\N
52	1	credit	54.00	level_commission_1_2_inv_5_1776975030	3.00% Level 2 Commission from User #5	2026-04-24 01:40:30.678767	35049.0000	\N	\N
53	1	credit	45.00	team_target_bonus_1_inv_5_1776975030	2.50% Target Bonus (Team Vol: ₹14400.00)	2026-04-24 01:40:30.678767	35094.0000	\N	\N
55	10001	credit	180.00	self_cashback_10001	5.00% Cashback on package purchase	2026-04-26 02:00:09.788015	180.0000	\N	\N
56	1	credit	360.00	direct_referral_10001_1	10.00% Direct Referral from User #10001	2026-04-26 02:00:09.788015	35484.0000	\N	\N
57	1	credit	90.00	team_target_bonus_10001_1	2.50% Team Target Bonus (Vol: ₹18000.00)	2026-04-26 02:00:09.788015	35574.0000	\N	\N
58	1	credit	90.00	self_cashback_1	5.00% Cashback on package purchase	2026-04-26 02:12:10.578517	35664.0000	\N	\N
8	1	debit	-500.00	withdraw_1	Withdraw approved	2026-04-21 15:59:25.522892	29500.00	\N	\N
54	5	debit	-100.00	withdraw_2	Withdraw approved	2026-04-26 00:04:22.544085	440.00	\N	\N
59	1	debit	-100.00	withdraw_3	Withdraw approved	2026-04-27 09:14:16.021535	35564.00	\N	\N
60	1	debit	-100.00	withdraw_4	Withdraw approved	2026-04-27 17:27:19.660157	35464.00	\N	\N
61	1	debit	-1000.00	withdraw_5	Withdraw approved	2026-04-28 11:39:46.674677	34464.00	\N	\N
62	1	debit	-2000.00	withdraw_6	Withdraw approved	2026-04-28 11:41:31.065664	32464.00	\N	\N
63	1	debit	-5000.00	withdraw_7	Withdraw approved	2026-04-28 11:48:23.265307	27464.00	\N	\N
64	1	debit	-2000.00	withdraw_8	Withdraw approved	2026-04-28 12:27:40.633305	25464.00	\N	\N
65	1	debit	-1000.00	withdraw_9	Withdraw approved	2026-04-28 12:37:59.082678	24464.00	\N	\N
66	1	debit	-5000.00	withdraw_10	Withdraw approved	2026-05-26 00:45:21.240495	19464.00	\N	\N
67	1	debit	-1000.00	withdraw_15	Withdraw approved	2026-08-24 13:30:15.721241	18464.00	\N	\N
68	1	debit	-1000.00	withdraw_16	Withdraw approved	2026-09-05 09:19:10.684908	17464.00	\N	\N
\.


--
-- Data for Name: wallets; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.wallets (user_id, balance) FROM stdin;
\.


--
-- Data for Name: withdraw_requests; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.withdraw_requests (id, user_id, amount, status, requested_at, processed_at, payout_method, payout_details, admin_note) FROM stdin;
1	1	500.00	approved	2026-04-21 12:43:49.466602	2026-04-21 15:59:25.522892	bank	\N	\N
2	5	100.00	approved	2026-04-25 01:24:01.770795	2026-04-26 00:04:22.544085	upi	{"upiId":"8745019117@ybl","upiMobile":"8745019117","bankAccount":"","bankIfsc":""}	\N
3	1	100.00	approved	2026-04-26 17:19:23.754623	2026-04-27 09:14:16.021535	upi	{"upiId":"8745019117@ybl","upiMobile":"8745019117","bankAccount":"","bankIfsc":""}	\N
4	1	100.00	approved	2026-04-27 09:31:37.827818	2026-04-27 17:27:19.660157	upi	{"upiId":"8745019117","upiMobile":"8745019117@ybl","bankAccount":"","bankIfsc":""}	\N
5	1	1000.00	approved	2026-04-28 11:39:21.311094	2026-04-28 11:39:46.674677	upi	{"upiId":"8745019117","upiMobile":"8745019117@YBL","bankAccount":"","bankIfsc":""}	\N
6	1	2000.00	approved	2026-04-28 11:41:01.477098	2026-04-28 11:41:31.065664	upi	{"upiId":"8745019117","upiMobile":"8745019117@YBL","bankAccount":"","bankIfsc":""}	\N
7	1	5000.00	approved	2026-04-28 11:48:13.942761	2026-04-28 11:48:23.265307	upi	{"upiId":"8745019117","upiMobile":"8745019117@YBL","bankAccount":"","bankIfsc":""}	\N
8	1	2000.00	approved	2026-04-28 12:27:32.292609	2026-04-28 12:27:40.633305	upi	{"upiId":"8745019117","upiMobile":"8745019117@ybl","bankAccount":"","bankIfsc":""}	\N
9	1	1000.00	approved	2026-04-28 12:37:45.062789	2026-04-28 12:37:59.082678	upi	{"upiId":"8745019117","upiMobile":"8745019117@ybl","bankAccount":"","bankIfsc":""}	\N
10	1	5000.00	approved	2026-05-26 00:27:45.882079	2026-05-26 00:45:21.240495	upi	{"upiId":"8700601083@ybl","upiMobile":"8700601083","bankAccount":"","bankIfsc":""}	\N
11	1	1000.00	rejected	2026-05-26 00:45:58.414444	2026-05-26 11:25:23.649522	upi	{"upiId":"8700601083","upiMobile":"8700601083","bankAccount":"","bankIfsc":""}	Rejected by Admin during review
12	1	1000.00	rejected	2026-05-26 15:33:41.654273	2026-06-02 13:47:27.417508	upi	{"upiId":"8700601083","upiMobile":"8700601083","bankAccount":"","bankIfsc":""}	Rejected by Admin during review
13	1	1000.00	rejected	2026-06-02 13:48:33.157002	2026-06-02 14:34:35.703755	upi	{"upiId":"8700601083","upiMobile":"8700601083","bankAccount":"","bankIfsc":""}	Rejected by Admin during review
14	1	500.00	rejected	2026-08-24 13:05:00.478437	2026-08-24 13:14:02.153383	upi	{"upiId":"8700601083","upiMobile":"8700601083","bankAccount":"","bankIfsc":""}	Rejected by Admin during review
15	1	1000.00	approved	2026-08-24 13:14:32.711649	2026-08-24 13:30:15.721241	upi	{"upiId":"8700601083","upiMobile":"8700601083","bankAccount":"","bankIfsc":""}	\N
16	1	1000.00	approved	2026-09-05 09:16:33.688627	2026-09-05 09:19:10.684908	upi	{"upiId":"870070707","upiMobile":"870070707","bankAccount":"","bankIfsc":""}	\N
\.


--
-- Data for Name: yoyo_lock; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.yoyo_lock (locked, ctime, pid) FROM stdin;
\.


--
-- Name: admin_activity_logs_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.admin_activity_logs_id_seq', 1, false);


--
-- Name: admin_audit_logs_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.admin_audit_logs_id_seq', 1, false);


--
-- Name: admin_logs_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.admin_logs_id_seq', 1, false);


--
-- Name: audit_logs_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.audit_logs_id_seq', 41, true);


--
-- Name: commission_plan_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.commission_plan_id_seq', 91, true);


--
-- Name: commission_recalc_logs_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.commission_recalc_logs_id_seq', 1, false);


--
-- Name: commissions_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.commissions_id_seq', 51, true);


--
-- Name: company_profile_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.company_profile_id_seq', 1, true);


--
-- Name: company_settings_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.company_settings_id_seq', 1, false);


--
-- Name: cron_job_logs_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.cron_job_logs_id_seq', 1, false);


--
-- Name: db_backup_logs_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.db_backup_logs_id_seq', 21, true);


--
-- Name: epins_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.epins_id_seq', 1, false);


--
-- Name: kyc_details_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.kyc_details_id_seq', 5, true);


--
-- Name: kyc_requests_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.kyc_requests_id_seq', 1, false);


--
-- Name: notification_logs_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.notification_logs_id_seq', 1, false);


--
-- Name: notifications_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.notifications_id_seq', 1, false);


--
-- Name: orders_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.orders_id_seq', 8, true);


--
-- Name: otp_verifications_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.otp_verifications_id_seq', 3, true);


--
-- Name: packages_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.packages_id_seq', 1, true);


--
-- Name: plan_images_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.plan_images_id_seq', 8, true);


--
-- Name: rank_rules_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.rank_rules_id_seq', 40, true);


--
-- Name: ranks_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.ranks_id_seq', 5, true);


--
-- Name: roles_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.roles_id_seq', 3, true);


--
-- Name: subscription_plans_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.subscription_plans_id_seq', 5, true);


--
-- Name: support_tickets_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.support_tickets_id_seq', 1, false);


--
-- Name: team_target_bonuses_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.team_target_bonuses_id_seq', 3, true);


--
-- Name: ticket_messages_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.ticket_messages_id_seq', 1, false);


--
-- Name: user_bonus_history_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.user_bonus_history_id_seq', 1, false);


--
-- Name: user_packages_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.user_packages_id_seq', 19, true);


--
-- Name: users_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.users_id_seq', 10001, true);


--
-- Name: wallet_ledger_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.wallet_ledger_id_seq', 68, true);


--
-- Name: withdraw_requests_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.withdraw_requests_id_seq', 16, true);


--
-- Name: _yoyo_log _yoyo_log_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public._yoyo_log
    ADD CONSTRAINT _yoyo_log_pkey PRIMARY KEY (id);


--
-- Name: _yoyo_migration _yoyo_migration_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public._yoyo_migration
    ADD CONSTRAINT _yoyo_migration_pkey PRIMARY KEY (migration_hash);


--
-- Name: _yoyo_version _yoyo_version_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public._yoyo_version
    ADD CONSTRAINT _yoyo_version_pkey PRIMARY KEY (version);


--
-- Name: admin_activity_logs admin_activity_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.admin_activity_logs
    ADD CONSTRAINT admin_activity_logs_pkey PRIMARY KEY (id);


--
-- Name: admin_audit_logs admin_audit_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.admin_audit_logs
    ADD CONSTRAINT admin_audit_logs_pkey PRIMARY KEY (id);


--
-- Name: admin_logs admin_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.admin_logs
    ADD CONSTRAINT admin_logs_pkey PRIMARY KEY (id);


--
-- Name: audit_logs audit_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.audit_logs
    ADD CONSTRAINT audit_logs_pkey PRIMARY KEY (id);


--
-- Name: commission_plan commission_plan_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.commission_plan
    ADD CONSTRAINT commission_plan_pkey PRIMARY KEY (id);


--
-- Name: commission_recalc_logs commission_recalc_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.commission_recalc_logs
    ADD CONSTRAINT commission_recalc_logs_pkey PRIMARY KEY (id);


--
-- Name: commissions commissions_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.commissions
    ADD CONSTRAINT commissions_pkey PRIMARY KEY (id);


--
-- Name: company_profile company_profile_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.company_profile
    ADD CONSTRAINT company_profile_pkey PRIMARY KEY (id);


--
-- Name: company_settings company_settings_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.company_settings
    ADD CONSTRAINT company_settings_pkey PRIMARY KEY (id);


--
-- Name: cron_job_logs cron_job_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cron_job_logs
    ADD CONSTRAINT cron_job_logs_pkey PRIMARY KEY (id);


--
-- Name: db_backup_logs db_backup_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.db_backup_logs
    ADD CONSTRAINT db_backup_logs_pkey PRIMARY KEY (id);


--
-- Name: epins epins_pin_code_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.epins
    ADD CONSTRAINT epins_pin_code_key UNIQUE (pin_code);


--
-- Name: epins epins_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.epins
    ADD CONSTRAINT epins_pkey PRIMARY KEY (id);


--
-- Name: global_commissions global_commissions_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.global_commissions
    ADD CONSTRAINT global_commissions_pkey PRIMARY KEY (setting_key);


--
-- Name: kyc_details kyc_details_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.kyc_details
    ADD CONSTRAINT kyc_details_pkey PRIMARY KEY (id);


--
-- Name: kyc_details kyc_details_user_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.kyc_details
    ADD CONSTRAINT kyc_details_user_id_key UNIQUE (user_id);


--
-- Name: kyc_requests kyc_requests_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.kyc_requests
    ADD CONSTRAINT kyc_requests_pkey PRIMARY KEY (id);


--
-- Name: level_commissions level_commissions_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.level_commissions
    ADD CONSTRAINT level_commissions_pkey PRIMARY KEY (level);


--
-- Name: notification_logs notification_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.notification_logs
    ADD CONSTRAINT notification_logs_pkey PRIMARY KEY (id);


--
-- Name: notifications notifications_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_pkey PRIMARY KEY (id);


--
-- Name: orders orders_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.orders
    ADD CONSTRAINT orders_pkey PRIMARY KEY (id);


--
-- Name: otp_verifications otp_verifications_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.otp_verifications
    ADD CONSTRAINT otp_verifications_pkey PRIMARY KEY (id);


--
-- Name: packages packages_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.packages
    ADD CONSTRAINT packages_pkey PRIMARY KEY (id);


--
-- Name: plan_images plan_images_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.plan_images
    ADD CONSTRAINT plan_images_pkey PRIMARY KEY (id);


--
-- Name: rank_rules rank_rules_level_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.rank_rules
    ADD CONSTRAINT rank_rules_level_key UNIQUE (level);


--
-- Name: rank_rules rank_rules_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.rank_rules
    ADD CONSTRAINT rank_rules_pkey PRIMARY KEY (id);


--
-- Name: ranks ranks_name_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.ranks
    ADD CONSTRAINT ranks_name_key UNIQUE (name);


--
-- Name: ranks ranks_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.ranks
    ADD CONSTRAINT ranks_pkey PRIMARY KEY (id);


--
-- Name: roles roles_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.roles
    ADD CONSTRAINT roles_pkey PRIMARY KEY (id);


--
-- Name: roles roles_role_name_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.roles
    ADD CONSTRAINT roles_role_name_key UNIQUE (role_name);


--
-- Name: subscription_plans subscription_plans_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.subscription_plans
    ADD CONSTRAINT subscription_plans_pkey PRIMARY KEY (id);


--
-- Name: support_tickets support_tickets_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.support_tickets
    ADD CONSTRAINT support_tickets_pkey PRIMARY KEY (id);


--
-- Name: team_target_bonuses team_target_bonuses_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.team_target_bonuses
    ADD CONSTRAINT team_target_bonuses_pkey PRIMARY KEY (id);


--
-- Name: ticket_messages ticket_messages_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.ticket_messages
    ADD CONSTRAINT ticket_messages_pkey PRIMARY KEY (id);


--
-- Name: commissions unique_commission; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.commissions
    ADD CONSTRAINT unique_commission UNIQUE (earner_id, from_user_id, level, commission_type);


--
-- Name: commission_plan unique_level; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.commission_plan
    ADD CONSTRAINT unique_level UNIQUE (level);


--
-- Name: users unique_referral_code; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT unique_referral_code UNIQUE (referral_code);


--
-- Name: user_bonus_history user_bonus_history_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_bonus_history
    ADD CONSTRAINT user_bonus_history_pkey PRIMARY KEY (id);


--
-- Name: user_bonus_history user_bonus_history_user_id_rank_level_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_bonus_history
    ADD CONSTRAINT user_bonus_history_user_id_rank_level_key UNIQUE (user_id, rank_level);


--
-- Name: user_packages user_packages_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_packages
    ADD CONSTRAINT user_packages_pkey PRIMARY KEY (id);


--
-- Name: users users_email_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_email_key UNIQUE (email);


--
-- Name: users users_phone_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_phone_key UNIQUE (phone);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: users users_referral_code_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_referral_code_key UNIQUE (referral_code);


--
-- Name: wallet_ledger wallet_ledger_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wallet_ledger
    ADD CONSTRAINT wallet_ledger_pkey PRIMARY KEY (id);


--
-- Name: wallets wallets_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wallets
    ADD CONSTRAINT wallets_pkey PRIMARY KEY (user_id);


--
-- Name: withdraw_requests withdraw_requests_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.withdraw_requests
    ADD CONSTRAINT withdraw_requests_pkey PRIMARY KEY (id);


--
-- Name: yoyo_lock yoyo_lock_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.yoyo_lock
    ADD CONSTRAINT yoyo_lock_pkey PRIMARY KEY (locked);


--
-- Name: idx_admin_activity_admin; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_admin_activity_admin ON public.admin_activity_logs USING btree (admin_id);


--
-- Name: idx_audit_action; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_audit_action ON public.audit_logs USING btree (action);


--
-- Name: idx_audit_user; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_audit_user ON public.audit_logs USING btree (user_id);


--
-- Name: idx_commissions_earner; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_commissions_earner ON public.commissions USING btree (earner_id);


--
-- Name: idx_commissions_fromuser; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_commissions_fromuser ON public.commissions USING btree (from_user_id);


--
-- Name: idx_cron_job_logs_name; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_cron_job_logs_name ON public.cron_job_logs USING btree (job_name);


--
-- Name: idx_orders_user; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_orders_user ON public.orders USING btree (user_id, created_at DESC);


--
-- Name: idx_otp_user_lookup; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_otp_user_lookup ON public.otp_verifications USING btree (user_id, otp_code);


--
-- Name: idx_users_active; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_users_active ON public.users USING btree (is_active);


--
-- Name: idx_users_created; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_users_created ON public.users USING btree (created_at DESC);


--
-- Name: idx_users_email_trgm; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_users_email_trgm ON public.users USING gin (email public.gin_trgm_ops);


--
-- Name: idx_users_name_trgm; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_users_name_trgm ON public.users USING gin (full_name public.gin_trgm_ops);


--
-- Name: idx_users_phone_trgm; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_users_phone_trgm ON public.users USING gin (phone public.gin_trgm_ops);


--
-- Name: idx_users_rank; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_users_rank ON public.users USING btree (rank_level);


--
-- Name: idx_users_sponsor; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_users_sponsor ON public.users USING btree (sponsor_id);


--
-- Name: idx_users_sponsor_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_users_sponsor_id ON public.users USING btree (sponsor_id);


--
-- Name: idx_users_tree_path; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_users_tree_path ON public.users USING gist (tree_path);


--
-- Name: idx_wallet_user_created; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_wallet_user_created ON public.wallet_ledger USING btree (user_id, created_at DESC);


--
-- Name: idx_wallet_user_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_wallet_user_id ON public.wallet_ledger USING btree (user_id);


--
-- Name: idx_withdraw_status; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_withdraw_status ON public.withdraw_requests USING btree (status);


--
-- Name: idx_withdraw_user; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_withdraw_user ON public.withdraw_requests USING btree (user_id);


--
-- Name: uq_commission_plan_level; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX uq_commission_plan_level ON public.commission_plan USING btree (level);


--
-- Name: uq_commissions_earner_order_level; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX uq_commissions_earner_order_level ON public.commissions USING btree (earner_id, order_id, level) WHERE (order_id IS NOT NULL);


--
-- Name: uq_global_comm_key; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX uq_global_comm_key ON public.global_commissions USING btree (setting_key);


--
-- Name: uq_level_comm_level; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX uq_level_comm_level ON public.level_commissions USING btree (level);


--
-- Name: uq_rank_rules_level; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX uq_rank_rules_level ON public.rank_rules USING btree (level);


--
-- Name: wallet_ledger trg_sync_ledger_reference; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER trg_sync_ledger_reference BEFORE INSERT OR UPDATE ON public.wallet_ledger FOR EACH ROW EXECUTE FUNCTION public.sync_ledger_reference();


--
-- Name: users trg_user_insert_counters; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER trg_user_insert_counters AFTER INSERT ON public.users FOR EACH ROW EXECUTE FUNCTION public.after_user_insert_counters();


--
-- Name: users trg_users_tree; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER trg_users_tree BEFORE INSERT OR UPDATE OF sponsor_id ON public.users FOR EACH ROW EXECUTE FUNCTION public.users_tree_maintenance();


--
-- Name: commissions commissions_order_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.commissions
    ADD CONSTRAINT commissions_order_id_fkey FOREIGN KEY (order_id) REFERENCES public.orders(id) ON DELETE CASCADE;


--
-- Name: commissions fk_commission_earner; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.commissions
    ADD CONSTRAINT fk_commission_earner FOREIGN KEY (earner_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: commissions fk_commission_from_user; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.commissions
    ADD CONSTRAINT fk_commission_from_user FOREIGN KEY (from_user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: kyc_requests fk_kyc_user; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.kyc_requests
    ADD CONSTRAINT fk_kyc_user FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: users fk_role; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT fk_role FOREIGN KEY (role_id) REFERENCES public.roles(id) ON DELETE RESTRICT;


--
-- Name: users fk_sponsor; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT fk_sponsor FOREIGN KEY (sponsor_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: kyc_details fk_user; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.kyc_details
    ADD CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: wallet_ledger fk_wallet_user; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wallet_ledger
    ADD CONSTRAINT fk_wallet_user FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: withdraw_requests fk_withdraw_user; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.withdraw_requests
    ADD CONSTRAINT fk_withdraw_user FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: notification_logs notification_logs_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.notification_logs
    ADD CONSTRAINT notification_logs_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: orders orders_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.orders
    ADD CONSTRAINT orders_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: otp_verifications otp_verifications_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.otp_verifications
    ADD CONSTRAINT otp_verifications_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: plan_images plan_images_plan_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.plan_images
    ADD CONSTRAINT plan_images_plan_id_fkey FOREIGN KEY (plan_id) REFERENCES public.subscription_plans(id) ON DELETE CASCADE;


--
-- Name: support_tickets support_tickets_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.support_tickets
    ADD CONSTRAINT support_tickets_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: user_bonus_history user_bonus_history_rank_level_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_bonus_history
    ADD CONSTRAINT user_bonus_history_rank_level_fkey FOREIGN KEY (rank_level) REFERENCES public.rank_rules(level);


--
-- Name: user_bonus_history user_bonus_history_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_bonus_history
    ADD CONSTRAINT user_bonus_history_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- PostgreSQL database dump complete
--

\unrestrict Ug2wO60n5QDDfXyvoe8rNjPsZdbtKexamfaN1pq11yKWiG3UcyBrgvIr7RF4Qp0

