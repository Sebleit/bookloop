# Demo users, courses, books and copies.
from sqlalchemy import text
from sqlalchemy.engine import Connection


CREATED_AT = "2026-11-14T00:00:00Z"

# What an owner might write about a copy, matching its condition.
NOTES = {
    4: "Bought new last term, read once.",
    3: "Pencil notes in a few chapters.",
    2: "Spine creased and the cover is a bit bent.",
    1: "Well used: the cover is loose, but every page is there.",
}
STUDENTS = ("Ana", "Ben", "Carla", "Dina", "Eli", "Farah")

# More classmates, so rounds and Browse look like a real course. They never log
# in during the demo, so they have no account online: the reset creates them.
# Their ids start with "extra-" so it can tell them apart.
CLASSMATES = (
    "Afonso", "Beatriz", "Diogo", "Gonçalo", "Hugo", "Inês", "Joana",
    "Leonor", "Marta", "Miguel", "Nuno", "Rita", "Sofia", "Tiago",
)
NO_LOGIN_PREFIX = "extra-"

# Each classmate's books: (copy, owner, book, condition). Like real students,
# most have two or three, and some put two into the same swap round
# (seed/rounds.py); the rest stay on their shelves for Browse.
CLASSMATE_COPIES = (
    ("copy-26", "Afonso", "book-10", 3),  # Biology
    ("copy-27", "Beatriz", "book-13", 4),  # Psychology
    ("copy-28", "Diogo", "book-15", 2),  # Business Essentials
    ("copy-29", "Gonçalo", "book-02", 3),  # Python Crash Course
    ("copy-30", "Hugo", "book-07", 4),  # The Economics Book
    ("copy-31", "Inês", "book-06", 3),  # Principles of Economics
    ("copy-32", "Joana", "book-01", 2),  # Introduction to Algorithms
    ("copy-33", "Leonor", "book-09", 3),  # A Little History of the World
    ("copy-34", "Marta", "book-03", 4),  # Automate the Boring Stuff with Python
    ("copy-35", "Miguel", "book-12", 3),  # University Physics
    ("copy-36", "Nuno", "book-05", 2),  # Calculus: Early Transcendentals
    ("copy-37", "Rita", "book-08", 3),  # World History: Patterns of Interaction
    ("copy-38", "Sofia", "book-04", 4),  # A Mind for Numbers
    ("copy-39", "Tiago", "book-14", 3),  # They Say / I Say
    ("copy-40", "Joana", "book-11", 3),  # Chemistry: The Central Science
    ("copy-41", "Miguel", "book-03", 2),  # Automate the Boring Stuff with Python
    ("copy-42", "Sofia", "book-08", 4),  # World History: Patterns of Interaction
    ("copy-43", "Hugo", "book-02", 1),  # Python Crash Course
    ("copy-44", "Marta", "book-06", 4),  # Principles of Economics
    ("copy-45", "Nuno", "book-13", 3),  # Psychology
    ("copy-46", "Inês", "book-05", 2),  # Calculus: Early Transcendentals
    ("copy-47", "Rita", "book-10", 4),  # Biology
    ("copy-48", "Beatriz", "book-05", 3),  # Calculus: Early Transcendentals
    ("copy-49", "Diogo", "book-07", 2),  # The Economics Book
    ("copy-50", "Gonçalo", "book-11", 4),  # Chemistry: The Central Science
    ("copy-51", "Afonso", "book-14", 3),  # They Say / I Say
    ("copy-52", "Leonor", "book-12", 3),  # University Physics
    ("copy-53", "Tiago", "book-01", 2),  # Introduction to Algorithms
    ("copy-54", "Afonso", "book-04", 4),  # A Mind for Numbers
    ("copy-55", "Beatriz", "book-02", 3),  # Python Crash Course
    ("copy-56", "Diogo", "book-09", 1),  # A Little History of the World
    ("copy-57", "Gonçalo", "book-15", 3),  # Business Essentials
    ("copy-58", "Leonor", "book-06", 4),  # Principles of Economics
    ("copy-59", "Tiago", "book-13", 2),  # Psychology
)


def _plain(name: str) -> str:
    """'Gonçalo' -> 'goncalo'."""
    return name.lower().replace("ç", "c").replace("ê", "e").replace("é", "e").replace("í", "i")


def classmate_id(name: str) -> str:
    """'Gonçalo' -> 'extra-goncalo'."""
    return f"{NO_LOGIN_PREFIX}{_plain(name)}"


