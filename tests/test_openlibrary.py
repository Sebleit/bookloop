# Person 1 owns this file: tests for Open Library service.


def test_fake_open_library_returns_a_fixed_book_without_network(fake_open_library):
    book = fake_open_library.lookup("9780000000000")

    assert book.isbn == "9780000000000"
    assert book.title == "A Fixed Open Library Book"
    assert book.authors == "Example Author"
