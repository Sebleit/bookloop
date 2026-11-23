-- PostgreSQL/Supabase only: enable row-level security on every BookLoop table.
-- (Databases made before profiles had an email column get it here.)
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS email TEXT;
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE books ENABLE ROW LEVEL SECURITY;
ALTER TABLE courses ENABLE ROW LEVEL SECURITY;
ALTER TABLE book_courses ENABLE ROW LEVEL SECURITY;
ALTER TABLE copies ENABLE ROW LEVEL SECURITY;
ALTER TABLE wishlist ENABLE ROW LEVEL SECURITY;
ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE offers ENABLE ROW LEVEL SECURITY;
ALTER TABLE loops ENABLE ROW LEVEL SECURITY;
ALTER TABLE trades ENABLE ROW LEVEL SECURITY;
ALTER TABLE rounds ENABLE ROW LEVEL SECURITY;
ALTER TABLE round_entries ENABLE ROW LEVEL SECURITY;
ALTER TABLE round_wants ENABLE ROW LEVEL SECURITY;
ALTER TABLE reviews ENABLE ROW LEVEL SECURITY;
ALTER TABLE entity_ids ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;

-- A signed-in user can read only their own profile through the Supabase API.
DROP POLICY IF EXISTS profiles_read_own ON public.profiles;
CREATE POLICY profiles_read_own
ON public.profiles
FOR SELECT
TO authenticated
USING (id = (SELECT auth.uid())::text);

-- The Supabase API (the public key in the app) never sees emails: a logged-in user
-- can read only these five columns of their own profile, and nobody can change profiles.
REVOKE ALL ON public.profiles FROM anon, authenticated;
GRANT SELECT (id, display_name, role, status, created_at) ON public.profiles TO authenticated;

-- Create a BookLoop profile as part of each Supabase Auth sign-up.
CREATE OR REPLACE FUNCTION public.bookloop_create_profile_for_auth_user()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $function$
BEGIN
    INSERT INTO public.profiles (id, display_name, role, status, created_at, email)
    VALUES (
        NEW.id::text,
        COALESCE(
            NULLIF(NEW.raw_user_meta_data ->> 'display_name', ''),
            NULLIF(split_part(COALESCE(NEW.email, ''), '@', 1), ''),
            'Student'
        ),
        'student',
        'active',
        to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
        NEW.email
    )
    ON CONFLICT (id) DO NOTHING;
    RETURN NEW;
END;
$function$;

REVOKE ALL ON FUNCTION public.bookloop_create_profile_for_auth_user() FROM PUBLIC;

DROP TRIGGER IF EXISTS bookloop_create_profile_after_auth_signup ON auth.users;
CREATE TRIGGER bookloop_create_profile_after_auth_signup
AFTER INSERT ON auth.users
FOR EACH ROW
EXECUTE FUNCTION public.bookloop_create_profile_for_auth_user();

-- Backfill Auth users that were created before the profile trigger was installed.
INSERT INTO public.profiles (id, display_name, role, status, created_at, email)
SELECT
    auth_user.id::text,
    COALESCE(
        NULLIF(auth_user.raw_user_meta_data ->> 'display_name', ''),
        NULLIF(split_part(COALESCE(auth_user.email, ''), '@', 1), ''),
        'Student'
    ),
    'student',
    'active',
    to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
    auth_user.email
FROM auth.users AS auth_user
ON CONFLICT (id) DO NOTHING;

-- Every profile keeps its account's email.
UPDATE public.profiles AS profile SET email = auth_user.email
FROM auth.users AS auth_user
WHERE profile.id = auth_user.id::text AND profile.email IS DISTINCT FROM auth_user.email;