def demo_email(name: str) -> str:
    """'Gonçalo' -> 'goncalo@example.com'. Online, people who log in keep their account's email."""
    return f"{_plain(name)}@example.com"

# Real Nova SBE bachelor's courses, with their codes from the course catalogue
# (guia.unl.pt, 2023). Students can add more on My Shelf.
COURSES = (
    ("1318", "Computer Programming"),
    ("1309", "Calculus I"),
    ("1311", "Linear Algebra with Programming"),
    ("1117", "Principles of Microeconomics"),
    ("1118", "Principles of Macroeconomics"),
    ("1313", "Statistics for Economics and Management"),
    ("1217", "Financial Accounting"),
    ("1219", "Finance"),
    ("1220", "Marketing"),
    ("1216", "Principles of Management"),
    ("1206", "Organizational Behaviour"),
    ("1124", "Economic History"),
    ("1465", "Introduction to Modern and Contemporary History"),
    ("1469", "Human Behaviour and Decision Making"),
    ("1462", "Communication & Leadership"),
)

BOOKS = (
    ("9780262046305", "Introduction to Algorithms", "Thomas H. Cormen et al.", "4th", None),
    ("9781718502703", "Python Crash Course", "Eric Matthes", "3rd", None),
    ("9781593279929", "Automate the Boring Stuff with Python", "Al Sweigart", "2nd", None),
    ("9780525561643", "A Mind for Numbers", "Barbara Oakley", "Revised", None),
    ("9781337613927", "Calculus: Early Transcendentals", "James Stewart", "8th", None),
    ("9781260598205", "Principles of Economics", "N. Gregory Mankiw", "9th", None),
    ("9780190936273", "The Economics Book", "DK", "1st", None),
    ("9780547168290", "World History: Patterns of Interaction", "Roger B. Beck et al.", "1st", None),
    ("9780316025846", "A Little History of the World", "E. H. Gombrich", "1st", None),
    ("9780134093413", "Biology", "Neil A. Campbell et al.", "11th", None),
    ("9781260211884", "Chemistry: The Central Science", "Theodore L. Brown et al.", "14th", None),
    ("9780135159553", "University Physics", "Hugh D. Young and Roger A. Freedman", "15th", None),
    ("9781319247209", "Psychology", "David G. Myers and C. Nathan DeWall", "13th", None),
    ("9780393538700", "They Say / I Say", "Gerald Graff and Cathy Birkenstein", "5th", None),
    ("9781260260517", "Business Essentials", "Ronald J. Ebert and Ricky W. Griffin", "12th", None),
)

# Open Library covers (each link checked): by ISBN where Open Library has one,
# otherwise a cover of the same book from Open Library's catalogue.
COVERS = {
    "9780262046305": "https://covers.openlibrary.org/b/isbn/9780262046305-M.jpg",
    "9781718502703": "https://covers.openlibrary.org/b/isbn/9781718502703-M.jpg",
    "9781593279929": "https://covers.openlibrary.org/b/isbn/9781593279929-M.jpg",
    "9780525561643": "https://covers.openlibrary.org/b/id/8352403-M.jpg",
    "9781337613927": "https://covers.openlibrary.org/b/isbn/9781337613927-M.jpg",
    "9781260598205": "https://covers.openlibrary.org/b/id/10319849-M.jpg",
    "9780190936273": "https://covers.openlibrary.org/b/id/8763438-M.jpg",
    "9780547168290": "https://covers.openlibrary.org/b/id/1325336-M.jpg",
    "9780316025846": "https://covers.openlibrary.org/b/id/6624825-M.jpg",
    "9780134093413": "https://covers.openlibrary.org/b/isbn/9780134093413-M.jpg",
    "9781260211884": "https://covers.openlibrary.org/b/id/8846343-M.jpg",
    "9780135159553": "https://covers.openlibrary.org/b/id/10370820-M.jpg",
    "9781319247209": "https://covers.openlibrary.org/b/id/6601727-M.jpg",
    "9780393538700": "https://covers.openlibrary.org/b/isbn/9780393538700-M.jpg",
    "9781260260517": "https://covers.openlibrary.org/b/id/10168707-M.jpg",
}

# The courses each demo book is used in. The science books have none: Nova SBE
# has no such courses.
BOOK_COURSES = {
    "9780262046305": ("1318",),  # Introduction to Algorithms
    "9781718502703": ("1318",),  # Python Crash Course
    "9781593279929": ("1318",),  # Automate the Boring Stuff with Python
    "9780525561643": ("1309",),  # A Mind for Numbers
    "9781337613927": ("1309",),  # Calculus: Early Transcendentals
    "9781260598205": ("1117", "1118"),  # Principles of Economics
    "9780190936273": ("1124",),  # The Economics Book
    "9780547168290": ("1465",),  # World History: Patterns of Interaction
    "9780316025846": ("1465",),  # A Little History of the World
    "9781319247209": ("1469", "1206"),  # Psychology
    "9780393538700": ("1462",),  # They Say / I Say
    "9781260260517": ("1216",),  # Business Essentials
}

