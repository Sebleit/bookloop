-- BookLoop tables. IDs and timestamps are text for SQLite/PostgreSQL portability.
CREATE TABLE IF NOT EXISTS profiles (
    id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('student', 'moderator')),
    status TEXT NOT NULL CHECK (status IN ('active', 'under_review', 'suspended')),
    created_at TEXT NOT NULL,
    -- Shown only to the other people in a direct swap, and to moderators on a report.
    email TEXT
);

CREATE TABLE IF NOT EXISTS books (
    id TEXT PRIMARY KEY,
    isbn TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    authors TEXT NOT NULL,
    edition TEXT,
    cover_url TEXT
);

CREATE TABLE IF NOT EXISTS courses (
    id TEXT PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS book_courses (
    book_id TEXT NOT NULL REFERENCES books(id),
    course_id TEXT NOT NULL REFERENCES courses(id),
    PRIMARY KEY (book_id, course_id)
);

CREATE TABLE IF NOT EXISTS copies (
    id TEXT PRIMARY KEY,
    book_id TEXT NOT NULL REFERENCES books(id),
    owner_id TEXT NOT NULL REFERENCES profiles(id),
    "condition" INTEGER NOT NULL CHECK ("condition" BETWEEN 1 AND 4),
    highlighting TEXT NOT NULL CHECK (highlighting IN ('none', 'light', 'heavy')),
    notes TEXT,
    status TEXT NOT NULL CHECK (status IN ('unlisted', 'available', 'in_round', 'reserved')),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS wishlist (
    user_id TEXT NOT NULL REFERENCES profiles(id),
    book_id TEXT NOT NULL REFERENCES books(id),
    created_at TEXT NOT NULL,
    PRIMARY KEY (user_id, book_id)
);

CREATE TABLE IF NOT EXISTS notifications (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES profiles(id),
    text TEXT NOT NULL,
    link TEXT,
    "read" INTEGER NOT NULL DEFAULT 0 CHECK ("read" IN (0, 1)),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS offers (
    id TEXT PRIMARY KEY,
    proposer_id TEXT NOT NULL REFERENCES profiles(id),
    offered_copy_id TEXT NOT NULL REFERENCES copies(id),
    requested_copy_id TEXT NOT NULL REFERENCES copies(id),
    status TEXT NOT NULL CHECK (status IN ('pending', 'accepted', 'declined', 'cancelled', 'expired')),
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS rounds (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    phase TEXT NOT NULL CHECK (phase IN ('entries', 'wants', 'matched', 'closed')),
    entries_close_at TEXT NOT NULL,
    wants_close_at TEXT NOT NULL,
    meet_place TEXT,
    meet_time TEXT,
    created_by TEXT NOT NULL REFERENCES profiles(id)
);

CREATE TABLE IF NOT EXISTS loops (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL CHECK (source IN ('offer', 'round')),
    offer_id TEXT REFERENCES offers(id),
    round_id TEXT REFERENCES rounds(id),
    status TEXT NOT NULL CHECK (status IN ('scheduled', 'completed', 'cancelled')),
    meet_place TEXT,
    meet_time TEXT,
    no_show_user_id TEXT REFERENCES profiles(id)
);

CREATE TABLE IF NOT EXISTS trades (
    id TEXT PRIMARY KEY,
    loop_id TEXT NOT NULL REFERENCES loops(id),
    copy_id TEXT NOT NULL REFERENCES copies(id),
    giver_id TEXT NOT NULL REFERENCES profiles(id),
    receiver_id TEXT NOT NULL REFERENCES profiles(id),
    handoff_code TEXT NOT NULL,
    code_attempts INTEGER NOT NULL DEFAULT 0 CHECK (code_attempts >= 0),
    status TEXT NOT NULL CHECK (status IN ('pending', 'completed', 'cancelled')),
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS round_entries (
    id TEXT PRIMARY KEY,
    round_id TEXT NOT NULL REFERENCES rounds(id),
    copy_id TEXT NOT NULL REFERENCES copies(id),
    min_partner_score REAL NOT NULL,
    UNIQUE (round_id, copy_id)
);

CREATE TABLE IF NOT EXISTS round_wants (
    entry_id TEXT NOT NULL REFERENCES round_entries(id),
    wanted_entry_id TEXT NOT NULL REFERENCES round_entries(id),
    CHECK (entry_id <> wanted_entry_id),
    PRIMARY KEY (entry_id, wanted_entry_id)
);

CREATE TABLE IF NOT EXISTS reviews (
    id TEXT PRIMARY KEY,
    trade_id TEXT NOT NULL UNIQUE REFERENCES trades(id),
    reviewer_id TEXT NOT NULL REFERENCES profiles(id),
    reviewee_id TEXT NOT NULL REFERENCES profiles(id),
    stars INTEGER NOT NULL CHECK (stars BETWEEN 1 AND 5),
    as_described INTEGER NOT NULL CHECK (as_described IN (0, 1)),
    actual_condition INTEGER NOT NULL CHECK (actual_condition BETWEEN 1 AND 4),
    comment TEXT,
    reply TEXT,
    visible_from TEXT,
    hidden_by_moderator INTEGER NOT NULL DEFAULT 0 CHECK (hidden_by_moderator IN (0, 1)),
    hidden_reason TEXT,
    created_at TEXT NOT NULL
);

-- Register polymorphic entity IDs so audit targets can have a real portable FK.
-- Writers must add the entity's (table_name, entity_id) in the same transaction.
CREATE TABLE IF NOT EXISTS entity_ids (
    table_name TEXT NOT NULL,
    entity_key TEXT NOT NULL,
    PRIMARY KEY (table_name, entity_key)
);

CREATE TABLE IF NOT EXISTS audit_log (
    id TEXT PRIMARY KEY,
    actor_id TEXT NOT NULL REFERENCES profiles(id),
    action TEXT NOT NULL,
    target_table TEXT NOT NULL CHECK (target_table IN (
        'profiles', 'books', 'courses', 'book_courses', 'copies', 'wishlist',
        'notifications', 'offers', 'loops', 'trades', 'rounds', 'round_entries',
        'round_wants', 'reviews', 'audit_log'
    )),
    target_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (target_table, target_id)
        REFERENCES entity_ids(table_name, entity_key)
);
