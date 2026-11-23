-- BookLoop: reset the online demo data. Paste all of it into Supabase -> SQL Editor -> Run.
-- It's one block: if anything fails, nothing changes. It works on any day: every demo
-- date moves to the day it runs. It also removes the profiles of accounts deleted in
-- Authentication -> Users, and gives every swap a new random handoff code.
-- Made by: uv run python reset_online_demo.py --sql db/demo_reset.sql
-- It needs one account for each of these first names: Ana, Ben, Carla, Dina, Eli, Farah, Morgan.
DO $reset$
DECLARE
    problem text;
    shift integer := (now() AT TIME ZONE 'UTC')::date - date '2026-11-23';
BEGIN
    -- Databases made before profiles had an email column get it here, hidden from
    -- the Supabase API: a logged-in user reads only these columns of their own profile.
    ALTER TABLE profiles ADD COLUMN IF NOT EXISTS email text;
    REVOKE ALL ON public.profiles FROM anon, authenticated;
    GRANT SELECT (id, display_name, role, status, created_at) ON public.profiles TO authenticated;
    CREATE TEMP TABLE demo_accounts (demo_id text PRIMARY KEY, name text, role text, status text, account_id text) ON COMMIT DROP;
    INSERT INTO demo_accounts (demo_id, name, role, status) VALUES
        ('user-ana', 'Ana', 'student', 'active'),
        ('user-ben', 'Ben', 'student', 'active'),
        ('user-carla', 'Carla', 'student', 'active'),
        ('user-dina', 'Dina', 'student', 'under_review'),
        ('user-eli', 'Eli', 'student', 'active'),
        ('user-farah', 'Farah', 'student', 'active'),
        ('user-moderator', 'Morgan', 'moderator', 'active');

    SELECT string_agg(d.name, ', ' ORDER BY d.name) INTO problem FROM demo_accounts d
    WHERE (SELECT count(*) FROM profiles p WHERE lower(trim(p.display_name)) = lower(d.name)) <> 1;
    IF problem IS NOT NULL THEN
        RAISE EXCEPTION 'Each of these needs exactly one account with that name: %. Nothing was changed.', problem;
    END IF;
    UPDATE demo_accounts d SET account_id = p.id FROM profiles p WHERE lower(trim(p.display_name)) = lower(d.name);

    DELETE FROM audit_log;
    DELETE FROM entity_ids;
    DELETE FROM reviews;
    DELETE FROM round_wants;
    DELETE FROM round_entries;
    DELETE FROM trades;
    DELETE FROM loops;
    DELETE FROM rounds;
    DELETE FROM offers;
    DELETE FROM notifications;
    DELETE FROM wishlist;
    DELETE FROM copies;
    DELETE FROM book_courses;
    DELETE FROM courses;
    DELETE FROM books;

    -- Accounts deleted in Authentication -> Users: remove their profiles too.
    -- This also removes the classmates who never log in; they're added again below.
    DELETE FROM profiles WHERE id NOT IN (SELECT id::text FROM auth.users);

    UPDATE profiles p SET display_name = d.name, role = d.role, status = d.status
    FROM demo_accounts d WHERE p.id = d.account_id;
    -- Each profile keeps its account's email (shown only in direct swaps and to moderators).
    UPDATE profiles p SET email = u.email FROM auth.users u WHERE p.id = u.id::text AND p.email IS DISTINCT FROM u.email;

    INSERT INTO profiles ("id", "display_name", "role", "status", "created_at", "email") VALUES
        ('extra-afonso', 'Afonso', 'student', 'active', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), 'afonso@example.com'),
        ('extra-beatriz', 'Beatriz', 'student', 'active', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), 'beatriz@example.com'),
        ('extra-diogo', 'Diogo', 'student', 'active', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), 'diogo@example.com'),
        ('extra-goncalo', 'Gonçalo', 'student', 'active', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), 'goncalo@example.com'),
        ('extra-hugo', 'Hugo', 'student', 'active', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), 'hugo@example.com'),
        ('extra-ines', 'Inês', 'student', 'active', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), 'ines@example.com'),
        ('extra-joana', 'Joana', 'student', 'active', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), 'joana@example.com'),
        ('extra-leonor', 'Leonor', 'student', 'active', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), 'leonor@example.com'),
        ('extra-marta', 'Marta', 'student', 'active', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), 'marta@example.com'),
        ('extra-miguel', 'Miguel', 'student', 'active', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), 'miguel@example.com'),
        ('extra-nuno', 'Nuno', 'student', 'active', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), 'nuno@example.com'),
        ('extra-rita', 'Rita', 'student', 'active', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), 'rita@example.com'),
        ('extra-sofia', 'Sofia', 'student', 'active', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), 'sofia@example.com'),
        ('extra-tiago', 'Tiago', 'student', 'active', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), 'tiago@example.com');
    INSERT INTO books ("id", "isbn", "title", "authors", "edition", "cover_url") VALUES
        ('book-01', '9780262046305', 'Introduction to Algorithms', 'Thomas H. Cormen et al.', '4th', 'https://covers.openlibrary.org/b/isbn/9780262046305-M.jpg'),
        ('book-02', '9781718502703', 'Python Crash Course', 'Eric Matthes', '3rd', 'https://covers.openlibrary.org/b/isbn/9781718502703-M.jpg'),
        ('book-03', '9781593279929', 'Automate the Boring Stuff with Python', 'Al Sweigart', '2nd', 'https://covers.openlibrary.org/b/isbn/9781593279929-M.jpg'),
        ('book-04', '9780525561643', 'A Mind for Numbers', 'Barbara Oakley', 'Revised', 'https://covers.openlibrary.org/b/id/8352403-M.jpg'),
        ('book-05', '9781337613927', 'Calculus: Early Transcendentals', 'James Stewart', '8th', 'https://covers.openlibrary.org/b/isbn/9781337613927-M.jpg'),
        ('book-06', '9781260598205', 'Principles of Economics', 'N. Gregory Mankiw', '9th', 'https://covers.openlibrary.org/b/id/10319849-M.jpg'),
        ('book-07', '9780190936273', 'The Economics Book', 'DK', '1st', 'https://covers.openlibrary.org/b/id/8763438-M.jpg'),
        ('book-08', '9780547168290', 'World History: Patterns of Interaction', 'Roger B. Beck et al.', '1st', 'https://covers.openlibrary.org/b/id/1325336-M.jpg'),
        ('book-09', '9780316025846', 'A Little History of the World', 'E. H. Gombrich', '1st', 'https://covers.openlibrary.org/b/id/6624825-M.jpg'),
        ('book-10', '9780134093413', 'Biology', 'Neil A. Campbell et al.', '11th', 'https://covers.openlibrary.org/b/isbn/9780134093413-M.jpg'),
        ('book-11', '9781260211884', 'Chemistry: The Central Science', 'Theodore L. Brown et al.', '14th', 'https://covers.openlibrary.org/b/id/8846343-M.jpg'),
        ('book-12', '9780135159553', 'University Physics', 'Hugh D. Young and Roger A. Freedman', '15th', 'https://covers.openlibrary.org/b/id/10370820-M.jpg'),
        ('book-13', '9781319247209', 'Psychology', 'David G. Myers and C. Nathan DeWall', '13th', 'https://covers.openlibrary.org/b/id/6601727-M.jpg'),
        ('book-14', '9780393538700', 'They Say / I Say', 'Gerald Graff and Cathy Birkenstein', '5th', 'https://covers.openlibrary.org/b/isbn/9780393538700-M.jpg'),
        ('book-15', '9781260260517', 'Business Essentials', 'Ronald J. Ebert and Ricky W. Griffin', '12th', 'https://covers.openlibrary.org/b/id/10168707-M.jpg');
    INSERT INTO courses ("id", "code", "name") VALUES
        ('course-01', '1318', 'Computer Programming'),
        ('course-02', '1309', 'Calculus I'),
        ('course-03', '1311', 'Linear Algebra with Programming'),
        ('course-04', '1117', 'Principles of Microeconomics'),
        ('course-05', '1118', 'Principles of Macroeconomics'),
        ('course-06', '1313', 'Statistics for Economics and Management'),
        ('course-07', '1217', 'Financial Accounting'),
        ('course-08', '1219', 'Finance'),
        ('course-09', '1220', 'Marketing'),
        ('course-10', '1216', 'Principles of Management'),
        ('course-11', '1206', 'Organizational Behaviour'),
        ('course-12', '1124', 'Economic History'),
        ('course-13', '1465', 'Introduction to Modern and Contemporary History'),
        ('course-14', '1469', 'Human Behaviour and Decision Making'),
        ('course-15', '1462', 'Communication & Leadership');
    INSERT INTO book_courses ("book_id", "course_id") VALUES
        ('book-01', 'course-01'),
        ('book-02', 'course-01'),
        ('book-03', 'course-01'),
        ('book-04', 'course-02'),
        ('book-05', 'course-02'),
        ('book-06', 'course-04'),
        ('book-06', 'course-05'),
        ('book-07', 'course-12'),
        ('book-08', 'course-13'),
        ('book-09', 'course-13'),
        ('book-13', 'course-14'),
        ('book-13', 'course-11'),
        ('book-14', 'course-15'),
        ('book-15', 'course-10');
    INSERT INTO copies ("id", "book_id", "owner_id", "condition", "highlighting", "notes", "status", "created_at") VALUES
        ('copy-01', 'book-01', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-ben'), 1, 'none', NULL, 'available', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-02', 'book-02', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-ana'), 2, 'light', 'Spine creased and the cover is a bit bent.', 'available', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-03', 'book-03', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-carla'), 3, 'heavy', 'Pencil notes in a few chapters.', 'reserved', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-04', 'book-04', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-dina'), 4, 'none', NULL, 'reserved', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-05', 'book-05', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-eli'), 1, 'light', 'Well used: the cover is loose, but every page is there.', 'in_round', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-06', 'book-06', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-farah'), 2, 'heavy', 'Spine creased and the cover is a bit bent.', 'in_round', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-07', 'book-07', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-ana'), 3, 'none', NULL, 'in_round', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-08', 'book-08', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-ben'), 4, 'light', 'Bought new last term, read once.', 'in_round', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-09', 'book-09', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-carla'), 1, 'heavy', 'Well used: the cover is loose, but every page is there.', 'in_round', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-10', 'book-10', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-dina'), 2, 'none', NULL, 'available', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-11', 'book-11', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-eli'), 3, 'light', 'Pencil notes in a few chapters.', 'available', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-12', 'book-12', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-farah'), 4, 'heavy', 'Bought new last term, read once.', 'in_round', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-13', 'book-13', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-ana'), 1, 'none', NULL, 'available', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-14', 'book-14', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-ben'), 2, 'light', 'Spine creased and the cover is a bit bent.', 'available', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-15', 'book-15', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-carla'), 3, 'heavy', 'Pencil notes in a few chapters.', 'available', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-16', 'book-01', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-dina'), 4, 'none', NULL, 'available', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-17', 'book-02', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-eli'), 1, 'light', 'Well used: the cover is loose, but every page is there.', 'available', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-18', 'book-03', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-farah'), 2, 'heavy', 'Spine creased and the cover is a bit bent.', 'available', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-19', 'book-04', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-ana'), 3, 'none', NULL, 'in_round', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-20', 'book-05', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-ben'), 4, 'light', 'Bought new last term, read once.', 'in_round', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-21', 'book-06', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-carla'), 1, 'heavy', 'Well used: the cover is loose, but every page is there.', 'available', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-22', 'book-07', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-dina'), 2, 'none', NULL, 'available', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-23', 'book-08', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-eli'), 3, 'light', 'Pencil notes in a few chapters.', 'available', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-24', 'book-09', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-farah'), 4, 'heavy', 'Bought new last term, read once.', 'available', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-25', 'book-10', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-ana'), 1, 'none', NULL, 'available', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-26', 'book-10', 'extra-afonso', 3, 'none', NULL, 'in_round', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-27', 'book-13', 'extra-beatriz', 4, 'light', 'Bought new last term, read once.', 'in_round', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-28', 'book-15', 'extra-diogo', 2, 'heavy', 'Spine creased and the cover is a bit bent.', 'in_round', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-29', 'book-02', 'extra-goncalo', 3, 'none', NULL, 'in_round', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-30', 'book-07', 'extra-hugo', 4, 'light', 'Bought new last term, read once.', 'in_round', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-31', 'book-06', 'extra-ines', 3, 'none', NULL, 'in_round', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-32', 'book-01', 'extra-joana', 2, 'heavy', 'Spine creased and the cover is a bit bent.', 'in_round', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-33', 'book-09', 'extra-leonor', 3, 'none', NULL, 'in_round', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-34', 'book-03', 'extra-marta', 4, 'light', 'Bought new last term, read once.', 'in_round', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-35', 'book-12', 'extra-miguel', 3, 'none', NULL, 'in_round', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-36', 'book-05', 'extra-nuno', 2, 'heavy', 'Spine creased and the cover is a bit bent.', 'in_round', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-37', 'book-08', 'extra-rita', 3, 'none', NULL, 'in_round', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-38', 'book-04', 'extra-sofia', 4, 'light', 'Bought new last term, read once.', 'in_round', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-39', 'book-14', 'extra-tiago', 3, 'none', NULL, 'in_round', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-40', 'book-11', 'extra-joana', 3, 'none', NULL, 'in_round', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-41', 'book-03', 'extra-miguel', 2, 'heavy', 'Spine creased and the cover is a bit bent.', 'in_round', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-42', 'book-08', 'extra-sofia', 4, 'light', 'Bought new last term, read once.', 'in_round', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-43', 'book-02', 'extra-hugo', 1, 'light', 'Well used: the cover is loose, but every page is there.', 'in_round', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-44', 'book-06', 'extra-marta', 4, 'light', 'Bought new last term, read once.', 'in_round', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-45', 'book-13', 'extra-nuno', 3, 'none', NULL, 'in_round', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-46', 'book-05', 'extra-ines', 2, 'heavy', 'Spine creased and the cover is a bit bent.', 'in_round', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-47', 'book-10', 'extra-rita', 4, 'light', 'Bought new last term, read once.', 'in_round', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-48', 'book-05', 'extra-beatriz', 3, 'none', NULL, 'in_round', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-49', 'book-07', 'extra-diogo', 2, 'heavy', 'Spine creased and the cover is a bit bent.', 'in_round', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-50', 'book-11', 'extra-goncalo', 4, 'light', 'Bought new last term, read once.', 'in_round', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-51', 'book-14', 'extra-afonso', 3, 'none', NULL, 'in_round', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-52', 'book-12', 'extra-leonor', 3, 'none', NULL, 'available', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-53', 'book-01', 'extra-tiago', 2, 'heavy', 'Spine creased and the cover is a bit bent.', 'available', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-54', 'book-04', 'extra-afonso', 4, 'light', 'Bought new last term, read once.', 'available', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-55', 'book-02', 'extra-beatriz', 3, 'none', NULL, 'available', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-56', 'book-09', 'extra-diogo', 1, 'light', 'Well used: the cover is loose, but every page is there.', 'available', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-57', 'book-15', 'extra-goncalo', 3, 'none', NULL, 'available', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-58', 'book-06', 'extra-leonor', 4, 'light', 'Bought new last term, read once.', 'available', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-59', 'book-13', 'extra-tiago', 2, 'heavy', 'Spine creased and the cover is a bit bent.', 'available', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-last-ana', 'book-10', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-farah'), 3, 'light', NULL, 'available', to_char(timestamp '2026-11-11 10:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-last-ben', 'book-11', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-ana'), 4, 'none', NULL, 'available', to_char(timestamp '2026-11-11 10:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-last-farah', 'book-13', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-farah'), 3, 'none', NULL, 'reserved', to_char(timestamp '2026-11-11 10:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-last-eli', 'book-01', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-eli'), 2, 'heavy', NULL, 'available', to_char(timestamp '2026-11-11 10:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-hist-01a', 'book-01', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-ana'), 4, 'none', NULL, 'unlisted', to_char(timestamp '2026-09-15 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-hist-01b', 'book-10', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-carla'), 3, 'none', NULL, 'unlisted', to_char(timestamp '2026-09-15 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-hist-02a', 'book-03', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-ben'), 3, 'none', NULL, 'unlisted', to_char(timestamp '2026-09-15 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-hist-02b', 'book-10', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-carla'), 3, 'none', NULL, 'unlisted', to_char(timestamp '2026-09-15 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-hist-03a', 'book-05', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-dina'), 3, 'none', NULL, 'unlisted', to_char(timestamp '2026-09-15 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-hist-03b', 'book-10', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-carla'), 3, 'none', NULL, 'unlisted', to_char(timestamp '2026-09-15 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-hist-04a', 'book-07', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-eli'), 4, 'none', NULL, 'unlisted', to_char(timestamp '2026-09-15 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-hist-04b', 'book-10', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-carla'), 3, 'none', NULL, 'unlisted', to_char(timestamp '2026-09-15 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-hist-05a', 'book-09', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-farah'), 2, 'none', NULL, 'unlisted', to_char(timestamp '2026-09-15 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-hist-05b', 'book-10', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-carla'), 3, 'none', NULL, 'unlisted', to_char(timestamp '2026-09-15 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-hist-06a', 'book-02', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-eli'), 4, 'none', NULL, 'unlisted', to_char(timestamp '2026-09-15 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-hist-06b', 'book-10', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-dina'), 3, 'none', NULL, 'unlisted', to_char(timestamp '2026-09-15 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-hist-07a', 'book-04', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-farah'), 3, 'none', NULL, 'unlisted', to_char(timestamp '2026-09-15 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-hist-07b', 'book-10', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-dina'), 3, 'none', NULL, 'unlisted', to_char(timestamp '2026-09-15 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-hist-08a', 'book-06', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-ana'), 3, 'none', NULL, 'unlisted', to_char(timestamp '2026-09-15 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-hist-08b', 'book-10', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-dina'), 3, 'none', NULL, 'unlisted', to_char(timestamp '2026-09-15 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-demo-review-a', 'book-11', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-carla'), 4, 'none', NULL, 'unlisted', to_char(timestamp '2026-10-20 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-demo-review-b', 'book-15', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-eli'), 3, 'none', NULL, 'unlisted', to_char(timestamp '2026-10-20 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'));
    INSERT INTO wishlist ("user_id", "book_id", "created_at") VALUES
        ((SELECT account_id FROM demo_accounts WHERE demo_id = 'user-ana'), 'book-12', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ((SELECT account_id FROM demo_accounts WHERE demo_id = 'user-ben'), 'book-12', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ((SELECT account_id FROM demo_accounts WHERE demo_id = 'user-carla'), 'book-04', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ((SELECT account_id FROM demo_accounts WHERE demo_id = 'user-eli'), 'book-14', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'));
    INSERT INTO notifications ("id", "user_id", "text", "link", "read", "created_at") VALUES
        ('note-last-moderator', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-moderator'), 'Ben says Farah didn''t hand over “Psychology”. Check it on the Moderator page.', NULL, 0, to_char(timestamp '2026-11-19 15:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('note-last-farah', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-farah'), 'Ben reported that you didn''t hand over “Psychology”. A moderator will check what happened.', NULL, 0, to_char(timestamp '2026-11-19 15:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'));
    INSERT INTO offers ("id", "proposer_id", "offered_copy_id", "requested_copy_id", "status", "created_at", "expires_at") VALUES
        ('offer-demo-completed', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-ana'), 'copy-01', 'copy-02', 'accepted', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), to_char(timestamp '2026-11-23 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('offer-demo-pending', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-carla'), 'copy-03', 'copy-04', 'accepted', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), to_char(timestamp '2026-11-23 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('offer-demo-leonor', 'extra-leonor', 'copy-52', 'copy-15', 'pending', to_char(timestamp '2026-11-22 16:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), to_char(timestamp '2026-11-25 16:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'));
    INSERT INTO rounds ("id", "name", "phase", "entries_close_at", "wants_close_at", "meet_place", "meet_time", "created_by") VALUES
        ('round-last', 'Weekly swap · ' || to_char(timestamp '2026-11-19 14:00:00' + shift * interval '1 day', 'FMDD Mon'), 'matched', to_char(timestamp '2026-11-15 18:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), to_char(timestamp '2026-11-18 18:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), 'Nova SBE library, ground floor', to_char(timestamp '2026-11-19 14:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-moderator')),
        ('round-demo', 'Weekly swap · ' || to_char(timestamp '2026-11-26 14:00:00' + shift * interval '1 day', 'FMDD Mon'), 'wants', to_char(timestamp '2026-11-22 18:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), to_char(timestamp '2026-11-25 18:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), 'Nova SBE library, ground floor', to_char(timestamp '2026-11-26 14:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-moderator')),
        ('round-next', 'Weekly swap · ' || to_char(timestamp '2026-12-03 14:00:00' + shift * interval '1 day', 'FMDD Mon'), 'entries', to_char(timestamp '2026-11-29 18:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), to_char(timestamp '2026-12-02 18:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), 'Nova SBE library, ground floor', to_char(timestamp '2026-12-03 14:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-moderator'));
    INSERT INTO loops ("id", "source", "offer_id", "round_id", "status", "meet_place", "meet_time", "no_show_user_id") VALUES
        ('loop-demo-completed', 'offer', 'offer-demo-completed', NULL, 'completed', 'Main library', to_char(timestamp '2026-11-15 14:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), NULL),
        ('loop-demo-pending', 'offer', 'offer-demo-pending', NULL, 'scheduled', NULL, NULL, NULL),
        ('loop-last', 'round', NULL, 'round-last', 'scheduled', 'Nova SBE library, ground floor', to_char(timestamp '2026-11-19 14:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), NULL),
        ('loop-hist-01', 'offer', NULL, NULL, 'completed', 'Nova SBE library', to_char(timestamp '2026-10-02 14:30:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), NULL),
        ('loop-hist-02', 'offer', NULL, NULL, 'completed', 'Nova SBE library', to_char(timestamp '2026-10-03 14:30:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), NULL),
        ('loop-hist-03', 'offer', NULL, NULL, 'completed', 'Nova SBE library', to_char(timestamp '2026-10-04 14:30:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), NULL),
        ('loop-hist-04', 'offer', NULL, NULL, 'completed', 'Nova SBE library', to_char(timestamp '2026-10-05 14:30:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), NULL),
        ('loop-hist-05', 'offer', NULL, NULL, 'completed', 'Nova SBE library', to_char(timestamp '2026-10-06 14:30:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), NULL),
        ('loop-hist-06', 'offer', NULL, NULL, 'completed', 'Nova SBE library', to_char(timestamp '2026-10-07 14:30:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), NULL),
        ('loop-hist-07', 'offer', NULL, NULL, 'completed', 'Nova SBE library', to_char(timestamp '2026-10-08 14:30:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), NULL),
        ('loop-hist-08', 'offer', NULL, NULL, 'completed', 'Nova SBE library', to_char(timestamp '2026-10-09 14:30:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), NULL),
        ('loop-demo-review', 'offer', NULL, NULL, 'completed', 'Nova SBE library', to_char(timestamp '2026-11-22 20:58:23' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), NULL);
    INSERT INTO trades ("id", "loop_id", "copy_id", "giver_id", "receiver_id", "handoff_code", "code_attempts", "status", "completed_at") VALUES
        ('trade-demo-completed-a', 'loop-demo-completed', 'copy-01', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-ana'), (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-ben'), lpad(floor(random() * 10000)::int::text, 4, '0'), 0, 'completed', to_char(timestamp '2026-11-15 14:10:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('trade-demo-completed-b', 'loop-demo-completed', 'copy-02', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-ben'), (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-ana'), lpad(floor(random() * 10000)::int::text, 4, '0'), 0, 'completed', to_char(timestamp '2026-11-15 14:10:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('trade-demo-pending-a', 'loop-demo-pending', 'copy-03', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-carla'), (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-dina'), lpad(floor(random() * 10000)::int::text, 4, '0'), 0, 'pending', NULL),
        ('trade-demo-pending-b', 'loop-demo-pending', 'copy-04', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-dina'), (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-carla'), lpad(floor(random() * 10000)::int::text, 4, '0'), 0, 'pending', NULL),
        ('trade-last-ben', 'loop-last', 'copy-last-ben', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-ben'), (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-ana'), lpad(floor(random() * 10000)::int::text, 4, '0'), 0, 'completed', to_char(timestamp '2026-11-19 14:10:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('trade-last-ana', 'loop-last', 'copy-last-ana', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-ana'), (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-farah'), lpad(floor(random() * 10000)::int::text, 4, '0'), 0, 'completed', to_char(timestamp '2026-11-19 14:10:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('trade-last-farah', 'loop-last', 'copy-last-farah', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-farah'), (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-ben'), lpad(floor(random() * 10000)::int::text, 4, '0'), 0, 'pending', NULL),
        ('trade-hist-01a', 'loop-hist-01', 'copy-hist-01a', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-carla'), (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-ana'), lpad(floor(random() * 10000)::int::text, 4, '0'), 0, 'completed', to_char(timestamp '2026-10-02 15:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('trade-hist-01b', 'loop-hist-01', 'copy-hist-01b', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-ana'), (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-carla'), lpad(floor(random() * 10000)::int::text, 4, '0'), 0, 'completed', to_char(timestamp '2026-10-02 15:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('trade-hist-02a', 'loop-hist-02', 'copy-hist-02a', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-carla'), (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-ben'), lpad(floor(random() * 10000)::int::text, 4, '0'), 0, 'completed', to_char(timestamp '2026-10-03 15:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('trade-hist-02b', 'loop-hist-02', 'copy-hist-02b', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-ben'), (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-carla'), lpad(floor(random() * 10000)::int::text, 4, '0'), 0, 'completed', to_char(timestamp '2026-10-03 15:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('trade-hist-03a', 'loop-hist-03', 'copy-hist-03a', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-carla'), (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-dina'), lpad(floor(random() * 10000)::int::text, 4, '0'), 0, 'completed', to_char(timestamp '2026-10-04 15:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('trade-hist-03b', 'loop-hist-03', 'copy-hist-03b', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-dina'), (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-carla'), lpad(floor(random() * 10000)::int::text, 4, '0'), 0, 'completed', to_char(timestamp '2026-10-04 15:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('trade-hist-04a', 'loop-hist-04', 'copy-hist-04a', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-carla'), (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-eli'), lpad(floor(random() * 10000)::int::text, 4, '0'), 0, 'completed', to_char(timestamp '2026-10-05 15:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('trade-hist-04b', 'loop-hist-04', 'copy-hist-04b', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-eli'), (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-carla'), lpad(floor(random() * 10000)::int::text, 4, '0'), 0, 'completed', to_char(timestamp '2026-10-05 15:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('trade-hist-05a', 'loop-hist-05', 'copy-hist-05a', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-carla'), (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-farah'), lpad(floor(random() * 10000)::int::text, 4, '0'), 0, 'completed', to_char(timestamp '2026-10-06 15:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('trade-hist-05b', 'loop-hist-05', 'copy-hist-05b', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-farah'), (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-carla'), lpad(floor(random() * 10000)::int::text, 4, '0'), 0, 'completed', to_char(timestamp '2026-10-06 15:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('trade-hist-06a', 'loop-hist-06', 'copy-hist-06a', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-dina'), (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-eli'), lpad(floor(random() * 10000)::int::text, 4, '0'), 0, 'completed', to_char(timestamp '2026-10-07 15:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('trade-hist-06b', 'loop-hist-06', 'copy-hist-06b', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-eli'), (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-dina'), lpad(floor(random() * 10000)::int::text, 4, '0'), 0, 'completed', to_char(timestamp '2026-10-07 15:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('trade-hist-07a', 'loop-hist-07', 'copy-hist-07a', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-dina'), (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-farah'), lpad(floor(random() * 10000)::int::text, 4, '0'), 0, 'completed', to_char(timestamp '2026-10-08 15:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('trade-hist-07b', 'loop-hist-07', 'copy-hist-07b', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-farah'), (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-dina'), lpad(floor(random() * 10000)::int::text, 4, '0'), 0, 'completed', to_char(timestamp '2026-10-08 15:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('trade-hist-08a', 'loop-hist-08', 'copy-hist-08a', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-dina'), (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-ana'), lpad(floor(random() * 10000)::int::text, 4, '0'), 0, 'completed', to_char(timestamp '2026-10-09 15:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('trade-hist-08b', 'loop-hist-08', 'copy-hist-08b', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-ana'), (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-dina'), lpad(floor(random() * 10000)::int::text, 4, '0'), 0, 'completed', to_char(timestamp '2026-10-09 15:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('trade-demo-review-a', 'loop-demo-review', 'copy-demo-review-a', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-eli'), (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-carla'), lpad(floor(random() * 10000)::int::text, 4, '0'), 0, 'completed', to_char(timestamp '2026-11-22 20:58:23' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('trade-demo-review-b', 'loop-demo-review', 'copy-demo-review-b', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-carla'), (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-eli'), lpad(floor(random() * 10000)::int::text, 4, '0'), 0, 'completed', to_char(timestamp '2026-11-22 20:58:23' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'));
    INSERT INTO round_entries ("id", "round_id", "copy_id", "min_partner_score") VALUES
        ('entry-eli', 'round-demo', 'copy-05', 0.0),
        ('entry-farah', 'round-demo', 'copy-06', 0.0),
        ('entry-ana', 'round-demo', 'copy-07', 0.0),
        ('entry-ben', 'round-demo', 'copy-08', 0.0),
        ('entry-carla', 'round-demo', 'copy-09', 0.0),
        ('entry-goncalo', 'round-demo', 'copy-29', 0.0),
        ('entry-ines', 'round-demo', 'copy-31', 0.0),
        ('entry-beatriz', 'round-demo', 'copy-27', 0.0),
        ('entry-diogo', 'round-demo', 'copy-28', 0.0),
        ('entry-leonor', 'round-demo', 'copy-33', 0.0),
        ('entry-joana', 'round-demo', 'copy-32', 0.0),
        ('entry-miguel', 'round-demo', 'copy-35', 0.0),
        ('entry-sofia', 'round-demo', 'copy-38', 0.0),
        ('entry-tiago', 'round-demo', 'copy-39', 0.0),
        ('entry-afonso', 'round-demo', 'copy-26', 0.0),
        ('entry-joana-2', 'round-demo', 'copy-40', 0.0),
        ('entry-miguel-2', 'round-demo', 'copy-41', 0.0),
        ('entry-sofia-2', 'round-demo', 'copy-42', 0.0),
        ('entry-ines-2', 'round-demo', 'copy-46', 0.0),
        ('entry-beatriz-2', 'round-demo', 'copy-48', 0.0),
        ('entry-diogo-2', 'round-demo', 'copy-49', 0.0),
        ('entry-goncalo-2', 'round-demo', 'copy-50', 0.0),
        ('entry-afonso-2', 'round-demo', 'copy-51', 0.0),
        ('entry-last-ana', 'round-last', 'copy-last-ana', 0.0),
        ('entry-last-ben', 'round-last', 'copy-last-ben', 0.0),
        ('entry-last-farah', 'round-last', 'copy-last-farah', 0.0),
        ('entry-last-eli', 'round-last', 'copy-last-eli', 0.0),
        ('entry-next-ana', 'round-next', 'copy-19', 0.0),
        ('entry-next-ben', 'round-next', 'copy-20', 0.0),
        ('entry-next-farah', 'round-next', 'copy-12', 0.0),
        ('entry-next-hugo', 'round-next', 'copy-30', 0.0),
        ('entry-next-marta', 'round-next', 'copy-34', 0.0),
        ('entry-next-nuno', 'round-next', 'copy-36', 0.0),
        ('entry-next-rita', 'round-next', 'copy-37', 0.0),
        ('entry-next-hugo-2', 'round-next', 'copy-43', 0.0),
        ('entry-next-marta-2', 'round-next', 'copy-44', 0.0),
        ('entry-next-nuno-2', 'round-next', 'copy-45', 0.0),
        ('entry-next-rita-2', 'round-next', 'copy-47', 0.0);
    INSERT INTO round_wants ("entry_id", "wanted_entry_id") VALUES
        ('entry-eli', 'entry-farah'),
        ('entry-farah', 'entry-ana'),
        ('entry-ana', 'entry-eli'),
        ('entry-ben', 'entry-eli'),
        ('entry-ben', 'entry-carla'),
        ('entry-carla', 'entry-ben'),
        ('entry-goncalo', 'entry-ines'),
        ('entry-ines', 'entry-goncalo'),
        ('entry-beatriz', 'entry-diogo'),
        ('entry-diogo', 'entry-leonor'),
        ('entry-leonor', 'entry-beatriz'),
        ('entry-joana', 'entry-miguel'),
        ('entry-miguel', 'entry-sofia'),
        ('entry-sofia', 'entry-tiago'),
        ('entry-tiago', 'entry-joana'),
        ('entry-afonso', 'entry-goncalo'),
        ('entry-joana-2', 'entry-miguel-2'),
        ('entry-miguel-2', 'entry-sofia-2'),
        ('entry-sofia-2', 'entry-joana-2'),
        ('entry-ines-2', 'entry-leonor'),
        ('entry-beatriz-2', 'entry-farah'),
        ('entry-goncalo-2', 'entry-tiago'),
        ('entry-afonso-2', 'entry-ines-2'),
        ('entry-leonor', 'entry-diogo-2'),
        ('entry-tiago', 'entry-diogo-2'),
        ('entry-last-ana', 'entry-last-ben'),
        ('entry-last-ben', 'entry-last-farah'),
        ('entry-last-farah', 'entry-last-ana'),
        ('entry-last-eli', 'entry-last-ana');
    INSERT INTO reviews ("id", "trade_id", "reviewer_id", "reviewee_id", "stars", "as_described", "actual_condition", "comment", "reply", "visible_from", "hidden_by_moderator", "hidden_reason", "created_at") VALUES
        ('review-hist-01', 'trade-hist-01a', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-ana'), (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-carla'), 5, 1, 4, 'Exactly as described, thanks!', NULL, to_char(timestamp '2026-10-02 20:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), 0, NULL, to_char(timestamp '2026-10-02 20:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('review-hist-02', 'trade-hist-02a', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-ben'), (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-carla'), 5, 1, 3, NULL, NULL, to_char(timestamp '2026-10-03 20:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), 0, NULL, to_char(timestamp '2026-10-03 20:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('review-hist-03', 'trade-hist-03a', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-dina'), (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-carla'), 5, 1, 3, 'Great condition.', NULL, to_char(timestamp '2026-10-04 20:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), 0, NULL, to_char(timestamp '2026-10-04 20:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('review-hist-04', 'trade-hist-04a', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-eli'), (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-carla'), 5, 1, 4, NULL, NULL, to_char(timestamp '2026-10-05 20:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), 0, NULL, to_char(timestamp '2026-10-05 20:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('review-hist-05', 'trade-hist-05a', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-farah'), (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-carla'), 5, 1, 2, 'Quick and friendly swap.', NULL, to_char(timestamp '2026-10-06 20:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), 0, NULL, to_char(timestamp '2026-10-06 20:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('review-hist-06', 'trade-hist-06a', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-eli'), (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-dina'), 1, 0, 1, 'Listed as like new, but pages were missing and there were coffee stains.', 'The pages were already loose when I got it. Sorry, I should have said so.', to_char(timestamp '2026-10-07 20:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), 0, NULL, to_char(timestamp '2026-10-07 20:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('review-hist-07', 'trade-hist-07a', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-farah'), (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-dina'), 2, 0, 1, 'Heavy highlighting on almost every page, not mentioned in the listing.', NULL, to_char(timestamp '2026-10-08 20:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), 0, NULL, to_char(timestamp '2026-10-08 20:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('review-hist-08', 'trade-hist-08a', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-ana'), (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-dina'), 2, 1, 3, 'Book was fine, but she was 40 minutes late.', NULL, to_char(timestamp '2026-10-09 20:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), 0, NULL, to_char(timestamp '2026-10-09 20:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('review-demo-eli', 'trade-demo-review-b', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-eli'), (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-carla'), 5, 1, 3, 'Exactly as described.', NULL, to_char(timestamp '2026-12-06 20:58:24' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), 0, NULL, to_char(timestamp '2026-11-22 22:58:23' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'));
    INSERT INTO entity_ids ("table_name", "entity_key") VALUES
        ('trades', 'trade-last-farah'),
        ('trades', 'trade-hist-06a'),
        ('trades', 'trade-hist-07a');
    INSERT INTO audit_log ("id", "actor_id", "action", "target_table", "target_id", "created_at") VALUES
        ('audit-last-report', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-ben'), 'reported a missing handoff', 'trades', 'trade-last-farah', to_char(timestamp '2026-11-19 15:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('audit-hist-06', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-eli'), 'flagged as misdescribed', 'trades', 'trade-hist-06a', to_char(timestamp '2026-10-07 20:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('audit-hist-07', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-farah'), 'flagged as misdescribed', 'trades', 'trade-hist-07a', to_char(timestamp '2026-10-08 20:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'));
END
$reset$;

-- Who's who now: Morgan should be the moderator and Dina under review.
SELECT display_name, role, status FROM profiles ORDER BY role DESC, display_name;
