--
-- PostgreSQL database dump
--

\restrict zBaojnovwIC4OiM33BPqeTIKUymhfWXtXzoFy6Ah2i3sabcC3KLdKG6FnS4hI59

-- Dumped from database version 18.4
-- Dumped by pg_dump version 18.4

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


--
-- Name: brands; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.brands (
    id integer NOT NULL,
    name character varying(150) NOT NULL,
    slug character varying(180) NOT NULL,
    description text,
    logo_url character varying(500),
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: brands_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.brands_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: brands_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.brands_id_seq OWNED BY public.brands.id;


--
-- Name: events_cache; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.events_cache (
    id integer NOT NULL,
    country_code character varying(5),
    event_name character varying(200),
    event_date timestamp without time zone,
    event_type character varying(50),
    raw_data jsonb,
    fetched_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: events_cache_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.events_cache_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: events_cache_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.events_cache_id_seq OWNED BY public.events_cache.id;


--
-- Name: notifications; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.notifications (
    id integer NOT NULL,
    user_id integer,
    type character varying(50) NOT NULL,
    title character varying(255) NOT NULL,
    message text,
    link text,
    post_id integer,
    is_read boolean DEFAULT false NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: notifications_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.notifications_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: notifications_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.notifications_id_seq OWNED BY public.notifications.id;


--
-- Name: post_approval_stages; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.post_approval_stages (
    id integer NOT NULL,
    scheduled_post_id integer NOT NULL,
    hr_status character varying(20) DEFAULT 'pending'::character varying NOT NULL,
    hr_approved_at timestamp without time zone,
    hr_rejection_reason text,
    superadmin_status character varying(20) DEFAULT 'pending'::character varying NOT NULL,
    superadmin_approved_at timestamp without time zone,
    superadmin_rejection_reason text,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    admin_status character varying(20) DEFAULT 'pending'::character varying NOT NULL,
    admin_approved_at timestamp without time zone,
    admin_rejection_reason text
);


--
-- Name: post_approval_stages_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.post_approval_stages_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: post_approval_stages_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.post_approval_stages_id_seq OWNED BY public.post_approval_stages.id;


--
-- Name: post_targets; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.post_targets (
    id integer NOT NULL,
    scheduled_post_id integer NOT NULL,
    platform character varying(50) NOT NULL,
    status character varying(50) DEFAULT 'pending'::character varying NOT NULL,
    error_message text,
    posted_at timestamp without time zone,
    social_account_id integer
);


--
-- Name: post_targets_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.post_targets_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: post_targets_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.post_targets_id_seq OWNED BY public.post_targets.id;


--
-- Name: post_templates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.post_templates (
    id integer NOT NULL,
    user_id integer NOT NULL,
    content_text text NOT NULL,
    media_url text,
    platforms character varying[] NOT NULL,
    recurrence_type character varying(50) DEFAULT 'ONE_TIME'::character varying NOT NULL,
    interval_days integer DEFAULT 1 NOT NULL,
    start_date timestamp without time zone NOT NULL,
    end_date timestamp without time zone,
    max_occurrences integer,
    occurrence_count integer DEFAULT 0 NOT NULL,
    timezone character varying(100) DEFAULT 'UTC'::character varying NOT NULL,
    status character varying(50) DEFAULT 'active'::character varying NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: post_templates_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.post_templates_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: post_templates_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.post_templates_id_seq OWNED BY public.post_templates.id;


--
-- Name: rag_chat_history; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.rag_chat_history (
    id integer NOT NULL,
    user_id integer,
    role character varying(10) NOT NULL,
    content text NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: rag_chat_history_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.rag_chat_history_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: rag_chat_history_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.rag_chat_history_id_seq OWNED BY public.rag_chat_history.id;


--
-- Name: scheduled_posts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.scheduled_posts (
    id integer NOT NULL,
    template_id integer NOT NULL,
    scheduled_at timestamp without time zone NOT NULL,
    confirmation_sent_at timestamp without time zone,
    confirmation_token text,
    superadmin_token text,
    token_used boolean DEFAULT false NOT NULL,
    superadmin_token_used boolean DEFAULT false NOT NULL,
    status character varying(50) DEFAULT 'scheduled'::character varying NOT NULL,
    approved_at timestamp without time zone,
    rejection_reason text,
    ai_generated boolean DEFAULT false NOT NULL,
    trigger_type character varying(50),
    trigger_name character varying(200),
    reposted_from_id integer,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    admin_token text,
    admin_token_used boolean DEFAULT false
);


--
-- Name: scheduled_posts_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.scheduled_posts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: scheduled_posts_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.scheduled_posts_id_seq OWNED BY public.scheduled_posts.id;


--
-- Name: social_accounts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.social_accounts (
    id integer NOT NULL,
    user_id integer NOT NULL,
    platform character varying(50) NOT NULL,
    access_token text NOT NULL,
    refresh_token text,
    token_expires_at timestamp without time zone,
    page_id character varying(255),
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    account_name character varying(255),
    account_email character varying(255),
    brand_id integer
);


--
-- Name: social_accounts_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.social_accounts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: social_accounts_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.social_accounts_id_seq OWNED BY public.social_accounts.id;


--
-- Name: trends_cache; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.trends_cache (
    id integer NOT NULL,
    country_code character varying(10),
    platform character varying(50),
    topic text,
    score double precision,
    raw_data jsonb,
    fetched_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: trends_cache_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.trends_cache_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: trends_cache_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.trends_cache_id_seq OWNED BY public.trends_cache.id;


--
-- Name: user_brands; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_brands (
    id integer NOT NULL,
    user_id integer NOT NULL,
    brand_id integer NOT NULL,
    role character varying(50) DEFAULT 'owner'::character varying NOT NULL,
    is_default boolean DEFAULT false NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: user_brands_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.user_brands_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: user_brands_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.user_brands_id_seq OWNED BY public.user_brands.id;


--
-- Name: user_profiles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_profiles (
    id integer NOT NULL,
    user_id integer NOT NULL,
    persona character varying(50),
    industry character varying(100),
    brand_name character varying(100),
    tone character varying(50),
    audience character varying(100),
    country_code character varying(5),
    language character varying(20),
    posts_per_week integer DEFAULT 3 NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    logo_url character varying(500),
    footer_enabled boolean DEFAULT false NOT NULL,
    footer_text character varying(500),
    footer_url character varying(500),
    overlay_text text,
    overlay_position character varying(50) DEFAULT 'bottom-center'::character varying NOT NULL,
    overlay_text_size integer DEFAULT 48 NOT NULL
);


--
-- Name: user_profiles_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.user_profiles_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: user_profiles_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.user_profiles_id_seq OWNED BY public.user_profiles.id;


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    id integer NOT NULL,
    email character varying(255) NOT NULL,
    password_hash text NOT NULL,
    timezone character varying(100) DEFAULT 'UTC'::character varying NOT NULL,
    role character varying(20) DEFAULT 'user'::character varying NOT NULL,
    admin_id integer,
    invite_code character varying(50),
    last_login_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    org_name character varying(150),
    address character varying(255)
);


--
-- Name: users_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;


--
-- Name: brands id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.brands ALTER COLUMN id SET DEFAULT nextval('public.brands_id_seq'::regclass);


--
-- Name: events_cache id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.events_cache ALTER COLUMN id SET DEFAULT nextval('public.events_cache_id_seq'::regclass);


--
-- Name: notifications id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notifications ALTER COLUMN id SET DEFAULT nextval('public.notifications_id_seq'::regclass);


--
-- Name: post_approval_stages id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.post_approval_stages ALTER COLUMN id SET DEFAULT nextval('public.post_approval_stages_id_seq'::regclass);


--
-- Name: post_targets id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.post_targets ALTER COLUMN id SET DEFAULT nextval('public.post_targets_id_seq'::regclass);


--
-- Name: post_templates id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.post_templates ALTER COLUMN id SET DEFAULT nextval('public.post_templates_id_seq'::regclass);


--
-- Name: rag_chat_history id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rag_chat_history ALTER COLUMN id SET DEFAULT nextval('public.rag_chat_history_id_seq'::regclass);


--
-- Name: scheduled_posts id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.scheduled_posts ALTER COLUMN id SET DEFAULT nextval('public.scheduled_posts_id_seq'::regclass);


--
-- Name: social_accounts id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.social_accounts ALTER COLUMN id SET DEFAULT nextval('public.social_accounts_id_seq'::regclass);


--
-- Name: trends_cache id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trends_cache ALTER COLUMN id SET DEFAULT nextval('public.trends_cache_id_seq'::regclass);


--
-- Name: user_brands id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_brands ALTER COLUMN id SET DEFAULT nextval('public.user_brands_id_seq'::regclass);


--
-- Name: user_profiles id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_profiles ALTER COLUMN id SET DEFAULT nextval('public.user_profiles_id_seq'::regclass);


--
-- Name: users id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: brands brands_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.brands
    ADD CONSTRAINT brands_pkey PRIMARY KEY (id);


--
-- Name: events_cache events_cache_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.events_cache
    ADD CONSTRAINT events_cache_pkey PRIMARY KEY (id);


--
-- Name: notifications notifications_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_pkey PRIMARY KEY (id);


--
-- Name: post_approval_stages post_approval_stages_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.post_approval_stages
    ADD CONSTRAINT post_approval_stages_pkey PRIMARY KEY (id);


--
-- Name: post_approval_stages post_approval_stages_scheduled_post_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.post_approval_stages
    ADD CONSTRAINT post_approval_stages_scheduled_post_id_key UNIQUE (scheduled_post_id);


--
-- Name: post_targets post_targets_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.post_targets
    ADD CONSTRAINT post_targets_pkey PRIMARY KEY (id);


--
-- Name: post_templates post_templates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.post_templates
    ADD CONSTRAINT post_templates_pkey PRIMARY KEY (id);


--
-- Name: rag_chat_history rag_chat_history_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rag_chat_history
    ADD CONSTRAINT rag_chat_history_pkey PRIMARY KEY (id);


--
-- Name: scheduled_posts scheduled_posts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.scheduled_posts
    ADD CONSTRAINT scheduled_posts_pkey PRIMARY KEY (id);


--
-- Name: social_accounts social_accounts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.social_accounts
    ADD CONSTRAINT social_accounts_pkey PRIMARY KEY (id);


--
-- Name: trends_cache trends_cache_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trends_cache
    ADD CONSTRAINT trends_cache_pkey PRIMARY KEY (id);


--
-- Name: brands uq_brands_slug; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.brands
    ADD CONSTRAINT uq_brands_slug UNIQUE (slug);


--
-- Name: social_accounts uq_social_accounts_user_brand_platform_page; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.social_accounts
    ADD CONSTRAINT uq_social_accounts_user_brand_platform_page UNIQUE (user_id, brand_id, platform, page_id);


--
-- Name: user_brands uq_user_brand; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_brands
    ADD CONSTRAINT uq_user_brand UNIQUE (user_id, brand_id);


--
-- Name: user_brands user_brands_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_brands
    ADD CONSTRAINT user_brands_pkey PRIMARY KEY (id);


--
-- Name: user_profiles user_profiles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_profiles
    ADD CONSTRAINT user_profiles_pkey PRIMARY KEY (id);


--
-- Name: user_profiles user_profiles_user_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_profiles
    ADD CONSTRAINT user_profiles_user_id_key UNIQUE (user_id);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: idx_approval_stages_admin_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_approval_stages_admin_status ON public.post_approval_stages USING btree (admin_status);


--
-- Name: idx_approval_stages_post; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_approval_stages_post ON public.post_approval_stages USING btree (scheduled_post_id);


--
-- Name: idx_notifications_user_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_notifications_user_created ON public.notifications USING btree (user_id, created_at DESC);


--
-- Name: idx_notifications_user_unread; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_notifications_user_unread ON public.notifications USING btree (user_id) WHERE (is_read = false);


--
-- Name: idx_rag_chat_history_user_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_rag_chat_history_user_created ON public.rag_chat_history USING btree (user_id, created_at DESC);


--
-- Name: idx_users_invite_code; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_users_invite_code ON public.users USING btree (invite_code) WHERE (invite_code IS NOT NULL);


--
-- Name: ix_brands_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_brands_id ON public.brands USING btree (id);


--
-- Name: ix_events_cache_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_events_cache_id ON public.events_cache USING btree (id);


--
-- Name: ix_notifications_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_notifications_id ON public.notifications USING btree (id);


--
-- Name: ix_post_approval_stages_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_post_approval_stages_id ON public.post_approval_stages USING btree (id);


--
-- Name: ix_post_targets_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_post_targets_id ON public.post_targets USING btree (id);


--
-- Name: ix_post_templates_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_post_templates_id ON public.post_templates USING btree (id);


--
-- Name: ix_rag_chat_history_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_rag_chat_history_id ON public.rag_chat_history USING btree (id);


--
-- Name: ix_scheduled_posts_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_scheduled_posts_id ON public.scheduled_posts USING btree (id);


--
-- Name: ix_social_accounts_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_social_accounts_id ON public.social_accounts USING btree (id);


--
-- Name: ix_trends_cache_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_trends_cache_id ON public.trends_cache USING btree (id);


--
-- Name: ix_user_brands_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_user_brands_id ON public.user_brands USING btree (id);


--
-- Name: ix_user_profiles_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_user_profiles_id ON public.user_profiles USING btree (id);


--
-- Name: ix_users_email; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_users_email ON public.users USING btree (email);


--
-- Name: ix_users_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_users_id ON public.users USING btree (id);


--
-- Name: uq_user_brands_one_default; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_user_brands_one_default ON public.user_brands USING btree (user_id) WHERE (is_default = true);


--
-- Name: post_targets fk_post_targets_social_account; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.post_targets
    ADD CONSTRAINT fk_post_targets_social_account FOREIGN KEY (social_account_id) REFERENCES public.social_accounts(id) ON DELETE SET NULL;


--
-- Name: social_accounts fk_social_accounts_brand_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.social_accounts
    ADD CONSTRAINT fk_social_accounts_brand_id FOREIGN KEY (brand_id) REFERENCES public.brands(id) ON DELETE CASCADE;


--
-- Name: notifications notifications_post_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_post_id_fkey FOREIGN KEY (post_id) REFERENCES public.scheduled_posts(id) ON DELETE SET NULL;


--
-- Name: notifications notifications_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: post_approval_stages post_approval_stages_scheduled_post_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.post_approval_stages
    ADD CONSTRAINT post_approval_stages_scheduled_post_id_fkey FOREIGN KEY (scheduled_post_id) REFERENCES public.scheduled_posts(id) ON DELETE CASCADE;


--
-- Name: post_targets post_targets_scheduled_post_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.post_targets
    ADD CONSTRAINT post_targets_scheduled_post_id_fkey FOREIGN KEY (scheduled_post_id) REFERENCES public.scheduled_posts(id) ON DELETE CASCADE;


--
-- Name: post_templates post_templates_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.post_templates
    ADD CONSTRAINT post_templates_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: rag_chat_history rag_chat_history_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rag_chat_history
    ADD CONSTRAINT rag_chat_history_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: scheduled_posts scheduled_posts_reposted_from_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.scheduled_posts
    ADD CONSTRAINT scheduled_posts_reposted_from_id_fkey FOREIGN KEY (reposted_from_id) REFERENCES public.scheduled_posts(id) ON DELETE SET NULL;


--
-- Name: scheduled_posts scheduled_posts_template_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.scheduled_posts
    ADD CONSTRAINT scheduled_posts_template_id_fkey FOREIGN KEY (template_id) REFERENCES public.post_templates(id) ON DELETE CASCADE;


--
-- Name: social_accounts social_accounts_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.social_accounts
    ADD CONSTRAINT social_accounts_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: user_brands user_brands_brand_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_brands
    ADD CONSTRAINT user_brands_brand_id_fkey FOREIGN KEY (brand_id) REFERENCES public.brands(id) ON DELETE CASCADE;


--
-- Name: user_brands user_brands_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_brands
    ADD CONSTRAINT user_brands_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: user_profiles user_profiles_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_profiles
    ADD CONSTRAINT user_profiles_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: users users_admin_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_admin_id_fkey FOREIGN KEY (admin_id) REFERENCES public.users(id);


--
-- PostgreSQL database dump complete
--

\unrestrict zBaojnovwIC4OiM33BPqeTIKUymhfWXtXzoFy6Ah2i3sabcC3KLdKG6FnS4hI59