HIGHLIGHTING = ("none", "light", "heavy")


def seed(connection: Connection) -> None:
    """Insert the same starter profiles, courses, books, and copies each run."""
    profiles = [
        {
            "id": "user-moderator",
            "display_name": "Morgan",
            "role": "moderator",
            "status": "active",
            "created_at": CREATED_AT,
            "email": demo_email("Morgan"),
        }
    ]
    profiles.extend(
        {
            "id": f"user-{name.lower()}",
            "display_name": name,
            "role": "student",
            "status": "active",
            "created_at": CREATED_AT,
            "email": demo_email(name),
        }
        for name in STUDENTS
    )
    profiles.extend(
        {
            "id": classmate_id(name),
            "display_name": name,
            "role": "student",
            "status": "active",
            "created_at": CREATED_AT,
            "email": demo_email(name),
        }
        for name in CLASSMATES
    )
    connection.execute(
        text(
            "INSERT INTO profiles (id, display_name, role, status, created_at, email) "
            "VALUES (:id, :display_name, :role, :status, :created_at, :email)"
        ),
        profiles,
    )

    courses = [
        {"id": f"course-{index:02}", "code": code, "name": name}
        for index, (code, name) in enumerate(COURSES, start=1)
    ]
    connection.execute(
        text("INSERT INTO courses (id, code, name) VALUES (:id, :code, :name)"),
        courses,
    )

    books = [
        {
            "id": f"book-{index:02}",
            "isbn": isbn,
            "title": title,
            "authors": authors,
            "edition": edition,
            "cover_url": cover_url or COVERS.get(isbn),
        }
        for index, (isbn, title, authors, edition, cover_url) in enumerate(BOOKS, start=1)
    ]
    connection.execute(
        text(
            "INSERT INTO books (id, isbn, title, authors, edition, cover_url) "
            "VALUES (:id, :isbn, :title, :authors, :edition, :cover_url)"
        ),
        books,
    )

    course_ids = {course["code"]: course["id"] for course in courses}
    book_courses = [
        {"book_id": book["id"], "course_id": course_ids[code]}
        for book in books
        for code in BOOK_COURSES.get(book["isbn"], ())
    ]
    connection.execute(
        text("INSERT INTO book_courses (book_id, course_id) VALUES (:book_id, :course_id)"),
        book_courses,
    )

    copies = []
    for index in range(25):
        copies.append(
            {
                "id": f"copy-{index + 1:02}",
                "book_id": books[index % len(books)]["id"],
                "owner_id": f"user-{STUDENTS[index % len(STUDENTS)].lower()}",
                "condition": index % 4 + 1,
                "highlighting": HIGHLIGHTING[index % len(HIGHLIGHTING)],
                "notes": None if index % 3 == 0 else NOTES[index % 4 + 1],
                "status": "available",
                "created_at": CREATED_AT,
            }
        )
    for copy_id, owner, book, condition in CLASSMATE_COPIES:
        copies.append(
            {
                "id": copy_id,
                "book_id": book,
                "owner_id": classmate_id(owner),
                "condition": condition,
                "highlighting": HIGHLIGHTING[condition % len(HIGHLIGHTING)],
                "notes": NOTES[condition] if condition != 3 else None,
                "status": "available",
                "created_at": CREATED_AT,
            }
        )
    connection.execute(
        text(
            'INSERT INTO copies '
            '(id, book_id, owner_id, "condition", highlighting, notes, status, created_at) '
            "VALUES (:id, :book_id, :owner_id, :condition, :highlighting, :notes, :status, :created_at)"
        ),
        copies,
    )

    # A few wishlists, so My Shelf and the Stats page's "most wanted" have data.
    wishes = [
        ("user-ana", "book-12"),  # University Physics
        ("user-ben", "book-12"),
        ("user-carla", "book-04"),  # A Mind for Numbers
        ("user-eli", "book-14"),  # They Say / I Say
    ]
    connection.execute(
        text("INSERT INTO wishlist (user_id, book_id, created_at) VALUES (:user, :book, :at)"),
        [{"user": user, "book": book, "at": CREATED_AT} for user, book in wishes],
    )
