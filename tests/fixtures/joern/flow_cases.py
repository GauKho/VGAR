def login(username):
    user = db.find(username)
    if user is None:
        return None
    session = create(user)
    return session


def guarded(path):
    try:
        data = read(path)
    except OSError as error:
        log(error)
        raise
    finally:
        close()
    return data


def managed(path):
    with open(path) as handle:
        content = handle.read()
    return content


def checked(value):
    if value < 0:
        raise ValueError(value)
    result = value + 1
    return result


def looped(items):
    total = 0
    for item in items:
        if item is None:
            break
        total = total + item
    return total


def matched(value):
    match value:
        case 1:
            result = one()
        case _:
            result = other()
    return result


def unpacked():
    x, y = pair()
    use(x)


class Box:
    @property
    def size(self):
        return self._size

    @size.setter
    def size(self, value):
        self._size = value


def one_line_guard(a):
    if a: raise ValueError(a)
    return 1
