from pypy.rpython.module.support import LLSupport
from pypy.jit.rainbow.test.test_portal import PortalTest
from pypy.jit.rainbow.test.test_vlist import P_OOPSPEC
from pypy.tool.sourcetools import func_with_new_name
from pypy.jit.conftest import Benchmark

from pypy.jit.tl import tiny2
from pypy.jit.tl.targettiny2 import MyHintAnnotatorPolicy


class TestTL(PortalTest):
    type_system = "lltype"

    def test_tl(self):
        def main(bytecode, arg1, arg2, arg3):
            if bytecode == 0:
                bytecode = "{ #1 #1 1 SUB ->#1 #1 }"
            elif bytecode == 1:
                bytecode = "{ #1 #2 #1 #2 ADD ->#2 ->#1 #3 1 SUB ->#3 #3 }"
            else:
                assert 0
            bytecode = [s for s in bytecode.split(' ') if s != '']
            args = [tiny2.StrBox(str(arg1)), tiny2.StrBox(str(arg2)), tiny2.StrBox(str(arg3))]
            return tiny2.repr(tiny2.interpret(bytecode, args))

        res = self.timeshift_from_portal(main, tiny2.interpret, [0, 5, 0, 0],
                                         policy=MyHintAnnotatorPolicy())
        assert "".join(res.chars._obj.items) == "5 4 3 2 1"
