# Person 1 owns this file: demo users, courses, books and copies.
from sqlalchemy import text
from sqlalchemy.engine import Connection


CREATED_AT = "2026-11-14T00:00:00Z"

STUDENTS = ("Ana", "Ben", "Carla", "Dina", "Eli", "Farah")

COURSES = (
    ("NOVA101", "Introduction to Programming"),
    ("MATH101", "Calculus I"),
    ("ECON101", "Principles of Economics"),
    ("HIST101", "World History"),
    ("BIO101", "Introduction to Biology"),
    ("CHEM101", "General Chemistry"),
    ("PHYS101", "University Physics"),
    ("PSY101", "Introduction to Psychology"),
    ("ENG101", "Academic Writing"),
    ("BUS101", "Business Foundations"),
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
        }
    ]
    profiles.extend(
        {
            "id": f"user-{name.lower()}",
            "display_name": name,
            "role": "student",
            "status": "active",
            "created_at": CREATED_AT,
        }
        for name in STUDENTS
    )
    connection.execute(
        text(
            "INSERT INTO profiles (id, display_name, role, status, created_at) "
            "VALUES (:id, :display_name, :role, :status, :created_at)"
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
            "cover_url": cover_url,
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

    book_courses = [
        {"book_id": book["id"], "course_id": courses[index % len(courses)]["id"]}
        for index, book in enumerate(books)
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
                "notes": None if index % 3 == 0 else f"Demo copy {index + 1}.",
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
