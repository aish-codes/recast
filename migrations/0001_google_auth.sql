-- Google sign-in: one row per Supabase account, and row-level security.
--
-- Run once, in the Supabase SQL editor, against the project the app points at.
-- Every statement is idempotent, so a re-run is a no-op.
--
-- Two things change here.
--
-- user_id becomes a uuid with a foreign key to auth.users. It held the literal
-- string 'me' before, because there was one shared password and therefore one
-- user; now it holds the `sub` claim out of the caller's JWT. The foreign key is
-- what makes deleting an account delete its data.
--
-- Row-level security goes on all three tables. This is not belt-and-braces: the
-- Supabase anon key now ships in the browser bundle, and Supabase publishes
-- every table in the `public` schema through PostgREST. Without RLS, anyone who
-- opens devtools, copies that key and calls
-- `GET /rest/v1/profiles?select=*` reads every resume in the database. The
-- policies below are the thing standing in the way.
--
-- The app itself is unaffected by them. The Python function connects as
-- `postgres` over the pooler, and the table owner bypasses RLS — so these
-- policies constrain PostgREST, which we do not use, and nothing else. That is
-- the intent: the API's own isolation is the user_id on every query, and this is
-- a second wall behind it.


-- Everything below runs as one transaction. Without this the file half-applies
-- when a step fails: the first attempt at it left row-level security switched on
-- with no policies behind it and the columns still `text`, which denies
-- PostgREST everything — safe, but not what anyone asked for, and confusing to
-- diagnose. All or nothing is easier to reason about.
begin;


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 1 — deal with the old single-user rows.  *** CHOOSE ONE ***
--
-- Everything currently in these tables is keyed to the string 'me'. That is not
-- a uuid, so step 2 cannot cast it and will fail while any such row remains.
-- Uncomment exactly one of the blocks below.
-- ─────────────────────────────────────────────────────────────────────────────

-- First, unconditionally: drop anything owned by a user_id that was never a real
-- account. 'user-uuid' is the placeholder from the API test fixture, which wrote
-- a copy of the example profile here when the suite was still reading the
-- deployment's .env and pointing at this database. tests/conftest.py stops that
-- happening again; this clears what it already left behind.
--
-- Not optional, and separate from the choice below, because profiles is keyed on
-- user_id alone: leaving that row in place and then running (A) would try to
-- give two rows the same primary key.

delete from profiles     where user_id = 'user-uuid';
delete from applications where user_id = 'user-uuid';
delete from analyses     where user_id = 'user-uuid';

-- (A) KEEP the existing applications and profile, reassigned to your account.
--     ACTIVE — this is the option that was chosen.
--
--     Sign in with Google once before running this. The account has to exist in
--     auth.users before a foreign key can point at it, and the lookup below has
--     to have something to find.
--
--     Resolved rather than pasted: a hand-copied uuid that is valid but wrong
--     fails silently, reassigning a profile to an account that is not yours. The
--     guards make both ways of getting it wrong say so instead.
--
--     user_id is still text at this point, hence the cast — step 2 is what
--     changes the column type, and it runs after this.

do $$
declare
    account uuid;
    accounts int;
begin
    select count(*) into accounts from auth.users;

    if accounts = 0 then
        raise exception
            'No account in auth.users yet. Sign in with Google once, then run '
            'this file again.';
    end if;

    if accounts > 1 then
        raise exception
            'auth.users holds % accounts, so "the" account is ambiguous. Replace '
            'this block with an explicit id from: select id, email from auth.users;',
            accounts;
    end if;

    select id into account from auth.users;

    update profiles     set user_id = account::text where user_id = 'me';
    update applications set user_id = account::text where user_id = 'me';
    update analyses     set user_id = account::text where user_id = 'me';
end $$;

