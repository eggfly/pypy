

class Test_DescrOperation:

    def test_nonzero(self):
        space = self.space
        assert space.nonzero(space.w_True) is space.w_True
        assert space.nonzero(space.w_False) is space.w_False
        assert space.nonzero(space.wrap(42)) is space.w_True
        assert space.nonzero(space.wrap(0)) is space.w_False
        l = space.newlist([])
        assert space.nonzero(l) is space.w_False
        space.call_method(l, 'append', space.w_False)
        assert space.nonzero(l) is space.w_True


class AppTest_Descroperation:

    def test_special_methods(self):
        class A(object):
            def __lt__(self, other):
                return "lt"
            def __imul__(self, other):
                return "imul"
            def __sub__(self, other):
                return "sub"
            def __rsub__(self, other):
                return "rsub"
            def __pow__(self, other):
                return "pow"
            def __rpow__(self, other):
                return "rpow"
            def __neg__(self):
                return "neg"
        a = A()
        assert (a < 5) == "lt"
        assert (object() > a) == "lt"
        a1 = a
        a1 *= 4
        assert a1 == "imul"
        assert a - 2 == "sub"
        assert a - object() == "sub"
        assert 2 - a == "rsub"
        assert object() - a == "rsub"
        assert a ** 2 == "pow"
        assert a ** object() == "pow"
        assert 2 ** a == "rpow"
        assert object() ** a == "rpow"
        assert -a == "neg"

        class B(A):
            def __lt__(self, other):
                return "B's lt"
            def __imul__(self, other):
                return "B's imul"
            def __sub__(self, other):
                return "B's sub"
            def __rsub__(self, other):
                return "B's rsub"
            def __pow__(self, other):
                return "B's pow"
            def __rpow__(self, other):
                return "B's rpow"
            def __neg__(self):
                return "B's neg"

        b = B()
        assert (a < b) == "lt"
        assert (b > a) == "lt"
        b1 = b
        b1 *= a
        assert b1 == "B's imul"
        a1 = a
        a1 *= b
        assert a1 == "imul"
        assert a - b == "B's rsub"
        assert b - a == "B's sub"
        assert b - b == "B's sub"
        assert a ** b == "B's rpow"
        assert b ** a == "B's pow"
        assert b ** b == "B's pow"
        assert -b == "B's neg"

        class C(B):
            pass
        c = C()
        assert c - 1 == "B's sub"
        assert 1 - c == "B's rsub"
        assert c - b == "B's sub"
        assert b - c == "B's sub"

        assert c ** 1 == "B's pow"
        assert 1 ** c == "B's rpow"
        assert c ** b == "B's pow"
        assert b ** c == "B's pow"

    def test_getslice(self):
        class Sq(object):
            def __getslice__(self, start, stop):
                return (start, stop)
            def __getitem__(self, key):
                return "booh"
            def __len__(self):
                return 100

        sq = Sq()

        assert sq[1:3] == (1,3)
        slice_min, slice_max = sq[:]
        assert slice_min == 0
        assert slice_max >= 2**31-1
        assert sq[1:] == (1, slice_max)
        assert sq[:3] == (0, 3)
        assert sq[:] == (0, slice_max)
        # negative indices
        assert sq[-1:3] == (99, 3)
        assert sq[1:-3] == (1, 97)
        assert sq[-1:-3] == (99, 97)
        # extended slice syntax always uses __getitem__()
        assert sq[::] == "booh"

    def test_setslice(self):
        class Sq(object):
            def __setslice__(self, start, stop, sequence):
                ops.append((start, stop, sequence))
            def __setitem__(self, key, value):
                raise AssertionError, key
            def __len__(self):
                return 100

        sq = Sq()
        ops = []
        sq[-5:3] = 'hello'
        sq[12:] = 'world'
        sq[:-1] = 'spam'
        sq[:] = 'egg'
        slice_max = ops[-1][1]
        assert slice_max >= 2**31-1

        assert ops == [
            (95, 3,          'hello'),
            (12, slice_max, 'world'),
            (0,  99,         'spam'),
            (0,  slice_max, 'egg'),
            ]

    def test_delslice(self):
        class Sq(object):
            def __delslice__(self, start, stop):
                ops.append((start, stop))
            def __delitem__(self, key):
                raise AssertionError, key
            def __len__(self):
                return 100

        sq = Sq()
        ops = []
        del sq[5:-3]
        del sq[-12:]
        del sq[:1]
        del sq[:]
        slice_max = ops[-1][1]
        assert slice_max >= 2**31-1

        assert ops == [
            (5,   97),
            (88,  slice_max),
            (0,   1),
            (0,   slice_max),
            ]

    def test_ipow(self):
        x = 2
        x **= 5
        assert x == 32

    def test_typechecks(self):
        class myint(int):
            pass
        class X(object):
            def __nonzero__(self):
                return myint(1)
        raises(TypeError, "not X()")

    def test_string_subclass(self):
        class S(str):
            def __hash__(self):
                return 123
        s = S("abc")
        setattr(s, s, s)
        assert len(s.__dict__) == 1
        # this behavior changed in 2.4
        #assert type(s.__dict__.keys()[0]) is str   # don't store S keys
        #assert s.abc is s
        getattr(s,s) is s

    def test_notimplemented(self):
        #import types
        import operator

        def specialmethod(self, other):
            return NotImplemented

        def check(expr, x, y, operator=operator):
            raises(TypeError, expr)

        for metaclass in [type]:   # [type, types.ClassType]:
            for name, expr, iexpr in [
                    ('__add__',      'x + y',                   'x += y'),
                    ('__sub__',      'x - y',                   'x -= y'),
                    ('__mul__',      'x * y',                   'x *= y'),
                    ('__truediv__',  'operator.truediv(x, y)',  None),
                    ('__floordiv__', 'operator.floordiv(x, y)', None),
                    ('__div__',      'x / y',                   'x /= y'),
                    ('__mod__',      'x % y',                   'x %= y'),
                    ('__divmod__',   'divmod(x, y)',            None),
                    ('__pow__',      'x ** y',                  'x **= y'),
                    ('__lshift__',   'x << y',                  'x <<= y'),
                    ('__rshift__',   'x >> y',                  'x >>= y'),
                    ('__and__',      'x & y',                   'x &= y'),
                    ('__or__',       'x | y',                   'x |= y'),
                    ('__xor__',      'x ^ y',                   'x ^= y'),
                    ('__coerce__',   'coerce(x, y)',            None)]:
                if name == '__coerce__':
                    rname = name
                else:
                    rname = '__r' + name[2:]
                A = metaclass('A', (), {name: specialmethod})
                B = metaclass('B', (), {rname: specialmethod})
                a = A()
                b = B()
                check(expr, a, a)
                check(expr, a, b)
                check(expr, b, a)
                check(expr, b, b)
                check(expr, a, 5)
                check(expr, 5, b)
                if iexpr:
                    check(iexpr, a, a)
                    check(iexpr, a, b)
                    check(iexpr, b, a)
                    check(iexpr, b, b)
                    check(iexpr, a, 5)
                    iname = '__i' + name[2:]
                    C = metaclass('C', (), {iname: specialmethod})
                    c = C()
                    check(iexpr, c, a)
                    check(iexpr, c, b)
                    check(iexpr, c, 5)
