-- BookLoop: reset the online demo data. Paste all of it into Supabase -> SQL Editor -> Run.
-- It's one block: if anything fails, nothing changes. It works on any day: every demo
-- date moves to the day it runs. It also removes the profiles of accounts deleted in
-- Authentication -> Users. Made by: uv run python reset_online_demo.py --sql db/demo_reset.sql
-- It needs one account for each of these first names: Ana, Ben, Carla, Dina, Eli, Farah, Morgan.
DO $reset$
DECLARE
    problem text;
    shift integer := (now() AT TIME ZONE 'UTC')::date - date '2026-11-23';
BEGIN
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
    DELETE FROM profiles WHERE id NOT IN (SELECT id::text FROM auth.users);

    UPDATE profiles p SET display_name = d.name, role = d.role, status = d.status
    FROM demo_accounts d WHERE p.id = d.account_id;

    INSERT INTO books ("id", "isbn", "title", "authors", "edition", "cover_url") VALUES
        ('book-01', '9780262046305', 'Introduction to Algorithms', 'Thomas H. Cormen et al.', '4th', NULL),
        ('book-02', '9781718502703', 'Python Crash Course', 'Eric Matthes', '3rd', NULL),
        ('book-03', '9781593279929', 'Automate the Boring Stuff with Python', 'Al Sweigart', '2nd', NULL),
        ('book-04', '9780525561643', 'A Mind for Numbers', 'Barbara Oakley', 'Revised', NULL),
        ('book-05', '9781337613927', 'Calculus: Early Transcendentals', 'James Stewart', '8th', NULL),
        ('book-06', '9781260598205', 'Principles of Economics', 'N. Gregory Mankiw', '9th', NULL),
        ('book-07', '9780190936273', 'The Economics Book', 'DK', '1st', NULL),
        ('book-08', '9780547168290', 'World History: Patterns of Interaction', 'Roger B. Beck et al.', '1st', NULL),
        ('book-09', '9780316025846', 'A Little History of the World', 'E. H. Gombrich', '1st', NULL),
        ('book-10', '9780134093413', 'Biology', 'Neil A. Campbell et al.', '11th', NULL),
        ('book-11', '9781260211884', 'Chemistry: The Central Science', 'Theodore L. Brown et al.', '14th', NULL),
        ('book-12', '9780135159553', 'University Physics', 'Hugh D. Young and Roger A. Freedman', '15th', NULL),
        ('book-13', '9781319247209', 'Psychology', 'David G. Myers and C. Nathan DeWall', '13th', NULL),
        ('book-14', '9780393538700', 'They Say / I Say', 'Gerald Graff and Cathy Birkenstein', '5th', NULL),
        ('book-15', '9781260260517', 'Business Essentials', 'Ronald J. Ebert and Ricky W. Griffin', '12th', NULL);
    INSERT INTO courses ("id", "code", "name") VALUES
        ('course-01', 'NOVA101', 'Introduction to Programming'),
        ('course-02', 'MATH101', 'Calculus I'),
        ('course-03', 'ECON101', 'Principles of Economics'),
        ('course-04', 'HIST101', 'World History'),
        ('course-05', 'BIO101', 'Introduction to Biology'),
        ('course-06', 'CHEM101', 'General Chemistry'),
        ('course-07', 'PHYS101', 'University Physics'),
        ('course-08', 'PSY101', 'Introduction to Psychology'),
        ('course-09', 'ENG101', 'Academic Writing'),
        ('course-10', 'BUS101', 'Business Foundations');
    INSERT INTO book_courses ("book_id", "course_id") VALUES
        ('book-01', 'course-01'),
        ('book-02', 'course-02'),
        ('book-03', 'course-03'),
        ('book-04', 'course-04'),
        ('book-05', 'course-05'),
        ('book-06', 'course-06'),
        ('book-07', 'course-07'),
        ('book-08', 'course-08'),
        ('book-09', 'course-09'),
        ('book-10', 'course-10'),
        ('book-11', 'course-01'),
        ('book-12', 'course-02'),
        ('book-13', 'course-03'),
        ('book-14', 'course-04'),
        ('book-15', 'course-05');
    INSERT INTO copies ("id", "book_id", "owner_id", "condition", "highlighting", "notes", "status", "created_at") VALUES
        ('copy-01', 'book-01', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-ben'), 1, 'none', NULL, 'available', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-02', 'book-02', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-ana'), 2, 'light', 'Demo copy 2.', 'available', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-03', 'book-03', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-carla'), 3, 'heavy', 'Demo copy 3.', 'reserved', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-04', 'book-04', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-dina'), 4, 'none', NULL, 'reserved', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-05', 'book-05', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-eli'), 1, 'light', 'Demo copy 5.', 'in_round', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-06', 'book-06', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-farah'), 2, 'heavy', 'Demo copy 6.', 'in_round', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-07', 'book-07', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-ana'), 3, 'none', NULL, 'in_round', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-08', 'book-08', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-ben'), 4, 'light', 'Demo copy 8.', 'in_round', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-09', 'book-09', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-carla'), 1, 'heavy', 'Demo copy 9.', 'available', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-10', 'book-10', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-dina'), 2, 'none', NULL, 'available', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-11', 'book-11', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-eli'), 3, 'light', 'Demo copy 11.', 'available', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-12', 'book-12', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-farah'), 4, 'heavy', 'Demo copy 12.', 'available', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-13', 'book-13', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-ana'), 1, 'none', NULL, 'available', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-14', 'book-14', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-ben'), 2, 'light', 'Demo copy 14.', 'available', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-15', 'book-15', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-carla'), 3, 'heavy', 'Demo copy 15.', 'available', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-16', 'book-01', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-dina'), 4, 'none', NULL, 'available', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-17', 'book-02', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-eli'), 1, 'light', 'Demo copy 17.', 'available', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-18', 'book-03', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-farah'), 2, 'heavy', 'Demo copy 18.', 'available', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-19', 'book-04', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-ana'), 3, 'none', NULL, 'available', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-20', 'book-05', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-ben'), 4, 'light', 'Demo copy 20.', 'available', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-21', 'book-06', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-carla'), 1, 'heavy', 'Demo copy 21.', 'available', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-22', 'book-07', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-dina'), 2, 'none', NULL, 'available', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-23', 'book-08', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-eli'), 3, 'light', 'Demo copy 23.', 'available', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-24', 'book-09', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-farah'), 4, 'heavy', 'Demo copy 24.', 'available', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('copy-25', 'book-10', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-ana'), 1, 'none', NULL, 'available', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
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
    INSERT INTO offers ("id", "proposer_id", "offered_copy_id", "requested_copy_id", "status", "created_at", "expires_at") VALUES
        ('offer-demo-completed', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-ana'), 'copy-01', 'copy-02', 'accepted', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), to_char(timestamp '2026-11-23 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('offer-demo-pending', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-carla'), 'copy-03', 'copy-04', 'accepted', to_char(timestamp '2026-11-14 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), to_char(timestamp '2026-11-23 00:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'));
    INSERT INTO rounds ("id", "name", "phase", "entries_close_at", "wants_close_at", "meet_place", "meet_time", "created_by") VALUES
        ('round-demo', 'Winter textbook swap', 'wants', to_char(timestamp '2026-11-22 18:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), to_char(timestamp '2026-11-25 18:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), 'Nova SBE library, ground floor', to_char(timestamp '2026-11-26 14:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-moderator'));
    INSERT INTO loops ("id", "source", "offer_id", "round_id", "status", "meet_place", "meet_time", "no_show_user_id") VALUES
        ('loop-demo-completed', 'offer', 'offer-demo-completed', NULL, 'completed', 'Main library', to_char(timestamp '2026-11-15 14:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), NULL),
        ('loop-demo-pending', 'offer', 'offer-demo-pending', NULL, 'scheduled', 'Student centre', to_char(timestamp '2026-11-23 12:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), NULL),
        ('loop-hist-01', 'offer', NULL, NULL, 'completed', 'Nova SBE library', to_char(timestamp '2026-10-02 14:30:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), NULL),
        ('loop-hist-02', 'offer', NULL, NULL, 'completed', 'Nova SBE library', to_char(timestamp '2026-10-03 14:30:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), NULL),
        ('loop-hist-03', 'offer', NULL, NULL, 'completed', 'Nova SBE library', to_char(timestamp '2026-10-04 14:30:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), NULL),
        ('loop-hist-04', 'offer', NULL, NULL, 'completed', 'Nova SBE library', to_char(timestamp '2026-10-05 14:30:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), NULL),
        ('loop-hist-05', 'offer', NULL, NULL, 'completed', 'Nova SBE library', to_char(timestamp '2026-10-06 14:30:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), NULL),
        ('loop-hist-06', 'offer', NULL, NULL, 'completed', 'Nova SBE library', to_char(timestamp '2026-10-07 14:30:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), NULL),
        ('loop-hist-07', 'offer', NULL, NULL, 'completed', 'Nova SBE library', to_char(timestamp '2026-10-08 14:30:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), NULL),
        ('loop-hist-08', 'offer', NULL, NULL, 'completed', 'Nova SBE library', to_char(timestamp '2026-10-09 14:30:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), NULL),
        ('loop-demo-review', 'offer', NULL, NULL, 'completed', 'Nova SBE library', to_char(timestamp '2026-11-22 11:39:44' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), NULL);
    INSERT INTO trades ("id", "loop_id", "copy_id", "giver_id", "receiver_id", "handoff_code", "code_attempts", "status", "completed_at") VALUES
        ('trade-demo-completed-a', 'loop-demo-completed', 'copy-01', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-ana'), (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-ben'), '1111', 0, 'completed', to_char(timestamp '2026-11-15 14:10:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('trade-demo-completed-b', 'loop-demo-completed', 'copy-02', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-ben'), (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-ana'), '2222', 0, 'completed', to_char(timestamp '2026-11-15 14:10:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('trade-demo-pending-a', 'loop-demo-pending', 'copy-03', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-carla'), (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-dina'), '3333', 0, 'pending', NULL),
        ('trade-demo-pending-b', 'loop-demo-pending', 'copy-04', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-dina'), (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-carla'), '4444', 0, 'pending', NULL),
        ('trade-hist-01a', 'loop-hist-01', 'copy-hist-01a', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-carla'), (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-ana'), '0000', 0, 'completed', to_char(timestamp '2026-10-02 15:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('trade-hist-01b', 'loop-hist-01', 'copy-hist-01b', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-ana'), (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-carla'), '0000', 0, 'completed', to_char(timestamp '2026-10-02 15:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('trade-hist-02a', 'loop-hist-02', 'copy-hist-02a', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-carla'), (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-ben'), '0000', 0, 'completed', to_char(timestamp '2026-10-03 15:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('trade-hist-02b', 'loop-hist-02', 'copy-hist-02b', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-ben'), (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-carla'), '0000', 0, 'completed', to_char(timestamp '2026-10-03 15:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('trade-hist-03a', 'loop-hist-03', 'copy-hist-03a', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-carla'), (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-dina'), '0000', 0, 'completed', to_char(timestamp '2026-10-04 15:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('trade-hist-03b', 'loop-hist-03', 'copy-hist-03b', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-dina'), (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-carla'), '0000', 0, 'completed', to_char(timestamp '2026-10-04 15:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('trade-hist-04a', 'loop-hist-04', 'copy-hist-04a', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-carla'), (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-eli'), '0000', 0, 'completed', to_char(timestamp '2026-10-05 15:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('trade-hist-04b', 'loop-hist-04', 'copy-hist-04b', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-eli'), (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-carla'), '0000', 0, 'completed', to_char(timestamp '2026-10-05 15:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('trade-hist-05a', 'loop-hist-05', 'copy-hist-05a', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-carla'), (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-farah'), '0000', 0, 'completed', to_char(timestamp '2026-10-06 15:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('trade-hist-05b', 'loop-hist-05', 'copy-hist-05b', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-farah'), (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-carla'), '0000', 0, 'completed', to_char(timestamp '2026-10-06 15:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('trade-hist-06a', 'loop-hist-06', 'copy-hist-06a', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-dina'), (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-eli'), '0000', 0, 'completed', to_char(timestamp '2026-10-07 15:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('trade-hist-06b', 'loop-hist-06', 'copy-hist-06b', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-eli'), (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-dina'), '0000', 0, 'completed', to_char(timestamp '2026-10-07 15:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('trade-hist-07a', 'loop-hist-07', 'copy-hist-07a', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-dina'), (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-farah'), '0000', 0, 'completed', to_char(timestamp '2026-10-08 15:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('trade-hist-07b', 'loop-hist-07', 'copy-hist-07b', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-farah'), (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-dina'), '0000', 0, 'completed', to_char(timestamp '2026-10-08 15:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('trade-hist-08a', 'loop-hist-08', 'copy-hist-08a', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-dina'), (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-ana'), '0000', 0, 'completed', to_char(timestamp '2026-10-09 15:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('trade-hist-08b', 'loop-hist-08', 'copy-hist-08b', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-ana'), (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-dina'), '0000', 0, 'completed', to_char(timestamp '2026-10-09 15:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('trade-demo-review-a', 'loop-demo-review', 'copy-demo-review-a', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-eli'), (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-carla'), '0000', 0, 'completed', to_char(timestamp '2026-11-22 11:39:44' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('trade-demo-review-b', 'loop-demo-review', 'copy-demo-review-b', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-carla'), (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-eli'), '0000', 0, 'completed', to_char(timestamp '2026-11-22 11:39:44' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'));
    INSERT INTO round_entries ("id", "round_id", "copy_id", "min_partner_score") VALUES
        ('entry-eli', 'round-demo', 'copy-05', 0.0),
        ('entry-farah', 'round-demo', 'copy-06', 0.0),
        ('entry-ana', 'round-demo', 'copy-07', 0.0),
        ('entry-ben', 'round-demo', 'copy-08', 0.0);
    INSERT INTO round_wants ("entry_id", "wanted_entry_id") VALUES
        ('entry-eli', 'entry-farah'),
        ('entry-farah', 'entry-ana'),
        ('entry-ana', 'entry-eli'),
        ('entry-ben', 'entry-eli');
    INSERT INTO reviews ("id", "trade_id", "reviewer_id", "reviewee_id", "stars", "as_described", "actual_condition", "comment", "reply", "visible_from", "hidden_by_moderator", "hidden_reason", "created_at") VALUES
        ('review-hist-01', 'trade-hist-01a', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-ana'), (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-carla'), 5, 1, 4, 'Exactly as described, thanks!', NULL, to_char(timestamp '2026-10-02 20:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), 0, NULL, to_char(timestamp '2026-10-02 20:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('review-hist-02', 'trade-hist-02a', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-ben'), (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-carla'), 5, 1, 3, NULL, NULL, to_char(timestamp '2026-10-03 20:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), 0, NULL, to_char(timestamp '2026-10-03 20:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('review-hist-03', 'trade-hist-03a', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-dina'), (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-carla'), 5, 1, 3, 'Great condition.', NULL, to_char(timestamp '2026-10-04 20:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), 0, NULL, to_char(timestamp '2026-10-04 20:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('review-hist-04', 'trade-hist-04a', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-eli'), (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-carla'), 5, 1, 4, NULL, NULL, to_char(timestamp '2026-10-05 20:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), 0, NULL, to_char(timestamp '2026-10-05 20:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('review-hist-05', 'trade-hist-05a', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-farah'), (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-carla'), 5, 1, 2, 'Quick and friendly swap.', NULL, to_char(timestamp '2026-10-06 20:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), 0, NULL, to_char(timestamp '2026-10-06 20:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('review-hist-06', 'trade-hist-06a', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-eli'), (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-dina'), 1, 0, 1, 'Listed as like new, but pages were missing and there were coffee stains.', 'The pages were already loose when I got it. Sorry, I should have said so.', to_char(timestamp '2026-10-07 20:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), 0, NULL, to_char(timestamp '2026-10-07 20:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('review-hist-07', 'trade-hist-07a', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-farah'), (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-dina'), 2, 0, 1, 'Heavy highlighting on almost every page, not mentioned in the listing.', NULL, to_char(timestamp '2026-10-08 20:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), 0, NULL, to_char(timestamp '2026-10-08 20:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('review-hist-08', 'trade-hist-08a', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-ana'), (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-dina'), 2, 1, 3, 'Book was fine, but she was 40 minutes late.', NULL, to_char(timestamp '2026-10-09 20:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), 0, NULL, to_char(timestamp '2026-10-09 20:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('review-demo-eli', 'trade-demo-review-b', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-eli'), (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-carla'), 5, 1, 3, 'Exactly as described.', NULL, to_char(timestamp '2026-12-06 11:39:45' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), 0, NULL, to_char(timestamp '2026-11-22 13:39:44' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'));
    INSERT INTO entity_ids ("table_name", "entity_key") VALUES
        ('trades', 'trade-hist-06a'),
        ('trades', 'trade-hist-07a');
    INSERT INTO audit_log ("id", "actor_id", "action", "target_table", "target_id", "created_at") VALUES
        ('audit-hist-06', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-eli'), 'flagged as misdescribed', 'trades', 'trade-hist-06a', to_char(timestamp '2026-10-07 20:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
        ('audit-hist-07', (SELECT account_id FROM demo_accounts WHERE demo_id = 'user-farah'), 'flagged as misdescribed', 'trades', 'trade-hist-07a', to_char(timestamp '2026-10-08 20:00:00' + shift * interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'));
END
$reset$;

-- Who's who now: Morgan should be the moderator and Dina under review.
SELECT display_name, role, status FROM profiles ORDER BY role DESC, display_name;