-- (B) DISCARD them and start clean. Irreversible.
--     Not chosen. To switch, comment out the whole do-block above and uncomment
--     these three lines.
--
-- delete from profiles     where user_id = 'me';
-- delete from applications where user_id = 'me';
-- delete from analyses     where user_id = 'me';


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 1b — stop here, loudly, if step 1 was skipped.
--
-- Without this the failure is `invalid input syntax for type uuid: "me"` from
-- step 2, which says what broke but not what to do about it. Naming the
-- offending values and pointing back at step 1 turns a puzzle into an
-- instruction.
-- ─────────────────────────────────────────────────────────────────────────────

do $$
declare
    stragglers text;
begin
    select string_agg(distinct quote_literal(user_id), ', ')
      into stragglers
      from (
          select user_id from profiles
          union select user_id from applications
          union select user_id from analyses
      ) s
     where user_id !~ '^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-'
                      '[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$';

    if stragglers is not null then
        raise exception
            'STEP 1 was skipped. These user_id values are not uuids and cannot '
            'be cast: %. Uncomment block (A) or (B) at the top of this file, '
            'fill in your own Supabase user id if you chose (A), and run the '
            'whole file again.', stragglers;
    end if;
end $$;


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 2 — text -> uuid.
--
-- Postgres rebuilds the primary keys and the secondary indexes on its own as
-- part of the type change, so they do not need dropping and recreating.
-- ─────────────────────────────────────────────────────────────────────────────

alter table profiles     alter column user_id type uuid using user_id::uuid;
alter table applications alter column user_id type uuid using user_id::uuid;
alter table analyses     alter column user_id type uuid using user_id::uuid;


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 3 — tie the rows to real accounts.
--
-- on delete cascade: removing a user from Supabase Auth takes their profile,
-- applications and analyses with it, which is what someone asking to have their
-- account deleted means by it.
-- ─────────────────────────────────────────────────────────────────────────────

do $$
begin
    if not exists (select 1 from pg_constraint where conname = 'profiles_user_fk') then
        alter table profiles add constraint profiles_user_fk
            foreign key (user_id) references auth.users (id) on delete cascade;
    end if;

    if not exists (select 1 from pg_constraint where conname = 'applications_user_fk') then
        alter table applications add constraint applications_user_fk
            foreign key (user_id) references auth.users (id) on delete cascade;
    end if;

    if not exists (select 1 from pg_constraint where conname = 'analyses_user_fk') then
        alter table analyses add constraint analyses_user_fk
            foreign key (user_id) references auth.users (id) on delete cascade;
    end if;
end $$;


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 4 — row-level security.
--
-- One policy per table, covering all four verbs. `using` is the read test and
-- `with check` is the write test; both are needed, or a signed-in user could
-- insert a row owned by someone else even while unable to read it back.
-- ─────────────────────────────────────────────────────────────────────────────

alter table profiles     enable row level security;
alter table applications enable row level security;
alter table analyses     enable row level security;

drop policy if exists own_profile      on profiles;
drop policy if exists own_applications on applications;
drop policy if exists own_analyses     on analyses;

create policy own_profile on profiles
    for all to authenticated
    using (auth.uid() = user_id)
    with check (auth.uid() = user_id);

create policy own_applications on applications
    for all to authenticated
    using (auth.uid() = user_id)
    with check (auth.uid() = user_id);

create policy own_analyses on analyses
    for all to authenticated
    using (auth.uid() = user_id)
    with check (auth.uid() = user_id);


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 5 — take PostgREST off the table entirely.
--
-- The policies above already restrict every role that reaches these tables
-- through the API. This goes further and withdraws the privilege itself, so an
-- accidentally-dropped policy is not the only thing between a resume and the
-- internet. Nothing in this app talks to PostgREST, so nothing notices.
--
-- Re-granting is the one thing to remember if a future feature ever does want
-- to query Supabase straight from the browser.
-- ─────────────────────────────────────────────────────────────────────────────

revoke all on table profiles, applications, analyses from anon, authenticated;


commit;
