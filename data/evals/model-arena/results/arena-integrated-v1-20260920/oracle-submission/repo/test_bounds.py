import bounds


def test_interior():
    assert bounds.within(0, 10, 5) is True


def test_outside():
    assert bounds.within(0, 10, 11) is False
